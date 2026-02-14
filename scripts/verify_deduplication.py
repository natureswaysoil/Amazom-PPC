#!/usr/bin/env python3
"""
Diagnostic script to verify deduplication and identify data inflation sources.

This script:
1. Queries BigQuery directly to show raw data
2. Calculates metrics with and without deduplication
3. Shows exactly where inflation is occurring
4. Verifies campaign_details table structure
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import bigquery
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Run diagnostic checks on BigQuery data."""
    
    # Get configuration from environment
    project_id = (
        os.getenv("GCP_PROJECT") 
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT_ID")
    )
    dataset_id = (
        os.getenv("BIGQUERY_DATASET")
        or os.getenv("BQ_DATASET_ID")
        or os.getenv("BIGQUERY_DATASET_ID")
        or "amazon_ppc_data"
    )
    
    perf_dataset_id = (
        os.getenv("BQ_PERFORMANCE_DATASET_ID")
        or os.getenv("PPC_PERFORMANCE_DATASET_ID")
        or dataset_id
    )
    
    if not project_id:
        logger.error("❌ No GCP project ID found. Set GCP_PROJECT or GOOGLE_CLOUD_PROJECT")
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info("🔍 BigQuery Deduplication Verification")
    logger.info("=" * 80)
    logger.info(f"Project: {project_id}")
    logger.info(f"Dataset: {dataset_id}")
    logger.info(f"Performance Dataset: {perf_dataset_id}")
    logger.info("")
    
    client = bigquery.Client(project=project_id)
    
    # 1. Check campaign_details table structure
    logger.info("=" * 80)
    logger.info("1. Verifying campaign_details table structure")
    logger.info("=" * 80)
    check_campaign_details_structure(client, perf_dataset_id)
    
    # 2. Check optimization_results for lookback window info
    logger.info("\n" + "=" * 80)
    logger.info("2. Checking optimization_results for lookback configuration")
    logger.info("=" * 80)
    check_lookback_windows(client, dataset_id)
    
    # 3. Compare deduplicated vs non-deduplicated data
    logger.info("\n" + "=" * 80)
    logger.info("3. Comparing deduplicated vs non-deduplicated metrics")
    logger.info("=" * 80)
    compare_deduplication(client, perf_dataset_id, dataset_id)
    
    # 4. Check for overlapping data in campaign_details
    logger.info("\n" + "=" * 80)
    logger.info("4. Analyzing campaign_details for overlapping windows")
    logger.info("=" * 80)
    analyze_overlapping_windows(client, perf_dataset_id)
    
    # 5. Calculate dashboard metrics both ways
    logger.info("\n" + "=" * 80)
    logger.info("5. Calculating 7-day dashboard metrics (both methods)")
    logger.info("=" * 80)
    calculate_dashboard_metrics(client, perf_dataset_id, dataset_id)
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Diagnostic complete")
    logger.info("=" * 80)


def check_campaign_details_structure(client: bigquery.Client, dataset_id: str):
    """Verify campaign_details table has required columns."""
    try:
        table_ref = f"{client.project}.{dataset_id}.campaign_details"
        table = client.get_table(table_ref)
        
        logger.info(f"Table: {table_ref}")
        logger.info(f"Rows: {table.num_rows:,}")
        logger.info(f"Size: {table.num_bytes / 1024 / 1024:.2f} MB")
        logger.info("\nSchema:")
        
        required_cols = {"campaign_id", "timestamp", "run_id", "spend", "sales"}
        found_cols = set()
        
        for field in table.schema:
            marker = "✓" if field.name in required_cols else " "
            logger.info(f"  {marker} {field.name:20s} {field.field_type:10s} {field.mode}")
            found_cols.add(field.name)
        
        missing = required_cols - found_cols
        if missing:
            logger.warning(f"\n⚠️  Missing required columns for deduplication: {missing}")
        else:
            logger.info(f"\n✓ All required columns present for deduplication")
            
    except Exception as e:
        logger.error(f"❌ Error checking campaign_details: {e}")


def check_lookback_windows(client: bigquery.Client, dataset_id: str):
    """Check what lookback windows are configured in recent runs."""
    query = f"""
    SELECT 
        DATE(timestamp) as run_date,
        lookback_days,
        COUNT(*) as run_count,
        AVG(total_spend) as avg_spend,
        AVG(total_sales) as avg_sales,
        AVG(average_acos) as avg_acos
    FROM `{client.project}.{dataset_id}.optimization_results`
    WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
    GROUP BY run_date, lookback_days
    ORDER BY run_date DESC
    LIMIT 20
    """
    
    try:
        results = list(client.query(query).result())
        
        if not results:
            logger.warning("⚠️  No recent optimization results found")
            return
        
        logger.info("\nRecent optimization runs:")
        logger.info(f"{'Date':12s} {'Lookback':10s} {'Runs':6s} {'Avg Spend':12s} {'Avg Sales':12s} {'ACOS':8s}")
        logger.info("-" * 70)
        
        for row in results:
            acos_pct = (row.avg_acos or 0) * 100
            logger.info(
                f"{str(row.run_date):12s} "
                f"{row.lookback_days or 'N/A':>10s} "
                f"{row.run_count:>6d} "
                f"${row.avg_spend or 0:>10.2f} "
                f"${row.avg_sales or 0:>10.2f} "
                f"{acos_pct:>6.1f}%"
            )
        
        # Check if lookback > 1 day
        lookback_days = results[0].lookback_days if results else 0
        if lookback_days and lookback_days > 1:
            logger.warning(
                f"\n⚠️  CRITICAL: Lookback window is {lookback_days} days!"
            )
            logger.warning(
                f"    This means each run's metrics aggregate {lookback_days} days of data."
            )
            logger.warning(
                f"    Summing multiple runs will count overlapping periods multiple times!"
            )
            
    except Exception as e:
        logger.error(f"❌ Error checking lookback windows: {e}")


def compare_deduplication(client: bigquery.Client, perf_dataset_id: str, dataset_id: str):
    """Compare metrics with and without deduplication."""
    
    # First, try campaign_details
    query = f"""
    WITH all_data AS (
        SELECT
            DATE(timestamp) as day,
            campaign_id,
            spend,
            sales,
            run_id,
            timestamp
        FROM `{client.project}.{perf_dataset_id}.campaign_details`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    ),
    deduplicated AS (
        SELECT
            day,
            campaign_id,
            spend,
            sales,
            ROW_NUMBER() OVER (
                PARTITION BY day, campaign_id
                ORDER BY timestamp DESC
            ) as rn
        FROM all_data
    ),
    no_dedup_metrics AS (
        SELECT
            'Without Deduplication' as method,
            SUM(spend) as total_spend,
            SUM(sales) as total_sales,
            COUNT(*) as row_count,
            COUNT(DISTINCT day) as day_count,
            COUNT(DISTINCT campaign_id) as campaign_count
        FROM all_data
    ),
    dedup_metrics AS (
        SELECT
            'With Deduplication' as method,
            SUM(spend) as total_spend,
            SUM(sales) as total_sales,
            COUNT(*) as row_count,
            COUNT(DISTINCT day) as day_count,
            COUNT(DISTINCT campaign_id) as campaign_count
        FROM deduplicated
        WHERE rn = 1
    )
    SELECT * FROM no_dedup_metrics
    UNION ALL
    SELECT * FROM dedup_metrics
    """
    
    try:
        results = list(client.query(query).result())
        
        if not results:
            logger.warning("⚠️  No campaign_details data found in last 7 days")
            return
        
        logger.info("\nCampaign Details (Last 7 Days):")
        logger.info(f"{'Method':25s} {'Total Spend':>12s} {'Total Sales':>12s} {'ACOS':>8s} {'Rows':>8s} {'Days':>6s} {'Campaigns':>10s}")
        logger.info("-" * 90)
        
        no_dedup_row = None
        dedup_row = None
        
        for row in results:
            acos = (row.total_spend / row.total_sales * 100) if row.total_sales > 0 else 0
            logger.info(
                f"{row.method:25s} "
                f"${row.total_spend:>10.2f} "
                f"${row.total_sales:>10.2f} "
                f"{acos:>6.1f}% "
                f"{row.row_count:>8d} "
                f"{row.day_count:>6d} "
                f"{row.campaign_count:>10d}"
            )
            
            if 'Without' in row.method:
                no_dedup_row = row
            else:
                dedup_row = row
        
        # Calculate inflation factor
        if no_dedup_row and dedup_row and dedup_row.total_spend > 0:
            spend_inflation = no_dedup_row.total_spend / dedup_row.total_spend
            sales_inflation = no_dedup_row.total_sales / dedup_row.total_sales if dedup_row.total_sales > 0 else 0
            
            logger.info("")
            if spend_inflation > 1.1:
                logger.warning(f"⚠️  Spend inflation factor: {spend_inflation:.2f}x")
                logger.warning(f"⚠️  Sales inflation factor: {sales_inflation:.2f}x")
                logger.warning("    Deduplication is reducing metrics significantly!")
            else:
                logger.info(f"✓ Minimal inflation detected ({spend_inflation:.2f}x)")
                
    except Exception as e:
        logger.error(f"❌ Error comparing deduplication: {e}")


def analyze_overlapping_windows(client: bigquery.Client, perf_dataset_id: str):
    """Analyze if campaign_details contains overlapping lookback windows."""
    query = f"""
    WITH daily_runs AS (
        SELECT
            DATE(timestamp) as day,
            COUNT(DISTINCT run_id) as run_count,
            COUNT(*) as total_rows,
            COUNT(DISTINCT campaign_id) as campaign_count,
            SUM(spend) as day_total_spend,
            SUM(sales) as day_total_sales
        FROM `{client.project}.{perf_dataset_id}.campaign_details`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
        GROUP BY day
        ORDER BY day DESC
    )
    SELECT * FROM daily_runs
    LIMIT 14
    """
    
    try:
        results = list(client.query(query).result())
        
        if not results:
            logger.warning("⚠️  No campaign_details data found in last 14 days")
            return
        
        logger.info("\nDaily run frequency in campaign_details:")
        logger.info(f"{'Date':12s} {'Runs':>6s} {'Campaigns':>10s} {'Rows':>8s} {'Spend':>12s} {'Sales':>12s}")
        logger.info("-" * 70)
        
        multi_run_days = 0
        for row in results:
            marker = "⚠️ " if row.run_count > 1 else "  "
            logger.info(
                f"{marker}{str(row.day):12s} "
                f"{row.run_count:>6d} "
                f"{row.campaign_count:>10d} "
                f"{row.total_rows:>8d} "
                f"${row.day_total_spend or 0:>10.2f} "
                f"${row.day_total_sales or 0:>10.2f}"
            )
            if row.run_count > 1:
                multi_run_days += 1
        
        if multi_run_days > 0:
            logger.warning(
                f"\n⚠️  {multi_run_days} days have multiple optimization runs!"
            )
            logger.warning(
                "    Without deduplication, these would be counted multiple times."
            )
        else:
            logger.info("\n✓ Each day has at most one optimization run")
            
    except Exception as e:
        logger.error(f"❌ Error analyzing overlapping windows: {e}")


def calculate_dashboard_metrics(client: bigquery.Client, perf_dataset_id: str, dataset_id: str):
    """Calculate dashboard metrics using both methods."""
    
    # Method 1: Sum daily aggregates (what dashboard currently does)
    query_sum_daily = f"""
    WITH deduplicated_campaigns AS (
        SELECT
            DATE(timestamp) AS day,
            campaign_id,
            spend,
            sales,
            ROW_NUMBER() OVER (
                PARTITION BY DATE(timestamp), campaign_id
                ORDER BY timestamp DESC
            ) AS rn
        FROM `{client.project}.{perf_dataset_id}.campaign_details`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    ),
    daily_totals AS (
        SELECT
            day,
            SUM(spend) AS total_spend,
            SUM(sales) AS total_sales
        FROM deduplicated_campaigns
        WHERE rn = 1
        GROUP BY day
    )
    SELECT
        'Sum Daily Aggregates' as method,
        SUM(total_spend) as total_spend,
        SUM(total_sales) as total_sales,
        COUNT(*) as days_counted
    FROM daily_totals
    """
    
    # Method 2: Use latest day only (what we should do if data contains lookback)
    query_latest_only = f"""
    WITH latest_run AS (
        SELECT
            DATE(timestamp) AS day,
            timestamp,
            ROW_NUMBER() OVER (ORDER BY timestamp DESC) as rn
        FROM `{client.project}.{dataset_id}.optimization_results`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    ),
    latest_day AS (
        SELECT day
        FROM latest_run
        WHERE rn = 1
    )
    SELECT
        'Latest Day Only' as method,
        SUM(spend) as total_spend,
        SUM(sales) as total_sales,
        1 as days_counted
    FROM `{client.project}.{perf_dataset_id}.campaign_details`
    WHERE DATE(timestamp) = (SELECT day FROM latest_day)
    """
    
    try:
        logger.info("\nDashboard metric calculation methods:")
        logger.info(f"{'Method':25s} {'Total Spend':>12s} {'Total Sales':>12s} {'ACOS':>8s} {'Days':>6s}")
        logger.info("-" * 65)
        
        # Execute both queries
        results_sum = list(client.query(query_sum_daily).result())
        results_latest = list(client.query(query_latest_only).result())
        
        sum_row = results_sum[0] if results_sum else None
        latest_row = results_latest[0] if results_latest else None
        
        if sum_row:
            acos = (sum_row.total_spend / sum_row.total_sales * 100) if sum_row.total_sales > 0 else 0
            logger.info(
                f"{sum_row.method:25s} "
                f"${sum_row.total_spend:>10.2f} "
                f"${sum_row.total_sales:>10.2f} "
                f"{acos:>6.1f}% "
                f"{sum_row.days_counted:>6d}"
            )
        
        if latest_row:
            acos = (latest_row.total_spend / latest_row.total_sales * 100) if latest_row.total_sales > 0 else 0
            logger.info(
                f"{latest_row.method:25s} "
                f"${latest_row.total_spend:>10.2f} "
                f"${latest_row.total_sales:>10.2f} "
                f"{acos:>6.1f}% "
                f"{latest_row.days_counted:>6d}"
            )
        
        # Compare and provide recommendation
        if sum_row and latest_row and latest_row.total_spend > 0:
            inflation = sum_row.total_spend / latest_row.total_spend
            logger.info("")
            
            if inflation > 2.0:
                logger.warning(f"⚠️  CRITICAL INFLATION DETECTED!")
                logger.warning(f"    Summing daily aggregates inflates metrics by {inflation:.1f}x")
                logger.warning(f"    This is likely because each day's data contains a lookback window")
                logger.warning(f"\n    RECOMMENDATION:")
                logger.warning(f"    Use 'Latest Day Only' method for dashboard metrics")
                logger.warning(f"    OR ensure campaign_details only contains single-day data")
            elif inflation > 1.2:
                logger.warning(f"⚠️  Moderate inflation detected ({inflation:.1f}x)")
                logger.warning(f"    Consider using 'Latest Day Only' method")
            else:
                logger.info(f"✓ Minimal difference between methods ({inflation:.1f}x)")
                logger.info(f"  Daily aggregates appear to be single-day data")
                
    except Exception as e:
        logger.error(f"❌ Error calculating dashboard metrics: {e}")


if __name__ == "__main__":
    main()
