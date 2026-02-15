"""
AOV Fetcher Module
==================

Fetches Average Order Value (AOV) data from BigQuery for bid optimization.

This module handles:
- Fetching campaign-level AOV data with proper type casting
- Fetching keyword performance data with INT64 to STRING conversions
- Handling BigQuery type mismatches by ensuring consistent ID types
"""

import logging
import os
from typing import Dict, List, Optional, Any
from google.cloud import bigquery

logger = logging.getLogger("aov_fetcher")


class AOVFetcher:
    """
    Fetches AOV data from BigQuery with proper type handling to avoid type mismatch errors.
    """

    def __init__(self, project_id: str, dataset_id: str = "amazon_ppc"):
        """
        Initialize AOV fetcher.

        Args:
            project_id: Google Cloud project ID
            dataset_id: BigQuery dataset ID (default: "amazon_ppc")
        """
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.client = bigquery.Client(project=project_id)

    def fetch_campaign_aov_data(self, lookback_days: int = 30) -> Dict[str, Dict[str, Any]]:
        """
        Fetch campaign-level AOV data from BigQuery.

        Args:
            lookback_days: Number of days to look back (default: 30)

        Returns:
            Dictionary mapping campaign_id (as string) to AOV metrics
        """
        logger.info("Fetching campaign AOV data from BigQuery...")

        # Use CAST to ensure campaign_id is STRING to avoid type mismatch errors
        query = f"""
        SELECT 
            CAST(campaign_id AS STRING) as campaign_id,
            campaign_name,
            SUM(sales) as total_sales,
            SUM(CAST(conversions AS FLOAT64)) as total_conversions,
            CASE 
                WHEN SUM(CAST(conversions AS FLOAT64)) > 0 
                THEN SUM(sales) / SUM(CAST(conversions AS FLOAT64))
                ELSE 0 
            END as aov,
            COUNT(*) as row_count
        FROM `{self.project_id}.{self.dataset_id}.campaign_performance`
        WHERE DATE(report_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_days} DAY)
        GROUP BY CAST(campaign_id AS STRING), campaign_name
        HAVING total_conversions > 0
        """

        try:
            query_job = self.client.query(query)
            results = query_job.result()

            campaign_data = {}
            for row in results:
                campaign_id = str(row.campaign_id)  # Ensure string type
                campaign_data[campaign_id] = {
                    "campaign_name": row.campaign_name,
                    "total_sales": float(row.total_sales or 0),
                    "total_conversions": float(row.total_conversions or 0),
                    "aov": float(row.aov or 0),
                    "row_count": int(row.row_count or 0),
                }

            return campaign_data

        except Exception as e:
            logger.error(f"Error fetching campaign AOV data: {e}")
            raise

    def fetch_keyword_performance(
        self, 
        campaign_ids: Optional[List[str]] = None,
        lookback_days: int = 30,
        min_clicks: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch keyword performance data from BigQuery with proper type handling.

        Args:
            campaign_ids: List of campaign IDs to filter (as strings)
            lookback_days: Number of days to look back (default: 30)
            min_clicks: Minimum clicks to consider (default: 10)

        Returns:
            List of keyword performance dictionaries
        """
        logger.info("Fetching keyword performance data from BigQuery...")

        # Build campaign filter with proper type casting
        campaign_filter = ""
        if campaign_ids:
            # Ensure campaign IDs are strings and properly quoted
            campaign_ids_str = ", ".join([f"'{str(cid)}'" for cid in campaign_ids])
            campaign_filter = f"AND CAST(campaign_id AS STRING) IN ({campaign_ids_str})"

        # Use CAST for all ID columns to ensure consistent STRING types
        query = f"""
        SELECT 
            CAST(campaign_id AS STRING) as campaign_id,
            campaign_name,
            CAST(ad_group_id AS STRING) as ad_group_id,
            ad_group_name,
            CAST(keyword_id AS STRING) as keyword_id,
            keyword_text,
            match_type,
            SUM(clicks) as clicks,
            SUM(impressions) as impressions,
            SUM(cost) as cost,
            SUM(sales) as sales,
            SUM(CAST(conversions AS FLOAT64)) as conversions,
            CASE 
                WHEN SUM(sales) > 0 
                THEN SUM(cost) / SUM(sales)
                ELSE 0 
            END as acos,
            CASE 
                WHEN SUM(clicks) > 0 
                THEN SUM(cost) / SUM(clicks)
                ELSE 0 
            END as cpc,
            current_bid
        FROM `{self.project_id}.{self.dataset_id}.keyword_performance`
        WHERE DATE(report_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_days} DAY)
        {campaign_filter}
        GROUP BY CAST(campaign_id AS STRING), campaign_name, CAST(ad_group_id AS STRING), ad_group_name, 
                 CAST(keyword_id AS STRING), keyword_text, match_type, current_bid
        HAVING clicks >= {min_clicks}
        ORDER BY clicks DESC
        """

        try:
            query_job = self.client.query(query)
            results = query_job.result()

            keywords = []
            for row in results:
                keywords.append({
                    "campaign_id": str(row.campaign_id),
                    "campaign_name": row.campaign_name,
                    "ad_group_id": str(row.ad_group_id),
                    "ad_group_name": row.ad_group_name,
                    "keyword_id": str(row.keyword_id),
                    "keyword_text": row.keyword_text,
                    "match_type": row.match_type,
                    "clicks": int(row.clicks or 0),
                    "impressions": int(row.impressions or 0),
                    "cost": float(row.cost or 0),
                    "sales": float(row.sales or 0),
                    "conversions": float(row.conversions or 0),
                    "acos": float(row.acos or 0),
                    "cpc": float(row.cpc or 0),
                    "current_bid": float(row.current_bid or 0),
                })

            return keywords

        except Exception as e:
            logger.error(f"Error fetching keyword performance data: {e}")
            raise

    def get_aggregated_aov_stats(self, lookback_days_list: List[int] = None) -> Dict[str, int]:
        """
        Get aggregated AOV statistics for different time periods.

        Args:
            lookback_days_list: List of lookback periods (default: [1, 14, 30])

        Returns:
            Dictionary with counts for each period: {"agg": X, "14d": Y, "30d": Z}
        """
        if lookback_days_list is None:
            lookback_days_list = [1, 14, 30]

        stats = {}
        
        # Overall aggregate
        try:
            agg_query = f"""
            SELECT COUNT(DISTINCT CAST(campaign_id AS STRING)) as count
            FROM `{self.project_id}.{self.dataset_id}.campaign_performance`
            WHERE DATE(report_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            """
            result = self.client.query(agg_query).result()
            stats["agg"] = next(result).count or 0
        except Exception:
            stats["agg"] = 0

        # Per-period counts
        for days in lookback_days_list:
            if days == 1:
                continue  # Skip 1-day period (not included in stats)
            
            key = f"{days}d"
            try:
                query = f"""
                SELECT COUNT(DISTINCT CAST(campaign_id AS STRING)) as count
                FROM `{self.project_id}.{self.dataset_id}.campaign_performance`
                WHERE DATE(report_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
                """
                result = self.client.query(query).result()
                stats[key] = next(result).count or 0
            except Exception:
                stats[key] = 0

        return stats
