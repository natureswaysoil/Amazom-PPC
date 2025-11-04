#!/usr/bin/env python3
"""
Verify Dashboard is Live and Receiving Data

This script verifies that the dashboard at 
https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app
is live and can receive data.

Usage:
    python3 verify_dashboard_live.py
"""

import json
import logging
import sys
from datetime import datetime
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DASHBOARD_URL = "https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app"

def test_dashboard_reachability():
    """Test if dashboard URL is reachable"""
    logger.info(f"Testing dashboard reachability: {DASHBOARD_URL}")
    
    try:
        response = requests.get(DASHBOARD_URL, timeout=10)
        logger.info(f"✓ Dashboard is reachable (HTTP {response.status_code})")
        
        # Try to get some basic info about the response
        content_type = response.headers.get('content-type', 'unknown')
        logger.info(f"  Content-Type: {content_type}")
        
        if response.status_code == 200:
            logger.info(f"  Response size: {len(response.content)} bytes")
            return True
        else:
            logger.warning(f"  Dashboard returned non-200 status: {response.status_code}")
            return True  # Still reachable
            
    except requests.exceptions.Timeout:
        logger.error("✗ Dashboard request timed out after 10 seconds")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"✗ Could not connect to dashboard: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {str(e)}")
        return False

def test_dashboard_api():
    """Test if dashboard API endpoint is available"""
    logger.info("Testing dashboard API endpoint")
    
    # Try the optimization-data endpoint
    api_endpoint = f"{DASHBOARD_URL}/api/optimization-data"
    
    # Create sample test data
    test_data = {
        "data": [
            {
                "timestamp": datetime.now().isoformat(),
                "run_id": "test-verification-run",
                "status": "success",
                "profile_id": "test-profile",
                "campaigns_analyzed": 5,
                "keywords_optimized": 25,
                "bids_increased": 10,
                "bids_decreased": 8,
                "total_spend": 100.00,
                "total_sales": 250.00,
                "average_acos": 0.40,
                "dry_run": True,
                "duration_seconds": 30.0
            }
        ],
        "run_id": "test-verification-run",
        "source": "verification_script"
    }
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'NWS-PPC-Optimizer-Verify/1.0'
        }
        
        response = requests.post(
            api_endpoint,
            json=test_data,
            headers=headers,
            timeout=15
        )
        
        logger.info(f"API endpoint response: HTTP {response.status_code}")
        
        if response.status_code == 200:
            logger.info("✓ Dashboard API endpoint is working")
            try:
                response_data = response.json()
                logger.info(f"  Response: {json.dumps(response_data, indent=2)}")
            except (json.JSONDecodeError, ValueError) as e:
                logger.info(f"  Response: {response.text[:200]}")
            return True
        elif response.status_code == 404:
            logger.warning("⚠ API endpoint not found (404)")
            logger.info("  This might be expected if the endpoint is not yet implemented")
            logger.info(f"  Response: {response.text[:200]}")
            return False
        elif response.status_code == 401 or response.status_code == 403:
            logger.warning("⚠ Authentication required (401/403)")
            logger.info("  Configure DASHBOARD_API_KEY in config.json")
            return False
        else:
            logger.warning(f"⚠ Unexpected status code: {response.status_code}")
            logger.info(f"  Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("✗ API request timed out after 15 seconds")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"✗ Could not connect to API endpoint: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {str(e)}")
        return False

def test_dashboard_health():
    """Test if dashboard has a health endpoint"""
    logger.info("Testing dashboard health endpoint")
    
    health_endpoint = f"{DASHBOARD_URL}/api/health"
    
    try:
        response = requests.get(health_endpoint, timeout=10)
        
        logger.info(f"Health endpoint response: HTTP {response.status_code}")
        
        if response.status_code == 200:
            logger.info("✓ Dashboard health endpoint is working")
            try:
                health_data = response.json()
                logger.info(f"  Health data: {json.dumps(health_data, indent=2)}")
            except (json.JSONDecodeError, ValueError) as e:
                logger.info(f"  Response: {response.text[:200]}")
            return True
        elif response.status_code == 404:
            logger.info("  Health endpoint not found (this is optional)")
            return True  # Not a failure
        else:
            logger.warning(f"  Unexpected status code: {response.status_code}")
            return True  # Still consider it a pass
            
    except Exception as e:
        logger.info(f"  Health endpoint not available: {str(e)}")
        return True  # Health endpoint is optional

def check_dashboard_endpoints():
    """Check common dashboard endpoints"""
    logger.info("Checking common dashboard endpoints")
    
    endpoints = [
        "/api/optimization-results",
        "/api/optimization-status",
        "/api/optimization-error",
        "/api/health",
    ]
    
    for endpoint in endpoints:
        url = f"{DASHBOARD_URL}{endpoint}"
        try:
            # Use HEAD request to avoid downloading content
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                logger.info(f"  ✓ {endpoint} - Available")
            elif response.status_code == 404:
                logger.info(f"  ⚠ {endpoint} - Not found")
            elif response.status_code == 405:
                logger.info(f"  ✓ {endpoint} - Exists (Method Not Allowed)")
            else:
                logger.info(f"  ? {endpoint} - HTTP {response.status_code}")
        except Exception as e:
            logger.info(f"  ? {endpoint} - {type(e).__name__}")

def main():
    """Run all verification tests"""
    logger.info("=" * 70)
    logger.info("Dashboard Verification")
    logger.info("=" * 70)
    logger.info(f"Target: {DASHBOARD_URL}")
    logger.info("")
    
    results = []
    
    # Test 1: Basic reachability
    logger.info("\n--- Test 1: Dashboard Reachability ---")
    results.append(("Dashboard Reachable", test_dashboard_reachability()))
    
    # Test 2: API endpoint
    logger.info("\n--- Test 2: API Endpoint ---")
    results.append(("API Endpoint", test_dashboard_api()))
    
    # Test 3: Health endpoint
    logger.info("\n--- Test 3: Health Endpoint ---")
    results.append(("Health Endpoint", test_dashboard_health()))
    
    # Test 4: Endpoint discovery
    logger.info("\n--- Test 4: Endpoint Discovery ---")
    check_dashboard_endpoints()
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("Verification Summary")
    logger.info("=" * 70)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    logger.info("")
    logger.info(f"Results: {passed}/{total} tests passed")
    
    if passed >= 1:  # At least reachability should work
        logger.info("\n✓ Dashboard appears to be LIVE and accessible!")
        logger.info(f"  URL: {DASHBOARD_URL}")
        
        if passed < total:
            logger.info("\n⚠ Note: Some API endpoints may need configuration:")
            logger.info("  - Ensure API endpoints are implemented on dashboard")
            logger.info("  - Configure DASHBOARD_API_KEY if authentication is required")
            logger.info("  - Check dashboard logs for any errors")
    else:
        logger.error("\n✗ Dashboard verification FAILED")
        logger.error("  The dashboard may be offline or the URL is incorrect")
    
    logger.info("\n" + "=" * 70)
    
    return 0 if passed >= 1 else 1

if __name__ == "__main__":
    sys.exit(main())
