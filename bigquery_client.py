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

import base64
import logging
import json
import os
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google.oauth2 import service_account
from google.api_core import exceptions as core_exceptions

# Import centralized credential loading
from gcp_credentials import load_credentials

logger = logging.getLogger(__name__)


RUN_EVENTS_TABLE = "optimizer_run_events"
RUN_EVENTS_SCHEMA = [
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("details", "STRING"),
]


def _normalise_timestamp(value: Optional[datetime]) -> Optional[datetime]:
    """Convert BigQuery timestamps to naive UTC datetimes."""
    if not isinstance(value, datetime):
        return None

    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    return value


class BigQueryClient:
    """
    Client for writing PPC optimization data to BigQuery

    Features:
    - Auto-creates dataset and tables if needed
    - Streams data in real-time
    - Handles schema validation
    - Provides error handling and retry logic
    """

    def __init__(
        self,
        project_id: str,
        dataset_id: Optional[str] = None,
        location: Optional[str] = None,
    ):
        """
        Initialize BigQuery client

        Args:
            project_id: Google Cloud project ID
            dataset_id: BigQuery dataset ID
                        (default: env(BQ_DATASET_ID / BIGQUERY_DATASET(_ID)) or 'ppc_data')
            location: BigQuery dataset location
                      (default: env(BQ_LOCATION / BIGQUERY_LOCATION) or 'US')
        """
        self.project_id = project_id

        # Allow overrides via env vars, then fall back to your real dataset.
        env_dataset = (
            os.getenv("BQ_DATASET_ID")
            or os.getenv("BIGQUERY_DATASET")
            or os.getenv("BIGQUERY_DATASET_ID")
        )
        env_location = os.getenv("BQ_LOCATION") or os.getenv("BIGQUERY_LOCATION")

        # Your actual dataset + location defaults
        self.dataset_id = dataset_id or env_dataset or "ppc_data"
        self.location = location or env_location or "US"

        credentials = self._resolve_credentials()
        if credentials:
            logger.info("Using explicit service account credentials for BigQuery client")
            self.client = bigquery.Client(project=project_id, credentials=credentials)
        else:
            logger.debug("Using Application Default Credentials for BigQuery client")
            self.client = bigquery.Client(project=project_id)

        self.dataset_ref = f"{project_id}.{self.dataset_id}"

        # Ensure dataset exists
        self._ensure_dataset_exists()

    def _resolve_credentials(self) -> Optional[service_account.Credentials]:
        """
        Resolve service account credentials.

        Precedence:
        1. Centralized load_credentials()
        2. JSON / base64 JSON from env:
           - GCP_SERVICE_ACCOUNT_KEY
           - GOOGLE_APPLICATION_CREDENTIALS_JSON
        3. Service account JSON file via GOOGLE_APPLICATION_CREDENTIALS
        4. Secret Manager via GCP_SERVICE_ACCOUNT_SECRET_NAME
        5. Fall back to Application Default Credentials (return None)
        """
        # 1) Central helper
        try:
            creds = load_credentials()
            if creds:
                logger.info("Loaded credentials via gcp_credentials.load_credentials()")
                return creds
        except Exception as exc:
            logger.warning("load_credentials() failed: %s", exc)

        # Helper: parse JSON or base64 JSON from a raw string
        def _creds_from_raw_json_or_b64(raw: str, source: str):
            if not raw:
                return None

            text = raw.strip()
            # Try plain JSON first
            try:
                info = json.loads(text)
                logger.info("Parsed service account JSON from %s", source)
                return service_account.Credentials.from_service_account_info(info)
            except Exception:
                pass

            # Try base64-decode → JSON
            try:
                decoded = base64.b64decode(text).decode("utf-8")
                info = json.loads(decoded)
                logger.info("Parsed base64-encoded service account JSON from %s", source)
                return service_account.Credentials.from_service_account_info(info)
            except Exception as exc:
                logger.warning(
                    "Failed to parse credentials from %s as JSON or base64 JSON: %s",
                    source,
                    exc,
                )
                return None

        # 2) Env JSON / base64 JSON
        env_raw = (
            os.getenv("GCP_SERVICE_ACCOUNT_KEY")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        )
        if env_raw:
            creds = _creds_from_raw_json_or_b64(
                env_raw, "GCP_SERVICE_ACCOUNT_KEY / GOOGLE_APPLICATION_CREDENTIALS_JSON"
            )
            if creds:
                return creds

        # 3) File path (GOOGLE_APPLICATION_CREDENTIALS)
        path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if path and os.path.isfile(path):
            try:
                logger.info("Loading credentials from file path GOOGLE_APPLICATION_CREDENTIALS=%s", path)
                return service_account.Credentials.from_service_account_file(path)
            except Exception as exc:
                logger.warning(
                    "Failed to load credentials from file %s: %s", path, exc
                )

        # 4) Secret Manager (GCP_SERVICE_ACCOUNT_SECRET_NAME)
        secret_name = os.getenv("GCP_SERVICE_ACCOUNT_SECRET_NAME")
        if secret_name:
            try:
                from google.cloud import secretmanager  # lazy import

                client = secretmanager.SecretManagerServiceClient()

                # If just a secret ID is given, build the resource path
                if "/secrets/" not in secret_name:
                    project_for_secret = (
                        self.project_id
                        or os.getenv("GCP_PROJECT")
                        or os.getenv("GOOGLE_CLOUD_PROJECT")
                    )
                    if project_for_secret:
                        secret_name = f"projects/{project_for_secret}/secrets/{secret_name}/versions/latest"
                    else:
                        logger.warning(
                            "GCP_SERVICE_ACCOUNT_SECRET_NAME set but no project ID to build resource path"
                        )

                logger.info("Fetching service account JSON from Secret Manager: %s", secret_name)
                response = client.access_secret_version(name=secret_name)
                payload = response.payload.data.decode("utf-8")
                creds = _creds_from_raw_json_or_b64(payload, "Secret Manager")
                if creds:
                    return creds
            except Exception as exc:
                logger.warning("Failed to load credentials from Secret Manager: %s", exc)

        # 5) Fall back to ADC
        logger.info(
            "No explicit service account credentials resolved; using Application Default Credentials"
        )
        return None

    def _ensure_dataset_exists(self):
        """Create dataset if it doesn't exist."""
        try:
            dataset = self.client.get_dataset(self.dataset_ref)
            logger.info(
                "Dataset %s exists in location %s",
                self.dataset_ref,
                getattr(dataset, "location", "unknown"),
            )
        except NotFound:
            logger.info(
                "Dataset %s not found. Creating it in location %s",
                self.dataset_ref,
                self.location,
            )
            dataset = bigquery.Dataset(self.dataset_ref)
            dataset.location = self.location
            dataset.description = "Amazon PPC Optimization data"
            self.client.create_dataset(dataset, timeout=30)
            logger.info("Created dataset %s", self.dataset_ref)

    def _ensure_table_exists(self, table_id: str, schema: List[bigquery.SchemaField]):
        """Create table if it doesn't exist"""
        table_ref = f"{self.dataset_ref}.{table_id}"
        try:
            self.client.get_table(table_ref)
            logger.debug("Table %s exists", table_ref)
        except NotFound:
            logger.info("Creating table %s", table_ref)
            table = bigquery.Table(table_ref, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp",
            )
            self.client.create_table(table, timeout=30)
            logger.info("Created table %s", table_ref)

    def write_optimization_results(self, results_data: Dict) -> bool:
        """
        Write optimization results to BigQuery

        Args:
            results_data: Complete results payload from dashboard_client

        Returns:
            True if successful, False otherwise
        """
        try:
            # Define schema for optimization_results table with enhanced fields
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
                # Enhanced fields for complete data from DATA_FLOW_SUMMARY.md
                bigquery.SchemaField("campaigns", "JSON"),
                bigquery.SchemaField("top_performers", "JSON"),
                bigquery.SchemaField("features", "JSON"),
                bigquery.SchemaField("config_snapshot", "JSON"),
            ]

            self._ensure_table_exists("optimization_results", schema)

            # Flatten the data for BigQuery
            summary = results_data.get("summary", {})
            config = results_data.get("config_snapshot", {})

            # Ensure REPEATED fields are properly formatted as lists
            enabled_features = config.get("enabled_features", [])
            if not isinstance(enabled_features, list):
                enabled_features = [str(enabled_features)]

            errors = results_data.get("errors", [])
            if not isinstance(errors, list):
                errors = []
            errors = [str(e) for e in errors]

            warnings = results_data.get("warnings", [])
            if not isinstance(warnings, list):
                warnings = []
            warnings = [str(w) for w in warnings]

            row = {
                "timestamp": results_data.get("timestamp", datetime.now().isoformat()),
                "run_id": results_data.get("run_id"),
                "status": results_data.get("status", "success"),
                "profile_id": results_data.get("profile_id", ""),
                "dry_run": results_data.get("dry_run", False),
                "duration_seconds": results_data.get("duration_seconds", 0),
                "campaigns_analyzed": summary.get("campaigns_analyzed", 0),
                "keywords_optimized": summary.get("keywords_optimized", 0),
                "bids_increased": summary.get("bids_increased", 0),
                "bids_decreased": summary.get("bids_decreased", 0),
                "negative_keywords_added": summary.get(
                    "negative_keywords_added", 0
                ),
                "budget_changes": summary.get("budget_changes", 0),
                "total_spend": summary.get("total_spend", 0.0),
                "total_sales": summary.get("total_sales", 0.0),
                "average_acos": summary.get("average_acos", 0.0),
                "target_acos": config.get("target_acos", 0.0),
                "lookback_days": config.get("lookback_days", 0),
                "enabled_features": enabled_features,
                "errors": errors,
                "warnings": warnings,
                # Enhanced fields - store as JSON strings for BigQuery JSON type
                "campaigns": json.dumps(results_data.get("campaigns", [])),
                "top_performers": json.dumps(results_data.get("top_performers", [])),
                "features": json.dumps(results_data.get("features", {})),
                "config_snapshot": json.dumps(
                    results_data.get("config_snapshot", {})
                ),
            }

            # Insert row
            table_ref = f"{self.dataset_ref}.optimization_results"
            errors = self.client.insert_rows_json(table_ref, [row])

            if errors:
                logger.error("Error inserting rows to BigQuery: %s", errors)
                return False

            logger.info(
                "Successfully wrote optimization results to BigQuery (run_id: %s)",
                row["run_id"],
            )

            # Also write detailed campaign data
            self._write_campaign_details(results_data)

            return True

        except Exception as e:
            logger.error("Failed to write to BigQuery: %s", str(e))
            logger.error(traceback.format_exc())
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

            campaigns = results_data.get("campaigns", [])
            if not campaigns:
                return

            rows = []
            timestamp = results_data.get("timestamp", datetime.now().isoformat())
            run_id = results_data.get("run_id")

            for campaign in campaigns:
                row = {
                    "timestamp": timestamp,
                    "run_id": run_id,
                    "campaign_id": campaign.get("campaign_id", ""),
                    "campaign_name": campaign.get("name", ""),
                    "spend": campaign.get("spend", 0.0),
                    "sales": campaign.get("sales", 0.0),
                    "acos": campaign.get("acos", 0.0),
                    "impressions": campaign.get("impressions", 0),
                    "clicks": campaign.get("clicks", 0),
                    "conversions": campaign.get("conversions", 0),
                    "budget": campaign.get("budget", 0.0),
                    "status": campaign.get("status", ""),
                }
                rows.append(row)

            table_ref = f"{self.dataset_ref}.campaign_details"
            errors = self.client.insert_rows_json(table_ref, rows)

            if errors:
                logger.error("Error inserting campaign details to BigQuery: %s", errors)
            else:
                logger.info(
                    "Successfully wrote %d campaign details to BigQuery", len(rows)
                )

        except Exception as e:
            logger.error("Failed to write campaign details to BigQuery: %s", str(e))

    def insert_campaign_budgets(
        self, budget_data: List[Dict[str, Any]], run_id: str
    ) -> bool:
        """
        Insert campaign budget data into BigQuery campaign_details table

        This method populates the campaign_details table with budget information
        fetched from the Amazon Advertising API. It's designed to run independently
        of the optimization results to ensure budget data is always current.

        Args:
            budget_data: List of campaign budget dictionaries from API.fetch_campaign_budgets()
            run_id: Unique identifier for this data collection run

        Returns:
            True if successful, False otherwise
        """
        try:
            if not budget_data:
                logger.warning("No budget data to insert")
                return False

            # Use the same schema as campaign_details table
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

            rows = []
            timestamp = datetime.now(timezone.utc).isoformat()

            for campaign in budget_data:
                row = {
                    "timestamp": timestamp,
                    "run_id": run_id,
                    "campaign_id": campaign.get("campaign_id", ""),
                    "campaign_name": campaign.get("campaign_name", ""),
                    "spend": 0.0,  # Will be populated by performance data
                    "sales": 0.0,  # Will be populated by performance data
                    "acos": 0.0,  # Will be populated by performance data
                    "impressions": 0,  # Will be populated by performance data
                    "clicks": 0,  # Will be populated by performance data
                    "conversions": 0,  # Will be populated by performance data
                    "budget": float(campaign.get("daily_budget", 0.0)),
                    "status": campaign.get("state", ""),
                }
                rows.append(row)

            table_ref = f"{self.dataset_ref}.campaign_details"
            errors = self.client.insert_rows_json(table_ref, rows)

            if errors:
                logger.error("Error inserting campaign budgets to BigQuery: %s", errors)
                return False

            logger.info(
                "✅ Successfully inserted %d campaign budgets into BigQuery", len(rows)
            )
            return True

        except Exception as e:
            logger.error("Failed to insert campaign budgets to BigQuery: %s", str(e))
            logger.error(traceback.format_exc())
            return False

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
                "timestamp": progress_data.get(
                    "timestamp", datetime.now().isoformat()
                ),
                "run_id": progress_data.get("run_id"),
                "status": progress_data.get("status", "running"),
                "message": progress_data.get("message", ""),
                "percent_complete": progress_data.get("percent_complete", 0.0),
                "profile_id": progress_data.get("profile_id", ""),
            }

            table_ref = f"{self.dataset_ref}.optimization_progress"
            errors = self.client.insert_rows_json(table_ref, [row])

            if errors:
                logger.error("Error inserting progress update to BigQuery: %s", errors)
                return False

            return True

        except Exception as e:
            logger.error("Failed to write progress update to BigQuery: %s", str(e))
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

            error_info = error_data.get("error", {})

            row = {
                "timestamp": error_data.get("timestamp", datetime.now().isoformat()),
                "run_id": error_data.get("run_id"),
                "status": error_data.get("status", "failed"),
                "profile_id": error_data.get("profile_id", ""),
                "error_type": error_info.get("type", ""),
                "error_message": error_info.get("message", ""),
                "traceback": error_info.get("traceback", ""),
                "context": json.dumps(error_info.get("context", {})),
            }

            table_ref = f"{self.dataset_ref}.optimization_errors"
            errors = self.client.insert_rows_json(table_ref, [row])

            if errors:
                logger.error("Error inserting error log to BigQuery: %s", errors)
                return False

            logger.info(
                "Successfully wrote error log to BigQuery (run_id: %s)", row["run_id"]
            )
            return True

        except Exception as e:
            logger.error("Failed to write error to BigQuery: %s", str(e))
            return False

    def record_run_event(
        self, run_id: str, status: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record lifecycle events for optimizer runs."""

        if not run_id or not status:
            logger.debug("Skipping run event record - run_id or status missing")
            return

        try:
            self._ensure_table_exists(RUN_EVENTS_TABLE, RUN_EVENTS_SCHEMA)

            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": str(run_id),
                "status": str(status),
                "details": json.dumps(details, default=str) if details else None,
            }

            table_ref = f"{self.dataset_ref}.{RUN_EVENTS_TABLE}"
            errors = self.client.insert_rows_json(table_ref, [payload])

            if errors:
                logger.warning("Error inserting run event to BigQuery: %s", errors)
        except Exception as exc:
            logger.debug("Failed to record run event in BigQuery: %s", exc)

    def _execute_single_timestamp_query(
        self,
        query: str,
        job_config: Optional[bigquery.QueryJobConfig] = None,
    ) -> Optional[datetime]:
        """Execute a query expected to return a single timestamp column."""

        try:
            job = self.client.query(query, job_config=job_config)
            result = job.result(timeout=30)

            for row in result:
                candidate = getattr(row, "last_run", None)
                normalised = _normalise_timestamp(candidate)
                if normalised:
                    return normalised

        except (core_exceptions.NotFound, NotFound):
            logger.debug("Query target not found for timestamp query: %s", query)
        except core_exceptions.BadRequest as exc:
            logger.warning("Bad request when executing timestamp query: %s", exc)
        except Exception as exc:
            logger.warning("Failed to execute timestamp query: %s", exc)

        return None

    def get_last_run_event_timestamp(
        self, statuses: Optional[List[str]] = None
    ) -> Optional[datetime]:
        """Return the timestamp of the most recent run event."""

        table_ref = f"`{self.dataset_ref}.{RUN_EVENTS_TABLE}`"
        query = f"SELECT MAX(timestamp) AS last_run FROM {table_ref}"
        job_config = None

        if statuses:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("statuses", "STRING", statuses)
                ]
            )
            query += " WHERE status IN UNNEST(@statuses)"

        return self._execute_single_timestamp_query(query, job_config)

    def get_last_result_timestamp(
        self, statuses: Optional[List[str]] = None
    ) -> Optional[datetime]:
        """Return the timestamp of the most recent optimizer result."""

        table_ref = f"`{self.dataset_ref}.optimization_results`"
        query = f"SELECT MAX(timestamp) AS last_run FROM {table_ref}"
        job_config = None

        if statuses:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("statuses", "STRING", statuses)
                ]
            )
            query += " WHERE status IN UNNEST(@statuses)"

        return self._execute_single_timestamp_query(query, job_config)
