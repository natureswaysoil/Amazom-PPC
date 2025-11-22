#!/usr/bin/env python3
"""
Update Dashboard URL Configuration

This script updates the dashboard URL in config.json and verifies connectivity.

Usage:
    python update_dashboard_url.py <dashboard_url> [api_key]
    
Example:
    python update_dashboard_url.py https://my-dashboard.vercel.app
    python update_dashboard_url.py https://my-dashboard.vercel.app my_api_key_123
"""

import json
import logging
import sys
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_url(url):
    """Validate that the URL is accessible"""
    try:
        logger.info(f"Testing connectivity to: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✓ URL is accessible (HTTP {response.status_code})")
            return True
        else:
            logger.warning(f"⚠️ URL returned HTTP {response.status_code}")
            logger.info("   Proceeding anyway - this might be okay if homepage requires auth")
            return True
    except requests.exceptions.ConnectionError as e:
        if 'Failed to resolve' in str(e) or 'Name or service not known' in str(e):
            logger.error(f"❌ URL cannot be resolved: {url}")
            logger.error("   DNS lookup failed - check that the URL is correct")
            return False
        logger.warning(f"⚠️ Connection error: {str(e)[:100]}")
        logger.info("   Proceeding anyway - might be network/firewall issue")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Error testing URL: {str(e)[:100]}")
        logger.info("   Proceeding anyway - URL might still work in production")
        return True


def update_config(dashboard_url, api_key=None):
    """Update config.json with new dashboard URL"""
    config_path = 'config.json'
    
    # Load current config
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"✓ Loaded config from {config_path}")
    except Exception as e:
        logger.error(f"❌ Failed to load config.json: {e}")
        return False
    
    # Update dashboard configuration
    if 'dashboard' not in config:
        config['dashboard'] = {}
    
    old_url = config['dashboard'].get('url', 'not set')
    logger.info(f"\nUpdating dashboard configuration:")
    logger.info(f"   Old URL: {old_url}")
    logger.info(f"   New URL: {dashboard_url}")
    
    config['dashboard']['url'] = dashboard_url
    
    if api_key:
        logger.info(f"   API Key: {'*' * 20} (set)")
        config['dashboard']['api_key'] = api_key
    else:
        current_key = config['dashboard'].get('api_key', '')
        if current_key and current_key != 'YOUR_DASHBOARD_API_KEY':
            logger.info(f"   API Key: (keeping existing)")
        else:
            logger.warning(f"   API Key: NOT SET (consider adding one)")
    
    # Ensure dashboard is enabled
    config['dashboard']['enabled'] = True
    config['dashboard']['send_real_time_updates'] = True
    
    # Save updated config
    try:
        # Create backup
        backup_path = f'config.json.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        with open(backup_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"✓ Backup saved to: {backup_path}")
        
        # Save new config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"✓ Updated config saved to: {config_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save config: {e}")
        return False


def print_next_steps(dashboard_url, api_key):
    """Print instructions for next steps"""
    logger.info("\n" + "=" * 80)
    logger.info("NEXT STEPS")
    logger.info("=" * 80)
    
    logger.info("\n1. Test the dashboard connection:")
    logger.info(f"   python test_dashboard_connection.py")
    
    logger.info("\n2. Update Cloud Function environment variables:")
    logger.info(f"   gcloud functions deploy amazon-ppc-optimizer \\")
    logger.info(f"     --update-env-vars DASHBOARD_URL={dashboard_url}")
    
    if api_key:
        logger.info(f"     --update-env-vars DASHBOARD_API_KEY={api_key}")
    
    logger.info("\n3. Or update via Secret Manager (recommended for production):")
    logger.info(f"   echo -n '{dashboard_url}' | \\")
    logger.info(f"     gcloud secrets create dashboard-url --data-file=-")
    
    if api_key:
        logger.info(f"\n   echo -n '{api_key}' | \\")
        logger.info(f"     gcloud secrets create dashboard-api-key --data-file=-")
    
    logger.info("\n4. Test the optimizer:")
    logger.info(f"   curl -X POST 'YOUR-CLOUD-FUNCTION-URL?dry_run=true'")
    
    logger.info("\n5. Check logs for dashboard communication:")
    logger.info(f"   gcloud functions logs read amazon-ppc-optimizer --limit=50 | grep Dashboard")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        logger.error("Usage: python update_dashboard_url.py <dashboard_url> [api_key]")
        logger.error("\nExample:")
        logger.error("  python update_dashboard_url.py https://my-dashboard.vercel.app")
        logger.error("  python update_dashboard_url.py https://my-dashboard.vercel.app my_api_key_123")
        sys.exit(1)
    
    dashboard_url = sys.argv[1].strip()
    api_key = sys.argv[2].strip() if len(sys.argv) > 2 else None
    
    logger.info("=" * 80)
    logger.info("DASHBOARD URL UPDATE TOOL")
    logger.info("=" * 80)
    
    # Validate URL format
    if not dashboard_url.startswith('http://') and not dashboard_url.startswith('https://'):
        logger.error(f"❌ Invalid URL format: {dashboard_url}")
        logger.error("   URL must start with http:// or https://")
        sys.exit(1)
    
    # Test connectivity
    if not validate_url(dashboard_url):
        logger.error("\n❌ URL validation failed")
        response = input("\nDo you want to proceed anyway? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            logger.info("Aborted by user")
            sys.exit(1)
    
    # Update config
    if update_config(dashboard_url, api_key):
        logger.info("\n✓ Configuration updated successfully!")
        print_next_steps(dashboard_url, api_key)
        return 0
    else:
        logger.error("\n❌ Failed to update configuration")
        return 1


if __name__ == '__main__':
    sys.exit(main())
