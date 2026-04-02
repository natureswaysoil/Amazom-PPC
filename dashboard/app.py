"""Amazon PPC BigQuery Dashboard
=============================

Clean Flask backend for browsing Amazon PPC BigQuery tables.

Project: Amazon PPC
Project ID: amazon-ppc-474902
Service Account:
    bigquery-data-reader@amazon-ppc-474902.iam.gserviceaccount.com
"""

import os
import sys
import logging
from datetime import datetime, timezone

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from google.cloud import bigquery

# Add parent directory so gcp_credentials can be imported from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gcp_credentials import load_credentials

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Flask app
# ------------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
PROJECT_ID = os.getenv("GCP_PROJECT_ID") \
    or os.getenv("GOOGLE_CLOUD_PROJECT") \
    or "amazon-ppc-474902"

DATASET_ID = os.getenv("BIGQUERY_DATASET", "amazon_ppc")

# Helpful error message shown when BigQuery credentials cannot be loaded.
BIGQUERY_CREDENTIAL_ERROR = (
    "Could not load Google Cloud credentials for BigQuery. "
    "Please ensure GCP_SERVICE_ACCOUNT_KEY or GOOGLE_APPLICATION_CREDENTIALS is set."
)

# Valid chart types for /api/chart-data/<chart_type>
VALID_CHART_TYPES = {"daily_performance", "campaign_performance"}

# ------------------------------------------------------------------------------
# Date column mapping
# ------------------------------------------------------------------------------
DATE_COLUMN_BY_TABLE = {
    "optimization_results": "timestamp",
    "optimization_progress": "timestamp",
    "optimization_errors": "timestamp",
    "optimizer_run_events": "timestamp",

    "campaign_details": "segments_date",
    "campaign_performance": "segments_date",
    "keyword_performance": "segments_date",
    "search_term_reports": "segments_date",

    "sp_campaigns_v3": "segments_date",
    "sp_campaign_metrics": "startDate",
}


def build_date_filter(table: str, days: int) -> str:
    if days <= 0:
        return ""
    col = DATE_COLUMN_BY_TABLE.get(table)
    if not col:
        return ""
    return f"WHERE DATE({col}) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)"


def build_order_by(table: str) -> str:
    col = DATE_COLUMN_BY_TABLE.get(table)
    return f"ORDER BY {col} DESC" if col else ""


# ------------------------------------------------------------------------------
# BigQuery Client
# ------------------------------------------------------------------------------
def get_bigquery_client():
    """
    Initialize and return a BigQuery client.

    Returns:
        Tuple of (client, error_message).
        On success: (bigquery.Client, None)
        On failure: (None, str) where str is a helpful error message.
    """
    try:
        credentials = load_credentials()
        if credentials is not None:
            client = bigquery.Client(project=PROJECT_ID, credentials=credentials)
        else:
            client = bigquery.Client(project=PROJECT_ID)
        logger.info(f"✓ BigQuery client ready for {PROJECT_ID}")
        return client, None
    except Exception as e:
        error_msg = f"{BIGQUERY_CREDENTIAL_ERROR} Error details: {str(e)}"
        logger.error(f"BigQuery client init failed: {e}")
        return None, error_msg


def _serialize_row(row):
    """Convert a BigQuery row to a JSON-serialisable dict."""
    result = {}
    for k, v in dict(row).items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project": PROJECT_ID,
        "dataset": DATASET_ID,
    })


@app.route("/api/tables")
def list_tables():
    client, error_msg = get_bigquery_client()
    if not client:
        return jsonify({"error": error_msg}), 500

    try:
        tables = client.list_tables(f"{PROJECT_ID}.{DATASET_ID}")
        out = []
        for t in tables:
            meta = client.get_table(t.reference)
            out.append({
                "table_id": t.table_id,
                "num_rows": meta.num_rows,
                "size_bytes": meta.num_bytes,
                "modified": meta.modified.isoformat() if meta.modified else None,
            })
        return jsonify({"tables": out})
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/table/<table>")
def table_data(table):
    client, error_msg = get_bigquery_client()
    if not client:
        return jsonify({"error": error_msg}), 500

    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    days = request.args.get("days", 30, type=int)

    where_clause = build_date_filter(table, days)
    order_clause = build_order_by(table)

    data_sql = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.{table}`
        {where_clause}
        {order_clause}
        LIMIT {limit}
        OFFSET {offset}
    """
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM `{PROJECT_ID}.{DATASET_ID}.{table}`
        {where_clause}
    """

    try:
        rows = [_serialize_row(r) for r in client.query(data_sql).result()]
        count_rows = list(client.query(count_sql).result())
        total_count = count_rows[0]["total"] if count_rows else 0

        return jsonify({
            "table_name": table,
            "rows": rows,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        logger.error(f"Error querying table {table}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/table/<table>/schema")
def table_schema(table):
    client, error_msg = get_bigquery_client()
    if not client:
        return jsonify({"error": error_msg}), 500

    try:
        t = client.get_table(f"{PROJECT_ID}.{DATASET_ID}.{table}")
        return jsonify({
            "table_name": table,
            "schema": [
                {
                    "name": f.name,
                    "field_type": f.field_type,
                    "mode": f.mode,
                    "description": f.description,
                }
                for f in t.schema
            ],
            "num_rows": t.num_rows,
            "size_bytes": t.num_bytes,
        })
    except Exception as e:
        logger.error(f"Error getting schema for table {table}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/summary")
def summary():
    client, error_msg = get_bigquery_client()
    if not client:
        return jsonify({"error": error_msg}), 500

    # Use deduplication to prevent counting overlapping lookback windows multiple times.
    # Each optimization run contains aggregated metrics from its lookback period.
    # Taking only the most recent run per day prevents duplicate counting.
    # Using run_id as secondary sort ensures deterministic results.
    sql = f"""
        WITH deduplicated_runs AS (
            SELECT
                total_spend,
                total_sales,
                average_acos,
                keywords_optimized,
                timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY DATE(timestamp)
                    ORDER BY timestamp DESC, run_id DESC
                ) AS rn
            FROM `{PROJECT_ID}.{DATASET_ID}.optimization_results`
        )
        SELECT
            COUNT(*) AS total_runs,
            SUM(keywords_optimized) AS total_keywords_optimized,
            (SELECT COUNT(DISTINCT campaign_id)
             FROM `{PROJECT_ID}.{DATASET_ID}.campaign_details`) AS total_campaigns_analyzed,
            AVG(average_acos) AS avg_acos,
            SUM(total_spend) AS total_spend,
            SUM(total_sales) AS total_sales,
            MAX(timestamp) AS last_run
        FROM deduplicated_runs
        WHERE rn = 1
    """

    try:
        rows = list(client.query(sql).result())
        if not rows:
            return jsonify({"summary": {}})

        row = _serialize_row(rows[0])
        return jsonify({"summary": row})
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/chart-data/<chart_type>")
def chart_data(chart_type):
    if chart_type not in VALID_CHART_TYPES:
        return jsonify({"error": f"Unknown chart type: {chart_type}"}), 400

    client, error_msg = get_bigquery_client()
    if not client:
        return jsonify({"error": error_msg}), 500

    days = request.args.get("days", 30, type=int)

    try:
        if chart_type == "daily_performance":
            sql = f"""
                SELECT
                    DATE(timestamp) AS date,
                    COUNT(*) AS runs,
                    SUM(keywords_optimized) AS keywords_optimized,
                    AVG(average_acos) AS avg_acos,
                    SUM(total_spend) AS total_spend,
                    SUM(total_sales) AS total_sales
                FROM `{PROJECT_ID}.{DATASET_ID}.optimization_results`
                WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
                GROUP BY date
                ORDER BY date DESC
            """
        else:  # campaign_performance
            sql = f"""
                SELECT
                    campaign_name,
                    SUM(spend) AS total_spend,
                    SUM(sales) AS total_sales,
                    AVG(acos) AS avg_acos
                FROM `{PROJECT_ID}.{DATASET_ID}.campaign_details`
                WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
                GROUP BY campaign_name
                ORDER BY total_spend DESC
                LIMIT 10
            """

        rows = [_serialize_row(r) for r in client.query(sql).result()]
        return jsonify({"chart_type": chart_type, "data": rows})
    except Exception as e:
        logger.error(f"Error getting chart data for {chart_type}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/bigquery-health")
def bigquery_health():
    """Detailed BigQuery connectivity health check."""
    client, error_msg = get_bigquery_client()

    if client is None:
        return jsonify({
            "status": "unhealthy",
            "bigquery": {
                "client_initialized": False,
                "client_error": error_msg,
            },
        }), 500

    return jsonify({
        "status": "healthy",
        "bigquery": {
            "client_initialized": True,
            "client_error": None,
            "project": PROJECT_ID,
            "dataset": DATASET_ID,
        },
    })


# ------------------------------------------------------------------------------
# Run
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

