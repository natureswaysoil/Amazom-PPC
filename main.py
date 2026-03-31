import json
import logging
import os
import sys
import tempfile
import traceback
import uuid
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
from optimizer_core import PPCAutomation, AmazonAdsAPI, AuthenticationError
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
    
    # Load configuration (respect request overrides when provided)
    try:
      request_json = request.get_json(silent=True) or {}
    except Exception:
      request_json = {}
    config = load_config(request_json)
    # Keep live-data behavior consistent with optimizer runs.
    # This enables config-driven env values like BQ_PERFORMANCE_DATASET_ID.
    set_environment_variables(config)
    
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
    try:
      request_json = request.get_json(silent=True) or {}
    except Exception:
      request_json = {}
    config = load_config(request_json)
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
            campaigns_url = "https://advertising-api.amazon.com/v2/sp/campaigns?startIndex=0&count=5"
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
    try:
      request_json = request.get_json(silent=True) or {}
    except Exception:
      request_json = {}
    config = load_config(request_json)
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


def run_verify_candidates(request) -> Tuple[Dict[str, Any], int]:
  """Verify whether there are keyword discovery / negative keyword candidates.

  Runs the same candidate-generation logic as the optimizer, but always in
  dry-run mode (no changes applied to Amazon).
  """
  logger.info("=== Verify Candidates Requested ===")

  try:
    try:
      request_json = request.get_json(silent=True) or {}
    except Exception:
      request_json = {}

    config = load_config(request_json)
    set_environment_variables(config)
    validate_credentials(config)

    # Make audit output safe in serverless environments.
    if isinstance(config.get('logging'), dict):
      config['logging'].setdefault('output_dir', '/tmp')

    with create_config_file(config) as config_file_path:
      profile_id = os.environ.get('AMAZON_PROFILE_ID', '').strip()
      if not profile_id:
        profile_id = config.get('amazon_api', {}).get('profile_id', '')
      if not profile_id:
        raise ValueError("profile_id is required")

      optimizer = PPCAutomation(
        config_path=config_file_path,
        profile_id=profile_id,
        dry_run=True,
      )

      keyword_discovery = optimizer.keyword_discovery.discover_keywords(dry_run=True)
      negative_keywords = optimizer.negative_keywords.add_negative_keywords(dry_run=True)

      return {
        'status': 'success',
        'message': 'Candidate verification complete (dry-run only; no changes applied)',
        'profile_id': profile_id,
        'keyword_discovery': {
          'keywords_discovered': keyword_discovery.get('keywords_discovered', 0),
          'keywords_would_add': keyword_discovery.get('keywords_would_add', 0),
        },
        'negative_keywords': {
          # In dry-run, this is the number of candidates that would be added.
          'negative_keywords_would_add': negative_keywords.get('negative_keywords_added', 0),
        },
      }, 200

  except Exception as e:
    return {'status': 'error', 'message': str(e)}, 500


def run_verify_dashboard(request) -> Tuple[Dict[str, Any], int]:
  """Verify dashboard connectivity (and auth if configured).

  This endpoint does not require Amazon Ads credentials.
  """
  logger.info("=== Verify Dashboard Requested ===")

  try:
    try:
      request_json = request.get_json(silent=True) or {}
    except Exception:
      request_json = {}

    config = load_config(request_json)

    dashboard_client = DashboardClient(config)
    details: Dict[str, Any] = {
      'enabled': bool(getattr(dashboard_client, 'enabled', False)),
      'url_configured': bool(getattr(dashboard_client, 'url', '')),
      'api_key_configured': bool(getattr(dashboard_client, 'api_key', '')),
    }

    if not details['enabled']:
      return {
        'status': 'error',
        'message': 'Dashboard client disabled (missing URL or disabled in config)',
        'dashboard': details,
      }, 400

    # 1) Reachability: /api/health
    health_resp = dashboard_client._make_request('/api/health', {}, method='GET')
    details['health_ok'] = health_resp is not None
    details['health_response_preview'] = (health_resp if isinstance(health_resp, dict) else None)

    # 2) Auth + write access: /api/optimization-status
    # This may create a harmless status log entry on the dashboard.
    status_payload = {
      'timestamp': datetime.now().isoformat(),
      'run_id': str(uuid.uuid4()),
      'status': 'running',
      'stage': 'verify_dashboard',
      'message': 'verify_dashboard ping',
      'percent_complete': 0.0,
      'profile_id': (config.get('amazon_api', {}) or {}).get('profile_id', ''),
      'dry_run': True,
    }
    status_resp = dashboard_client._make_request('/api/optimization-status', status_payload, method='POST')
    details['status_post_ok'] = status_resp is not None
    details['status_response_preview'] = (status_resp if isinstance(status_resp, dict) else None)

    ok = bool(details['health_ok'] and details['status_post_ok'])
    return {
      'status': 'success' if ok else 'error',
      'message': 'Dashboard verification complete' if ok else 'Dashboard verification failed',
      'dashboard': details,
    }, 200 if ok else 502

  except Exception as e:
    return {'status': 'error', 'message': str(e)}, 500


def _resolve_dashboard_api_key_from_config(config: Dict[str, Any]) -> str:
  key = (os.getenv('DASHBOARD_API_KEY') or '').strip()
  if not key and isinstance(config.get('dashboard'), dict):
    key = (config.get('dashboard', {}).get('api_key') or '').strip()
  if not key:
    return ''
  upper = key.upper()
  if upper.startswith('YOUR_') or key == 'YOUR_DASHBOARD_API_KEY':
    return ''
  return key


def _is_authorized_dashboard_request(request, api_key: str) -> bool:
  if not api_key:
    return True

  auth_header = request.headers.get('Authorization') or request.headers.get('authorization') or ''
  token = ''
  if auth_header.startswith('Bearer '):
    token = auth_header[len('Bearer '):].strip()
  else:
    token = auth_header.strip()

  header_api_key = (
    request.headers.get('X-API-Key') or
    request.headers.get('x-api-key') or
    ''
  ).strip()
  return token == api_key or header_api_key == api_key


def run_live_data(request) -> Tuple[Dict[str, Any], int]:
  """Serve read-only live dashboard data from BigQuery.

  The Next.js dashboard calls the optimizer with query param `live=<section>`.
  This endpoint returns normalized shapes per section.
  """

  section = (request.args.get('live', '') or request.args.get('section', '') or 'overview').strip().lower()
  logger.info("=== Live Data Requested (section=%s) ===", section)

  try:
    # Validate GCP credentials early for clearer errors.
    creds_valid, creds_error = validate_credentials_early()
    if not creds_valid:
      return {
        'status': 'error',
        'message': f'GCP credential error: {creds_error}',
      }, 500

    try:
      request_json = request.get_json(silent=True) or {}
    except Exception:
      request_json = {}

    config = load_config(request_json)

    # Keep behavior consistent with optimizer runs so config-driven env vars
    # (e.g. BQ_PERFORMANCE_DATASET_ID) take effect for live-data requests.
    set_environment_variables(config)

    # Optional shared-key auth: enforce if configured.
    api_key = _resolve_dashboard_api_key_from_config(config)
    if api_key and not _is_authorized_dashboard_request(request, api_key):
      return {
        'status': 'error',
        'message': 'Unauthorized',
      }, 401

    # Parse params
    try:
      days = int(request.args.get('days', '7'))
    except Exception:
      days = 7
    days = max(1, min(days, 365))

    try:
      limit = int(request.args.get('limit', '50'))
    except Exception:
      limit = 50
    limit = max(1, min(limit, 500))

    profile_id = (request.args.get('profile_id', '') or request.headers.get('X-Profile-ID', '') or '').strip() or None

    # Initialize BigQuery client
    bigquery_client = None
    bigquery_config = config.get('bigquery', {}) if isinstance(config, dict) else {}
    if isinstance(bigquery_config, dict) and bigquery_config.get('enabled', False):
      project_id = bigquery_config.get('project_id') or os.getenv('GCP_PROJECT') or os.getenv('GOOGLE_CLOUD_PROJECT')
      dataset_id = bigquery_config.get('dataset_id', 'amazon_ppc_data')
      location = bigquery_config.get('location', 'us-east4')
      if project_id:
        set_bigquery_env_vars(project_id)
        bigquery_client = BigQueryClient(project_id, dataset_id, location)

    if not bigquery_client:
      # Keep the API contract stable even when BigQuery is disabled.
      empty = {
        'status': 'success',
        'message': 'BigQuery disabled or not configured',
      }
      if section in ('overview', 'reports'):
        empty.update({'recent_results': [], 'daily': []})
      elif section == 'campaigns':
        empty.update({'campaigns': []})
      elif section == 'automation':
        empty.update({'events': []})
      else:
        empty.update({'data': {}})
      return empty, 200

    # Fetch + shape per section.
    if section in ('overview', ''):
      recent_results = bigquery_client.fetch_recent_optimization_results(days=days, limit=limit, profile_id=profile_id)
      daily = bigquery_client.fetch_daily_overview(days=days, profile_id=profile_id)
      
      # Add metadata about lookback attribution to help dashboard display correctly
      # When data contains lookback windows (e.g., attributedSales14d), summing daily values
      # causes duplicate counting. The dashboard should use the latest day's value instead.
      metadata = {
        'has_lookback_attribution': True,  # Assume true since most Amazon data has 7d/14d/30d attribution
        'lookback_warning': 'Daily metrics contain multi-day attribution windows. Use latest day for totals, do not sum across days.',
      }
      
      return {
        'status': 'success',
        'recent_results': recent_results,
        'daily': daily,
        'metadata': metadata,
      }, 200

    if section == 'campaigns':
      campaigns = bigquery_client.fetch_campaigns_summary(days=days, limit=limit, profile_id=profile_id)
      return {
        'status': 'success',
        'campaigns': campaigns,
      }, 200

    if section == 'automation':
      events = bigquery_client.fetch_run_events(limit=limit, profile_id=profile_id)
      return {
        'status': 'success',
        'events': events,
      }, 200

    if section == 'discovery':
      data = bigquery_client.fetch_keyword_discovery_summary(days=days)
      top_keywords = bigquery_client.fetch_top_performing_keywords(days=days, limit=20)
      data['top_performing_keywords'] = top_keywords
      return {
        'status': 'success',
        'data': data,
      }, 200

    if section in ('budget', 'dayparting'):
      latest = bigquery_client.fetch_latest_optimization_result(profile_id=profile_id, include_payload_json=True) or {}
      features = latest.get('features') or {}
      data = features.get(section) if isinstance(features, dict) else None
      if not isinstance(data, dict):
        data = {}
      return {
        'status': 'success',
        'data': data,
      }, 200

    if section == 'reports':
      recent_results = bigquery_client.fetch_recent_optimization_results(days=days, limit=limit, profile_id=profile_id)
      daily = bigquery_client.fetch_daily_overview(days=days, profile_id=profile_id)
      
      # Add metadata about lookback attribution
      metadata = {
        'has_lookback_attribution': True,
        'lookback_warning': 'Daily metrics contain multi-day attribution windows. Use latest day for totals, do not sum across days.',
      }
      
      return {
        'status': 'success',
        'recent_results': recent_results,
        'daily': daily,
        'metadata': metadata,
      }, 200

    # Unknown section -> keep backward-compatible payload.
    return {
      'status': 'success',
      'message': f"Unknown live section '{section}', returning overview payload",
      'recent_results': bigquery_client.fetch_recent_optimization_results(days=days, limit=limit, profile_id=profile_id),
      'daily': bigquery_client.fetch_daily_overview(days=days, profile_id=profile_id),
    }, 200

  except Exception as e:
    logger.error("Live data failed: %s", e)
    logger.error(traceback.format_exc())
    return {
      'status': 'error',
      'message': str(e),
    }, 500


def run_permission_health(request) -> Tuple[Dict[str, Any], int]:
  """Permission / product access health endpoint."""
  logger.info("=== Permission Health Requested ===")
  try:
    try:
      request_json = request.get_json(silent=True) or {}
    except Exception:
      request_json = {}
    config = load_config(request_json)
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
      body_preview = ''
      try:
        body_preview = json.dumps(token_resp.json())[:800]
      except Exception:
        body_preview = (token_resp.text or '')[:800]
      return {
        'status': 'error',
        'message': 'Failed to exchange refresh token',
        'status_code': token_resp.status_code,
        'body_preview': body_preview,
      }, 500

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
      ('SP Campaigns legacy', '/v2/sp/campaigns?startIndex=0&count=1'),
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

  # Cloud Run / Cloud Functions Gen2 health probes and uptime checks often issue
  # a plain GET / with no query params. Treat this as a lightweight health
  # response instead of starting a full optimizer run, which can saturate
  # instances (containerConcurrency=1) and cause "no available instance" errors.
  if request.method == 'GET' and not request.args:
    return {
      'status': 'healthy',
      'message': 'OK',
      'timestamp': datetime.utcnow().isoformat(),
    }, 200

  # Live dashboard data endpoint (read-only)
  if request.args.get('live', '').strip():
    return run_live_data(request)
  
  # Handle special endpoints
  if request.args.get('health', '').lower() == 'true':
    return run_health_check(request)
  if request.args.get('list_profiles', '').lower() == 'true':
    return run_list_profiles(request)
  if request.args.get('verify_connection', '').lower() == 'true':
    return run_verify_connection(request)
  if request.args.get('verify_candidates', '').lower() == 'true':
    return run_verify_candidates(request)
  if request.args.get('verify_dashboard', '').lower() == 'true':
    return run_verify_dashboard(request)
  if request.args.get('permission_health', '').lower() == 'true':
    return run_permission_health(request)
  
  logger.info(f"=== Amazon PPC Optimizer Started at {start_time} ===")
  
  config = None
  dashboard_client = None
  bigquery_client = None
  dry_run = False
  run_id: Optional[str] = None
  preflight_details: Optional[Dict[str, Any]] = None
  
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
    
    # Load Config (respect request overrides when provided)
    config = load_config(request_json)
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

    # Preflight: verify Amazon OAuth and basic connectivity before heavy work
    try:
      profile_id = os.environ.get('AMAZON_PROFILE_ID', '').strip() or config.get('amazon_api', {}).get('profile_id', '')
      region = (config.get('amazon_api', {}) or {}).get('region', 'NA')
      preflight_api = AmazonAdsAPI(profile_id, region)
      preflight = preflight_api.verify_connection(sample_size=1)
      if not preflight.get('success'):
        # Report to dashboard (non-blocking) then abort early
        try:
          dashboard_client.send_error(Exception('Amazon Ads API preflight failed'), {
            'stage': 'preflight',
            'details': preflight,
          })
        except Exception:
          pass
        return {
          'status': 'error',
          'message': 'Amazon Ads API preflight failed',
          'error': preflight.get('error') or 'connection_failed'
        }, 500
      else:
        # Record succinct preflight summary for response/logging
        preflight_details = {
          'method': preflight.get('method'),
          'campaign_count': preflight.get('campaign_count', 0)
        }
        logger.info(
          "Preflight OK: %s (campaign_count=%s)",
          preflight_details['method'], preflight_details['campaign_count']
        )
    except AuthenticationError as auth_err:
      # Clear message on auth failure and abort
      try:
        dashboard_client.send_error(auth_err, {'stage': 'preflight'})
      except Exception:
        pass
      return {'status': 'error', 'message': str(auth_err)}, 500
    except Exception as pf_exc:
      # Unexpected preflight issue: log and continue (do not hard-fail)
      logger.warning(f"Preflight check encountered an issue but will continue: {pf_exc}")

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

          # If this request is for dashboard live data, still serve the BigQuery-backed
          # payload so the UI can render last-run/7d metrics even when runs are skipped.
          if request.args.get('live', '').strip() or request.args.get('section', '').strip():
            try:
              live_payload, live_status = run_live_data(request)
              if live_status == 200 and isinstance(live_payload, dict):
                enriched = dict(live_payload)
                enriched.update({
                  'status': 'skipped',
                  'message': f'Run interval not met. Wait {wait_minutes:.1f} more minutes.',
                  'last_run': last_run.isoformat(),
                  'min_interval_minutes': min_interval_minutes,
                  'run_interval_skipped': True,
                })
                return enriched, 200
            except Exception:
              pass

          return {
            'status': 'skipped',
            'message': f'Run interval not met. Wait {wait_minutes:.1f} more minutes.',
            'last_run': last_run.isoformat(),
            'min_interval_minutes': min_interval_minutes
          }, 200
      
      # Update last run time
      _update_last_run_memory(now_utc)
      _write_last_run_to_cache(now_utc)

    # Start Run (include preflight summary in initial dashboard status)
    run_id = dashboard_client.start_run(dry_run=dry_run, preflight=preflight_details)
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
    
    # Mark the run as completed in the dashboard (always try, even if send_results failed)
    try:
      dashboard_client.complete_run(duration, dry_run)
    except Exception as e:
      logger.warning(f"Failed to mark run as completed: {e}")

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
      'run_id': run_id,
      'preflight': preflight_details
    }, 200

  except SystemExit as e:
    # Some deep optimizer modules call sys.exit() for fatal config/auth errors.
    # SystemExit does NOT inherit from Exception, so without this handler the
    # run would appear as "started" with no terminal event in BigQuery.
    code = getattr(e, 'code', None)
    error_msg = f"Optimizer exited early (SystemExit): {code}"
    logger.error(error_msg)
    logger.error(traceback.format_exc())

    if 'dashboard_client' in locals() and dashboard_client:
      try:
        dashboard_client.send_error(RuntimeError(error_msg), {'stage': 'system_exit', 'code': code})
      except Exception:
        pass

    if 'bigquery_client' in locals() and bigquery_client and 'run_id' in locals() and run_id:
      try:
        bigquery_client.record_run_event(run_id, 'failed', {'error': error_msg, 'code': str(code)})
      except Exception:
        pass

    preflight = locals().get('preflight_details', {})
    return {'status': 'error', 'message': error_msg, 'preflight': preflight}, 500

  except Exception as e:
    error_msg = str(e)
    logger.error(f"Optimization failed: {error_msg}")
    logger.error(traceback.format_exc())
    
    if bigquery_client and run_id:
      try:
        bigquery_client.record_run_event(run_id, 'failed', {'error': error_msg})
      except Exception:
        pass
        
    return {'status': 'error', 'message': error_msg, 'preflight': preflight_details}, 500


# Create aliases for backward compatibility
# Note: These must be actual functions with @functions_framework.http decorator,
# not just variable references, so that functions_framework can find them by name

@functions_framework.http
def optimizePPC(request) -> Tuple[Dict[str, Any], int]:
  """Alias for run_optimizer for backward compatibility"""
  return run_optimizer(request)

@functions_framework.http
def run_pipeline(request) -> Tuple[Dict[str, Any], int]:
  """Alias for run_optimizer to support Cloud Run Job compatibility"""
  return run_optimizer(request)


def _load_config_from_path(path: str) -> Dict[str, Any]:
  if not path or not os.path.exists(path):
    raise ValueError(f"Config path not found: {path}")

  with open(path, 'r', encoding='utf-8') as handle:
    raw = handle.read()

  # Determine parser by extension, but fall back to YAML for robustness.
  ext = os.path.splitext(path)[1].lower()
  try:
    if ext in {'.json'}:
      parsed = json.loads(raw)
    else:
      parsed = yaml.safe_load(raw)
  except Exception as exc:
    raise ValueError(f"Failed to parse config at {path}: {exc}") from exc

  if not isinstance(parsed, dict):
    raise ValueError(f"Invalid config format at {path}: expected object/dict")

  return parsed


def load_config(request_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
  """Load configuration using runtime priority order.

  Priority:
    1) request_data['config']
    2) request_data['config_path'] (if exists)
    3) PPC_CONFIG_PATH env var (file path)
    4) PPC_CONFIG env var (JSON/YAML string)
    5) bundled config.json
  """

  request_data = request_data or {}
  if isinstance(request_data.get('config'), dict):
    return request_data['config']

  request_path = _resolve_config_path(request_data)
  if request_path:
    return _load_config_from_path(request_path)

  env_path = (os.environ.get('PPC_CONFIG_PATH') or '').strip()
  if env_path:
    return _load_config_from_path(env_path)

  raw_config = os.environ.get('PPC_CONFIG', None)
  if raw_config:
    # PPC_CONFIG may be JSON or YAML.
    try:
      parsed = json.loads(raw_config)
    except Exception:
      parsed = yaml.safe_load(raw_config)
    if not isinstance(parsed, dict):
      raise ValueError("Invalid PPC_CONFIG: expected object/dict")
    return parsed

  config_file = os.path.join(os.path.dirname(__file__), 'config.json')
  if os.path.exists(config_file):
    with open(config_file, 'r', encoding='utf-8') as f:
      parsed = json.load(f)
    if not isinstance(parsed, dict):
      raise ValueError("Invalid bundled config.json: expected object/dict")
    return parsed

  raise ValueError("No configuration found")


def _fetch_secret_from_gsm(secret_name: str, project_id: str) -> Optional[str]:
  """Fetch a secret's latest value from Google Secret Manager.

  Returns the stripped secret string on success, or None if the secret cannot
  be fetched (missing IAM permission, secret not found, import error, etc.).
  Failures are logged at DEBUG level so they don't pollute normal log output.
  """
  try:
    from google.cloud import secretmanager as _sm
    client = _sm.SecretManagerServiceClient()
    resource = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": resource})
    value = response.payload.data.decode("UTF-8").strip()
    return value if value else None
  except Exception as exc:
    logger.debug("Could not fetch secret '%s' from Secret Manager: %s", secret_name, type(exc).__name__)
    return None


def set_environment_variables(config: Dict[str, Any]) -> None:
  """Set env vars from config if not already present"""
  amazon_api = config.get('amazon_api', {})
  # When config carries a Google Secret Manager *secret name* instead of the
  # actual credential value (common when the config is generated from a Cloud
  # Run job template that embeds secret identifiers), resolve the value
  # directly from Secret Manager before falling through to the error path.
  # This makes the Cloud Function resilient to missing --set-secrets bindings.
  known_secret_names = {
    'Amazon_Ads_Client_identifier',
    'Amazon_Ads_Client_secret',
    'Amazon_Ads_Refresh_Token',
  }
  # Derive the GCP project ID from available sources (used only for GSM fetch).
  gsm_project_id: Optional[str] = (
    os.getenv('GCP_PROJECT_ID') or
    os.getenv('GCP_PROJECT') or
    os.getenv('GOOGLE_CLOUD_PROJECT') or
    (config.get('bigquery', {}) or {}).get('project_id') or
    ''
  )
  for key, val in [('AMAZON_CLIENT_ID', 'client_id'),
                   ('AMAZON_CLIENT_SECRET', 'client_secret'),
                   ('AMAZON_REFRESH_TOKEN', 'refresh_token'),
                   ('AMAZON_PROFILE_ID', 'profile_id')]:
    if not os.environ.get(key):
      cfg_value = (amazon_api.get(val) or '').strip() if isinstance(amazon_api, dict) else ''
      if not cfg_value:
        continue
      if cfg_value in known_secret_names:
        # The config carries the Secret Manager secret name, not the actual
        # value.  Attempt a direct fetch so that the credential is available
        # even when --set-secrets binding is absent or misconfigured.
        if gsm_project_id:
          fetched = _fetch_secret_from_gsm(cfg_value, gsm_project_id)
          if fetched:
            os.environ[key] = fetched
            logger.info(
              "Loaded %s from Google Secret Manager (secret: %s)",
              key, cfg_value,
            )
            continue
        logger.error(
          "Config contains a Secret Manager secret name for %s (%s) but the "
          "value could not be fetched. Ensure --set-secrets binds the secret "
          "to the env var, or that the service account has "
          "roles/secretmanager.secretAccessor on this secret.",
          key, cfg_value,
        )
        continue
      # Skip obvious placeholders.
      if 'YOUR_' in cfg_value or 'XXXX' in cfg_value.upper():
        continue
      os.environ[key] = cfg_value

  # Optional: allow performance tables to live in a different dataset than optimizer tables.
  # If configured, BigQueryClient will read this via env var.
  bigquery_cfg = config.get('bigquery', {}) if isinstance(config, dict) else {}
  if not os.environ.get('BQ_PERFORMANCE_DATASET_ID') and isinstance(bigquery_cfg, dict):
    perf_dataset = (bigquery_cfg.get('performance_dataset_id') or bigquery_cfg.get('perf_dataset_id') or '').strip()
    if perf_dataset and 'YOUR_' not in perf_dataset:
      os.environ['BQ_PERFORMANCE_DATASET_ID'] = perf_dataset
  
  # Optional: allow configuration of preferred performance table for dashboard metrics
  if not os.environ.get('BQ_PREFERRED_PERFORMANCE_TABLE') and isinstance(bigquery_cfg, dict):
    preferred_table = (bigquery_cfg.get('preferred_performance_table') or '').strip()
    if preferred_table and 'YOUR_' not in preferred_table.upper():
      os.environ['BQ_PREFERRED_PERFORMANCE_TABLE'] = preferred_table


def set_bigquery_env_vars(project_id: str) -> None:
  if not os.getenv('GCP_PROJECT'):
    os.environ['GCP_PROJECT'] = project_id
  if not os.getenv('GOOGLE_CLOUD_PROJECT'):
    os.environ['GOOGLE_CLOUD_PROJECT'] = project_id


def validate_credentials(config: Dict[str, Any]) -> None:
  """Validate Amazon credentials.

  Credentials can come from env vars (typical for Secret Manager deployments)
  or from config (common for local runs via PPC_CONFIG).
  """

  amazon_api = config.get('amazon_api', {}) if isinstance(config, dict) else {}

  def _looks_like_secret_ref(value: str) -> bool:
    if not value:
      return False
    lower = value.lower()
    if lower.startswith('projects/') and '/secrets/' in lower:
      return True
    if '/secrets/' in lower and '/versions/' in lower:
      return True
    return False

  def _looks_like_placeholder(value: str) -> bool:
    if not value:
      return False
    upper = value.upper()
    if 'YOUR_' in upper or upper in {'CHANGEME', 'REPLACE_ME'}:
      return True
    # Common repo sample placeholders.
    if 'XXXXX' in value:
      return True
    return False

  def _get_env_or_config(env_key: str, config_key: str) -> str:
    env_val = (os.environ.get(env_key) or '').strip()
    if env_val:
      return env_val
    if isinstance(amazon_api, dict):
      return str(amazon_api.get(config_key) or '').strip()
    return ''

  client_id = _get_env_or_config('AMAZON_CLIENT_ID', 'client_id')
  client_secret = _get_env_or_config('AMAZON_CLIENT_SECRET', 'client_secret')
  refresh_token = _get_env_or_config('AMAZON_REFRESH_TOKEN', 'refresh_token')
  profile_id = _get_env_or_config('AMAZON_PROFILE_ID', 'profile_id')

  # Treat placeholders as missing to avoid falling through to OAuth calls.
  for env_key, value in [
    ('AMAZON_CLIENT_ID', client_id),
    ('AMAZON_CLIENT_SECRET', client_secret),
    ('AMAZON_REFRESH_TOKEN', refresh_token),
    ('AMAZON_PROFILE_ID', profile_id),
  ]:
    if _looks_like_placeholder(value):
      raise ValueError(
        f"{env_key} appears to be a placeholder value. Provide real credentials via Secret Manager env injection or PPC_CONFIG."
      )

  missing = [
    name for name, value in [
      ('client_id', client_id),
      ('client_secret', client_secret),
      ('refresh_token', refresh_token),
      ('profile_id', profile_id),
    ]
    if not value
  ]
  if missing:
    raise ValueError(
      "Missing API credentials: %s. Provide via env vars (AMAZON_CLIENT_ID/AMAZON_CLIENT_SECRET/AMAZON_REFRESH_TOKEN/AMAZON_PROFILE_ID) "
      "or via PPC_CONFIG amazon_api.*"
      % ", ".join(missing)
    )

  known_secret_names = {
    'Amazon_Ads_Client_identifier',
    'Amazon_Ads_Client_secret',
    'Amazon_Ads_Refresh_Token',
  }
  for field_name, value in [
    ('client_id', client_id),
    ('client_secret', client_secret),
    ('refresh_token', refresh_token),
  ]:
    if value in known_secret_names or _looks_like_secret_ref(value):
      raise ValueError(
        f"{field_name} appears to be a Secret Manager secret reference/name ({value}), not the actual credential value. "
        "This typically happens when secrets failed to load into env vars and config contains secret identifiers. "
        "Fix by injecting Secret Manager secrets into AMAZON_* env vars (recommended) or putting actual values in PPC_CONFIG."
      )

  # Light sanity: catch accidental newlines/spaces in refresh token.
  if any(ch in refresh_token for ch in ['\n', '\r']):
    raise ValueError("refresh_token contains newlines; Secret Manager value likely has formatting issues")


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
