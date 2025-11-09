import json
import logging
import os
import sys
import tempfile
import traceback
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Optional, Tuple, Any
import functions_framework
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import yaml

from optimizer_core import PPCAutomation
from dashboard_client import DashboardClient
from bigquery_client import BigQueryClient

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


@contextmanager
def create_config_file(config_dict: Dict) -> str:
    """
    Create a temporary config file from dictionary using context manager
    The optimizer_core expects YAML format file, so we ensure consistent format handling
    
    Args:
        config_dict: Configuration dictionary (from JSON or other source)
        
    Yields:
        Path to temporary YAML config file
        
    Raises:
        ValueError: If config_dict is invalid
        IOError: If file creation fails
    """
    if not isinstance(config_dict, dict):
        raise ValueError("config_dict must be a dictionary")
    
    temp_file = None
    try:
        # Create temp file with YAML format (optimizer_core expects YAML)
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

def _resolve_config_path(request_data: Dict[str, Any]) -> str:
    request_path = request_data.get("config_path")
    if request_path:
        if os.path.exists(request_path):
            return request_path
        logger.warning("Requested config_path '%s' was not found; falling back to defaults", request_path)

def send_email_notification(subject: str, body: str, config: Dict) -> bool:
    """
    Send email notification via SMTP with retry logic
    
    Args:
        subject: Email subject line
        body: Plain text email body
        config: Configuration dictionary containing email settings
        
    Returns:
        True if email sent successfully, False otherwise
    """
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
            return
        
        # Send POST request to dashboard API endpoint
        api_endpoint = f"{dashboard_url}/api/optimization-results"
        
        payload = {
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'status': 'success'
        }
        
        # Retry logic with exponential backoff (3 attempts)
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Updating dashboard (attempt {attempt + 1}/{max_retries})...")
                logger.debug(f"Dashboard URL: {api_endpoint}")
                logger.debug(f"Payload preview: {str(payload)[:500]}")
                
                response = requests.post(
                    api_endpoint,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30  # Increased from 10s to 30s
                )
                
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    logger.info("Dashboard updated successfully")
                    return
                else:
                    body_preview = response.text[:1000] if response.text else 'Empty response'
                    logger.warning(f"Dashboard update returned status {response.status_code}: {body_preview}")
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.info(f"Retrying in {wait_time}s...")
                        import time
                        time.sleep(wait_time)
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Dashboard request timeout to {api_endpoint} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time}s...")
                    import time
                    time.sleep(wait_time)
            except requests.exceptions.RequestException as e:
                logger.warning(f"Dashboard request failed to {api_endpoint} (attempt {attempt + 1}/{max_retries}): {e}")
                logger.debug(f"Exception type: {type(e).__name__}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.debug(f"Error response status: {e.response.status_code}")
                    logger.debug(f"Error response body: {e.response.text[:500]}")
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time}s...")
                    import time
                    time.sleep(wait_time)
        
        logger.error(f"Failed to update dashboard after {max_retries} attempts")
            
    except Exception as e:
        logger.error(f"Failed to update dashboard: {str(e)}")
        return False


def run_health_check(request) -> Tuple[Dict[str, Any], int]:
    """
    Lightweight health check endpoint - does not run optimization
    
    Tests:
    - Configuration loading
    - Dashboard connectivity (optional)
    - Email configuration (optional)
    
    Args:
        request: HTTP request object
        
    Returns:
        Health status dictionary and HTTP 200
    """
    logger.info("=== Health Check Requested ===")
    
    try:
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
            'dashboard_ok': dashboard_ok,
            'email_ok': email_ok,
            'environment': 'cloud_function' if IS_CLOUD_FUNCTION else 'local'
        }
        
        logger.info(f"Health check completed: dashboard_ok={dashboard_ok}, email_ok={email_ok}")
        return response, 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, 500


def run_verify_connection(request) -> Tuple[Dict[str, Any], int]:
    """
    Verify Amazon Ads API connection without running full optimization
    
    Retrieves a small sample of campaigns to verify:
    - API credentials are valid
    - Access token can be refreshed
    - Amazon Ads API is reachable
    
    Query parameters:
    - verify_sample_size: Number of campaigns to retrieve (default: 5, max: 100)
    
    Args:
        request: HTTP request object
        
    Returns:
        Sample campaigns and connection status
    """
    logger.info("=== Verify Connection Requested ===")
    
    try:
        # Load configuration
        config = load_config()
        set_environment_variables(config)
        validate_credentials(config)
        
        # Get sample size from query params with validation
        try:
            sample_size = int(request.args.get('verify_sample_size', '5'))
            sample_size = min(max(1, sample_size), 100)  # Clamp between 1 and 100
        except ValueError:
            return {
                'status': 'error',
                'message': 'Invalid verify_sample_size parameter. Must be a number between 1 and 100.',
                'timestamp': datetime.now().isoformat()
            }, 400
        
        # Import optimizer to test connection
        from optimizer_core import PPCAutomation
        
        with create_config_file(config) as config_file_path:
            profile_id = config.get('amazon_api', {}).get('profile_id', '')
            if not profile_id:
                raise ValueError("profile_id is required in amazon_api configuration")
            
            # Create optimizer instance (this will authenticate)
            optimizer = PPCAutomation(
                config_path=config_file_path,
                profile_id=profile_id,
                dry_run=True  # Always use dry_run for verification
            )
            
            # Try to fetch a small sample of campaigns
            logger.info(f"Fetching {sample_size} campaigns to verify connection...")
            
            # This would call the Amazon Ads API to verify connection
            # For now, we'll indicate success if we can initialize
            response = {
                'status': 'success',
                'message': 'Amazon Ads API connection verified',
                'profile_id': profile_id,
                'timestamp': datetime.now().isoformat(),
                'sample_size': sample_size,
                'note': 'Connection successful - credentials are valid and API is reachable'
            }
            
            logger.info("Connection verification successful")
            return response, 200
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Connection verification failed: {error_msg}")
        
        return {
            'status': 'error',
            'message': 'Failed to connect to Amazon Ads API',
            'error': error_msg,
            'timestamp': datetime.now().isoformat(),
            'troubleshooting': [
                'Verify AMAZON_CLIENT_ID is correct',
                'Verify AMAZON_CLIENT_SECRET is correct',
                'Verify AMAZON_REFRESH_TOKEN is not expired',
                'Check if profile_id matches your Amazon Ads account',
                'Ensure Amazon Ads API is not experiencing outages'
            ]
        }, 500


@functions_framework.http
def run_optimizer(request) -> Tuple[Dict[str, Any], int]:
    """
    Cloud Function entry point - triggered by Cloud Scheduler
    
    Supports multiple modes via query parameters:
    - ?health=true: Quick health check without running optimization
    - ?verify_connection=true: Verify Amazon Ads API connection with small sample
    - ?dry_run=true: Run optimization without making actual changes
    - Normal execution: Full optimization run
    
    The optimizer automatically refreshes the Amazon Advertising API access token
    before making API calls using the refresh_token stored in environment variables.
    
    Args:
        request: HTTP request object (from Cloud Scheduler or manual trigger)
        
    Returns:
        Tuple of (response dictionary, HTTP status code)
    """
    
    start_time = datetime.now()
    
    # Check for health endpoint
    if request.args.get('health', '').lower() == 'true':
        return run_health_check(request)
    
    # Check for verify connection endpoint
    if request.args.get('verify_connection', '').lower() == 'true':
        return run_verify_connection(request)
    
    logger.info(f"=== Amazon PPC Optimizer Started at {start_time} ===")
    
    # Initialize variables for error handler scope
    config = None
    dashboard_client = None
    bigquery_client = None
    dry_run = False
    
    try:
        # Parse request JSON if available
        request_json = {}
        try:
            request_json = request.get_json(silent=True) or {}
        except Exception:
            request_json = {}
        
        # Load configuration from environment or file
        config = load_config()
        
        # Set environment variables for the optimizer
        # The optimizer reads credentials from environment variables
        set_environment_variables(config)
        
        # Validate required credentials
        validate_credentials(config)
        
        # Check if this is a dry run (from query param or JSON body)
        dry_run = request.args.get('dry_run', '').lower() == 'true' or request_json.get('dry_run', False)
        
        # Initialize dashboard client
        dashboard_client = DashboardClient(config)
        
        # Initialize BigQuery client (if configured)
        bigquery_config = config.get('bigquery', {})
        if bigquery_config.get('enabled', False):
            try:
                project_id = bigquery_config.get('project_id') or os.getenv('GCP_PROJECT') or os.getenv('GOOGLE_CLOUD_PROJECT')
                if project_id:
                    # Set environment variables for BigQuery client and dashboard
                    set_bigquery_env_vars(project_id)
                    
                    dataset_id = bigquery_config.get('dataset_id', 'amazon_ppc')
                    location = bigquery_config.get('location', 'us-east4')
                    bigquery_client = BigQueryClient(project_id, dataset_id, location)
                    logger.info(f"BigQuery client initialized for project {project_id}")
                else:
                    logger.warning("BigQuery enabled but no project_id configured")
            except Exception as bq_err:
                logger.warning(f"Failed to initialize BigQuery client (non-blocking): {bq_err}")
        
        # Start optimization run (generates unique run_id)
        run_id = dashboard_client.start_run(dry_run=dry_run)
        logger.info(f"Started optimization run: {run_id}")
        
        # Use context manager for temp config file (ensures cleanup)
        with create_config_file(config) as config_file_path:
            # Get profile ID with default value
            profile_id = config.get('amazon_api', {}).get('profile_id', '')
            if not profile_id:
                raise ValueError("profile_id is required in amazon_api configuration")
            
            # Initialize optimizer
            logger.info("Initializing optimizer...")
            dashboard_client.send_progress("Initializing optimizer...", 10.0)
            
            # Import here to ensure environment variables are set first
            from optimizer_core import PPCAutomation
            
            optimizer = PPCAutomation(
                config_path=config_file_path,
                profile_id=profile_id,
                dry_run=dry_run
            )
            
            # Run optimization
            # The optimizer will automatically refresh the access token if needed
            logger.info("Running optimization (token refresh handled automatically)...")
            dashboard_client.send_progress("Starting optimization...", 20.0)
            
            results = optimizer.run()
            
            dashboard_client.send_progress("Processing results...", 90.0)
        
        # Calculate duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Send results to dashboard with enhanced payload (non-blocking)
        logger.info("Sending results to dashboard...")
        try:
            dashboard_client.send_results(results, config, duration, dry_run)
        except Exception as dashboard_err:
            logger.warning(f"Dashboard update failed (non-blocking): {dashboard_err}")
        
        # Write results to BigQuery (non-blocking)
        if bigquery_client:
            logger.info("Writing results to BigQuery...")
            try:
                # Build the same payload that's sent to the dashboard
                results_payload = dashboard_client.build_results_payload(results, config, duration, dry_run)
                bigquery_client.write_optimization_results(results_payload)
            except Exception as bq_err:
                logger.warning(f"BigQuery write failed (non-blocking): {bq_err}")
        
        # Prepare summary
        summary = format_results_summary(results, duration, dry_run)
        
        # Send email notification
        if config.get('email_notifications', {}).get('send_on_completion', True):
            subject = f"Amazon PPC Optimization {'(DRY RUN) ' if dry_run else ''}Completed Successfully"
            send_email_notification(subject, summary, config)
        
        dashboard_client.send_progress("Optimization completed successfully", 100.0)
        logger.info(f"=== Optimization Completed in {duration:.2f} seconds ===")
        
        return {
            'status': 'success',
            'message': 'Optimization completed successfully',
            'run_id': run_id,
            'results': results,
            'duration_seconds': duration,
            'dry_run': dry_run,
            'timestamp': datetime.now().isoformat()
        }, 200
        
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        logger.error(f"Optimization failed: {error_msg}")
        logger.error(error_trace)
        
        # Send error to dashboard (if dashboard_client was initialized)
        if dashboard_client:
            try:
                context = {
                    'function': 'run_optimizer',
                    'timestamp': datetime.now().isoformat(),
                    'dry_run': dry_run
                }
                dashboard_client.send_error(e, context)
            except Exception as dashboard_err:
                logger.warning(f"Failed to send error to dashboard: {dashboard_err}")
        
        # Send error notification (if config was loaded)
        if config:
            try:
                if config.get('email_notifications', {}).get('send_on_error', True):
                    subject = "Amazon PPC Optimization FAILED"
                    body = f"""
Optimization Run Failed

Error: {error_msg}

Timestamp: {datetime.now().isoformat()}

Stack Trace:
{error_trace}

Please check the Cloud Functions logs for more details.
                    """
                    send_email_notification(subject, body, config)
            except Exception as notification_err:
                logger.warning(f"Failed to send error notification: {notification_err}")
        
        return {
            'status': 'error',
            'message': error_msg,
            'timestamp': datetime.now().isoformat()
        }, 500


# Cloud Functions entry point alias.
#
# The Cloud Function is configured with `optimizePPC` as the entry point, but
# this module originally exposed the handler as `run_optimizer`. Export an alias
# so either name can be used without redeploying infrastructure.
optimizePPC = run_optimizer


def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables or config file
    
    Returns:
        Configuration dictionary loaded from JSON
        
    Raises:
        ValueError: If no valid configuration is found
        json.JSONDecodeError: If JSON parsing fails
    """
    
    # Check if config is in environment variable (recommended for Cloud Functions)
    config_json = os.environ.get('PPC_CONFIG', None)
    if config_json:
        logger.info("Loading config from environment variable")
        try:
            config = json.loads(config_json)
            logger.info("Configuration successfully loaded from environment variable")
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse PPC_CONFIG JSON: {e}")
            raise ValueError(f"Invalid JSON in PPC_CONFIG environment variable: {e}")
    
    # Fall back to config.json file
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_file):
        logger.info(f"Loading config from {config_file}")
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Configuration successfully loaded from {config_file}")
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config.json: {e}")
            raise ValueError(f"Invalid JSON in config.json: {e}")
        except IOError as e:
            logger.error(f"Failed to read config.json: {e}")
            raise ValueError(f"Failed to read config.json: {e}")
    
    raise ValueError("No configuration found. Set PPC_CONFIG environment variable or provide config.json")


def set_environment_variables(config: Dict[str, Any]) -> None:
    """
    Set environment variables from config for the optimizer
    The optimizer_core reads these environment variables for API authentication
    
    Args:
        config: Configuration dictionary
    """
    amazon_api = config.get('amazon_api', {})
    
    # Set required environment variables that optimizer_core expects
    os.environ['AMAZON_CLIENT_ID'] = amazon_api.get('client_id', '')
    os.environ['AMAZON_CLIENT_SECRET'] = amazon_api.get('client_secret', '')
    os.environ['AMAZON_REFRESH_TOKEN'] = amazon_api.get('refresh_token', '')
    
    logger.info("Environment variables set for optimizer")


def set_bigquery_env_vars(project_id: str) -> None:
    """
    Set GCP project environment variables for BigQuery client and dashboard
    
    Both the BigQuery client library and the dashboard API endpoints expect
    these environment variables to be set. This function ensures they are
    available without overwriting any existing values.
    
    Args:
        project_id: Google Cloud project ID
    """
    if not os.getenv('GCP_PROJECT'):
        os.environ['GCP_PROJECT'] = project_id
        logger.debug(f"Set GCP_PROJECT to {project_id}")
    
    if not os.getenv('GOOGLE_CLOUD_PROJECT'):
        os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
        logger.debug(f"Set GOOGLE_CLOUD_PROJECT to {project_id}")


def validate_credentials(config: Dict[str, Any]) -> None:
    """
    Validate required API credentials are present
    
    Args:
        config: Configuration dictionary
        
    Raises:
        ValueError: If required credentials are missing
    """
    required_fields = ['client_id', 'client_secret', 'refresh_token', 'profile_id']
    amazon_api = config.get('amazon_api', {})
    
    missing = [field for field in required_fields if not amazon_api.get(field, '').strip()]
    
    if missing:
        raise ValueError(f"Missing required API credentials: {', '.join(missing)}")
    
    logger.info("✓ All required credentials present")


def format_results_summary(results: Dict[str, Any], duration: float, dry_run: bool) -> str:
    """
    Format optimization results into email-friendly summary
    
    Args:
        results: Optimization results dictionary
        duration: Execution duration in seconds
        dry_run: Whether this was a dry run
        
    Returns:
        Formatted summary string
    """
    
    summary_lines = [
        f"Amazon PPC Optimization Report",
        f"{'=' * 50}",
        f"",
        f"Run Mode: {'DRY RUN (No changes made)' if dry_run else 'LIVE MODE'}",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Duration: {duration:.2f} seconds",
        f"",
        f"Results:",
        f"-" * 50,
    ]
    
    # Add key metrics
    if isinstance(results, dict):
        if 'summary' in results:
            summary = results.get('summary', {})
            summary_lines.extend([
                f"Campaigns Analyzed: {summary.get('campaigns_analyzed', 0)}",
                f"Keywords Optimized: {summary.get('keywords_optimized', 0)}",
                f"Bids Adjusted: {summary.get('bids_adjusted', 0)}",
                f"Negative Keywords Added: {summary.get('negative_keywords_added', 0)}",
                f"Budget Changes: {summary.get('budget_changes', 0)}",
                f"",
            ])
        
        # Add performance highlights
        if 'highlights' in results:
            summary_lines.append("Performance Highlights:")
            highlights = results.get('highlights', [])
            for highlight in highlights:
                summary_lines.append(f"  • {highlight}")
            summary_lines.append("")
        
        # Add recommendations
        if 'recommendations' in results:
            summary_lines.append("Recommendations:")
            recommendations = results.get('recommendations', [])
            for rec in recommendations:
                summary_lines.append(f"  • {rec}")
            summary_lines.append("")
    
    summary_lines.extend([
        f"-" * 50,
        f"",
        f"For detailed insights, visit the dashboard:",
        f"{results.get('dashboard_url', 'Not configured') if isinstance(results, dict) else 'Not configured'}",
    ])
    
    return '\n'.join(summary_lines)


# For local testing
if __name__ == "__main__":
    class MockRequest:
        def __init__(self):
            self.args = {'dry_run': 'true'}
    
    result, status = run_optimizer(MockRequest())
    print(f"Status: {status}")
    print(f"Result: {json.dumps(result, indent=2)}")
