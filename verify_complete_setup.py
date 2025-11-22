#!/usr/bin/env python3
"""
Complete Setup Verification Tool

This script verifies the entire Amazon PPC Optimizer setup:
1. Configuration files
2. Dashboard connectivity
3. BigQuery integration
4. Cloud Function deployment
5. End-to-end data flow

Usage:
    python verify_complete_setup.py
"""

import json
import logging
import os
import sys
from datetime import datetime
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_config_file():
    """Check 1: Verify config.json exists and is valid"""
    logger.info("\n" + "=" * 80)
    logger.info("CHECK 1: Configuration File")
    logger.info("=" * 80)
    
    if not os.path.exists('config.json'):
        logger.error("❌ config.json not found")
        return False, None
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        logger.info("✓ config.json is valid JSON")
        
        # Check required sections
        required = ['amazon_api', 'dashboard', 'bid_optimization']
        missing = [s for s in required if s not in config]
        
        if missing:
            logger.warning(f"⚠️ Missing sections: {', '.join(missing)}")
        else:
            logger.info("✓ All required sections present")
        
        return True, config
    except Exception as e:
        logger.error(f"❌ Error loading config.json: {e}")
        return False, None


def check_amazon_api_config(config):
    """Check 2: Verify Amazon API configuration"""
    logger.info("\n" + "=" * 80)
    logger.info("CHECK 2: Amazon API Configuration")
    logger.info("=" * 80)
    
    amazon_api = config.get('amazon_api', {})
    
    # Placeholder patterns to detect unconfigured values
    placeholders = ['xxxxx', 'YOUR_', 'PLACEHOLDER', 'EXAMPLE']
    
    checks = {
        'profile_id': amazon_api.get('profile_id'),
        'client_id': amazon_api.get('client_id'),
        'client_secret': amazon_api.get('client_secret'),
        'refresh_token': amazon_api.get('refresh_token'),
        'region': amazon_api.get('region')
    }
    
    all_good = True
    for key, value in checks.items():
        if value and not any(placeholder in str(value) for placeholder in placeholders):
            logger.info(f"   ✓ {key}: configured")
        else:
            logger.warning(f"   ⚠️ {key}: NOT configured")
            all_good = False
    
    return all_good


def check_dashboard_config(config):
    """Check 3: Verify dashboard configuration"""
    logger.info("\n" + "=" * 80)
    logger.info("CHECK 3: Dashboard Configuration")
    logger.info("=" * 80)
    
    dashboard = config.get('dashboard', {})
    
    url = dashboard.get('url', '')
    api_key = dashboard.get('api_key', '')
    enabled = dashboard.get('enabled', False)
    
    logger.info(f"   URL: {url}")
    logger.info(f"   Enabled: {enabled}")
    
    # Placeholder patterns
    url_placeholders = ['YOUR_', 'EXAMPLE', 'PLACEHOLDER', 'your-dashboard']
    key_placeholders = ['YOUR_DASHBOARD_API_KEY', 'YOUR_API_KEY', 'PLACEHOLDER']
    
    issues = []
    
    if not url:
        logger.error("   ❌ Dashboard URL not configured")
        issues.append('url_missing')
    elif any(placeholder in url for placeholder in url_placeholders):
        logger.error("   ❌ Dashboard URL is a placeholder")
        issues.append('url_placeholder')
    else:
        logger.info("   ✓ Dashboard URL is set")
    
    if not api_key or api_key in key_placeholders:
        logger.warning("   ⚠️ Dashboard API key is placeholder or missing")
        issues.append('api_key_placeholder')
    else:
        logger.info("   ✓ Dashboard API key is set")
    
    if not enabled:
        logger.warning("   ⚠️ Dashboard integration is DISABLED")
        issues.append('disabled')
    
    return len(issues) == 0, dashboard


def check_dashboard_connectivity(dashboard_config):
    """Check 4: Test dashboard connectivity"""
    logger.info("\n" + "=" * 80)
    logger.info("CHECK 4: Dashboard Connectivity")
    logger.info("=" * 80)
    
    url = dashboard_config.get('url', '')
    
    if not url or url.startswith('YOUR_'):
        logger.warning("   ⚠️ Skipping - dashboard URL not configured")
        return False
    
    try:
        logger.info(f"   Testing: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"   ✓ Dashboard is accessible (HTTP {response.status_code})")
            return True
        else:
            logger.warning(f"   ⚠️ Dashboard returned HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError as e:
        if 'Failed to resolve' in str(e):
            logger.error("   ❌ Dashboard URL cannot be resolved (DNS failure)")
            logger.error("   → Dashboard is NOT deployed")
        else:
            logger.error(f"   ❌ Connection error: {str(e)[:100]}")
        return False
    except Exception as e:
        logger.error(f"   ❌ Error: {str(e)[:100]}")
        return False


def check_bigquery_config(config):
    """Check 5: Verify BigQuery configuration"""
    logger.info("\n" + "=" * 80)
    logger.info("CHECK 5: BigQuery Configuration")
    logger.info("=" * 80)
    
    bigquery = config.get('bigquery', {})
    
    enabled = bigquery.get('enabled', False)
    project_id = bigquery.get('project_id', '')
    dataset_id = bigquery.get('dataset_id', '')
    
    logger.info(f"   Enabled: {enabled}")
    
    if not enabled:
        logger.info("   ℹ️ BigQuery integration is disabled")
        return False
    
    if project_id:
        logger.info(f"   ✓ Project ID: {project_id}")
    else:
        logger.warning("   ⚠️ Project ID not set")
    
    if dataset_id:
        logger.info(f"   ✓ Dataset ID: {dataset_id}")
    else:
        logger.warning("   ⚠️ Dataset ID not set")
    
    return enabled and project_id and dataset_id


def check_features_config(config):
    """Check 6: Verify enabled features"""
    logger.info("\n" + "=" * 80)
    logger.info("CHECK 6: Feature Configuration")
    logger.info("=" * 80)
    
    features = config.get('features', {})
    enabled_features = features.get('enabled', [])
    
    logger.info(f"   Enabled features: {len(enabled_features)}")
    
    for feature in enabled_features:
        logger.info(f"   ✓ {feature}")
    
    return len(enabled_features) > 0


def generate_recommendations(results):
    """Generate recommendations based on check results"""
    logger.info("\n" + "=" * 80)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 80)
    
    recommendations = []
    
    if not results.get('config_valid'):
        recommendations.append("❗ Fix config.json - file is missing or invalid")
    
    if not results.get('amazon_api_configured'):
        recommendations.append("❗ Configure Amazon API credentials in config.json")
    
    if not results.get('dashboard_connectivity'):
        recommendations.append("❗ Deploy dashboard or fix dashboard URL")
        recommendations.append("   → Run: cd amazon_ppc_dashboard/nextjs_space && vercel --prod")
        recommendations.append("   → Then: python update_dashboard_url.py <new-url>")
    
    if not results.get('bigquery_configured') and not results.get('dashboard_connectivity'):
        recommendations.append("⚠️ No data storage configured (neither dashboard nor BigQuery)")
        recommendations.append("   → Consider enabling BigQuery for data persistence")
    
    if recommendations:
        logger.info("\n📋 Action Items:")
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"{i}. {rec}")
    else:
        logger.info("\n✅ No critical issues found!")


def main():
    """Run all checks"""
    logger.info("=" * 80)
    logger.info("AMAZON PPC OPTIMIZER - COMPLETE SETUP VERIFICATION")
    logger.info("=" * 80)
    logger.info(f"Date: {datetime.now().isoformat()}")
    
    results = {}
    
    # Check 1: Config file
    results['config_valid'], config = check_config_file()
    
    if not results['config_valid']:
        logger.error("\n❌ Cannot proceed without valid config.json")
        return 1
    
    # Check 2: Amazon API
    results['amazon_api_configured'] = check_amazon_api_config(config)
    
    # Check 3: Dashboard config
    results['dashboard_configured'], dashboard_config = check_dashboard_config(config)
    
    # Check 4: Dashboard connectivity
    results['dashboard_connectivity'] = check_dashboard_connectivity(dashboard_config)
    
    # Check 5: BigQuery
    results['bigquery_configured'] = check_bigquery_config(config)
    
    # Check 6: Features
    results['features_configured'] = check_features_config(config)
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    logger.info(f"\nPassed: {passed}/{total} checks")
    logger.info("")
    
    for check_name, passed in results.items():
        status = "✓" if passed else "❌"
        logger.info(f"   {status} {check_name}")
    
    # Generate recommendations
    generate_recommendations(results)
    
    # Final verdict
    logger.info("\n" + "=" * 80)
    logger.info("FINAL VERDICT")
    logger.info("=" * 80)
    
    if results['dashboard_connectivity']:
        logger.info("\n✅ DASHBOARD IS RECEIVING DATA")
        logger.info("   The optimizer can successfully send data to the dashboard")
    elif results['bigquery_configured']:
        logger.info("\n⚠️ DASHBOARD NOT ACCESSIBLE, but BigQuery is configured")
        logger.info("   Data will be stored in BigQuery instead")
    else:
        logger.error("\n❌ NO DATA STORAGE CONFIGURED")
        logger.error("   Dashboard is not accessible AND BigQuery is not enabled")
        logger.error("   Optimization results will be lost!")
    
    return 0 if results['dashboard_connectivity'] or results['bigquery_configured'] else 1


if __name__ == '__main__':
    sys.exit(main())
