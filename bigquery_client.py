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
import decimal
import logging
import json
import os
import traceback
from datetime import datetime, timezone, date
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

        # Cache table schemas to make read helpers tolerant to schema drift.
        self._table_columns_cache: Dict[str, set] = {}

        # Ensure dataset exists
        self._ensure_dataset_exists()

    def _get_table_columns(self, table_id: str) -> set:
        """Return a cached set of column names for the given table."""

        cached = self._table_columns_cache.get(table_id)
        if cached is not None:
            return cached

        table_ref = f"{self.dataset_ref}.{table_id}"
        try:
            table = self.client.get_table(table_ref)
            cols = {field.name for field in table.schema}
            self._table_columns_cache[table_id] = cols
            return cols
        except Exception as exc:
            logger.warning("Failed to read schema for %s: %s", table_ref, exc)
            self._table_columns_cache[table_id] = set()
            return set()

    def _select_existing_fields(self, table_id: str, desired_fields: List[str]) -> List[str]:
        """Filter desired fields down to those that exist in BigQuery.

        This prevents query failures when the production schema is missing newer
        columns.
        """

        available = self._get_table_columns(table_id)
        selected = [field for field in desired_fields if field in available]
        if selected:
            return selected

        # Fallback to a minimal set if possible.
        fallback = [
            field
            for field in ("timestamp", "run_id", "status", "profile_id")
            if field in available
        ]
        return fallback or ["*"]

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

    def _ensure_table_schema(self, table_id: str, desired_schema: List[bigquery.SchemaField]) -> None:
        """Ensure an existing table contains (at least) the desired fields.

        BigQuery allows adding new nullable/repeated columns. This enables safe
        schema evolution so historical tables created with an older schema don't
        break newer writers/readers.
        """

        table_ref = f"{self.dataset_ref}.{table_id}"
        try:
            table = self.client.get_table(table_ref)
        except NotFound:
            return
        except Exception as exc:
            logger.warning("Failed to fetch table for schema check %s: %s", table_ref, exc)
            return

        existing = {field.name: field for field in (table.schema or [])}
        to_add: List[bigquery.SchemaField] = []
        for field in desired_schema:
            if field.name not in existing:
                to_add.append(field)

        if not to_add:
            return

        logger.info(
            "Updating BigQuery schema for %s; adding fields: %s",
            table_ref,
            ", ".join(f.name for f in to_add),
        )

        table.schema = list(table.schema or []) + to_add
        try:
            self.client.update_table(table, ["schema"], timeout=30)
            # Invalidate schema cache.
            self._table_columns_cache.pop(table_id, None)
        except Exception as exc:
            logger.warning("Failed to update schema for %s: %s", table_ref, exc)

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
            self._ensure_table_schema("optimization_results", schema)

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
                # Enhanced fields - write as native JSON values.
                "campaigns": results_data.get("campaigns", []),
                "top_performers": results_data.get("top_performers", []),
                "features": results_data.get("features", {}),
                "config_snapshot": results_data.get("config_snapshot", {}),
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

    def _safe_json_loads(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return json.loads(text)
            except Exception:
                return value
        return value

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        """Convert a BigQuery Row into a JSON-serializable dict."""

        def _jsonify(value: Any) -> Any:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, date):
                return value.isoformat()
            if isinstance(value, decimal.Decimal):
                try:
                    return float(value)
                except Exception:
                    return str(value)
            if isinstance(value, (bytes, bytearray)):
                return base64.b64encode(value).decode("utf-8")
            if isinstance(value, dict):
                return {k: _jsonify(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [_jsonify(v) for v in value]
            return value

        result: Dict[str, Any] = {}
        for key in row.keys():
            result[key] = _jsonify(row.get(key))
        return result

    def fetch_latest_optimization_result(
        self,
        profile_id: Optional[str] = None,
        include_payload_json: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent optimization result row (optionally filtered)."""

        table_id = "optimization_results"
        table_ref = f"`{self.dataset_ref}.{table_id}`"
        desired_fields = [
            "timestamp",
            "run_id",
            "status",
            "profile_id",
            "dry_run",
            "duration_seconds",
            "campaigns_analyzed",
            "keywords_optimized",
            "bids_increased",
            "bids_decreased",
            "negative_keywords_added",
            "budget_changes",
            "total_spend",
            "total_sales",
            "average_acos",
            "target_acos",
            "lookback_days",
            "enabled_features",
            "errors",
            "warnings",
        ]

        payload_field = None
        if include_payload_json:
            desired_fields += ["campaigns", "top_performers", "features", "config_snapshot"]

            # Back-compat: older tables may store a single JSON/string payload.
            available = self._get_table_columns(table_id)
            for candidate in (
                "payload",
                "payload_json",
                "results",
                "results_json",
                "result_json",
                "raw_results",
            ):
                if candidate in available:
                    payload_field = candidate
                    desired_fields.append(candidate)
                    break

        select_fields = self._select_existing_fields(table_id, desired_fields)

        query = (
            f"SELECT {', '.join(select_fields)} "
            f"FROM {table_ref} "
            "WHERE (@profile_id IS NULL OR profile_id = @profile_id) "
            "ORDER BY (profile_id IS NULL OR profile_id = '') ASC, timestamp DESC "
            "LIMIT 1"
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("profile_id", "STRING", profile_id)
            ]
        )

        try:
            job = self.client.query(query, job_config=job_config)
            rows = list(job.result(timeout=30))
            if not rows:
                return None
            data = self._row_to_dict(rows[0])

            if include_payload_json:
                for key in ("campaigns", "top_performers", "features", "config_snapshot"):
                    if key in data:
                        data[key] = self._safe_json_loads(data[key])

                if payload_field and payload_field in data:
                    payload = self._safe_json_loads(data.get(payload_field))
                    if isinstance(payload, dict):
                        for key in ("campaigns", "top_performers", "features", "config_snapshot"):
                            if data.get(key) is None and key in payload:
                                data[key] = payload.get(key)
            return data
        except Exception as exc:
            logger.warning("Failed to fetch latest optimization result: %s", exc)
            return None

    def fetch_daily_overview(
        self,
        days: int = 14,
        profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return day-level metrics for the dashboard.

        Runs/keyword counts come from optimization_results.
        Spend/sales/ACOS come from sp_search_term_metrics when available.
        """

        import datetime

        days = max(1, min(int(days), 365))
        # Last N calendar days including today (UTC), e.g. days=7 -> today..today-6.
        start_date = datetime.datetime.utcnow().date() - datetime.timedelta(days=days - 1)
        results_ref = f"`{self.dataset_ref}.optimization_results`"

        perf_table_id = "sp_search_term_metrics"
        perf_ref = f"`{self.dataset_ref}.{perf_table_id}`"

        keyword_table_id = "keyword_performance"
        keyword_ref = f"`{self.dataset_ref}.{keyword_table_id}`"

        keyword_columns = self._get_table_columns(keyword_table_id)
        keyword_has_profile = "profile_id" in keyword_columns
        keyword_profile_filter = (
            "AND (@profile_id IS NULL OR profile_id = @profile_id)" if keyword_has_profile else ""
        )

        # Prefer sp_search_term_metrics if it has data, but fall back to keyword_performance
        # (cost/conversion_value) for days where the search term metrics table is sparse.
        perf_query = f"""
        WITH runs AS (
            SELECT
                DATE(timestamp) AS day,
                COUNT(1) AS runs,
                SUM(COALESCE(campaigns_analyzed, 0)) AS campaigns_analyzed,
                SUM(COALESCE(keywords_optimized, 0)) AS keywords_optimized,
                SUM(COALESCE(budget_changes, 0)) AS budget_changes
            FROM {results_ref}
            WHERE DATE(timestamp) >= @start_date
                AND (@profile_id IS NULL OR profile_id = @profile_id)
            GROUP BY day
        ),
        perf_stm AS (
            SELECT
                date AS day,
                SUM(COALESCE(cost, 0)) AS total_spend,
                SUM(COALESCE(sales, 0)) AS total_sales
            FROM {perf_ref}
            WHERE date >= @start_date
                AND (@profile_id IS NULL OR profile_id = @profile_id)
            GROUP BY day
        ),
        perf_kw AS (
            SELECT
                day,
                SUM(COALESCE(cost, 0)) AS total_spend,
                SUM(COALESCE(conversion_value, 0)) AS total_sales
            FROM (
                SELECT
                    date AS day,
                    keyword_id,
                    cost,
                    conversion_value,
                    created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY date, keyword_id
                        ORDER BY created_at DESC
                    ) AS rn
                FROM {keyword_ref}
                WHERE date >= @start_date
                    {keyword_profile_filter}
            )
            WHERE rn = 1
            GROUP BY day
        ),
        perf AS (
            SELECT
                COALESCE(s.day, k.day) AS day,
                COALESCE(s.total_spend, k.total_spend, 0) AS total_spend,
                COALESCE(s.total_sales, k.total_sales, 0) AS total_sales
            FROM perf_stm s
            FULL OUTER JOIN perf_kw k
                ON s.day = k.day
        )
        SELECT
            COALESCE(r.day, p.day) AS day,
            COALESCE(r.runs, 0) AS runs,
            COALESCE(p.total_spend, 0) AS total_spend,
            COALESCE(p.total_sales, 0) AS total_sales,
            SAFE_DIVIDE(COALESCE(p.total_spend, 0), NULLIF(COALESCE(p.total_sales, 0), 0)) AS blended_acos,
            COALESCE(r.campaigns_analyzed, 0) AS campaigns_analyzed,
            COALESCE(r.keywords_optimized, 0) AS keywords_optimized,
            COALESCE(r.budget_changes, 0) AS budget_changes
        FROM runs r
        FULL OUTER JOIN perf p
            ON r.day = p.day
        ORDER BY day DESC
        """

        fallback_query = f"""
        SELECT
            DATE(timestamp) AS day,
            COUNT(1) AS runs,
            SUM(COALESCE(total_spend, 0)) AS total_spend,
            SUM(COALESCE(total_sales, 0)) AS total_sales,
            SAFE_DIVIDE(SUM(COALESCE(total_spend, 0)), NULLIF(SUM(COALESCE(total_sales, 0)), 0)) AS blended_acos,
            SUM(COALESCE(campaigns_analyzed, 0)) AS campaigns_analyzed,
            SUM(COALESCE(keywords_optimized, 0)) AS keywords_optimized,
            SUM(COALESCE(budget_changes, 0)) AS budget_changes
        FROM {results_ref}
        WHERE DATE(timestamp) >= @start_date
            AND (@profile_id IS NULL OR profile_id = @profile_id)
        GROUP BY day
        ORDER BY day DESC
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days),
                bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
                bigquery.ScalarQueryParameter("profile_id", "STRING", profile_id),
            ]
        )

        try:
            try:
                job = self.client.query(perf_query, job_config=job_config)
                rows_iter = job.result(timeout=30)
            except Exception as exc:
                logger.warning(
                    "Daily perf query failed; falling back to optimization_results-only aggregation: %s",
                    exc,
                )
                job = self.client.query(fallback_query, job_config=job_config)
                rows_iter = job.result(timeout=30)
            result: List[Dict[str, Any]] = []
            for row in rows_iter:
                data = self._row_to_dict(row)
                day_val = data.get("day")
                if day_val is not None:
                    data["day"] = str(day_val)
                result.append(data)
            return result
        except Exception as exc:
            logger.warning("Failed to fetch daily overview: %s", exc)
            return []

    def fetch_top_performing_keywords(
        self,
        days: int = 30,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return top-performing keywords for the dashboard.

        Uses keyword_performance (deduped by latest created_at per date+keyword_id)
        joined to keywords for keyword_text.
        """

        import datetime

        days = max(1, min(int(days), 365))
        limit = max(1, min(int(limit), 200))
        start_date = datetime.datetime.utcnow().date() - datetime.timedelta(days=days - 1)

        kw_perf_ref = f"`{self.dataset_ref}.keyword_performance`"
        kw_meta_ref = f"`{self.dataset_ref}.keywords`"

        query = f"""
        WITH base AS (
          SELECT
            date,
            keyword_id,
            clicks,
            cost,
            conversion_value,
            created_at,
            ROW_NUMBER() OVER (
              PARTITION BY date, keyword_id
              ORDER BY created_at DESC
            ) AS rn
          FROM {kw_perf_ref}
          WHERE date >= @start_date
        )
        SELECT
          COALESCE(m.keyword_text, CAST(b.keyword_id AS STRING)) AS keyword_text,
          SUM(COALESCE(b.clicks, 0)) AS clicks,
          SUM(COALESCE(b.conversion_value, 0)) AS sales,
          SAFE_DIVIDE(
            SUM(COALESCE(b.cost, 0)),
            NULLIF(SUM(COALESCE(b.conversion_value, 0)), 0)
          ) AS acos
        FROM base b
        LEFT JOIN {kw_meta_ref} m
          ON b.keyword_id = m.keyword_id
        WHERE b.rn = 1
        GROUP BY keyword_text
        ORDER BY sales DESC
        LIMIT @limit
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )

        try:
            job = self.client.query(query, job_config=job_config)
            result: List[Dict[str, Any]] = []
            for row in job.result(timeout=30):
                data = self._row_to_dict(row)
                # Keep payload shape compatible with the Next.js dashboard.
                data.setdefault("bid_change", None)
                result.append(data)
            return result
        except Exception as exc:
            logger.warning("Failed to fetch top performing keywords: %s", exc)
            return []

    def fetch_keyword_discovery_summary(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Return keyword discovery summary for the dashboard.

        Derived from keyword_harvest_log when present.
        """

        import datetime

        days = max(1, min(int(days), 365))
        start_ts = datetime.datetime.utcnow() - datetime.timedelta(days=days)

        harvest_ref = f"`{self.dataset_ref}.keyword_harvest_log`"
        query = f"""
        SELECT
          COUNT(DISTINCT search_term) AS keywords_discovered,
          SUM(CASE WHEN LOWER(action) IN ('created','added') AND NOT COALESCE(dry_run, FALSE) THEN 1 ELSE 0 END) AS keywords_added
        FROM {harvest_ref}
        WHERE harvested_at >= @start_ts
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", start_ts),
            ]
        )

        try:
            job = self.client.query(query, job_config=job_config)
            rows = list(job.result(timeout=30))
            if not rows:
                return {"keywords_discovered": 0, "keywords_added": 0}
            data = self._row_to_dict(rows[0])
            return {
                "keywords_discovered": int(data.get("keywords_discovered") or 0),
                "keywords_added": int(data.get("keywords_added") or 0),
            }
        except Exception as exc:
            logger.warning("Failed to fetch keyword discovery summary: %s", exc)
            return {"keywords_discovered": 0, "keywords_added": 0}

    def fetch_campaigns_summary(
        self,
        days: int = 14,
        limit: int = 200,
        profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return campaign aggregates by joining campaign_details to optimization_results."""

        days = max(1, min(int(days), 365))
        limit = max(1, min(int(limit), 500))

        results_ref = f"`{self.dataset_ref}.optimization_results`"
        campaigns_ref = f"`{self.dataset_ref}.campaign_details`"

        query = f"""
        WITH runs AS (
          SELECT run_id
          FROM {results_ref}
          WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            AND (@profile_id IS NULL OR profile_id = @profile_id)
        )
        SELECT
          c.campaign_id AS campaign_id,
          ANY_VALUE(c.campaign_name) AS campaign_name,
          SUM(COALESCE(c.spend, 0)) AS spend,
          SUM(COALESCE(c.sales, 0)) AS sales,
          SAFE_DIVIDE(SUM(COALESCE(c.spend, 0)), NULLIF(SUM(COALESCE(c.sales, 0)), 0)) AS acos,
          SUM(COALESCE(c.impressions, 0)) AS impressions,
          SUM(COALESCE(c.clicks, 0)) AS clicks,
          SUM(COALESCE(c.conversions, 0)) AS conversions,
          MAX(c.timestamp) AS last_seen
        FROM {campaigns_ref} c
        JOIN runs r ON c.run_id = r.run_id
        GROUP BY campaign_id
        ORDER BY spend DESC
        LIMIT @limit
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
                bigquery.ScalarQueryParameter("profile_id", "STRING", profile_id),
            ]
        )

        try:
            job = self.client.query(query, job_config=job_config)
            result = []
            for row in job.result(timeout=30):
                result.append(self._row_to_dict(row))
            return result
        except Exception as exc:
            logger.warning("Failed to fetch campaigns summary: %s", exc)
            return []

    def fetch_run_events(
        self,
        limit: int = 200,
        profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent run lifecycle events, optionally filtered by profile via join."""

        limit = max(1, min(int(limit), 500))

        events_ref = f"`{self.dataset_ref}.{RUN_EVENTS_TABLE}`"
        results_ref = f"`{self.dataset_ref}.optimization_results`"

        query = f"""
        SELECT
          e.timestamp AS timestamp,
          e.run_id AS run_id,
          e.status AS status,
          e.details AS details,
          r.profile_id AS profile_id
        FROM {events_ref} e
        LEFT JOIN {results_ref} r
          ON e.run_id = r.run_id
        WHERE (@profile_id IS NULL OR r.profile_id = @profile_id)
        ORDER BY e.timestamp DESC
        LIMIT @limit
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
                bigquery.ScalarQueryParameter("profile_id", "STRING", profile_id),
            ]
        )

        try:
            job = self.client.query(query, job_config=job_config)
            result = []
            for row in job.result(timeout=30):
                data = self._row_to_dict(row)
                if "details" in data:
                    data["details"] = self._safe_json_loads(data["details"])
                result.append(data)
            return result
        except Exception as exc:
            logger.warning("Failed to fetch run events: %s", exc)
            return []

    def fetch_recent_optimization_results(
        self,
        days: int = 30,
        limit: int = 50,
        profile_id: Optional[str] = None,
        include_payload_json: bool = True,
    ) -> List[Dict[str, Any]]:
        """Return recent optimization_results rows for dashboard tables."""

        days = max(1, min(int(days), 365))
        limit = max(1, min(int(limit), 500))

        table_id = "optimization_results"
        table_ref = f"`{self.dataset_ref}.{table_id}`"
        desired_fields = [
            "timestamp",
            "run_id",
            "status",
            "profile_id",
            "dry_run",
            "duration_seconds",
            "campaigns_analyzed",
            "keywords_optimized",
            "bids_increased",
            "bids_decreased",
            "negative_keywords_added",
            "budget_changes",
            "total_spend",
            "total_sales",
            "average_acos",
            "target_acos",
            "lookback_days",
            "enabled_features",
            "errors",
            "warnings",
        ]

        payload_field = None
        if include_payload_json:
            desired_fields += ["campaigns", "top_performers", "features", "config_snapshot"]

            available = self._get_table_columns(table_id)
            for candidate in (
                "payload",
                "payload_json",
                "results",
                "results_json",
                "result_json",
                "raw_results",
            ):
                if candidate in available:
                    payload_field = candidate
                    desired_fields.append(candidate)
                    break

        select_fields = self._select_existing_fields(table_id, desired_fields)

        query = (
            f"SELECT {', '.join(select_fields)} "
            f"FROM {table_ref} "
            "WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY) "
            "AND (@profile_id IS NULL OR profile_id = @profile_id) "
            "ORDER BY (profile_id IS NULL OR profile_id = '') ASC, timestamp DESC "
            "LIMIT @limit"
        )

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", days),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
                bigquery.ScalarQueryParameter("profile_id", "STRING", profile_id),
            ]
        )

        try:
            job = self.client.query(query, job_config=job_config)
            rows = []
            for row in job.result(timeout=30):
                data = self._row_to_dict(row)
                if include_payload_json:
                    for key in ("campaigns", "top_performers", "features", "config_snapshot"):
                        if key in data:
                            data[key] = self._safe_json_loads(data[key])

                    if payload_field and payload_field in data:
                        payload = self._safe_json_loads(data.get(payload_field))
                        if isinstance(payload, dict):
                            for key in (
                                "campaigns",
                                "top_performers",
                                "features",
                                "config_snapshot",
                            ):
                                if data.get(key) is None and key in payload:
                                    data[key] = payload.get(key)
                rows.append(data)
            return rows
        except Exception as exc:
            logger.warning("Failed to fetch recent optimization results: %s", exc)
            return []
