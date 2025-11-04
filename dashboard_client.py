"""
Dashboard Client Module
========================

Handles all communication with the PPC Dashboard including:
- Real-time optimization results
- Progress updates during optimization
- Error reporting
- Health checks
- Retry logic with exponential backoff
- Secure authentication

Author: Nature's Way Soil
Version: 1.0.0
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import requests
from functools import wraps

logger = logging.getLogger(__name__)


def retry_with_backoff(max_attempts=3, initial_delay=2, max_delay=10):
    """
    Decorator for retry logic with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {str(e)}")
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay = min(delay * 2, max_delay)
                    else:
                        logger.error(f"All {max_attempts} attempts failed: {str(e)}")
            
            raise last_exception
        return wrapper
    return decorator


class DashboardClient:
    """
    Client for communicating with the PPC Dashboard
    
    Features:
    - Sends optimization results with enhanced payload
    - Real-time progress updates
    - Error reporting
    - Health checks
    - Retry logic with exponential backoff
    - API key authentication
    """
    
    def __init__(self, config: Dict):
        """
        Initialize dashboard client
        
        Args:
            config: Configuration dictionary containing dashboard settings
        """
        dashboard_config = config.get('dashboard', {})
        
        self.url = dashboard_config.get('url', '')
        self.api_key = dashboard_config.get('api_key', '')
        self.enabled = dashboard_config.get('enabled', True)
        self.send_real_time_updates = dashboard_config.get('send_real_time_updates', True)
        self.timeout = dashboard_config.get('timeout', 30)
        
        self.session = requests.Session()
        self.current_run_id = None
        self.profile_id = config.get('amazon_api', {}).get('profile_id', '')
        
        if not self.url:
            logger.warning("Dashboard URL not configured")
            self.enabled = False
        
        if self.enabled and not self.api_key:
            logger.warning("Dashboard API key not configured - requests may be rejected")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for dashboard API requests"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'NWS-PPC-Optimizer/2.0'
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        if self.profile_id:
            headers['X-Profile-ID'] = str(self.profile_id)
        
        return headers
    
    def _make_request(self, endpoint: str, payload: Dict, method: str = 'POST') -> Optional[Dict]:
        """
        Make HTTP request to dashboard with error handling
        
        Args:
            endpoint: API endpoint (e.g., '/api/optimization-results')
            payload: Request payload
            method: HTTP method (default: POST)
            
        Returns:
            Response data as dictionary or None on failure
        """
        if not self.enabled:
            logger.debug("Dashboard client disabled, skipping request")
            return None
        
        try:
            url = f"{self.url}{endpoint}"
            
            response = self.session.request(
                method=method,
                url=url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            # Log response details
            logger.info(f"Dashboard {method} {endpoint}: HTTP {response.status_code}")
            
            if response.status_code == 200:
                return response.json() if response.content else {}
            elif response.status_code == 429:
                logger.warning(f"Dashboard rate limit exceeded: {response.text}")
                retry_after = response.headers.get('Retry-After', '60')
                logger.info(f"Retry after {retry_after} seconds")
            else:
                logger.warning(f"Dashboard returned {response.status_code}: {response.text}")
            
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"Dashboard request timeout after {self.timeout}s")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Dashboard connection error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Dashboard request failed: {str(e)}")
            return None
    
    def start_run(self, dry_run: bool = False) -> str:
        """
        Start a new optimization run and generate unique run ID
        
        Args:
            dry_run: Whether this is a dry run
            
        Returns:
            Unique run ID
        """
        self.current_run_id = str(uuid.uuid4())
        
        if self.send_real_time_updates:
            payload = {
                'timestamp': datetime.now().isoformat(),
                'run_id': self.current_run_id,
                'status': 'started',
                'profile_id': self.profile_id,
                'dry_run': dry_run
            }
            self._make_request('/api/optimization-status', payload)
        
        return self.current_run_id
    
    @retry_with_backoff(max_attempts=3, initial_delay=2, max_delay=10)
    def send_results(self, results: Dict, config: Dict, duration_seconds: float, 
                    dry_run: bool = False) -> bool:
        """
        Send optimization results to dashboard with enhanced payload
        
        Args:
            results: Optimization results from PPCAutomation.run()
            config: Configuration dictionary
            duration_seconds: Duration of optimization run
            dry_run: Whether this was a dry run
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.info("Dashboard updates disabled")
            return False
        
        try:
            # Build enhanced payload
            payload = self.build_results_payload(results, config, duration_seconds, dry_run)
            
            # Send to dashboard
            response = self._make_request('/api/optimization-results', payload)
            
            if response is not None:
                logger.info("Dashboard updated successfully with optimization results")
                self._handle_dashboard_response(response)
                return True
            else:
                logger.warning("Dashboard update failed")
                return False
                
        except Exception as e:
            logger.error(f"Error sending results to dashboard: {str(e)}")
            return False
    
    def send_progress(self, message: str, percent_complete: float = 0.0) -> bool:
        """
        Send real-time progress update to dashboard
        
        Args:
            message: Progress message (e.g., "Analyzing keywords")
            percent_complete: Percentage complete (0-100)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.send_real_time_updates:
            return False
        
        payload = {
            'timestamp': datetime.now().isoformat(),
            'run_id': self.current_run_id,
            'status': 'running',
            'message': message,
            'percent_complete': percent_complete,
            'profile_id': self.profile_id
        }
        
        response = self._make_request('/api/optimization-status', payload)
        return response is not None
    
    def send_error(self, error: Exception, context: Dict = None) -> bool:
        """
        Send error details to dashboard
        
        Args:
            error: Exception that occurred
            context: Additional context about the error
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        import traceback
        
        payload = {
            'timestamp': datetime.now().isoformat(),
            'run_id': self.current_run_id,
            'status': 'failed',
            'profile_id': self.profile_id,
            'error': {
                'type': type(error).__name__,
                'message': str(error),
                'traceback': traceback.format_exc(),
                'context': context or {}
            }
        }
        
        response = self._make_request('/api/optimization-error', payload)
        
        if response is not None:
            logger.info("Error reported to dashboard")
            return True
        else:
            logger.warning("Failed to report error to dashboard")
            return False
    
    def health_check(self) -> bool:
        """
        Check dashboard connectivity
        
        Returns:
            True if dashboard is reachable, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            response = self._make_request('/api/health', {}, method='GET')
            return response is not None
        except Exception as e:
            logger.error(f"Dashboard health check failed: {str(e)}")
            return False
    
    def build_results_payload(self, results: Dict, config: Dict, 
                               duration_seconds: float, dry_run: bool) -> Dict:
        """
        Build enhanced payload with detailed metrics
        
        This is a public method that can be used by external modules like
        BigQueryClient to ensure consistent data formatting.
        
        Args:
            results: Raw results from optimization
            config: Configuration dictionary
            duration_seconds: Duration of optimization
            dry_run: Whether this was a dry run
            
        Returns:
            Enhanced payload dictionary
        """
        # Extract summary metrics from results
        summary = self._extract_summary(results)
        
        # Build campaigns list
        campaigns = self._extract_campaigns(results)
        
        # Extract top performers
        top_performers = self._extract_top_performers(results)
        
        # Collect errors and warnings
        errors = self._extract_errors(results)
        warnings = self._extract_warnings(results)
        
        payload = {
            'timestamp': datetime.now().isoformat(),
            'run_id': self.current_run_id or str(uuid.uuid4()),
            'status': 'success',
            'profile_id': self.profile_id,
            'dry_run': dry_run,
            'duration_seconds': duration_seconds,
            
            # Summary metrics
            'summary': summary,
            
            # Detailed results by feature
            'features': results,
            
            # Campaign-level breakdown
            'campaigns': campaigns,
            
            # Top performing keywords
            'top_performers': top_performers,
            
            # Errors and warnings
            'errors': errors,
            'warnings': warnings,
            
            # Configuration snapshot
            'config_snapshot': {
                'target_acos': config.get('bid_optimization', {}).get('target_acos'),
                'lookback_days': config.get('bid_optimization', {}).get('lookback_days'),
                'enabled_features': config.get('features', {}).get('enabled', [])
            }
        }
        
        return payload
    
    def _extract_summary(self, results: Dict) -> Dict:
        """Extract summary metrics from results"""
        summary = {
            'campaigns_analyzed': 0,
            'keywords_optimized': 0,
            'bids_increased': 0,
            'bids_decreased': 0,
            'negative_keywords_added': 0,
            'budget_changes': 0,
            'total_spend': 0.0,
            'total_sales': 0.0,
            'average_acos': 0.0
        }

        total_spend = 0.0
        total_sales = 0.0

        # Extract from bid_optimization
        if 'bid_optimization' in results:
            bid_data = results['bid_optimization']
            summary['bids_increased'] += bid_data.get('bids_increased', 0)
            summary['bids_decreased'] += bid_data.get('bids_decreased', 0)
            summary['keywords_optimized'] += bid_data.get(
                'keywords_optimized',
                bid_data.get('bids_increased', 0) + bid_data.get('bids_decreased', 0)
            )
            total_spend += bid_data.get('total_spend', 0.0)
            total_sales += bid_data.get('total_sales', 0.0)

        # Extract from negative_keywords
        if 'negative_keywords' in results:
            neg_data = results['negative_keywords']
            summary['negative_keywords_added'] += neg_data.get(
                'negative_keywords_added',
                neg_data.get('keywords_added', 0)
            )

        # Extract from campaign_management
        if 'campaign_management' in results:
            camp_data = results['campaign_management']
            campaigns_analyzed = camp_data.get('campaigns_analyzed')
            if campaigns_analyzed is None:
                campaigns_analyzed = (
                    camp_data.get('campaigns_paused', 0)
                    + camp_data.get('campaigns_activated', 0)
                    + camp_data.get('no_change', 0)
                )
            summary['campaigns_analyzed'] += campaigns_analyzed
            summary['budget_changes'] += camp_data.get(
                'budget_changes',
                camp_data.get('campaigns_paused', 0) + camp_data.get('campaigns_activated', 0)
            )
            total_spend += camp_data.get('total_spend', 0.0)
            total_sales += camp_data.get('total_sales', 0.0)
            # If module already calculated ACOS, prefer that value
            pass  # Removed logic that overwrites average_acos; always use aggregate calculation
        # Populate totals and derived averages
        summary['total_spend'] = total_spend
        summary['total_sales'] = total_sales
        if total_sales > 0:
            summary['average_acos'] = total_spend / total_sales

        return summary
    
    def _extract_campaigns(self, results: Dict) -> List[Dict]:
        """Extract campaign-level data from results"""
        campaigns = []
        
        # This would need to be populated with actual campaign data
        # from the results if available
        
        return campaigns
    
    def _extract_top_performers(self, results: Dict) -> List[Dict]:
        """Extract top performing keywords from results"""
        top_performers = []
        
        # This would need to be populated with actual keyword performance data
        # from the results if available
        
        return top_performers
    
    def _extract_errors(self, results: Dict) -> List[str]:
        """Extract error messages from results"""
        errors = []
        
        for feature, data in results.items():
            if isinstance(data, dict) and 'errors' in data:
                errors.extend(data['errors'])
        
        return errors
    
    def _extract_warnings(self, results: Dict) -> List[str]:
        """Extract warning messages from results"""
        warnings = []
        
        for feature, data in results.items():
            if isinstance(data, dict) and 'warnings' in data:
                warnings.extend(data['warnings'])
        
        return warnings
    
    def _handle_dashboard_response(self, response: Dict):
        """
        Handle response from dashboard API
        
        Dashboard may send commands or instructions in response
        
        Args:
            response: Response data from dashboard
        """
        if not response:
            return
        
        # Check for commands from dashboard
        if 'command' in response:
            command = response['command']
            logger.info(f"Dashboard sent command: {command}")
            
            # Handle different commands
            if command == 'pause':
                logger.warning("Dashboard requested pause - not implemented")
            elif command == 'increase_dry_run':
                logger.info("Dashboard suggested enabling dry run mode")
        
        # Log any messages from dashboard
        if 'message' in response:
            logger.info(f"Dashboard message: {response['message']}")
