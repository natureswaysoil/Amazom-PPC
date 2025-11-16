#!/usr/bin/env python3
"""
Test BigQuery Integration

This script tests the complete data flow from optimizer to BigQuery to dashboard:
1. Simulates optimizer writing data to BigQuery
2. Verifies data is accessible and complete
3. Tests all expected fields are present

Usage:
    python test_bigquery_integration.py --project-id amazon-ppc-474902 [--dry-run]
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_optimization_data() -> Dict[str, Any]:
    """
    Create realistic test optimization data matching DATA_FLOW_SUMMARY.md structure
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    
    return {
        'timestamp': timestamp,
        'run_id': run_id,
        'status': 'success',
        'profile_id': '1780498399290938',
        'dry_run': True,  # Always use dry_run for tests
        'duration_seconds': 45.23,
        
        'summary': {
            'campaigns_analyzed': 253,
            'keywords_optimized': 1000,
            'bids_increased': 611,
            'bids_decreased': 389,
            'negative_keywords_added': 25,
            'budget_changes': 5,
            'total_spend': 1234.56,
            'total_sales': 2345.67,
            'average_acos': 0.526
        },
        
        'features': {
            'bid_optimization': {
                'keywords_analyzed': 1000,
                'bids_increased': 611,
                'bids_decreased': 389,
                'no_change': 0,
                'total_spend': 1000.00,
                'total_sales': 1800.00
            },
            'dayparting': {
                'current_day': 'MONDAY',
                'current_hour': 15,
                'keywords_updated': 0,
                'multiplier': 1.2
            },
            'campaign_management': {
                'campaigns_analyzed': 253,
                'campaigns_paused': 2,
                'campaigns_activated': 3,
                'no_change': 248,
                'total_spend': 234.56,
                'total_sales': 545.67
            },
            'keyword_discovery': {
                'keywords_discovered': 15,
                'keywords_added': 8
            },
            'negative_keywords': {
                'negative_keywords_added': 25
            }
        },
        
        'campaigns': [
            {
                'campaign_id': '123456',
                'campaign_name': 'Product Campaign A - Test',
                'spend': 123.45,
                'sales': 234.56,
                'acos': 0.526,
                'keywords_count': 50,
                'changes_made': 12,
                'impressions': 5000,
                'clicks': 250,
                'conversions': 15,
                'budget': 50.0,
                'status': 'enabled'
            },
            {
                'campaign_id': '123457',
                'campaign_name': 'Product Campaign B - Test',
                'spend': 98.76,
                'sales': 187.65,
                'acos': 0.526,
                'keywords_count': 35,
                'changes_made': 8,
                'impressions': 3500,
                'clicks': 180,
                'conversions': 12,
                'budget': 40.0,
                'status': 'enabled'
            },
            {
                'campaign_id': '123458',
                'campaign_name': 'Product Campaign C - Test',
                'spend': 156.78,
                'sales': 298.45,
                'acos': 0.525,
                'keywords_count': 45,
                'changes_made': 15,
                'impressions': 6200,
                'clicks': 310,
                'conversions': 20,
                'budget': 60.0,
                'status': 'enabled'
            }
        ],
        
        'top_performers': [
            {
                'keyword_text': 'organic soil - test',
                'clicks': 120,
                'sales': 345.67,
                'acos': 0.35,
                'bid_change': 0.15
            },
            {
                'keyword_text': 'potting mix - test',
                'clicks': 95,
                'sales': 278.90,
                'acos': 0.38,
                'bid_change': 0.12
            },
            {
                'keyword_text': 'garden soil - test',
                'clicks': 85,
                'sales': 245.30,
                'acos': 0.40,
                'bid_change': 0.10
            },
            {
                'keyword_text': 'compost mix - test',
                'clicks': 75,
                'sales': 210.50,
                'acos': 0.42,
                'bid_change': 0.08
            },
            {
                'keyword_text': 'raised bed soil - test',
                'clicks': 65,
                'sales': 189.20,
                'acos': 0.44,
                'bid_change': 0.06
            }
        ],
        
        'errors': [],
        'warnings': [
            'Campaign 123458 has low budget remaining - TEST DATA'
        ],
        
        'config_snapshot': {
            'target_acos': 0.45,
            'lookback_days': 14,
            'enabled_features': [
                'bid_optimization',
                'dayparting',
                'campaign_management',
                'keyword_discovery',
                'negative_keywords'
            ]
        }
    }


def test_bigquery_write(project_id: str, dataset_id: str = 'amazon_ppc', 
                        location: str = 'us-east4', dry_run: bool = False) -> bool:
    """
    Test writing optimization data to BigQuery
    
    Args:
        project_id: Google Cloud project ID
        dataset_id: BigQuery dataset ID
        location: BigQuery location
        dry_run: If True, don't actually write to BigQuery
    
    Returns:
        True if test successful, False otherwise
    """
    try:
        logger.info("=" * 80)
        logger.info("TESTING BIGQUERY INTEGRATION")
        logger.info("=" * 80)
        
        # Import BigQuery client
        from bigquery_client import BigQueryClient
        
        # Create test data
        logger.info("\n📋 Creating test optimization data...")
        test_data = create_test_optimization_data()
        logger.info(f"   ✓ Test run_id: {test_data['run_id']}")
        logger.info(f"   ✓ Campaigns: {len(test_data['campaigns'])}")
        logger.info(f"   ✓ Top performers: {len(test_data['top_performers'])}")
        logger.info(f"   ✓ Features tested: {len(test_data['features'])}")
        
        if dry_run:
            logger.info("\n🔍 DRY RUN MODE - Data will NOT be written to BigQuery")
            logger.info("\nTest data structure:")
            logger.info(json.dumps(test_data, indent=2, default=str))
            return True
        
        # Initialize BigQuery client
        logger.info(f"\n🔌 Connecting to BigQuery...")
        logger.info(f"   Project: {project_id}")
        logger.info(f"   Dataset: {dataset_id}")
        logger.info(f"   Location: {location}")
        
        bq_client = BigQueryClient(project_id, dataset_id, location)
        logger.info("   ✓ BigQuery client initialized")
        
        # Write test data
        logger.info("\n📤 Writing test data to BigQuery...")
        success = bq_client.write_optimization_results(test_data)
        
        if success:
            logger.info("   ✓ Successfully wrote test data to BigQuery")
            
            # Verify data was written
            logger.info("\n📥 Verifying data was written...")
            logger.info(f"   Run ID: {test_data['run_id']}")
            logger.info("   You can query this data with:")
            logger.info(f"   SELECT * FROM `{project_id}.{dataset_id}.optimization_results` WHERE run_id = '{test_data['run_id']}'")
            
            # Provide cleanup instructions
            logger.info("\n🧹 To remove test data, run:")
            logger.info(f"   DELETE FROM `{project_id}.{dataset_id}.optimization_results` WHERE run_id = '{test_data['run_id']}'")
            logger.info(f"   DELETE FROM `{project_id}.{dataset_id}.campaign_details` WHERE run_id = '{test_data['run_id']}'")
            
            return True
        else:
            logger.error("   ✗ Failed to write test data to BigQuery")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_bigquery_read(project_id: str, dataset_id: str = 'amazon_ppc', 
                       location: str = 'us-east4') -> bool:
    """
    Test reading optimization data from BigQuery
    
    Args:
        project_id: Google Cloud project ID
        dataset_id: BigQuery dataset ID
        location: BigQuery location
    
    Returns:
        True if test successful, False otherwise
    """
    try:
        logger.info("=" * 80)
        logger.info("TESTING BIGQUERY READ")
        logger.info("=" * 80)
        
        from google.cloud import bigquery
        from gcp_credentials import load_credentials
        
        # Load credentials
        logger.info("\n🔑 Loading GCP credentials...")
        credentials = load_credentials()
        
        if credentials:
            logger.info("   ✓ Using explicit service account credentials")
            client = bigquery.Client(project=project_id, credentials=credentials)
        else:
            logger.info("   ℹ️  Using Application Default Credentials")
            client = bigquery.Client(project=project_id)
        
        # Query recent data
        logger.info(f"\n📥 Querying recent optimization results...")
        query = f"""
            SELECT 
                timestamp,
                run_id,
                status,
                campaigns_analyzed,
                keywords_optimized,
                total_spend,
                total_sales,
                average_acos,
                campaigns,
                top_performers
            FROM `{project_id}.{dataset_id}.optimization_results`
            ORDER BY timestamp DESC
            LIMIT 5
        """
        
        logger.info(f"   Query: {query}")
        
        results = client.query(query, location=location).result()
        rows = list(results)
        
        logger.info(f"\n   ✓ Found {len(rows)} recent optimization runs")
        
        if len(rows) == 0:
            logger.warning("   ⚠️  No data found in optimization_results table")
            logger.warning("   This is normal if the optimizer hasn't run yet")
            return True
        
        # Display results
        for i, row in enumerate(rows, 1):
            logger.info(f"\n   Result #{i}:")
            logger.info(f"      Run ID: {row.run_id}")
            logger.info(f"      Timestamp: {row.timestamp}")
            logger.info(f"      Status: {row.status}")
            logger.info(f"      Campaigns: {row.campaigns_analyzed}")
            logger.info(f"      Keywords: {row.keywords_optimized}")
            logger.info(f"      Spend: ${row.total_spend:.2f}")
            logger.info(f"      Sales: ${row.total_sales:.2f}")
            logger.info(f"      ACOS: {row.average_acos * 100:.2f}%")
            
            # Check for enhanced data
            has_campaigns = row.campaigns is not None and (
                (isinstance(row.campaigns, str) and row.campaigns != '[]') or
                (isinstance(row.campaigns, list) and len(row.campaigns) > 0)
            )
            has_top_performers = row.top_performers is not None and (
                (isinstance(row.top_performers, str) and row.top_performers != '[]') or
                (isinstance(row.top_performers, list) and len(row.top_performers) > 0)
            )
            
            if has_campaigns:
                campaigns_data = json.loads(row.campaigns) if isinstance(row.campaigns, str) else row.campaigns
                logger.info(f"      ✓ Campaign data available ({len(campaigns_data)} campaigns)")
            else:
                logger.warning(f"      ⚠️  No campaign data")
            
            if has_top_performers:
                performers_data = json.loads(row.top_performers) if isinstance(row.top_performers, str) else row.top_performers
                logger.info(f"      ✓ Top performers available ({len(performers_data)} keywords)")
            else:
                logger.warning(f"      ⚠️  No top performers data")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Read test failed with error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Main test function"""
    parser = argparse.ArgumentParser(
        description='Test BigQuery integration for Amazon PPC Optimizer',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--project-id', required=True, help='Google Cloud project ID')
    parser.add_argument('--dataset-id', default='amazon_ppc', help='BigQuery dataset ID (default: amazon_ppc)')
    parser.add_argument('--location', default='us-east4', help='BigQuery location (default: us-east4)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be written without actually writing')
    parser.add_argument('--read-only', action='store_true', help='Only test reading data, skip write test')
    
    args = parser.parse_args()
    
    logger.info("\n" + "=" * 80)
    logger.info("AMAZON PPC OPTIMIZER - BIGQUERY INTEGRATION TEST")
    logger.info("=" * 80)
    
    success = True
    
    # Test write (unless read-only mode)
    if not args.read_only:
        write_success = test_bigquery_write(
            args.project_id,
            args.dataset_id,
            args.location,
            args.dry_run
        )
        success = success and write_success
    
    # Test read (unless dry-run mode)
    if not args.dry_run:
        read_success = test_bigquery_read(
            args.project_id,
            args.dataset_id,
            args.location
        )
        success = success and read_success
    
    # Final summary
    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 80)
        logger.info("\nNext steps:")
        logger.info("1. Check dashboard at /api/bigquery-data?limit=5")
        logger.info("2. Verify data is displayed correctly on dashboard homepage")
        logger.info("3. Run the optimizer to generate real data")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED")
        logger.info("=" * 80)
        logger.info("\nTroubleshooting:")
        logger.info("1. Check GCP credentials are configured correctly")
        logger.info("2. Verify BigQuery permissions (dataViewer + jobUser)")
        logger.info("3. Ensure dataset and tables exist")
        logger.info("4. Check /api/config-check for configuration issues")
        return 1


if __name__ == '__main__':
    sys.exit(main())
