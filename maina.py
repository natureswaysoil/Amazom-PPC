"""
Cloud Function Entry Point for Amazon PPC Optimizer

This file provides the entry point for Google Cloud Functions/Cloud Run.
It wraps the core optimizer_core.py functionality with proper request handling.
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime

# Import the core optimizer
from optimizer_core import PPCAutomation, Config, AmazonAdsAPI

# Set up logging
logger = logging.getLogger(__name__)


def validate_credentials(config):
    """
    Validate that all required credentials are present
    Raises ValueError with helpful message if any are missing
    """
    required_creds = {
        'client_id': os.getenv('AMAZON_CLIENT_ID') or config.get('amazon_api.client_id'),
        'client_secret': os.getenv('AMAZON_CLIENT_SECRET') or config.get('amazon_api.client_secret'),
        'refresh_token': os.getenv('AMAZON_REFRESH_TOKEN') or config.get('amazon_api.refresh_token'),
        'profile_id': os.getenv('AMAZON_PROFILE_ID') or os.getenv('PPC_PROFILE_ID') or config.get('amazon_api.profile_id')
    }
    
    missing = [key for key, value in required_creds.items() if not value]
    
    if missing:
        error_msg = f"Missing required API credentials: {', '.join(missing)}"
        logger.error(error_msg)
        logger.error("Set these as environment variables:")
        logger.error("  AMAZON_CLIENT_ID")
        logger.error("  AMAZON_CLIENT_SECRET")
        logger.error("  AMAZON_REFRESH_TOKEN")
        logger.error("  AMAZON_PROFILE_ID (or PPC_PROFILE_ID)")
        raise ValueError(error_msg)
    
    logger.info("✅ All required credentials found")
    return required_creds


def run_optimization(request):
    """
    Cloud Function entry point (name expected by Cloud Run configuration)
    This is the main entry point that Cloud Run will call.
    """
    return run_optimizer(request)


def run_optimizer(request):
    """
    Cloud Function entry point for Google Cloud Functions/Cloud Run
    
    Expected environment variables:
      - AMAZON_CLIENT_ID
      - AMAZON_CLIENT_SECRET
      - AMAZON_REFRESH_TOKEN
      - AMAZON_PROFILE_ID or PPC_PROFILE_ID
    
    Optional request parameters:
      - dry_run: boolean
      - features: list of feature names
      - verify_connection: boolean
      - health: boolean (lightweight health check)
    """
    try:
        # Parse request
        request_json = request.get_json(silent=True) or {}
        request_args = request.args
        
        logger.info("=" * 80)
        logger.info("PPC Optimizer Cloud Function invoked")
        logger.info(f"Request args: {dict(request_args)}")
        logger.info(f"Request JSON: {request_json}")
        
        # Health check endpoint (lightweight, no optimization)
        if request_args.get('health') == 'true':
            logger.info("Health check requested")
            return {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'Amazon PPC Optimizer',
                'version': '2.0.0'
            }, 200
        
        # Load configuration
        config_path = os.getenv('PPC_CONFIG_PATH', './config.json')
        logger.info(f"Loading config from: {config_path}")
        
        # Try to load config file
        try:
            if os.path.exists(config_path):
                config = Config(config_path)
                logger.info(f"✅ Config loaded from {config_path}")
            else:
                logger.warning(f"Config file not found at {config_path}")
                raise FileNotFoundError(f"Config file not found: {config_path}")
        except Exception as e:
            logger.warning(f"Could not load config file: {e}")
            logger.info("Creating minimal config from environment variables")
            
            # Create minimal config dict
            class MinimalConfig:
                def __init__(self):
                    self.data = {
                        'amazon_api': {
                            'region': os.getenv('AMAZON_REGION', 'NA')
                        },
                        'features': {
                            'enabled': ['bid_optimization']
                        },
                        'bid_optimization': {
                            'enabled': True,
                            'lookback_days': 14,
                            'min_clicks': 25,
                            'min_spend': 5.0,
                            'high_acos': 0.60,
                            'low_acos': 0.25,
                            'up_pct': 0.15,
                            'down_pct': 0.20,
                            'min_bid': 0.25,
                            'max_bid': 5.0
                        }
                    }
                
                def get(self, key, default=None):
                    keys = key.split('.')
                    value = self.data
                    for k in keys:
                        if isinstance(value, dict):
                            value = value.get(k)
                            if value is None:
                                return default
                        else:
                            return default
                    return value if value is not None else default
            
            config = MinimalConfig()
            logger.info("✅ Using minimal config with environment variables")
        
        # Validate credentials
        try:
            creds = validate_credentials(config)
            profile_id = creds['profile_id']
            logger.info(f"Profile ID: {profile_id}")
        except ValueError as e:
            logger.error(f"❌ Credential validation failed: {e}")
            return {
                'error': 'Missing required credentials',
                'details': str(e),
                'status': 'failed',
                'timestamp': datetime.now().isoformat()
            }, 400
        
        # Get parameters from request
        dry_run = request_json.get('dry_run', False) or request_args.get('dry_run') == 'true'
        features_param = request_json.get('features') or request_args.get('features', '')
        features = features_param.split(',') if isinstance(features_param, str) and features_param else features_param
        
        logger.info(f"Dry run: {dry_run}")
        logger.info(f"Features: {features or 'all enabled'}")
        
        # Verify connection check
        if request_args.get('verify_connection') == 'true':
            logger.info("Verify connection requested")
            verify_sample_size = int(request_args.get('verify_sample_size', 5))
            region = os.getenv('AMAZON_REGION', config.get('amazon_api.region', 'NA'))
            
            api = AmazonAdsAPI(profile_id, region)
            verification = api.verify_connection(verify_sample_size)
            
            return {
                'verification': verification,
                'timestamp': datetime.now().isoformat()
            }, 200 if verification.get('success') else 500
        
        # Run optimization
        logger.info("=" * 80)
        logger.info("Starting PPC optimization")
        logger.info("=" * 80)
        
        automation = PPCAutomation(config_path, profile_id, dry_run)
        results = automation.run(features)
        
        logger.info("=" * 80)
        logger.info("✅ Optimization completed successfully")
        logger.info("=" * 80)
        
        return {
            'status': 'success',
            'results': results,
            'profile_id': profile_id,
            'dry_run': dry_run,
            'timestamp': datetime.now().isoformat()
        }, 200
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Optimization failed: {e}")
        logger.error("=" * 80)
        logger.error(traceback.format_exc())
        
        return {
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }, 500


# For local testing
if __name__ == '__main__':
    print("This file is meant to be deployed as a Cloud Function.")
    print("For local testing, use: python optimizer_core.py --config config.json --profile-id YOUR_PROFILE_ID")
