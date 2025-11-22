#!/usr/bin/env python3
"""
Test Complete Data Flow: Optimizer → BigQuery → Dashboard

This script tests the complete data flow to ensure:
1. GCP credentials are loaded correctly
2. BigQuery client can be initialized
3. Data can be written to BigQuery
4. Dashboard can read data from BigQuery

Usage:
    python test_data_flow.py [--project-id PROJECT_ID] [--write-test-data]
"""

import argparse
import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_credentials():
    """Test 1: Verify GCP credentials can be loaded"""
    logger.info("=" * 80)
    logger.info("TEST 1: GCP Credentials Loading")
    logger.info("=" * 80)
    
    try:
        from gcp_credentials import load_credentials, validate_credentials_early
        
        # Test validation
        logger.info("Testing credential validation...")
        is_valid, error_msg = validate_credentials_early()
        
        if is_valid:
            logger.info("✓ Credentials validated successfully")
        else:
            logger.warning(f"⚠️ Credential validation returned False")
            if error_msg:
                logger.warning(f"   Error: {error_msg}")
        
        # Test loading
        logger.info("\nTesting credential loading...")
        credentials = load_credentials()
        
        if credentials:
            logger.info("✓ Credentials loaded successfully")
            logger.info(f"   Type: {type(credentials).__name__}")
            if hasattr(credentials, 'project_id'):
                logger.info(f"   Project ID: {credentials.project_id}")
            if hasattr(credentials, 'service_account_email'):
                logger.info(f"   Service Account: {credentials.service_account_email}")
        else:
            logger.info("ℹ️ No explicit credentials - will use Application Default Credentials")
        
        return True, credentials
        
    except Exception as e:
        logger.error(f"❌ Credential test failed: {e}")
        logger.error(traceback.format_exc())
        return False, None


def test_bigquery_client(project_id: str):
    """Test 2: Verify BigQuery client can be initialized"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: BigQuery Client Initialization")
    logger.info("=" * 80)
    
    try:
        from bigquery_client import BigQueryClient
        
        dataset_id = 'amazon_ppc'
        location = 'us-east4'
        
        logger.info(f"Initializing BigQuery client...")
        logger.info(f"   Project: {project_id}")
        logger.info(f"   Dataset: {dataset_id}")
        logger.info(f"   Location: {location}")
        
        client = BigQueryClient(project_id, dataset_id, location)
        
        logger.info("✓ BigQuery client initialized successfully")
        
        # Test dataset access
        try:
            dataset = client.client.get_dataset(f"{project_id}.{dataset_id}")
            logger.info(f"✓ Dataset accessible: {dataset.dataset_id}")
            logger.info(f"   Created: {dataset.created}")
            logger.info(f"   Location: {dataset.location}")
        except Exception as dataset_err:
            logger.warning(f"⚠️ Dataset access check failed: {dataset_err}")
        
        return True, client
        
    except Exception as e:
        logger.error(f"❌ BigQuery client test failed: {e}")
        logger.error(traceback.format_exc())
        return False, None


def test_bigquery_write(bq_client, write_data: bool):
    """Test 3: Verify data can be written to BigQuery"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: BigQuery Write Operation")
    logger.info("=" * 80)
    
    if not write_data:
        logger.info("ℹ️ Skipping write test (use --write-test-data to enable)")
        return True
    
    try:
        from dashboard_client import DashboardClient
        
        # Create minimal test config
        config = {
            'amazon_api': {
                'profile_id': '1780498399290938'
            },
            'dashboard': {
                'enabled': False  # Disable dashboard for this test
            }
        }
        
        # Create test data
        logger.info("Creating test optimization data...")
        test_results = {
            'bid_optimization': {
                'keywords_optimized': 10,
                'bids_increased': 6,
                'bids_decreased': 4,
                'total_spend': 100.0,
                'total_sales': 200.0
            }
        }
        
        run_id = str(uuid.uuid4())
        dashboard_client = DashboardClient(config)
        dashboard_client.current_run_id = run_id
        
        results_payload = dashboard_client.build_results_payload(
            test_results, 
            config, 
            duration_seconds=10.5, 
            dry_run=True
        )
        
        logger.info(f"Test run_id: {run_id}")
        logger.info(f"Writing test data to BigQuery...")
        
        success = bq_client.write_optimization_results(results_payload)
        
        if success:
            logger.info("✓ Test data written successfully")
            logger.info(f"\nTo view the test data, run:")
            logger.info(f"   SELECT * FROM `{bq_client.project_id}.{bq_client.dataset_id}.optimization_results`")
            logger.info(f"   WHERE run_id = '{run_id}'")
            logger.info(f"\nTo remove the test data, run:")
            logger.info(f"   DELETE FROM `{bq_client.project_id}.{bq_client.dataset_id}.optimization_results`")
            logger.info(f"   WHERE run_id = '{run_id}'")
        else:
            logger.error("❌ Failed to write test data")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Write test failed: {e}")
        logger.error(traceback.format_exc())
        return False


def test_bigquery_read(project_id: str):
    """Test 4: Verify dashboard can read data from BigQuery"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: BigQuery Read Operation (Dashboard)")
    logger.info("=" * 80)
    
    try:
        from google.cloud import bigquery
        from gcp_credentials import load_credentials
        
        # Initialize client the same way the dashboard does
        credentials = load_credentials()
        if credentials:
            logger.info("Using service account credentials")
            client = bigquery.Client(project=project_id, credentials=credentials)
        else:
            logger.info("Using Application Default Credentials")
            client = bigquery.Client(project=project_id)
        
        # Test reading recent data
        dataset_id = 'amazon_ppc'
        query = f"""
            SELECT 
                timestamp,
                run_id,
                status,
                campaigns_analyzed,
                keywords_optimized
            FROM `{project_id}.{dataset_id}.optimization_results`
            ORDER BY timestamp DESC
            LIMIT 5
        """
        
        logger.info("Executing query...")
        logger.info(f"   Query: {query[:100]}...")
        
        results = client.query(query).result()
        rows = list(results)
        
        logger.info(f"✓ Query executed successfully")
        logger.info(f"   Found {len(rows)} recent optimization runs")
        
        if len(rows) == 0:
            logger.warning("⚠️ No data found in optimization_results table")
            logger.warning("   This is expected if the optimizer hasn't run yet")
            logger.warning("   Run the optimizer with: python main.py or trigger the Cloud Function")
        else:
            logger.info("\nRecent optimization runs:")
            for i, row in enumerate(rows, 1):
                logger.info(f"   {i}. Run ID: {row.run_id[:8]}... | "
                          f"Campaigns: {row.campaigns_analyzed} | "
                          f"Keywords: {row.keywords_optimized} | "
                          f"Status: {row.status}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Read test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Main test function"""
    parser = argparse.ArgumentParser(
        description='Test complete data flow for Amazon PPC Optimizer',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--project-id', 
                       default=os.getenv('GCP_PROJECT', 'amazon-ppc-474902'),
                       help='Google Cloud project ID')
    parser.add_argument('--write-test-data', 
                       action='store_true',
                       help='Write test data to BigQuery (default: skip)')
    
    args = parser.parse_args()
    
    logger.info("\n" + "=" * 80)
    logger.info("AMAZON PPC OPTIMIZER - DATA FLOW TEST")
    logger.info("=" * 80)
    logger.info(f"Project ID: {args.project_id}")
    logger.info(f"Write test data: {args.write_test_data}")
    logger.info("=" * 80)
    
    # Track test results
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Credentials
    success, credentials = test_credentials()
    if success:
        tests_passed += 1
    else:
        tests_failed += 1
        logger.error("\n⚠️ Credential test failed - cannot proceed with other tests")
        logger.error("   Please check your GCP_SERVICE_ACCOUNT_KEY or GOOGLE_APPLICATION_CREDENTIALS")
        return 1
    
    # Test 2: BigQuery Client
    success, bq_client = test_bigquery_client(args.project_id)
    if success:
        tests_passed += 1
    else:
        tests_failed += 1
        logger.error("\n⚠️ BigQuery client test failed - cannot proceed with write/read tests")
        return 1
    
    # Test 3: Write (optional)
    if args.write_test_data:
        success = test_bigquery_write(bq_client, args.write_test_data)
        if success:
            tests_passed += 1
        else:
            tests_failed += 1
    
    # Test 4: Read
    success = test_bigquery_read(args.project_id)
    if success:
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Tests passed: {tests_passed}")
    logger.info(f"Tests failed: {tests_failed}")
    logger.info("=" * 80)
    
    if tests_failed == 0:
        logger.info("\n✅ ALL TESTS PASSED")
        logger.info("\nNext steps:")
        logger.info("1. Run the optimizer to generate real data:")
        logger.info("   - Local: python main.py")
        logger.info("   - Cloud: Trigger the Cloud Function")
        logger.info("2. Check the dashboard at /api/bigquery-health")
        logger.info("3. Verify data in dashboard UI")
        return 0
    else:
        logger.error("\n❌ SOME TESTS FAILED")
        logger.info("\nTroubleshooting:")
        logger.info("1. Ensure GCP_SERVICE_ACCOUNT_KEY is set with valid credentials")
        logger.info("2. Verify service account has BigQuery permissions:")
        logger.info("   - roles/bigquery.dataEditor (for writes)")
        logger.info("   - roles/bigquery.jobUser (for queries)")
        logger.info("3. Check that the dataset exists: amazon_ppc")
        logger.info("4. Run with --write-test-data to test write operations")
        return 1


if __name__ == '__main__':
    sys.exit(main())
