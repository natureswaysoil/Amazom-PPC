import json
import logging
import os
import sys
import tempfile
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Third-party imports
import functions_framework
import requests
import yaml

# Local application imports
from optimizer_core import PPCAutomation
from dashboard_client import DashboardClient
from bigquery_client import BigQueryClient
from gcp_credentials import validate_credentials_early, GCPCredentialError

# Configure logging for Cloud Functions
# Detect if running in Cloud Functions environment
IS_CLOUD_FUNCTION = os.getenv('K_SERVICE') is not None or os.getenv('FUNCTION_TARGET') is not None

def _determine_log_level(default_level: int = logging.INFO) -> Tuple[int, Optional[str], bool]:
  """Resolve the log level from the LOG_LEVEL environment variable."""
  level_name = os.getenv('LOG_LEVEL')
  if not level_name:
    return default_level, None, False

  level_name = level_name.strip()
  if not level_name:
    return default_level, '', True

  resolved_level = logging.getLevelName(level_name.upper())
  if isinstance(resolved_level, int):
    return resolved_level, level_name, False

  try:
    numeric_level = int(level_name)
  except ValueError:
    return default_level, level_name, True

  # Clamp numeric level to the supported logging range
  numeric_level = max(logging.NOTSET, min(logging.CRITICAL, numeric_level))
  return numeric_level, level_name, False


LOG_LEVEL, _raw_log_level, _log_level_fallback = _determine_log_level()

if IS_CLOUD_FUNCTION:
  # Use only StreamHandler for Cloud Functions (logs go to Cloud Logging)
  logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
  )
else:
  # For local development, use both console and file logging
  logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
      logging.StreamHandler(sys.stdout),
      logging.FileHandler(f'ppc_main_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
  )

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

if _log_level_fallback and _raw_log_level is not None:
  logger.warning(
    "Invalid LOG_LEVEL value '%s'; defaulting to INFO", _raw_log_level
  )


DEFAULT_MIN_RUN_INTERVAL_MINUTES = 120
LAST_RUN_CACHE_PATH = "/tmp/ppc_optimizer_last_run.txt"
_LAST_RUN_MEMORY: Optional[datetime] = None


def _normalise_timestamp(value: Optional[datetime]) -> Optional[datetime]:
  """Convert timestamp to naive UTC for consistent comparisons."""
  if not isinstance(value, datetime):
    return None
  if value.tzinfo is not None:
    return value.astimezone(timezone.utc).replace(tzinfo=None)
  return value


def _get_last_run_memory() -> Optional[datetime]:
  """Return the last run timestamp stored in process memory."""
  return _LAST_RUN_MEMORY


def _update_last_run_memory(timestamp: datetime) -> None:
  """Persist last run timestamp in process memory (naive UTC)."""
  global _LAST_RUN_MEMORY
  _LAST_RUN_MEMORY = _normalise_timestamp(timestamp)


def _read_last_run_from_cache(path: str = LAST_RUN_CACHE_PATH) -> Optional[datetime]:
  """Read last run timestamp from local cache file."""
  try:
    with open(path, "r", encoding="utf-8") as handle:
      raw_value = handle.read().strip()
    if not raw_value:
      return None
    try:
      parsed = datetime.fromisoformat(raw_value)
    except ValueError:
      logger.warning("Invalid timestamp cached at %s; ignoring", path)
      return None
    return _normalise_timestamp(parsed)
  except FileNotFoundError:
    return None
  except Exception as exc:
    logger.debug("Failed to read last-run cache from %s: %s", path, exc)
    return None


def _write_last_run_to_cache(timestamp: datetime, path: str = LAST_RUN_CACHE_PATH) -> None:
  """Write last run timestamp to local cache file (best effort)."""
  normalised = _normalise_timestamp(timestamp)
  if normalised is None:
    return
  try:
    with open(path, "w", encoding="utf-8") as handle:
      handle.write(normalised.isoformat())
  except Exception as exc:
    logger.debug("Failed to update last-run cache at %s: %s", path, exc)


def _select_latest_timestamp(*timestamps: Optional[datetime]) -> Optional[datetime]:
  """Return the most recent timestamp from the provided values."""
  valid = [ts for ts in timestamps if isinstance(ts, datetime)]
  if not valid:
    return None
  return max(valid)


def _parse_positive_int(value: Any, source: str) -> Optional[int]:
  """Parse a positive integer (>=0) from value; log on failure."""
  if value is None:
    return None
  try:
    value_str = str(value).strip()
  except Exception:
    logger.warning("Invalid %s value '%s'; ignoring", source, value)
    return None
  if not value_str:
    return None
  try:
    parsed = int(value_str)
    if parsed < 0:
      raise ValueError
    return parsed
  except ValueError:
    logger.warning("Invalid %s value '%s'; ignoring", source, value)
    return None


def _get_min_run_interval_minutes(config: Dict[str, Any]) -> int:
  """Determine the minimum run interval from env or configuration."""
  env_override = _parse_positive_int(os.getenv("MIN_RUN_INTERVAL_MINUTES"), "MIN_RUN_INTERVAL_MINUTES")
  if env_override is not None:
    return env_override

  schedule_config = config.get("schedule") if isinstance(config, dict) else None
  if isinstance(schedule_config, dict):
    config_value = _parse_positive_int(
      schedule_config.get("min_run_interval_minutes"),
      "schedule.min_run_interval_minutes",
    )
    if config_value is not None:
      return config_value
  return DEFAULT_MIN_RUN_INTERVAL_MINUTES


@contextmanager
def create_config_file(config_dict: Dict) -> Iterator[str]:
  """
  Create a temporary config file from dictionary using context manager
  The optimizer_core expects YAML format file.
  """
  if not isinstance(config_dict, dict):
    raise ValueError("config_dict must be a dictionary")
  
  temp_file = None
  try:
    # Create temp file with YAML format
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8')
    yaml.dump(config_dict, temp_file, default_flow_style=False, allow_unicode=True)
    temp_file.close()
    logger.info(f"Created temporary config file: {temp_file.name}")
    yield temp_file.name
  except Exception as e:
    logger.error(f"Failed to create config file: {e}")
    if temp_file and os.path.exists(temp_file.name):
      try:
        os.unlink(temp_file.name)
      except Exception as cleanup_err:
        logger.warning(f"Failed to cleanup temp file: {cleanup_err}")
    raise
  finally:
    # Cleanup temp file
    if temp_file and os.path.exists(temp_file.name):
      try:
        os.unlink(temp_file.name)
        logger.debug(f"Cleaned up temporary config file: {temp_file.name}")
      except Exception as e:
        logger.warning(f"Failed to cleanup temp file {temp_file.name}: {e}")

def _resolve_config_path(request_data: Dict[str, Any]) -> Optional[str]:
  request_path = request_data.get("config_path")
  if request_path:
    if os.path.exists(request_path):
      return request_path
    logger.warning("Requested config_path '%s' was not found; falling back to defaults", request_path)
  return None

def send_email_notification(subject: str, body: str, config: Dict) -> bool:
  """Send email notification via SMTP with retry logic"""
  try:
    email_config = config.get('email_notifications', {})
    if not email_config.get('enabled', False):
      logger.info("Email notifications disabled")
      return True
    
    # Validate required email config fields
    required_fields = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'from_email', 'to_email']
    missing_fields = [field for field in required_fields if not email_config.get(field)]
    if missing_fields:
      logger.error(f"Missing required email configuration fields: {', '.join(missing_fields)}")
      return False
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = email_config['from_email']
    msg['To'] = email_config['to_email']
    
    # Create HTML version
    dashboard_url = config.get('dashboard', {}).get('url', '#')
    html_body = f"""
    <html>
    <head></head>
    <body>
      <h2>{subject}</h2>
      <div style="font-family: Arial, sans-serif;">
        {body.replace(chr(10), '<br>')}
      </div>
      <hr>
      <p style="color: #666; font-size: 12px;">
        Generated by Amazon PPC Optimizer on Google Cloud Functions<br>
        Dashboard: <a href="{dashboard_url}">View Dashboard</a>
      </p>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))
    
    # Send via SMTP with retry logic
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
      try:
        with smtplib.SMTP(email_config['smtp_host'], int(email_config['smtp_port']), timeout=30) as server:
          server.starttls()
          server.login(email_config['smtp_user'], email_config['smtp_password'])
          server.send_message(msg)
        
        logger.info(f"Email notification sent to {email_config['to_email']}")
        return True
        
      except (smtplib.SMTPException, OSError) as smtp_err:
        if attempt < max_retries - 1:
          logger.warning(f"Email send attempt {attempt + 1}/{max_retries} failed: {smtp_err}. Retrying...")
          import time
          time.sleep(retry_delay * (attempt + 1))
        else:
          logger.error(f"Failed to send email after {max_retries} attempts: {smtp_err}")
          return False
    
    return False
    
  except Exception as e:
    logger.error(f"Failed to send email notification: {str(e)}")
    return False


def update_dashboard(results, config):
  """Send optimization results to the dashboard with retry logic and exponential backoff"""
  try:
    dashboard_url = config.get('dashboard', {}).get('url')
    if not dashboard_url:
      logger.warning("Dashboard URL not configured")
      return False
    
    # Send POST request to dashboard API endpoint
    api_endpoint = f"{dashboard_url}/api/optimization-results"
    
    payload = {
      'timestamp': datetime.now().isoformat(),
      'results': results,
      'status': 'success'
    }
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
      try:
        logger.info(f"Updating dashboard (attempt {attempt + 1}/{max_retries})...")
        
        response = requests.post(
          api_endpoint,
          json=payload,
          headers={'Content-Type': 'application/json'},
          timeout=30
        )
        
        if response.status_code == 200:
          logger.info("Dashboard updated successfully")
          return True
        else:
          body_preview = response.text[:1000] if response.text else 'Empty response'
          logger.warning(f"Dashboard update returned status {response.status_code}: {body_preview}")
          if attempt < max_retries - 1:
            wait_time = retry_delay * (2 ** attempt)
            import time
            time.sleep(wait_time)
          
      except requests.exceptions.RequestException as e:
        logger.warning(f"Dashboard request failed: {e}")
        if attempt < max_retries - 1:
          wait_time = retry_delay * (2 ** attempt)
          import time
          time.sleep(wait_time)
    
    logger.error(f"Failed to update dashboard after {max_retries} attempts")
    return False
      
  except Exception as e:
    logger.error(f"Failed to update dashboard: {str(e)}")
    return False


def run_health_check(request) -> Tuple[Dict[str, Any], int]:
  """Lightweight health check endpoint - does not run optimization"""
  logger.info("=== Health Check Requested ===")
  
  try:
    # Validate GCP credentials early
    gcp_credentials_ok = False
    gcp_credentials_error = None
    try:
      creds_valid, error_msg = validate_credentials_early()
      gcp_credentials_ok = creds_valid
      if not creds_valid:
        gcp_credentials_error = error_msg
        logger.warning(f"GCP credentials validation failed: {error_msg}")
    except Exception as e:
      logger.warning(f"GCP credentials check failed: {e}")
      gcp_credentials_error = str(e)
    
    # Load configuration
    config = load_config()
    
    # Test dashboard connectivity
    dashboard_ok = False
    try:
      dashboard_client = DashboardClient(config)
      dashboard_ok = dashboard_client.health_check()
    except Exception as e:
      logger.warning(f"Dashboard health check failed: {e}")
    
    # Check email configuration
    email_ok = False
    try:
      email_config = config.get('email_notifications', {})
      email_ok = email_config.get('enabled', False) and bool(email_config.get('smtp_host'))
    except Exception as e:
      logger.warning(f"Email config check failed: {e}")
    
    response = {
      'status': 'healthy',
      'timestamp': datetime.now().isoformat(),
      'gcp_credentials_ok': gcp_credentials_ok,
      'gcp_credentials_error': gcp_credentials_error,
      'dashboard_ok': dashboard_ok,
      'email_ok': email_ok,
      'environment': 'cloud_function' if IS_CLOUD_FUNCTION else 'local'
    }
    
    return response, 200
    
  except Exception as e:
    logger.error(f"Health check failed: {str(e)}")
    return {
      'status': 'unhealthy',
      'error': str(e),
      'timestamp': datetime.now().isoformat()
    }, 500


def run_list_profiles(request) -> Tuple[Dict[str, Any], int]:
  """List accessible Amazon Advertising profiles"""
  logger.info("=== List Profiles Requested ===")
  
  try:
    config = load_config()
    set_environment_variables(config)
    validate_credentials(config)
    
    configured_profile_id = os.environ.get('AMAZON_PROFILE_ID', '').strip()
    if not configured_profile_id:
      configured_profile_id = config.get('amazon_api', {}).get('profile_id', '')
    
    with create_config_file(config) as config_file_path:
      optimizer = PPCAutomation(
        config_path=config_file_path,
        profile_id=configured_profile_id or 'dummy',
        dry_run=True
      )
      
      profiles_url = "https://advertising-api.amazon.com/v2/profiles"
      headers = {
        "Authorization": f"Bearer {optimizer.api.auth.access_token}",
        "Amazon-Advertising-API-ClientId": optimizer.api.client_id,
        "Content-Type": "application/json"
      }
      
      response = requests.get(profiles_url, headers=headers, timeout=30)
      
      if response.status_code != 200:
        return {
          'status': 'error',
          'message': 'Failed to fetch profiles',
          'error_code': response.status_code
        }, 500
      
      profiles = response.json()
      
      profile_list = []
      for profile in profiles:
        profile_id = str(profile.get('profileId', ''))
        profile_info = {
          'profileId': profile_id,
          'countryCode': profile.get('countryCode', 'N/A'),
          'currencyCode': profile.get('currencyCode', 'N/A'),
          'timezone': profile.get('timezone', 'N/A'),
          'accountType': profile.get('accountInfo', {}).get('type', 'N/A'),
          'is_configured': profile_id == configured_profile_id
        }
        profile_list.append(profile_info)
      
      campaigns_test = None
      if configured_profile_id:
        profile_ids = [p['profileId'] for p in profile_list]
        if configured_profile_id in profile_ids:
          try:
            campaigns_url = "https://advertising-api.amazon.com/sp/campaigns?startIndex=0&count=5"
            headers["Amazon-Advertising-API-Scope"] = configured_profile_id
            campaigns_response = requests.get(campaigns_url, headers=headers, timeout=30)
            
            campaigns_test = {
              'status_code': campaigns_response.status_code,
              'success': campaigns_response.status_code == 200,
              'campaign_count': len(campaigns_response.json()) if campaigns_response.status_code == 200 else 0
            }
          except Exception as e:
            campaigns_test = {'success': False, 'error': str(e)}
      
      response_data = {
        'status': 'success',
        'configured_profile_id': configured_profile_id,
        'profiles': profile_list,
        'campaigns_test': campaigns_test
      }
      
      return response_data, 200
      
  except Exception as e:
    return {'status': 'error', 'message': str(e)}, 500


def run_verify_connection(request) -> Tuple[Dict[str, Any], int]:
  """Verify Amazon Ads API connection"""
  logger.info("=== Verify Connection Requested ===")
  
  try:
    config = load_config()
    set_environment_variables(config)
    validate_credentials(config)
    
    try:
      sample_size = int(request.args.get('verify_sample_size', '5'))
      sample_size = min(max(1, sample_size), 100)
    except ValueError:
      return {'status': 'error', 'message': 'Invalid verify_sample_size'}, 400
    
    with create_config_file(config) as config_file_path:
      profile_id = os.environ.get('AMAZON_PROFILE_ID', '').strip()
      if not profile_id:
        profile_id = config.get('amazon_api', {}).get('profile_id', '')
      if not profile_id:
        raise ValueError("profile_id is required")

      optimizer = PPCAutomation(
        config_path=config_file_path,
        profile_id=profile_id,
        dry_run=True
      )

      logger.info(f"Verifying connectivity by requesting up to {sample_size} campaigns...")
      verification = optimizer.api.verify_connection(sample_size)

      if not verification.get('success'):
        return {
          'status': 'error',
          'message': 'Amazon Ads API verification failed',
          'error': verification.get('error', 'unknown_error')
        }, 500

      response = {
        'status': 'success',
        'message': 'Amazon Ads API connection verified',
        'profile_id': profile_id,
        'campaign_count': verification.get('campaign_count', 0),
        'sample': verification.get('sample', [])
      }
      return response, 200
      
  except Exception as e:
    return {'status': 'error', 'message': str(e)}, 500


def run_permission_health(request) -> Tuple[Dict[str, Any], int]:
  """Permission / product access health endpoint."""
  logger.info("=== Permission Health Requested ===")
  try:
    config = load_config()
    set_environment_variables(config)
    validate_credentials(config)

    profile_id = os.environ.get('AMAZON_PROFILE_ID', '').strip() or config.get('amazon_api', {}).get('profile_id', '').strip()
    if not profile_id:
      raise ValueError("profile_id is required")

    token_resp = requests.post(
      'https://api.amazon.com/auth/o2/token',
      data={
        'grant_type': 'refresh_token',
        'refresh_token': os.environ.get('AMAZON_REFRESH_TOKEN', ''),
        'client_id': os.environ.get('AMAZON_CLIENT_ID', ''),
        'client_secret': os.environ.get('AMAZON_CLIENT_SECRET', ''),
      },
      timeout=30
    )
    if token_resp.status_code != 200:
      return {'status': 'error', 'message': 'Failed to exchange refresh token'}, 500

    access_token = token_resp.json().get('access_token', '')

    def _probe(name: str, path: str) -> Dict[str, Any]:
      url = f"https://advertising-api.amazon.com{path}"
      headers = {
        'Authorization': f'Bearer {access_token}',
        'Amazon-Advertising-API-ClientId': os.environ.get('AMAZON_CLIENT_ID', ''),
        'Amazon-Advertising-API-Scope': profile_id,
        'Content-Type': 'application/json'
      }
      if name.startswith('SB') and 'v4' in path and 'Accept' not in headers:
        headers['Accept'] = 'application/vnd.sbCampaign.v4+json'
      if name.startswith('SP') and '/sp/v3/' in path and 'Accept' not in headers:
        headers['Accept'] = 'application/vnd.spCampaign.v3+json'
      
      try:
        resp = requests.get(url, headers=headers, timeout=30)
        return {
          'probe': name,
          'status_code': resp.status_code,
          'body_preview': resp.text[:300].replace('\n', ' ')
        }
      except Exception as ex:
        return {'probe': name, 'error': str(ex)}

    probes = [
      ('Profiles', '/v2/profiles'),
      ('SP Campaigns legacy', '/sp/campaigns?startIndex=0&count=1'),
      ('SP Campaigns v3', '/sp/v3/campaigns?startIndex=0&count=1'),
      ('SB Campaigns v4', '/sb/v4/campaigns?startIndex=0&count=1'),
      ('SD Campaigns', '/sd/campaigns?startIndex=0&count=1'),
    ]
    results = [_probe(name, path) for name, path in probes]

    return {
      'status': 'success',
      'probes': results,
    }, 200
  except Exception as e:
    return {'status': 'error', 'message': str(e)}, 500


@functions_framework.http
def run_optimizer(request) -> Tuple[Dict[str, Any], int]:
  """
  Cloud Function entry point - triggered by Cloud Scheduler
  """
  start_time = datetime.now()
  
  # Handle special endpoints
  if request.args.get('health', '').lower() == 'true':
    return run_health_check(request)
  if request.args.get('list_profiles', '').lower() == 'true':
    return run_list_profiles(request)
  if request.args.get('verify_connection', '').lower() == 'true':
    return run_verify_connection(request)
  if request.args.get('permission_health', '').lower() == 'true':
    return run_permission_health(request)
  
  logger.info(f"=== Amazon PPC Optimizer Started at {start_time} ===")
  
  config = None
  dashboard_client = None
  bigquery_client = None
  dry_run = False
  run_id: Optional[str] = None
  
  try:
    # Validate GCP credentials
    gcp_creds_valid, gcp_creds_error = validate_credentials_early()
    if not gcp_creds_valid:
      return {'status': 'error', 'message': f'GCP credential error: {gcp_creds_error}'}, 500
    
    # Get Request JSON
    try:
      request_json = request.get_json(silent=True) or {}
    except Exception:
      request_json = {}
    
    # Load Config
    config = load_config()
    set_environment_variables(config)
    validate_credentials(config)
    
    dry_run = request.args.get('dry_run', '').lower() == 'true' or request_json.get('dry_run', False)
    
    # Initialize BigQuery Client first (so it can be passed to DashboardClient)
    bigquery_client = None
    bigquery_config = config.get('bigquery', {})
    if bigquery_config.get('enabled', False):
      try:
        project_id = bigquery_config.get('project_id') or os.getenv('GCP_PROJECT') or os.getenv('GOOGLE_CLOUD_PROJECT')
        if project_id:
          set_bigquery_env_vars(project_id)
          dataset_id = bigquery_config.get('dataset_id', 'amazon_ppc_data')
          location = bigquery_config.get('location', 'us-east4')
          bigquery_client = BigQueryClient(project_id, dataset_id, location)
          logger.info(f"BigQuery client initialized for project {project_id}, dataset {dataset_id}")
        else:
          logger.warning("BigQuery enabled but no project_id configured")
      except Exception as bq_err:
        logger.warning(f"Failed to initialize BigQuery client: {bq_err}")

    # Initialize Dashboard Client with BigQuery integration
    dashboard_client = DashboardClient(config, bigquery_client=bigquery_client)

    # Run Interval Logic
    now_utc = _normalise_timestamp(datetime.now(timezone.utc))
    min_interval_minutes = _get_min_run_interval_minutes(config)
    force_run = request.args.get('force', '').lower() == 'true' or bool(request_json.get('force'))

    if not force_run and min_interval_minutes > 0:
      # Check if enough time has passed since last run
      last_run_memory = _get_last_run_memory()
      last_run_cache = _read_last_run_from_cache()
      last_run = _select_latest_timestamp(last_run_memory, last_run_cache)
      
      if last_run:
        time_since_last_run = (now_utc - last_run).total_seconds() / 60  # minutes
        if time_since_last_run < min_interval_minutes:
          wait_minutes = min_interval_minutes - time_since_last_run
          logger.info(f"Skipping run - only {time_since_last_run:.1f} minutes since last run. Need {min_interval_minutes} minutes. Wait {wait_minutes:.1f} more minutes.")
          return {
            'status': 'skipped',
            'message': f'Run interval not met. Wait {wait_minutes:.1f} more minutes.',
            'last_run': last_run.isoformat(),
            'min_interval_minutes': min_interval_minutes
          }, 200
      
      # Update last run time
      _update_last_run_memory(now_utc)
      _write_last_run_to_cache(now_utc)

    # Start Run
    run_id = dashboard_client.start_run(dry_run=dry_run)
    logger.info(f"Started optimization run: {run_id}")

    # Optimize
    with create_config_file(config) as config_file_path:
      profile_id = os.environ.get('AMAZON_PROFILE_ID', '').strip() or config.get('amazon_api', {}).get('profile_id', '')
      
      logger.info("Initializing optimizer...")
      dashboard_client.send_progress("Initializing optimizer...", 10.0)
      
      optimizer = PPCAutomation(
        config_path=config_file_path,
        profile_id=profile_id,
        dry_run=dry_run,
        bigquery_client=bigquery_client,
        dashboard_client=dashboard_client
      )
      
      logger.info("Running optimization...")
      results = optimizer.run()
      dashboard_client.send_progress("Processing results...", 90.0)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Send to Dashboard (which now also writes to BigQuery automatically)
    try:
      dashboard_client.send_results(results, config, duration, dry_run)
    except Exception as e:
      logger.warning(f"Dashboard update failed: {e}")

    # Email & Finish
    summary = format_results_summary(results, duration, dry_run)
    if config.get('email_notifications', {}).get('send_on_completion', True):
      send_email_notification(f"Optimization {'(DRY RUN) ' if dry_run else ''}Completed", summary, config)

    if bigquery_client:
      try:
        bigquery_client.record_run_event(run_id, 'completed', {'duration': duration})
      except Exception:
        pass

    return {
      'status': 'success', 
      'results': results,
      'run_id': run_id
    }, 200

  except Exception as e:
    error_msg = str(e)
    logger.error(f"Optimization failed: {error_msg}")
    logger.error(traceback.format_exc())
    
    if bigquery_client and run_id:
      try:
        bigquery_client.record_run_event(run_id, 'failed', {'error': error_msg})
      except Exception:
        pass
        
    return {'status': 'error', 'message': error_msg}, 500


# Create aliases for backward compatibility
# Note: optimizePPC and run_pipeline need to be actual functions, not just references,
# so that functions_framework can find them by name
optimizePPC = run_optimizer

@functions_framework.http
def run_pipeline(request) -> Tuple[Dict[str, Any], int]:
  """Alias for run_optimizer to support Cloud Run Job compatibility"""
  return run_optimizer(request)


def load_config() -> Dict[str, Any]:
  """Load configuration from environment or file"""
  config_json = os.environ.get('PPC_CONFIG', None)
  if config_json:
    return json.loads(config_json)
  
  config_file = os.path.join(os.path.dirname(__file__), 'config.json')
  if os.path.exists(config_file):
    with open(config_file, 'r', encoding='utf-8') as f:
      return json.load(f)
  
  raise ValueError("No configuration found")


def set_environment_variables(config: Dict[str, Any]) -> None:
  """Set env vars from config if not already present"""
  amazon_api = config.get('amazon_api', {})
  for key, val in [('AMAZON_CLIENT_ID', 'client_id'), 
                   ('AMAZON_CLIENT_SECRET', 'client_secret'),
                   ('AMAZON_REFRESH_TOKEN', 'refresh_token'),
                   ('AMAZON_PROFILE_ID', 'profile_id')]:
    if not os.environ.get(key):
      if amazon_api.get(val):
        os.environ[key] = amazon_api.get(val)


def set_bigquery_env_vars(project_id: str) -> None:
  if not os.getenv('GCP_PROJECT'):
    os.environ['GCP_PROJECT'] = project_id
  if not os.getenv('GOOGLE_CLOUD_PROJECT'):
    os.environ['GOOGLE_CLOUD_PROJECT'] = project_id


def validate_credentials(config: Dict[str, Any]) -> None:
  required = ['client_id', 'client_secret', 'refresh_token', 'profile_id']
  amazon_api = config.get('amazon_api', {})
  missing = [f for f in required if not amazon_api.get(f, '').strip()]
  if missing:
    raise ValueError(f"Missing API credentials: {', '.join(missing)}")


def format_results_summary(results: Dict[str, Any], duration: float, dry_run: bool) -> str:
  summary = [f"Duration: {duration:.2f}s", f"Mode: {'Dry Run' if dry_run else 'Live'}"]
  return "\n".join(summary)


if __name__ == "__main__":
  class MockRequest:
    def __init__(self):
      self.args = {'dry_run': 'true'}
    def get_json(self, silent=True):
      return {}
  
  result, status = run_optimizer(MockRequest())
  print(f"Status: {status}")
  print(f"Result: {json.dumps(result, indent=2)}")
