#!/usr/bin/env python3
"""
Comprehensive Dashboard Issue Diagnosis

This script:
1. Checks all dashboard URLs mentioned in the codebase
2. Tests connectivity to each URL
3. Checks optimizer configuration
4. Provides actionable recommendations to fix the issue

Usage:
    python diagnose_dashboard_issue.py
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_dashboard_urls():
    """Find all dashboard URLs mentioned in the codebase"""
    logger.info("=" * 80)
    logger.info("STEP 1: Finding Dashboard URLs in Codebase")
    logger.info("=" * 80)
    
    urls = set()
    url_pattern = re.compile(r'https://[a-zA-Z0-9.-]+\.(?:vercel\.app|abacusai\.app)[^\s"\'<>]*')
    
    # Search in key files
    search_files = [
        'config.json',
        'README.md',
        'DEPLOYMENT_GUIDE.md',
        'COMPLETE_DEPLOYMENT_GUIDE.md',
        'DASHBOARD_INTEGRATION.md',
        'DEPLOY_NOW_COMPLETE.md'
    ]
    
    for filename in search_files:
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    content = f.read()
                    found_urls = url_pattern.findall(content)
                    for url in found_urls:
                        # Clean up URL (remove trailing punctuation)
                        url = url.rstrip('.,;:)')
                        if 'dashboard' in url.lower() or 'ppc' in url.lower():
                            urls.add(url)
            except Exception as e:
                logger.debug(f"Error reading {filename}: {e}")
    
    logger.info(f"Found {len(urls)} unique dashboard URLs:")
    for url in sorted(urls):
        logger.info(f"   - {url}")
    
    return sorted(urls)


def test_url_connectivity(url):
    """Test if a URL is accessible"""
    try:
        # Try HEAD request first (faster)
        response = requests.head(url, timeout=10, allow_redirects=True)
        return True, response.status_code, f"Accessible (HTTP {response.status_code})"
    except requests.exceptions.SSLError as e:
        return False, None, f"SSL Error: {str(e)[:100]}"
    except requests.exceptions.ConnectionError as e:
        if 'Name or service not known' in str(e) or 'Failed to resolve' in str(e):
            return False, None, "DNS Resolution Failed (URL not found)"
        return False, None, f"Connection Error: {str(e)[:100]}"
    except requests.exceptions.Timeout:
        return False, None, "Connection Timeout"
    except Exception as e:
        return False, None, f"Error: {str(e)[:100]}"


def test_all_urls(urls):
    """Test connectivity to all URLs"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Testing URL Connectivity")
    logger.info("=" * 80)
    
    results = {}
    for url in urls:
        logger.info(f"\nTesting: {url}")
        accessible, status_code, message = test_url_connectivity(url)
        results[url] = {
            'accessible': accessible,
            'status_code': status_code,
            'message': message
        }
        
        if accessible:
            logger.info(f"   ✓ {message}")
        else:
            logger.error(f"   ❌ {message}")
    
    return results


def check_config_json():
    """Check dashboard configuration in config.json"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Checking config.json")
    logger.info("=" * 80)
    
    if not os.path.exists('config.json'):
        logger.error("❌ config.json not found")
        return None
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        dashboard_config = config.get('dashboard', {})
        
        logger.info("\nDashboard Configuration:")
        logger.info(f"   URL: {dashboard_config.get('url', 'NOT SET')}")
        logger.info(f"   API Key: {'SET' if dashboard_config.get('api_key') and dashboard_config.get('api_key') != 'YOUR_DASHBOARD_API_KEY' else 'NOT SET'}")
        logger.info(f"   Enabled: {dashboard_config.get('enabled', False)}")
        logger.info(f"   Real-time Updates: {dashboard_config.get('send_real_time_updates', False)}")
        
        return dashboard_config
    except Exception as e:
        logger.error(f"❌ Error reading config.json: {e}")
        return None


def check_dashboard_deployment():
    """Check if dashboard code exists and can be deployed"""
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: Checking Dashboard Deployment Status")
    logger.info("=" * 80)
    
    dashboard_paths = [
        'amazon_ppc_dashboard/nextjs_space',
        'dashboard'
    ]
    
    found_dashboard = False
    for path in dashboard_paths:
        if os.path.exists(path):
            logger.info(f"✓ Dashboard code found at: {path}")
            found_dashboard = True
            
            # Check for key files
            if os.path.exists(os.path.join(path, 'package.json')):
                logger.info(f"   ✓ package.json found")
            if os.path.exists(os.path.join(path, 'vercel.json')):
                logger.info(f"   ✓ vercel.json found")
            if os.path.exists(os.path.join(path, 'next.config.js')):
                logger.info(f"   ✓ Next.js configuration found")
    
    if not found_dashboard:
        logger.warning("⚠️ No dashboard code found in repository")
    
    return found_dashboard


def analyze_results(url_results, dashboard_config):
    """Analyze results and provide recommendations"""
    logger.info("\n" + "=" * 80)
    logger.info("ANALYSIS & RECOMMENDATIONS")
    logger.info("=" * 80)
    
    accessible_urls = [url for url, result in url_results.items() if result['accessible']]
    inaccessible_urls = [url for url, result in url_results.items() if not result['accessible']]
    
    logger.info(f"\n✓ Accessible URLs: {len(accessible_urls)}")
    logger.info(f"❌ Inaccessible URLs: {len(inaccessible_urls)}")
    
    # Determine the issue
    if not accessible_urls:
        logger.error("\n🚨 CRITICAL ISSUE: No dashboard URLs are accessible!")
        logger.info("\nThis means:")
        logger.info("   1. The dashboard is NOT deployed or NOT running")
        logger.info("   2. The optimizer CANNOT send data to the dashboard")
        logger.info("   3. The dashboard CANNOT display live data")
        
        logger.info("\n📋 IMMEDIATE ACTION REQUIRED:")
        logger.info("\n1. Deploy the Dashboard to Vercel:")
        logger.info("   cd amazon_ppc_dashboard/nextjs_space")
        logger.info("   npm install")
        logger.info("   vercel --prod")
        logger.info("   # Or deploy via Vercel dashboard at https://vercel.com")
        
        logger.info("\n2. Update config.json with the new dashboard URL:")
        logger.info('   {')
        logger.info('     "dashboard": {')
        logger.info('       "url": "https://YOUR-NEW-VERCEL-URL.vercel.app",')
        logger.info('       "api_key": "YOUR_API_KEY",')
        logger.info('       "enabled": true')
        logger.info('     }')
        logger.info('   }')
        
        logger.info("\n3. Update Cloud Function environment variables:")
        logger.info("   gcloud functions deploy amazon-ppc-optimizer \\")
        logger.info("     --update-env-vars DASHBOARD_URL=https://YOUR-NEW-VERCEL-URL.vercel.app")
        
        return False
    else:
        logger.info(f"\n✓ Found {len(accessible_urls)} working URL(s):")
        for url in accessible_urls:
            logger.info(f"   {url}")
        
        # Check if config.json uses a working URL
        config_url = dashboard_config.get('url', '') if dashboard_config else ''
        if config_url in accessible_urls:
            logger.info(f"\n✓ config.json uses a working URL: {config_url}")
            logger.info("\n🔍 Dashboard is accessible but may not be receiving data. Check:")
            logger.info("   1. Cloud Function logs for POST requests to dashboard")
            logger.info("   2. Dashboard API endpoints are implemented")
            logger.info("   3. API key is correct")
            return True
        else:
            logger.warning(f"\n⚠️ config.json uses a non-working URL: {config_url}")
            logger.info(f"\n📋 ACTION REQUIRED: Update config.json to use a working URL")
            logger.info(f"   Recommended URL: {accessible_urls[0]}")
            return False


def generate_fix_commands(accessible_urls, dashboard_config):
    """Generate specific commands to fix the issue"""
    logger.info("\n" + "=" * 80)
    logger.info("FIX COMMANDS")
    logger.info("=" * 80)
    
    if accessible_urls:
        working_url = accessible_urls[0]
        logger.info("\n# Update config.json with working dashboard URL")
        logger.info(f'python -c "')
        logger.info('import json')
        logger.info("with open(\'config.json\', \'r\') as f:")
        logger.info('    config = json.load(f)')
        logger.info(f'config[\'dashboard\'][\'url\'] = \'{working_url}\'')
        logger.info("with open(\'config.json\', \'w\') as f:")
        logger.info('    json.dump(config, f, indent=2)')
        logger.info('"')
        
        logger.info("\n# Update Cloud Function")
        logger.info(f"gcloud functions deploy amazon-ppc-optimizer \\")
        logger.info(f"  --update-env-vars DASHBOARD_URL={working_url}")
    else:
        logger.info("\nNo working dashboard URL found. Deploy dashboard first:")
        logger.info("cd amazon_ppc_dashboard/nextjs_space")
        logger.info("vercel --prod")


def main():
    """Main diagnosis function"""
    logger.info("=" * 80)
    logger.info("DASHBOARD ISSUE DIAGNOSIS TOOL")
    logger.info("=" * 80)
    logger.info(f"Date: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    # Step 1: Find all dashboard URLs
    urls = find_dashboard_urls()
    
    if not urls:
        logger.error("\n❌ No dashboard URLs found in codebase")
        return 1
    
    # Step 2: Test connectivity
    url_results = test_all_urls(urls)
    
    # Step 3: Check config
    dashboard_config = check_config_json()
    
    # Step 4: Check deployment
    has_dashboard_code = check_dashboard_deployment()
    
    # Step 5: Analysis
    is_working = analyze_results(url_results, dashboard_config)
    
    # Step 6: Generate fix commands
    accessible_urls = [url for url, result in url_results.items() if result['accessible']]
    generate_fix_commands(accessible_urls, dashboard_config)
    
    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    
    if not accessible_urls:
        logger.error("\n❌ DASHBOARD IS NOT ACCESSIBLE")
        logger.error("   The optimizer CANNOT send data to the dashboard")
        logger.error("   The dashboard CANNOT receive live data")
        logger.info("\n   ROOT CAUSE: Dashboard is not deployed or URLs are incorrect")
    elif is_working:
        logger.info("\n✓ Dashboard appears to be accessible")
        logger.info("   If still not receiving data, check:")
        logger.info("   - Cloud Function logs")
        logger.info("   - Dashboard API implementation")
        logger.info("   - API key configuration")
    else:
        logger.warning("\n⚠️ Dashboard exists but config.json needs updating")
    
    return 0 if is_working else 1


if __name__ == '__main__':
    sys.exit(main())
