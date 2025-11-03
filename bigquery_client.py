"""
BigQuery Client Module
=======================

Handles writing optimization data to BigQuery for dashboard analytics and reporting.

This module:
- Writes optimization results to BigQuery tables
- Creates tables/datasets if they don't exist
- Handles schema evolution
- Provides data validation and error handling

Author: Nature's Way Soil
Version: 1.0.0
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

logger = logging.getLogger(__name__)


class BigQueryClient:
    """
    Client for writing PPC optimization data to BigQuery
    
    Features:
    - Auto-creates dataset and tables if needed
    - Streams data in real-time
    - Handles schema validation
    - Provides error handling and retry logic
    """
    
    def __init__(self, project_id: str, dataset_id: str = 'amazon_ppc', 
                 location: str = 'us-east4'):
        """
        Initialize BigQuery client
        
        Args:
            project_id: Google Cloud project ID
            dataset_id: BigQuery dataset ID (default: amazon_ppc)
            location: BigQuery dataset location (default: us-east4)
        """
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.location = location
        self.client = bigquery.Client(project=project_id)
        self.dataset_ref = f"{project_id}.{dataset_id}"
        
        # Ensure dataset exists
        self._ensure_dataset_exists()
    
    def _ensure_dataset_exists(self):
        """Create dataset if it doesn't exist"""
        try:
            self.client.get_dataset(self.dataset_ref)
            logger.info(f"Dataset {self.dataset_ref} exists")
        except NotFound:
            logger.info(f"Creating dataset {self.dataset_ref}")
            dataset = bigquery.Dataset(self.dataset_ref)
            dataset.location = self.location
            dataset.description = "Amazon PPC Optimization data"
            self.client.create_dataset(dataset, timeout=30)
            logger.info(f"Created dataset {self.dataset_ref}")
    
    def _ensure_table_exists(self, table_id: str, schema: List[bigquery.SchemaField]):
        """Create table if it doesn't exist"""
        table_ref = f"{self.dataset_ref}.{table_id}"
        try:
            self.client.get_table(table_ref)
            logger.debug(f"Table {table_ref} exists")
        except NotFound:
            logger.info(f"Creating table {table_ref}")
            table = bigquery.Table(table_ref, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )
            self.client.create_table(table, timeout=30)
            logger.info(f"Created table {table_ref}")
    
    def write_optimization_results(self, results_data: Dict) -> bool:
        """
        Write optimization results to BigQuery
        
        Args:
            results_data: Complete results payload from dashboard_client
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Define schema for optimization_results table
            schema = [
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("profile_id", "STRING"),
                bigquery.SchemaField("dry_run", "BOOLEAN"),
                bigquery.SchemaField("duration_seconds", "FLOAT"),
                bigquery.SchemaField("campaigns_analyzed", "INTEGER"),
                bigquery.SchemaField("keywords_optimized", "INTEGER"),
                bigquery.SchemaField("bids_increased", "INTEGER"),
                bigquery.SchemaField("bids_decreased", "INTEGER"),
                bigquery.SchemaField("negative_keywords_added", "INTEGER"),
                bigquery.SchemaField("budget_changes", "INTEGER"),
                bigquery.SchemaField("total_spend", "FLOAT"),
                bigquery.SchemaField("total_sales", "FLOAT"),
                bigquery.SchemaField("average_acos", "FLOAT"),
                bigquery.SchemaField("target_acos", "FLOAT"),
                bigquery.SchemaField("lookback_days", "INTEGER"),
                bigquery.SchemaField("enabled_features", "STRING", mode="REPEATED"),
                bigquery.SchemaField("errors", "STRING", mode="REPEATED"),
                bigquery.SchemaField("warnings", "STRING", mode="REPEATED"),
            ]
            
            self._ensure_table_exists("optimization_results", schema)
            
            # Flatten the data for BigQuery
            summary = results_data.get('summary', {})
            config = results_data.get('config_snapshot', {})
            
            row = {
                "timestamp": results_data.get('timestamp', datetime.now().isoformat()),
                "run_id": results_data.get('run_id'),
                "status": results_data.get('status', 'success'),
                "profile_id": results_data.get('profile_id', ''),
                "dry_run": results_data.get('dry_run', False),
                "duration_seconds": results_data.get('duration_seconds', 0),
                "campaigns_analyzed": summary.get('campaigns_analyzed', 0),
                "keywords_optimized": summary.get('keywords_optimized', 0),
                "bids_increased": summary.get('bids_increased', 0),
                "bids_decreased": summary.get('bids_decreased', 0),
                "negative_keywords_added": summary.get('negative_keywords_added', 0),
                "budget_changes": summary.get('budget_changes', 0),
                "total_spend": summary.get('total_spend', 0.0),
                "total_sales": summary.get('total_sales', 0.0),
                "average_acos": summary.get('average_acos', 0.0),
                "target_acos": config.get('target_acos', 0.0),
                "lookback_days": config.get('lookback_days', 0),
                "enabled_features": config.get('enabled_features', []),
                "errors": [str(e) for e in results_data.get('errors', [])],
                "warnings": [str(w) for w in results_data.get('warnings', [])],
            }
            
            # Insert row
            table_ref = f"{self.dataset_ref}.optimization_results"
            errors = self.client.insert_rows_json(table_ref, [row])
            
            if errors:
                logger.error(f"Error inserting rows to BigQuery: {errors}")
                return False
            
            logger.info(f"Successfully wrote optimization results to BigQuery (run_id: {row['run_id']})")
            
            # Also write detailed campaign data
            self._write_campaign_details(results_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to write to BigQuery: {str(e)}")
            return False
    
    def _write_campaign_details(self, results_data: Dict):
        """Write detailed campaign-level data"""
        try:
            schema = [
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("campaign_id", "STRING"),
                bigquery.SchemaField("campaign_name", "STRING"),
                bigquery.SchemaField("spend", "FLOAT"),
                bigquery.SchemaField("sales", "FLOAT"),
                bigquery.SchemaField("acos", "FLOAT"),
                bigquery.SchemaField("impressions", "INTEGER"),
                bigquery.SchemaField("clicks", "INTEGER"),
                bigquery.SchemaField("conversions", "INTEGER"),
                bigquery.SchemaField("budget", "FLOAT"),
                bigquery.SchemaField("status", "STRING"),
            ]
            
            self._ensure_table_exists("campaign_details", schema)
            
            campaigns = results_data.get('campaigns', [])
            if not campaigns:
                return
            
            rows = []
            timestamp = results_data.get('timestamp', datetime.now().isoformat())
            run_id = results_data.get('run_id')
            
            for campaign in campaigns:
                row = {
                    "timestamp": timestamp,
                    "run_id": run_id,
                    "campaign_id": campaign.get('campaign_id', ''),
                    "campaign_name": campaign.get('name', ''),
                    "spend": campaign.get('spend', 0.0),
                    "sales": campaign.get('sales', 0.0),
                    "acos": campaign.get('acos', 0.0),
                    "impressions": campaign.get('impressions', 0),
                    "clicks": campaign.get('clicks', 0),
                    "conversions": campaign.get('conversions', 0),
                    "budget": campaign.get('budget', 0.0),
                    "status": campaign.get('status', ''),
                }
                rows.append(row)
            
            table_ref = f"{self.dataset_ref}.campaign_details"
            errors = self.client.insert_rows_json(table_ref, rows)
            
            if errors:
                logger.error(f"Error inserting campaign details to BigQuery: {errors}")
            else:
                logger.info(f"Successfully wrote {len(rows)} campaign details to BigQuery")
                
        except Exception as e:
            logger.error(f"Failed to write campaign details to BigQuery: {str(e)}")
    
    def write_progress_update(self, progress_data: Dict) -> bool:
        """
        Write optimization progress update to BigQuery
        
        Args:
            progress_data: Progress update payload
            
        Returns:
            True if successful, False otherwise
        """
        try:
            schema = [
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("status", "STRING"),
                bigquery.SchemaField("message", "STRING"),
                bigquery.SchemaField("percent_complete", "FLOAT"),
                bigquery.SchemaField("profile_id", "STRING"),
            ]
            
            self._ensure_table_exists("optimization_progress", schema)
            
            row = {
                "timestamp": progress_data.get('timestamp', datetime.now().isoformat()),
                "run_id": progress_data.get('run_id'),
                "status": progress_data.get('status', 'running'),
                "message": progress_data.get('message', ''),
                "percent_complete": progress_data.get('percent_complete', 0.0),
                "profile_id": progress_data.get('profile_id', ''),
            }
            
            table_ref = f"{self.dataset_ref}.optimization_progress"
            errors = self.client.insert_rows_json(table_ref, [row])
            
            if errors:
                logger.error(f"Error inserting progress update to BigQuery: {errors}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to write progress update to BigQuery: {str(e)}")
            return False
    
    def write_error(self, error_data: Dict) -> bool:
        """
        Write optimization error to BigQuery
        
        Args:
            error_data: Error data payload
            
        Returns:
            True if successful, False otherwise
        """
        try:
            schema = [
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("status", "STRING"),
                bigquery.SchemaField("profile_id", "STRING"),
                bigquery.SchemaField("error_type", "STRING"),
                bigquery.SchemaField("error_message", "STRING"),
                bigquery.SchemaField("traceback", "STRING"),
                bigquery.SchemaField("context", "STRING"),
            ]
            
            self._ensure_table_exists("optimization_errors", schema)
            
            error_info = error_data.get('error', {})
            
            row = {
                "timestamp": error_data.get('timestamp', datetime.now().isoformat()),
                "run_id": error_data.get('run_id'),
                "status": error_data.get('status', 'failed'),
                "profile_id": error_data.get('profile_id', ''),
                "error_type": error_info.get('type', ''),
                "error_message": error_info.get('message', ''),
                "traceback": error_info.get('traceback', ''),
                "context": json.dumps(error_info.get('context', {})),
            }
            
            table_ref = f"{self.dataset_ref}.optimization_errors"
            errors = self.client.insert_rows_json(table_ref, [row])
            
            if errors:
                logger.error(f"Error inserting error log to BigQuery: {errors}")
                return False
            
            logger.info(f"Successfully wrote error log to BigQuery (run_id: {row['run_id']})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write error to BigQuery: {str(e)}")
            return False
