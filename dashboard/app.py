"""Amazon PPC BigQuery Dashboard
=============================

Clean Flask backend for browsing Amazon PPC BigQuery tables.

Project: Amazon PPC
Project ID: amazon-ppc-474902
Service Account:
    bigquery-data-reader@amazon-ppc-474902.iam.gserviceaccount.com
"""

import os
import traceback
import logging
from datetime import datetime

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from google.cloud import bigquery

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

# ------------------------------------------------------------------------------
# Date column mapping (NO MORE `timestamp` ERRORS)
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
def get_bq_client():
    try:
        client = bigquery.Client(project=PROJECT_ID)
        logger.info(f"✓ BigQuery client ready for {PROJECT_ID}")
        return client
    except Exception as e:
        logger.error("BigQuery client init failed")
        logger.error(traceback.format_exc())
        raise RuntimeError(str(e))

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/tables")
def list_tables():
    client = get_bq_client()
    tables = client.list_tables(f"{PROJECT_ID}.{DATASET_ID}")

    out = []
    for t in tables:
        meta = client.get_table(t.reference)
        out.append({
            "table_id": t.table_id,
            "rows": meta.num_rows,
            "size_bytes": meta.num_bytes,
            "modified": meta.modified.isoformat() if meta.modified else None,
        })

    return jsonify({"tables": out})

@app.route("/api/table/<table>")
def table_data(table):
    client = get_bq_client()

    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    days = request.args.get("days", 30, type=int)

    where_clause = build_date_filter(table, days)
    order_clause = build_order_by(table)

    sql = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.{table}`
        {where_clause}
        {order_clause}
        LIMIT {limit}
        OFFSET {offset}
    """

    rows = []
    for r in client.query(sql):
        row = dict(r)
        for k, v in row.items():
            if isinstance(v, datetime):
                row[k] = v.isoformat()
        rows.append(row)

    return jsonify({
        "table": table,
        "rows": rows,
        "limit": limit,
        "offset": offset
    })

@app.route("/api/table/<table>/schema")
def table_schema(table):
    client = get_bq_client()
    t = client.get_table(f"{PROJECT_ID}.{DATASET_ID}.{table}")

    return jsonify({
        "table": table,
        "schema": [
            {
                "name": f.name,
                "type": f.field_type,
                "mode": f.mode,
                "description": f.description
            }
            for f in t.schema
        ],
        "rows": t.num_rows,
        "size_bytes": t.num_bytes
    })

@app.route("/api/summary")
def summary():
    client = get_bq_client()

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
            SUM(keywords_optimized) AS keywords_optimized,
            AVG(average_acos) AS avg_acos,
            SUM(total_spend) AS total_spend,
            SUM(total_sales) AS total_sales,
            MAX(timestamp) AS last_run
        FROM deduplicated_runs
        WHERE rn = 1
    """

    rows = list(client.query(sql))
    if not rows:
        return jsonify({})

    row = dict(rows[0])
    if row.get("last_run"):
        row["last_run"] = row["last_run"].isoformat()

    return jsonify(row)

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "project": PROJECT_ID,
        "dataset": DATASET_ID,
        "time": datetime.utcnow().isoformat()
    })

# ------------------------------------------------------------------------------
# Run
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

