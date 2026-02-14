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
            self.client = bigquery.Client(
                project=project_id,
                credentials=credentials,
            )
        else:
            logger.debug("Using Application Default Credentials for BigQuery client")
            self.client = bigquery.Client(project=project_id)

        self.dataset_ref = f"{project_id}.{self.dataset_id}"

        # Cache table schemas to make read helpers tolerant to schema drift.
        self._table_columns_cache: Dict[str, set] = {}

        # Cache dataset locations so queries can run in the correct region.
        self._dataset_location_cache: Dict[str, Optional[str]] = {}

        # Cache discovered performance sources (keyed by dataset_ref + mode).
        self._perf_source_cache: Dict[str, Optional[Dict[str, Any]]] = {}

        # Ensure dataset exists
        self._ensure_dataset_exists()

    def _get_dataset_location(self, dataset_ref: str) -> Optional[str]:
        """Return the dataset location for `project.dataset` (cached)."""

        if not dataset_ref:
            return None

        cached = self._dataset_location_cache.get(dataset_ref)
        if cached is not None:
            return cached

        try:
            dataset = self.client.get_dataset(dataset_ref)
            location = getattr(dataset, "location", None)
            self._dataset_location_cache[dataset_ref] = location
            return location
        except Exception as exc:
            logger.debug("Failed to get dataset location for %s: %s", dataset_ref, exc)
            self._dataset_location_cache[dataset_ref] = None
            return None

    def _query(
        self,
        query: str,
        job_config: Optional[bigquery.QueryJobConfig] = None,
        *,
        dataset_ref: Optional[str] = None,
        location: Optional[str] = None,
    ):
        """Execute a query with an explicit location when possible."""

        effective_location = location
        if not effective_location and dataset_ref:
            effective_location = self._get_dataset_location(dataset_ref)
        if not effective_location:
            effective_location = self.location

        if effective_location:
            return self.client.query(query, job_config=job_config, location=effective_location)
        return self.client.query(query, job_config=job_config)

    def _get_table_columns(self, table_id: str, dataset_ref: Optional[str] = None) -> set:
        """Return a cached set of column names for the given table.

        dataset_ref may be provided to inspect tables outside of self.dataset_ref
        (e.g. when performance tables live in a different dataset).
        """

        effective_dataset_ref = dataset_ref or self.dataset_ref
        cache_key = f"{effective_dataset_ref}.{table_id}"

        cached = self._table_columns_cache.get(cache_key)
        if cached is not None:
            return cached

        table_ref = f"{effective_dataset_ref}.{table_id}"
        try:
            table = self.client.get_table(table_ref)
            cols = {field.name for field in table.schema}
            self._table_columns_cache[cache_key] = cols
            return cols
        except Exception as exc:
            logger.warning("Failed to read schema for %s: %s", table_ref, exc)
            self._table_columns_cache[cache_key] = set()
            return set()

    def _discover_performance_source(
        self,
        dataset_ref: str,
        mode: str = "daily",
    ) -> Optional[Dict[str, Any]]:
        """Discover a suitable performance table in a dataset by inspecting INFORMATION_SCHEMA.

        This is a fallback used when expected table names (e.g. campaign_performance) do not
        exist. It searches for a table containing at least:
        - a date-like column
        - a spend/cost-like column
        - a sales/revenue-like column

        For mode='keywords', it also requires a keyword identifier column and clicks.
        """

        mode = (mode or "daily").strip().lower()
        cache_key = f"{dataset_ref}:{mode}"
        if cache_key in self._perf_source_cache:
            return self._perf_source_cache[cache_key]

        def _case_order(expr: str, candidates: List[str]) -> str:
            parts = [
                f"WHEN LOWER({expr}) = '{c.lower()}' THEN {idx}"
                for idx, c in enumerate(candidates, start=1)
            ]
            return f"(CASE {' '.join(parts)} ELSE 999 END)"

        date_candidates = [
            "segments_date",
            "segmentsDate",
            "report_date",
            "reportDate",
            "startDate",
            "date",
            "day",
            "reporting_date",
            "reportingDate",
            "timestamp",
        ]

        spend_candidates = [
            "cost",
            "spend",
            "ad_spend",
            "adSpend",
            "spend_amount",
            "spendAmount",
            "cost_amount",
            "costAmount",
            "costInMicros",
            "cost_in_micros",
            "cost_micros",
            "costMicros",
            "spendInMicros",
            "spend_in_micros",
            "spend_micros",
            "spendMicros",
        ]

        sales_candidates = [
            "attributedSales7d",
            "attributedSales14d",
            "attributedSales30d",
            "attributedSales7dSameSKU",
            "attributedSales14dSameSKU",
            "attributedSales30dSameSKU",
            "attributed_sales_7d",
            "attributed_sales_14d",
            "attributed_sales_30d",
            "attributed_sales_7d_same_sku",
            "attributed_sales_14d_same_sku",
            "attributed_sales_30d_same_sku",
            "sales14d",
            "sales_7d",
            "sales_14d",
            "sales_30d",
            "sales",
            "revenue",
            "conversion_value",
            "conversionValue",
            "conversion_value_14d",
            "conversionValue14d",
            "ordered_product_sales",
            "orderedProductSales",
            "ordered_product_sales_14d",
            "orderedProductSales14d",
            "ordered_product_sales_7d",
            "orderedProductSales7d",
            "purchases",
            "purchases_14d",
            "purchases14d",
        ]

        keyword_candidates = [
            "keyword_id",
            "keywordId",
            "keyword",
            "keyword_text",
            "keywordText",
            "search_term",
            "searchTerm",
            "customer_search_term",
            "customerSearchTerm",
        ]

        clicks_candidates = ["clicks"]

        info_ref = f"`{dataset_ref}.INFORMATION_SCHEMA.COLUMNS`"

        date_in = ", ".join([f"'{c.lower()}'" for c in date_candidates])
        spend_in = ", ".join([f"'{c.lower()}'" for c in spend_candidates])
        sales_in = ", ".join([f"'{c.lower()}'" for c in sales_candidates])
        keyword_in = ", ".join([f"'{c.lower()}'" for c in keyword_candidates])
        clicks_in = ", ".join([f"'{c.lower()}'" for c in clicks_candidates])

        date_order = _case_order("column_name", date_candidates)
        spend_order = _case_order("column_name", spend_candidates)
        sales_order = _case_order("column_name", sales_candidates)
        keyword_order = _case_order("column_name", keyword_candidates)
        clicks_order = _case_order("column_name", clicks_candidates)

        # Prefer likely table names by mode.
        if mode == "keywords":
            table_pref = "(CASE WHEN LOWER(table_name) LIKE '%keyword%' THEN 1 WHEN LOWER(table_name) LIKE '%search%' THEN 2 WHEN LOWER(table_name) LIKE '%term%' THEN 3 ELSE 99 END)"
        else:
            table_pref = "(CASE WHEN LOWER(table_name) LIKE '%campaign%' THEN 1 WHEN LOWER(table_name) LIKE '%performance%' THEN 2 WHEN LOWER(table_name) LIKE '%report%' THEN 3 WHEN LOWER(table_name) LIKE '%sp_%' THEN 4 ELSE 99 END)"

        query = f"""
        WITH picked AS (
            SELECT
                table_name,
                (SELECT column_name FROM {info_ref} c2
                    WHERE c2.table_name = c.table_name AND LOWER(c2.column_name) IN ({date_in})
                    ORDER BY {date_order} LIMIT 1) AS date_col,
                (SELECT column_name FROM {info_ref} c2
                    WHERE c2.table_name = c.table_name AND LOWER(c2.column_name) IN ({spend_in})
                    ORDER BY {spend_order} LIMIT 1) AS spend_col,
                (SELECT column_name FROM {info_ref} c2
                    WHERE c2.table_name = c.table_name AND LOWER(c2.column_name) IN ({sales_in})
                    ORDER BY {sales_order} LIMIT 1) AS sales_col,
                (SELECT column_name FROM {info_ref} c2
                    WHERE c2.table_name = c.table_name AND LOWER(c2.column_name) IN ({keyword_in})
                    ORDER BY {keyword_order} LIMIT 1) AS keyword_col,
                (SELECT column_name FROM {info_ref} c2
                    WHERE c2.table_name = c.table_name AND LOWER(c2.column_name) IN ({clicks_in})
                    ORDER BY {clicks_order} LIMIT 1) AS clicks_col,
                MAX(IF(LOWER(column_name) = 'profile_id', 1, 0)) AS has_profile
            FROM {info_ref} c
            GROUP BY table_name
        )
        SELECT
            table_name,
            date_col,
            spend_col,
            sales_col,
            keyword_col,
            clicks_col,
            has_profile
        FROM picked
        WHERE date_col IS NOT NULL
            AND spend_col IS NOT NULL
            AND sales_col IS NOT NULL
            {"AND keyword_col IS NOT NULL AND clicks_col IS NOT NULL" if mode == "keywords" else ""}
        ORDER BY {table_pref}, table_name
        LIMIT 1
        """

        try:
            job = self._query(query, dataset_ref=dataset_ref)
            rows = list(job.result(timeout=30))
            if not rows:
                self._perf_source_cache[cache_key] = None
                return None

            row = rows[0]
            source = {
                "table_id": row.get("table_name"),
                "date_col": row.get("date_col"),
                "spend_col": row.get("spend_col"),
                "sales_col": row.get("sales_col"),
                "keyword_col": row.get("keyword_col"),
                "clicks_col": row.get("clicks_col"),
                "has_profile": bool(row.get("has_profile")),
            }
            self._perf_source_cache[cache_key] = source
            return source
        except Exception as exc:
            logger.warning(
                "Failed to discover performance source in %s (mode=%s): %s",
                dataset_ref,
                mode,
                exc,
            )
            self._perf_source_cache[cache_key] = None
            return None

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

        def _as_additive_field(field: bigquery.SchemaField) -> bigquery.SchemaField:
            """Return a SchemaField that is safe to ADD to an existing table.

            BigQuery allows adding new columns only when they are NULLABLE or REPEATED.
            If our desired schema marks a new field as REQUIRED, relax it to NULLABLE
            during schema evolution.
            """

            mode = (getattr(field, "mode", None) or "NULLABLE").upper()
            if mode == "REQUIRED":
                mode = "NULLABLE"

            return bigquery.SchemaField(
                field.name,
                field.field_type,
                mode=mode,
                description=getattr(field, "description", None),
                fields=getattr(field, "fields", ()) or (),
                policy_tags=getattr(field, "policy_tags", None),
            )
        for field in desired_schema:
            if field.name not in existing:
                to_add.append(_as_additive_field(field))

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
            self._table_columns_cache.pop(f"{self.dataset_ref}.{table_id}", None)
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

            # Coerce JSON-ish fields based on the *actual* table schema.
            # Some deployments created these columns as STRING; newer code uses JSON.
            table_ref = f"{self.dataset_ref}.optimization_results"
            try:
                table = self.client.get_table(table_ref)
                field_map = {f.name: f for f in (table.schema or [])}
            except Exception:
                field_map = {}

            def _coerce_jsonish(field_name: str, value: Any) -> Any:
                field = field_map.get(field_name)
                if field is None:
                    return value

                ftype = (getattr(field, "field_type", None) or "").upper()
                if ftype == "STRING":
                    try:
                        return json.dumps(value, default=str)
                    except Exception:
                        return str(value)

                if ftype == "JSON":
                    try:
                        # Streaming inserts (`insert_rows_json`) treat dict/list values as RECORDs
                        # and can reject them with errors like: "This field: features is not a record."
                        # BigQuery accepts JSON values as JSON-serialized strings for JSON columns.
                        return json.dumps(value, default=str)
                    except Exception:
                        return str(value)
                return value

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
                "campaigns": _coerce_jsonish("campaigns", results_data.get("campaigns", [])),
                "top_performers": _coerce_jsonish(
                    "top_performers", results_data.get("top_performers", [])
                ),
                "features": _coerce_jsonish("features", results_data.get("features", {})),
                "config_snapshot": _coerce_jsonish(
                    "config_snapshot", results_data.get("config_snapshot", {})
                ),
            }

            # Insert row
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
            self._ensure_table_schema("campaign_details", schema)

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
            self._ensure_table_schema("campaign_details", schema)

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
            self._ensure_table_schema("optimization_progress", schema)

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
            self._ensure_table_schema("optimization_errors", schema)

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
        dataset_ref: Optional[str] = None,
    ) -> Optional[datetime]:
        """Execute a query expected to return a single timestamp column."""

        try:
            job = self._query(query, job_config=job_config, dataset_ref=dataset_ref)
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

        return self._execute_single_timestamp_query(
            query,
            job_config,
            dataset_ref=self.dataset_ref,
        )

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

        return self._execute_single_timestamp_query(
            query,
            job_config,
            dataset_ref=self.dataset_ref,
        )

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
            job = self._query(query, job_config=job_config, dataset_ref=self.dataset_ref)
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
        Spend/sales/ACOS come from the best available performance table.

        Preferred sources (first match wins, campaign-level only to avoid duplication):
        1. campaign_performance (Amazon Ads API campaign reports - PREFERRED)
        2. sp_campaign_metrics (Sponsored Products campaign metrics)
        3. campaign_details (optimizer-written campaign data)
        
        Note: keyword_performance and search_term_reports are intentionally excluded
        because aggregating keyword/search-term level data causes duplication
        (same campaign spend/sales counted multiple times across different keywords).
        """

        import datetime

        days = max(1, min(int(days), 365))
        debug_bq = str(os.getenv("PPC_DEBUG_BIGQUERY", "")).strip().lower() in (
            "1",
            "true",
            "yes",
            "y",
            "on",
        )

        perf_dataset_id = (
            os.getenv("BQ_PERFORMANCE_DATASET_ID")
            or os.getenv("PPC_PERFORMANCE_DATASET_ID")
            or os.getenv("BIGQUERY_PERFORMANCE_DATASET")
            or os.getenv("BIGQUERY_PERF_DATASET")
            or os.getenv("BQ_PERF_DATASET_ID")
        )
        perf_dataset_ref = (
            f"{self.project_id}.{perf_dataset_id}" if perf_dataset_id else self.dataset_ref
        )
        # Last N calendar days including today (UTC), e.g. days=7 -> today..today-6.
        start_date = datetime.datetime.utcnow().date() - datetime.timedelta(days=days - 1)
        results_ref = f"`{self.dataset_ref}.optimization_results`"

        def _pick_column(available: set, candidates: List[str]) -> Optional[str]:
            lowered = {str(c).lower(): str(c) for c in available}
            for cand in candidates:
                key = str(cand).lower()
                if key in lowered:
                    return lowered[key]
            return None

        def _has_recent_rows(
            table_id: str,
            date_col: str,
            has_profile: bool,
        ) -> bool:
            """Return True if the table has any rows since start_date.

            This avoids selecting an empty-but-present table (common cause of
            'all zeros' dashboards).
            """

            table_ref = f"`{perf_dataset_ref}.{table_id}`"
            profile_filter = (
                "AND (@profile_id IS NULL OR profile_id = @profile_id)" if has_profile else ""
            )
            probe = f"""
            SELECT 1
            FROM {table_ref}
            WHERE SAFE_CAST(`{date_col}` AS DATE) >= @start_date
              {profile_filter}
            LIMIT 1
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
                    bigquery.ScalarQueryParameter("profile_id", "STRING", profile_id),
                ]
            )
            try:
                rows = list(
                    self._query(
                        probe,
                        job_config=job_config,
                        dataset_ref=perf_dataset_ref,
                    ).result(timeout=15)
                )
                return bool(rows)
            except Exception as exc:
                if debug_bq:
                    logger.info(
                        "Perf source probe failed for %s.%s: %s",
                        perf_dataset_ref,
                        table_id,
                        exc,
                    )
                # If probing fails for any reason, don't block selection.
                return True

        def _resolve_perf_source() -> Optional[Dict[str, Any]]:
            # Check if user has configured a preferred table
            preferred_table = os.getenv("BQ_PREFERRED_PERFORMANCE_TABLE", "").strip().lower()
            
            sources = [
                # campaign_performance: Preferred source - campaign-level data from Amazon Ads API.
                # This is the most authoritative source as it comes directly from Amazon's reporting API.
                # We use deduplication to handle any potential duplicate rows.
                {
                    "table_id": "campaign_performance",
                    "date": ["segments_date", "segmentsDate", "report_date", "reportDate", "date", "timestamp"],
                    "spend": ["cost", "spend"],
                    "sales": [
                        "attributedSales7d",
                        "attributedSales14d",
                        "attributedSales30d",
                        "attributedSales7dSameSKU",
                        "attributedSales14dSameSKU",
                        "attributedSales30dSameSKU",
                        "attributed_sales_7d",
                        "sales14d",
                        "attributed_sales_14d",
                        "attributed_sales_30d",
                        "sales_7d",
                        "sales_14d",
                        "sales_30d",
                        "sales",
                        "conversion_value",
                        "conversion_value_14d",
                        "ordered_product_sales",
                        "ordered_product_sales_14d",
                    ],
                    "use_deduplication": True,  # Deduplicate by campaign_id and date
                },
                # sp_campaign_metrics: Second choice - Sponsored Products campaign metrics
                {
                    "table_id": "sp_campaign_metrics",
                    "date": ["startDate", "segments_date", "segmentsDate", "report_date", "reportDate", "date"],
                    "spend": ["cost", "spend"],
                    "sales": [
                        "attributedSales7d",
                        "attributedSales14d",
                        "attributedSales30d",
                        "attributedSales7dSameSKU",
                        "attributedSales14dSameSKU",
                        "attributedSales30dSameSKU",
                        "attributed_sales_7d",
                        "sales14d",
                        "attributed_sales_14d",
                        "attributed_sales_30d",
                        "sales_7d",
                        "sales_14d",
                        "sales_30d",
                        "sales",
                        "conversion_value",
                        "conversion_value_14d",
                        "ordered_product_sales",
                        "ordered_product_sales_14d",
                    ],
                    "use_deduplication": True,  # Deduplicate by campaign_id and date
                },
                # campaign_details: Third choice - optimizer-written campaign data.
                # Contains campaign-level data from each optimization run.
                # Each row represents a campaign's metrics during an optimization run's lookback window.
                # We deduplicate by taking the most recent run's data per day to avoid counting
                # overlapping lookback windows multiple times.
                {
                    "table_id": "campaign_details",
                    "date": ["timestamp"],
                    "spend": ["spend"],
                    "sales": ["sales"],
                    "use_deduplication": True,  # Deduplicate by campaign_id and date
                },
                # NOTE: keyword_performance and search_term_reports are NOT used here
                # because they contain keyword/search-term level data which would cause
                # duplication when aggregated (same spend/sales counted multiple times
                # across different keywords/search terms for the same campaign).
                # We only use campaign-level tables for accurate daily totals.
            ]
            
            # If user specified a preferred table, try it first
            if preferred_table:
                # Move the preferred table to the front
                preferred_src = None
                remaining_srcs = []
                for src in sources:
                    if src["table_id"].lower() == preferred_table:
                        preferred_src = src
                    else:
                        remaining_srcs.append(src)
                
                if preferred_src:
                    sources = [preferred_src] + remaining_srcs
                    if debug_bq:
                        logger.info(
                            "User specified preferred performance table: %s",
                            preferred_table
                        )

            for src in sources:
                table_id = src["table_id"]
                cols = self._get_table_columns(table_id, dataset_ref=perf_dataset_ref)
                if not cols:
                    continue

                date_col = _pick_column(cols, src["date"])
                spend_col = _pick_column(cols, src["spend"])
                sales_col = _pick_column(cols, src["sales"])

                if not date_col or not spend_col or not sales_col:
                    continue

                # For deduplication, we also need campaign_id
                use_deduplication = src.get("use_deduplication", False)
                if use_deduplication:
                    has_campaign_id = "campaign_id" in {str(c).lower() for c in cols}
                    if not has_campaign_id:
                        if debug_bq:
                            logger.info(
                                "Perf source %s.%s requires campaign_id for deduplication but doesn't have it; skipping",
                                perf_dataset_ref,
                                table_id,
                            )
                        continue

                has_profile = "profile_id" in {str(c).lower() for c in cols}

                # Skip empty tables so we don't return all zeros.
                if not _has_recent_rows(table_id, date_col, has_profile):
                    if debug_bq:
                        logger.info(
                            "Perf source %s.%s has no recent rows since %s; trying next candidate",
                            perf_dataset_ref,
                            table_id,
                            start_date,
                        )
                    continue

                return {
                    "table_id": table_id,
                    "date_col": date_col,
                    "spend_col": spend_col,
                    "sales_col": sales_col,
                    "has_profile": has_profile,
                    "use_deduplication": src.get("use_deduplication", False),
                }

            # Fallback: discover table by schema in INFORMATION_SCHEMA.
            discovered = self._discover_performance_source(perf_dataset_ref, mode="daily")
            if discovered and discovered.get("table_id"):
                return {
                    "table_id": discovered.get("table_id"),
                    "date_col": discovered.get("date_col"),
                    "spend_col": discovered.get("spend_col"),
                    "sales_col": discovered.get("sales_col"),
                    "has_profile": bool(discovered.get("has_profile")),
                }

            return None

        perf_source = _resolve_perf_source()

        if debug_bq:
            if perf_source:
                logger.info(
                    "Daily overview perf source selected: table=%s date=%s spend=%s sales=%s has_profile=%s perf_dataset=%s results_dataset=%s profile_id=%s start_date=%s days=%s",
                    perf_source.get("table_id"),
                    perf_source.get("date_col"),
                    perf_source.get("spend_col"),
                    perf_source.get("sales_col"),
                    perf_source.get("has_profile"),
                    perf_dataset_ref,
                    self.dataset_ref,
                    profile_id,
                    start_date,
                    days,
                )
            else:
                logger.info(
                    "Daily overview perf source not found; will use optimization_results-only aggregation (perf_dataset=%s results_dataset=%s profile_id=%s start_date=%s days=%s)",
                    perf_dataset_ref,
                    self.dataset_ref,
                    profile_id,
                    start_date,
                    days,
                )

        # NOTE: Do not join perf + results in a single query.
        # BigQuery cannot query across datasets in different locations.
        runs_query = f"""
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
        ORDER BY day DESC
        """

        perf_only_query: Optional[str] = None
        if perf_source:
            perf_ref = f"`{perf_dataset_ref}.{perf_source['table_id']}`"
            date_col = perf_source["date_col"]
            spend_col = perf_source["spend_col"]
            sales_col = perf_source["sales_col"]
            use_deduplication = perf_source.get("use_deduplication", False)

            def _is_micros(col_name: str) -> bool:
                name = str(col_name or "").lower()
                return "micros" in name or name.endswith("_micro") or name.endswith("_micros")

            spend_expr = (
                f"SAFE_DIVIDE(COALESCE(`{spend_col}`, 0), 1000000)"
                if _is_micros(spend_col)
                else f"COALESCE(`{spend_col}`, 0)"
            )
            sales_expr = (
                f"SAFE_DIVIDE(COALESCE(`{sales_col}`, 0), 1000000)"
                if _is_micros(sales_col)
                else f"COALESCE(`{sales_col}`, 0)"
            )
            perf_profile_filter = (
                "AND (@profile_id IS NULL OR profile_id = @profile_id)"
                if perf_source["has_profile"]
                else ""
            )

            # For campaign_details, we need to deduplicate by taking the most recent
            # optimization run's view of each campaign per day. This prevents duplicate
            # counting from overlapping lookback windows across multiple runs.
            if use_deduplication:
                # campaign_details stores campaign-level data from optimization runs.
                # Each run may have multiple campaigns, and multiple runs may occur per day.
                # To get accurate daily metrics without duplicate counting:
                # 1. Group by date and campaign_id
                # 2. Take the most recent run's data for each campaign per day
                # 3. Sum across all campaigns for that day
                # This ensures we count each campaign's metrics only once per day.
                perf_only_query = f"""
                WITH deduplicated_campaigns AS (
                    SELECT
                        DATE(`{date_col}`) AS day,
                        `campaign_id`,
                        {spend_expr} AS spend,
                        {sales_expr} AS sales,
                        ROW_NUMBER() OVER (
                            PARTITION BY DATE(`{date_col}`), `campaign_id`
                            ORDER BY `{date_col}` DESC
                        ) AS rn
                    FROM {perf_ref}
                    WHERE DATE(`{date_col}`) >= @start_date
                        {perf_profile_filter}
                )
                SELECT
                    day,
                    SUM(spend) AS total_spend,
                    SUM(sales) AS total_sales,
                    COUNT(DISTINCT campaign_id) AS campaigns_with_data
                FROM deduplicated_campaigns
                WHERE rn = 1
                GROUP BY day
                ORDER BY day DESC
                """
            else:
                # Standard query for performance tables that already have deduplicated daily data
                perf_only_query = f"""
                SELECT
                    SAFE_CAST(`{date_col}` AS DATE) AS day,
                    SUM({spend_expr}) AS total_spend,
                    SUM({sales_expr}) AS total_sales
                FROM {perf_ref}
                WHERE SAFE_CAST(`{date_col}` AS DATE) >= @start_date
                    {perf_profile_filter}
                GROUP BY day
                ORDER BY day DESC
                """

        # FALLBACK QUERY - LAST RESORT ONLY
        # This query uses optimization_results as a fallback when no performance tables are available.
        # To prevent DUPLICATE COUNTING (each run contains aggregated metrics from lookback windows),
        # we deduplicate by taking only the most recent run per day.
        # This ensures we count metrics only once per day, avoiding inflation from multiple daily runs.
        fallback_query = f"""
        WITH deduplicated_runs AS (
            SELECT
                DATE(timestamp) AS day,
                COALESCE(total_spend, 0) AS total_spend,
                COALESCE(total_sales, 0) AS total_sales,
                COALESCE(campaigns_analyzed, 0) AS campaigns_analyzed,
                COALESCE(keywords_optimized, 0) AS keywords_optimized,
                COALESCE(budget_changes, 0) AS budget_changes,
                ROW_NUMBER() OVER (
                    PARTITION BY DATE(timestamp)
                    ORDER BY timestamp DESC, run_id DESC
                ) AS rn
            FROM {results_ref}
            WHERE DATE(timestamp) >= @start_date
                AND (@profile_id IS NULL OR profile_id = @profile_id)
        )
        SELECT
            day,
            COUNT(1) AS runs,
            SUM(total_spend) AS total_spend,
            SUM(total_sales) AS total_sales,
            SAFE_DIVIDE(SUM(total_spend), NULLIF(SUM(total_sales), 0)) AS blended_acos,
            SUM(campaigns_analyzed) AS campaigns_analyzed,
            SUM(keywords_optimized) AS keywords_optimized,
            SUM(budget_changes) AS budget_changes
        FROM deduplicated_runs
        WHERE rn = 1
        GROUP BY day
        ORDER BY day DESC
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
                bigquery.ScalarQueryParameter("profile_id", "STRING", profile_id),
            ]
        )

        try:
            def _as_float(value: Any) -> float:
                if value is None:
                    return 0.0
                try:
                    return float(value)
                except Exception:
                    return 0.0

            runs_job = self._query(runs_query, job_config=job_config, dataset_ref=self.dataset_ref)
            runs_rows = [self._row_to_dict(r) for r in runs_job.result(timeout=30)]

            perf_rows: List[Dict[str, Any]] = []
            if perf_only_query:
                try:
                    perf_job = self._query(
                        perf_only_query,
                        job_config=job_config,
                        dataset_ref=perf_dataset_ref,
                    )
                    perf_rows = [self._row_to_dict(r) for r in perf_job.result(timeout=30)]
                except Exception as exc:
                    logger.warning(
                        "Daily perf query failed; falling back to optimization_results-only aggregation: %s",
                        exc,
                    )
                    if debug_bq:
                        logger.info(
                            "Daily overview fell back to optimization_results-only aggregation (dataset=%s profile_id=%s start_date=%s days=%s)",
                            self.dataset_ref,
                            profile_id,
                            start_date,
                            days,
                        )
                    job = self._query(
                        fallback_query,
                        job_config=job_config,
                        dataset_ref=self.dataset_ref,
                    )
                    rows_iter = job.result(timeout=30)
                    result: List[Dict[str, Any]] = []
                    for row in rows_iter:
                        data = self._row_to_dict(row)
                        day_val = data.get("day")
                        if day_val is not None:
                            data["day"] = str(day_val)
                        result.append(data)
                    return result

            by_day: Dict[str, Dict[str, Any]] = {}

            for row in runs_rows:
                day_val = row.get("day")
                if day_val is None:
                    continue
                day_key = str(day_val)
                by_day[day_key] = {
                    "day": day_key,
                    "runs": int(row.get("runs") or 0),
                    "total_spend": 0.0,
                    "total_sales": 0.0,
                    "blended_acos": 0.0,
                    "campaigns_analyzed": int(row.get("campaigns_analyzed") or 0),
                    "keywords_optimized": int(row.get("keywords_optimized") or 0),
                    "budget_changes": int(row.get("budget_changes") or 0),
                }

            for row in perf_rows:
                day_val = row.get("day")
                if day_val is None:
                    continue
                day_key = str(day_val)
                entry = by_day.get(day_key)
                if not entry:
                    entry = {
                        "day": day_key,
                        "runs": 0,
                        "total_spend": 0.0,
                        "total_sales": 0.0,
                        "blended_acos": 0.0,
                        "campaigns_analyzed": 0,
                        "keywords_optimized": 0,
                        "budget_changes": 0,
                    }
                    by_day[day_key] = entry

                entry["total_spend"] = _as_float(row.get("total_spend"))
                entry["total_sales"] = _as_float(row.get("total_sales"))

            for entry in by_day.values():
                spend = _as_float(entry.get("total_spend"))
                sales = _as_float(entry.get("total_sales"))
                entry["blended_acos"] = (spend / sales) if sales else 0.0

            # Data quality check: warn if we have less data than expected
            days_with_spend = sum(1 for e in by_day.values() if _as_float(e.get("total_spend")) > 0)
            if days_with_spend < days and debug_bq:
                logger.warning(
                    "Daily overview data quality: only %d days with spend data out of %d requested days (dataset=%s profile_id=%s start_date=%s)",
                    days_with_spend,
                    days,
                    self.dataset_ref,
                    profile_id,
                    start_date,
                )

            # ACOS sanity check: validate data quality to detect potential duplication issues
            total_spend = sum(_as_float(e.get("total_spend")) for e in by_day.values())
            total_sales = sum(_as_float(e.get("total_sales")) for e in by_day.values())
            
            if total_sales > 0 and total_spend > 0:
                acos = total_spend / total_sales
                source_info = f"table={perf_source.get('table_id')}" if perf_source else "fallback=optimization_results"
                
                # Log summary for all requests
                logger.info(
                    "Daily overview summary: spend=$%.2f sales=$%.2f acos=%.2f days=%d source=%s",
                    total_spend,
                    total_sales,
                    acos,
                    days,
                    source_info,
                )
                
                # Warn if ACOS is outside typical range (0.1 to 2.0)
                # ACOS > 5.0 often indicates duplicate counting of spend
                # ACOS < 0.01 may indicate missing spend or inflated sales
                if acos > 5.0:
                    logger.warning(
                        "⚠️ Suspicious ACOS=%.2f (spend=$%.2f, sales=$%.2f). "
                        "ACOS > 5.0 may indicate duplicate counting across tables. "
                        "Source: %s. Consider running scripts/diagnose_sales_data.py to investigate.",
                        acos,
                        total_spend,
                        total_sales,
                        source_info,
                    )
                elif acos < 0.01 and total_spend > 10:
                    logger.warning(
                        "⚠️ Suspicious ACOS=%.2f (spend=$%.2f, sales=$%.2f). "
                        "ACOS < 0.01 may indicate missing spend data or inflated sales. "
                        "Source: %s",
                        acos,
                        total_spend,
                        total_sales,
                        source_info,
                    )
            elif total_spend > 0:
                source_info = f"table={perf_source.get('table_id')}" if perf_source else "fallback=optimization_results"
                logger.warning(
                    "⚠️ Spend data exists ($%.2f) but sales is zero. Source: %s",
                    total_spend,
                    source_info,
                )

            return sorted(by_day.values(), key=lambda d: d.get("day", ""), reverse=True)
        except Exception as exc:
            logger.warning("Failed to fetch daily overview: %s", exc)
            return []

    def fetch_top_performing_keywords(
        self,
        days: int = 30,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return top-performing keywords for the dashboard.

        Uses keyword_performance when available. This helper is best-effort and
        intentionally schema-tolerant.
        """

        import datetime

        days = max(1, min(int(days), 365))
        limit = max(1, min(int(limit), 200))
        start_date = datetime.datetime.utcnow().date() - datetime.timedelta(days=days - 1)

        perf_dataset_id = (
            os.getenv("BQ_PERFORMANCE_DATASET_ID")
            or os.getenv("PPC_PERFORMANCE_DATASET_ID")
            or os.getenv("BIGQUERY_PERFORMANCE_DATASET")
            or os.getenv("BIGQUERY_PERF_DATASET")
            or os.getenv("BQ_PERF_DATASET_ID")
        )
        perf_dataset_ref = (
            f"{self.project_id}.{perf_dataset_id}" if perf_dataset_id else self.dataset_ref
        )

        kw_table_id = "keyword_performance"
        cols = self._get_table_columns(kw_table_id, dataset_ref=perf_dataset_ref)
        source_table_id = kw_table_id

        # Fallback: discover a keyword-level table by schema.
        discovered = None
        if not cols:
            discovered = self._discover_performance_source(perf_dataset_ref, mode="keywords")
            if discovered and discovered.get("table_id"):
                source_table_id = str(discovered.get("table_id"))
                cols = self._get_table_columns(source_table_id, dataset_ref=perf_dataset_ref)

        if not cols:
            return []

        kw_perf_ref = f"`{perf_dataset_ref}.{source_table_id}`"

        def _pick(available: set, candidates: List[str]) -> Optional[str]:
            lowered = {str(c).lower(): str(c) for c in available}
            for cand in candidates:
                key = str(cand).lower()
                if key in lowered:
                    return lowered[key]
            return None

        date_col = _pick(cols, ["report_date", "reportDate", "segments_date", "segmentsDate", "date", "timestamp", "startDate"])
        keyword_id_col = _pick(cols, ["keyword_id", "keywordId", "keyword", "keyword_text", "keywordText", "search_term", "searchTerm", "customer_search_term", "customerSearchTerm"])
        clicks_col = _pick(cols, ["clicks"])
        cost_col = _pick(cols, ["cost", "spend"])
        sales_col = _pick(
            cols,
            [
                "attributedSales7d",
                "attributedSales14d",
                "attributedSales30d",
                "attributedSales7dSameSKU",
                "attributedSales14dSameSKU",
                "attributedSales30dSameSKU",
                "attributed_sales_7d",
                "sales14d",
                "attributed_sales_14d",
                "attributed_sales_30d",
                "sales_7d",
                "sales_14d",
                "sales_30d",
                "conversion_value",
                "conversion_value_14d",
                "ordered_product_sales",
                "ordered_product_sales_14d",
                "sales",
            ],
        )

        if not keyword_id_col and discovered and discovered.get("keyword_col"):
            keyword_id_col = str(discovered.get("keyword_col"))

        if not clicks_col and discovered and discovered.get("clicks_col"):
            clicks_col = str(discovered.get("clicks_col"))

        if not (date_col and keyword_id_col and clicks_col and cost_col and sales_col):
            return []

        query = f"""
        SELECT
          CAST(`{keyword_id_col}` AS STRING) AS keyword_text,
          SUM(COALESCE(`{clicks_col}`, 0)) AS clicks,
          SUM(COALESCE(`{sales_col}`, 0)) AS sales,
          SAFE_DIVIDE(
            SUM(COALESCE(`{cost_col}`, 0)),
            NULLIF(SUM(COALESCE(`{sales_col}`, 0)), 0)
          ) AS acos
        FROM {kw_perf_ref}
                WHERE SAFE_CAST(`{date_col}` AS DATE) >= @start_date
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
            job = self._query(query, job_config=job_config, dataset_ref=perf_dataset_ref)
            result: List[Dict[str, Any]] = []
            for row in job.result(timeout=30):
                data = self._row_to_dict(row)
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

        Best-effort query over keyword_harvest_log when present.
        """

        import datetime

        days = max(1, min(int(days), 365))
        start_ts = datetime.datetime.utcnow() - datetime.timedelta(days=days)

        table_id = "keyword_harvest_log"
        cols = self._get_table_columns(table_id)
        if not cols:
            return {"keywords_discovered": 0, "keywords_added": 0}

        lowered = {str(c).lower(): str(c) for c in cols}

        def _pick(candidates: List[str]) -> Optional[str]:
            for cand in candidates:
                key = str(cand).lower()
                if key in lowered:
                    return lowered[key]
            return None

        ts_col = _pick(["harvested_at", "timestamp", "created_at", "fetch_timestamp"])
        term_col = _pick(["search_term", "keyword", "term"])
        action_col = _pick(["action", "event", "status"])
        dry_run_col = _pick(["dry_run", "is_dry_run"])  # optional

        if not (ts_col and term_col and action_col):
            return {"keywords_discovered": 0, "keywords_added": 0}

        harvest_ref = f"`{self.dataset_ref}.{table_id}`"

        added_condition = f"LOWER(CAST(`{action_col}` AS STRING)) IN ('created', 'added')"
        if dry_run_col:
            added_condition += f" AND NOT COALESCE(`{dry_run_col}`, FALSE)"

        query = f"""
        SELECT
          COUNT(DISTINCT CAST(`{term_col}` AS STRING)) AS keywords_discovered,
          SUM(CASE WHEN {added_condition} THEN 1 ELSE 0 END) AS keywords_added
        FROM {harvest_ref}
        WHERE `{ts_col}` >= @start_ts
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", start_ts),
            ]
        )

        try:
            job = self._query(query, job_config=job_config, dataset_ref=self.dataset_ref)
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
        """Return campaign aggregates by joining campaign_details to optimization_results.
        
        Uses deduplication to prevent duplicate counting when campaigns appear in multiple runs.
        For each campaign and date, takes only the most recent run's data to avoid inflated metrics.
        """

        days = max(1, min(int(days), 365))
        limit = max(1, min(int(limit), 500))

        results_ref = f"`{self.dataset_ref}.optimization_results`"
        campaigns_ref = f"`{self.dataset_ref}.campaign_details`"

        query = f"""
        WITH runs AS (
          SELECT run_id, timestamp
          FROM {results_ref}
          WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            AND (@profile_id IS NULL OR profile_id = @profile_id)
        ),
        deduplicated_campaigns AS (
          SELECT
            c.campaign_id,
            c.campaign_name,
            c.spend,
            c.sales,
            c.impressions,
            c.clicks,
            c.conversions,
            c.timestamp,
            ROW_NUMBER() OVER (
              PARTITION BY DATE(c.timestamp), c.campaign_id
              ORDER BY c.timestamp DESC, c.run_id DESC
            ) AS rn
          FROM {campaigns_ref} c
          JOIN runs r ON c.run_id = r.run_id
        )
        SELECT
          campaign_id,
          ANY_VALUE(campaign_name) AS campaign_name,
          SUM(COALESCE(spend, 0)) AS spend,
          SUM(COALESCE(sales, 0)) AS sales,
          SAFE_DIVIDE(SUM(COALESCE(spend, 0)), NULLIF(SUM(COALESCE(sales, 0)), 0)) AS acos,
          SUM(COALESCE(impressions, 0)) AS impressions,
          SUM(COALESCE(clicks, 0)) AS clicks,
          SUM(COALESCE(conversions, 0)) AS conversions,
          MAX(timestamp) AS last_seen
        FROM deduplicated_campaigns
        WHERE rn = 1
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
            job = self._query(query, job_config=job_config, dataset_ref=self.dataset_ref)
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
            job = self._query(query, job_config=job_config, dataset_ref=self.dataset_ref)
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
            job = self._query(query, job_config=job_config, dataset_ref=self.dataset_ref)
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
