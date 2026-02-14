#!/usr/bin/env python3
"""
Diagnostic script to identify which BigQuery tables contain performance data
and check for data duplication issues.

This script helps diagnose inflated sales/spend numbers in the dashboard by:
1. Checking each performance table for sales/spend data
2. Identifying potential duplication issues across tables
3. Showing what naive summation would produce vs single-source data
4. Recommending which table to use as the primary data source

Usage:
    python scripts/diagnose_sales_data.py --project amazon-ppc-474902 --dataset amazon_ppc_data --days 7
    python scripts/diagnose_sales_data.py --project amazon-ppc-474902 --dataset amazon_ppc_data --days 14 --verbose
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from google.cloud import bigquery
from google.oauth2 import service_account


def load_credentials() -> Optional[service_account.Credentials]:
    """Load GCP credentials from environment."""
    # Try various environment variables
    creds_json = (
        os.getenv("GCP_SERVICE_ACCOUNT_KEY")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        or os.getenv("GOOGLE_CREDENTIALS_JSON")
    )
    
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if creds_json:
        import json
        import base64
        
        # Handle base64-encoded credentials
        if not creds_json.strip().startswith("{"):
            try:
                creds_json = base64.b64decode(creds_json).decode("utf-8")
            except Exception:
                pass
        
        try:
            creds_dict = json.loads(creds_json)
            return service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            print(f"Warning: Failed to parse credentials from env vars: {e}", file=sys.stderr)
    
    if creds_path and os.path.exists(creds_path):
        return service_account.Credentials.from_service_account_file(creds_path)
    
    return None


def diagnose_sales_data(
    project_id: str,
    dataset_id: str,
    days: int = 7,
    verbose: bool = False
) -> int:
    """
    Diagnose sales/spend data across BigQuery tables.
    
    Returns:
        0 if successful
        1 if errors occurred
    """
    credentials = load_credentials()
    if credentials:
        client = bigquery.Client(project=project_id, credentials=credentials)
    else:
        # Try default credentials
        client = bigquery.Client(project=project_id)
    
    # Check each table for sales/spend data
    tables_to_check = [
        "campaign_performance",
        "sp_campaign_metrics",
        "campaign_details",
        "keyword_performance", 
        "search_term_reports",
    ]
    
    print(f"\n{'='*80}")
    print(f"🔍 DIAGNOSING SALES/SPEND DATA")
    print(f"{'='*80}")
    print(f"Project: {project_id}")
    print(f"Dataset: {dataset_id}")
    print(f"Date Range: Last {days} days")
    print(f"{'='*80}\n")
    
    total_across_tables: Dict[str, Dict[str, Any]] = {}
    campaign_level_tables = []
    keyword_level_tables = []
    errors = []
    
    for table_name in tables_to_check:
        try:
            # Build query to aggregate data
            query = f"""
            SELECT
              '{table_name}' as source_table,
              COUNT(*) as row_count,
              COUNT(DISTINCT 
                COALESCE(campaign_id, campaignId, campaign)
              ) as unique_campaigns,
              COUNT(DISTINCT 
                COALESCE(
                  CAST(segments_date AS DATE),
                  CAST(segmentsDate AS DATE),
                  CAST(report_date AS DATE),
                  CAST(reportDate AS DATE),
                  CAST(startDate AS DATE),
                  CAST(date AS DATE),
                  CAST(timestamp AS DATE)
                )
              ) as unique_dates,
              SUM(COALESCE(cost, spend, 0)) as total_spend,
              SUM(COALESCE(
                attributedSales14d, 
                attributed_sales_14d,
                attributedSales7d,
                attributed_sales_7d,
                sales,
                0
              )) as total_sales
            FROM `{project_id}.{dataset_id}.{table_name}`
            WHERE COALESCE(
              CAST(segments_date AS DATE),
              CAST(segmentsDate AS DATE),
              CAST(report_date AS DATE),
              CAST(reportDate AS DATE),
              CAST(startDate AS DATE),
              CAST(date AS DATE),
              CAST(timestamp AS DATE)
            ) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
            """
            
            if verbose:
                print(f"\n--- Query for {table_name} ---")
                print(query)
                print("---\n")
            
            results = client.query(query).result()
            
            for row in results:
                spend = float(row.total_spend or 0)
                sales = float(row.total_sales or 0)
                
                print(f"\n📊 {row.source_table}")
                print(f"   ├─ Rows: {row.row_count:,}")
                print(f"   ├─ Unique Campaigns: {row.unique_campaigns}")
                print(f"   ├─ Unique Dates: {row.unique_dates}")
                print(f"   ├─ Total Spend: ${spend:,.2f}")
                print(f"   └─ Total Sales: ${sales:,.2f}")
                
                if row.row_count > 0:
                    total_across_tables[table_name] = {
                        'spend': spend,
                        'sales': sales,
                        'rows': row.row_count,
                        'campaigns': row.unique_campaigns,
                        'dates': row.unique_dates,
                    }
                    
                    # Categorize tables
                    if table_name in ["campaign_performance", "sp_campaign_metrics", "campaign_details"]:
                        campaign_level_tables.append(table_name)
                    else:
                        keyword_level_tables.append(table_name)
                
        except Exception as e:
            error_msg = f"❌ {table_name}: {str(e)}"
            print(f"\n{error_msg}")
            errors.append(error_msg)
            if verbose:
                import traceback
                traceback.print_exc()
    
    # Show analysis
    print(f"\n{'='*80}")
    print("💡 ANALYSIS")
    print(f"{'='*80}\n")
    
    if not total_across_tables:
        print("⚠️  No data found in any performance tables!")
        print("    Check that:")
        print("    1. Tables exist in the dataset")
        print("    2. Tables contain recent data")
        print("    3. Service account has BigQuery Data Viewer permissions")
        return 1
    
    # Analysis: Campaign-level tables
    if campaign_level_tables:
        print(f"✅ Campaign-level tables found ({len(campaign_level_tables)}):")
        for table in campaign_level_tables:
            data = total_across_tables[table]
            print(f"   • {table}: ${data['spend']:,.2f} spend, ${data['sales']:,.2f} sales")
        
        if len(campaign_level_tables) > 1:
            print(f"\n⚠️  WARNING: Multiple campaign-level tables contain data!")
            print(f"   This could cause issues if aggregated naively.")
            print(f"   Recommendation: Use campaign_performance as primary source")
            
            # Show what naive sum would be
            naive_spend = sum(total_across_tables[t]['spend'] for t in campaign_level_tables)
            naive_sales = sum(total_across_tables[t]['sales'] for t in campaign_level_tables)
            print(f"\n   If summed naively across campaign-level tables:")
            print(f"   - Total Spend: ${naive_spend:,.2f}")
            print(f"   - Total Sales: ${naive_sales:,.2f}")
            
            # Compare to single source
            if "campaign_performance" in campaign_level_tables:
                single_source = total_across_tables["campaign_performance"]
                print(f"\n   Using campaign_performance alone:")
                print(f"   - Total Spend: ${single_source['spend']:,.2f}")
                print(f"   - Total Sales: ${single_source['sales']:,.2f}")
                
                if naive_spend > 0 and single_source['spend'] > 0:
                    inflation_ratio = naive_spend / single_source['spend']
                    print(f"\n   ⚠️  INFLATION RATIO: {inflation_ratio:.1f}x")
                    if inflation_ratio > 2:
                        print(f"      Data would be inflated by {inflation_ratio:.1f}x if summed naively!")
    else:
        print("⚠️  No campaign-level tables found with data")
    
    # Analysis: Keyword-level tables
    if keyword_level_tables:
        print(f"\n⚠️  Keyword/search-term level tables found ({len(keyword_level_tables)}):")
        for table in keyword_level_tables:
            data = total_across_tables[table]
            print(f"   • {table}: ${data['spend']:,.2f} spend, ${data['sales']:,.2f} sales")
        
        print(f"\n   ⚠️  WARNING: These tables should NOT be used for dashboard totals!")
        print(f"   Aggregating keyword-level data causes MASSIVE DUPLICATION")
        print(f"   (same campaign spend counted multiple times across keywords)")
    
    # Final recommendations
    print(f"\n{'='*80}")
    print("📋 RECOMMENDATIONS")
    print(f"{'='*80}\n")
    
    if "campaign_performance" in total_across_tables:
        print("✅ Use campaign_performance as primary data source")
        print("   This table contains campaign-level data from Amazon Ads API")
        print("   and is the most authoritative source.")
    elif "sp_campaign_metrics" in total_across_tables:
        print("✅ Use sp_campaign_metrics as primary data source")
        print("   (campaign_performance not available)")
    elif "campaign_details" in total_across_tables:
        print("⚠️  Use campaign_details as fallback")
        print("   (No Amazon API tables available)")
    else:
        print("❌ No suitable campaign-level tables found!")
    
    print(f"\nConfiguration:")
    print(f"   # Specify which dataset contains performance tables:")
    print(f"   Set environment variable: BQ_PERFORMANCE_DATASET_ID={dataset_id}")
    print(f"   Or in config: bigquery.performance_dataset_id: {dataset_id}")
    print(f"")
    print(f"   # Optionally specify preferred table (recommended):")
    print(f"   Set environment variable: BQ_PREFERRED_PERFORMANCE_TABLE=campaign_performance")
    print(f"   Or in config: bigquery.preferred_performance_table: campaign_performance")
    
    if errors:
        print(f"\n⚠️  {len(errors)} error(s) occurred during diagnosis")
        return 1
    
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose sales/spend data duplication in BigQuery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/diagnose_sales_data.py --project amazon-ppc-474902 --dataset amazon_ppc_data
  python scripts/diagnose_sales_data.py --project my-project --dataset ppc_data --days 14 --verbose
        """
    )
    parser.add_argument(
        "--project",
        required=True,
        help="GCP project ID"
    )
    parser.add_argument(
        "--dataset",
        default="amazon_ppc_data",
        help="BigQuery dataset ID (default: amazon_ppc_data)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to analyze (default: 7)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output including queries"
    )
    
    args = parser.parse_args()
    
    try:
        return diagnose_sales_data(
            args.project,
            args.dataset,
            args.days,
            args.verbose
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
