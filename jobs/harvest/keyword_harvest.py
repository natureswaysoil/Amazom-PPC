import os
import time
import gzip
import json
import logging
from io import BytesIO
from typing import Optional

import pandas as pd
import requests
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "14"))
MIN_CLICKS_ADD = int(os.getenv("MIN_CLICKS_ADD", "12"))
MIN_ORDERS_ADD = int(os.getenv("MIN_ORDERS_ADD", "1"))
MAX_ACOS_TO_ADD = float(os.getenv("MAX_ACOS_TO_ADD", "0.35"))

MIN_BID = float(os.getenv("MIN_BID", "0.35"))
MAX_BID = float(os.getenv("MAX_BID", "5.00"))

BQ_PROJECT = os.getenv("BQ_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
BQ_DATASET = os.getenv("BQ_DATASET", "amazon_ppc")

# Make this configurable so you can adjust without redeploy
SP_SEARCH_TERM_REPORT_TYPE_ID = os.getenv("SP_SEARCH_TERM_REPORT_TYPE_ID", "spSearchTerm")

def clamp(x, lo, hi): 
    return max(lo, min(hi, x))

def _parse_gzip_json_lines(raw: bytes) -> pd.DataFrame:
    with gzip.GzipFile(fileobj=BytesIO(raw)) as gz:
        lines = gz.read().splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    return pd.DataFrame(rows)

def _download_report_file(url: str) -> pd.DataFrame:
    r = requests.get(url, timeout=180)
    r.raise_for_status()

    # Try gzip first if content looks gzipped OR if URL suggests gz
    if r.content[:2] == b"\x1f\x8b" or url.lower().endswith((".gz", ".gzip")):
        try:
            return _parse_gzip_json_lines(r.content)
        except Exception as e:
            logger.warning("Failed to parse gzip json lines, falling back. err=%s", e)

    # fallback: try JSONL then CSV
    try:
        return pd.read_json(BytesIO(r.content), lines=True)
    except Exception:
        return pd.read_csv(BytesIO(r.content))

def _ensure_bq_table_exists(bq: bigquery.Client, table_id: str):
    """Create the keyword_harvest_actions table if it doesn't exist."""
    try:
        bq.get_table(table_id)
        return
    except NotFound:
        logger.warning("BQ table missing, creating: %s", table_id)

    schema = [
        bigquery.SchemaField("ts", "TIMESTAMP"),
        bigquery.SchemaField("action", "STRING"),
        bigquery.SchemaField("campaignId", "INT64"),
        bigquery.SchemaField("adGroupId", "INT64"),
        bigquery.SchemaField("searchTerm", "STRING"),
        bigquery.SchemaField("keywordText", "STRING"),
        bigquery.SchemaField("matchType", "STRING"),
        bigquery.SchemaField("bid", "FLOAT64"),
        bigquery.SchemaField("clicks", "INT64"),
        bigquery.SchemaField("orders", "INT64"),
        bigquery.SchemaField("sales", "FLOAT64"),
        bigquery.SchemaField("cost", "FLOAT64"),
        bigquery.SchemaField("acos", "FLOAT64"),
        bigquery.SchemaField("applied", "BOOL"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    bq.create_table(table)

def run_keyword_harvest():
    """
    MVP:
    - Pull SP search term report (v3 reporting, async)
    - Filter winners
    - Dedupe vs existing keywords + prior actions
    - Add keywords (phrase/exact)
    - Write actions to BigQuery
    """
    from services.amazon_ads_client import AmazonAdsClient
    from services.amazon_reporting_v3 import create_report, wait_report_success_get_url

    ads = AmazonAdsClient()
    bq = bigquery.Client(project=BQ_PROJECT)

    actions_table = f"{BQ_PROJECT}.{BQ_DATASET}.keyword_harvest_actions"
    _ensure_bq_table_exists(bq, actions_table)

    logger.info("🚀 Starting keyword harvest")

    start_date = (pd.Timestamp.utcnow().date() - pd.Timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end_date = (pd.Timestamp.utcnow().date() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    payload = {
        "name": f"sp_search_terms_{LOOKBACK_DAYS}d",
        "startDate": start_date,
        "endDate": end_date,
        "configuration": {
            "adProduct": "SPONSORED_PRODUCTS",
            "reportTypeId": SP_SEARCH_TERM_REPORT_TYPE_ID,
            "timeUnit": "DAILY",
            "format": "GZIP_JSON",
        }
    }

    # IMPORTANT: if report creation fails (400), you want the payload + response body.
    try:
        report_id = create_report(ads, payload)
    except Exception as e:
        logger.error("Report create failed. payload=%s err=%s", json.dumps(payload), e)
        raise

    url = wait_report_success_get_url(ads, report_id, timeout_s=900)
    df = _download_report_file(url)

    if df.empty:
        logger.info("No rows in search term report; exiting.")
        return

    # Normalize column names
    col_map = {}
    for c in df.columns:
        lc = str(c).lower()
        if lc in ("customersearchterm", "searchterm", "query"):
            col_map[c] = "searchTerm"
        elif lc in ("purchases", "orders", "attributedconversions14d", "attributedorders14d"):
            col_map[c] = "orders"
        elif lc in ("attributedsales14d", "sales", "attributedsales7d"):
            col_map[c] = "sales"
        elif lc in ("spend", "cost"):
            col_map[c] = "cost"
        elif lc == "clicks":
            col_map[c] = "clicks"
        elif lc == "campaignid":
            col_map[c] = "campaignId"
        elif lc == "adgroupid":
            col_map[c] = "adGroupId"
    df = df.rename(columns=col_map)

    required = {"campaignId", "adGroupId", "searchTerm", "clicks", "cost", "sales", "orders"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Search term report missing columns: {missing}. Columns present: {list(df.columns)[:60]}")

    df["clicks"] = pd.to_numeric(df["clicks"], errors="coerce").fillna(0).astype(int)
    df["orders"] = pd.to_numeric(df["orders"], errors="coerce").fillna(0).astype(int)
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0.0).astype(float)
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0.0).astype(float)
    df["searchTerm"] = df["searchTerm"].astype(str).str.strip()

    # Aggregate
    g = df.groupby(["campaignId", "adGroupId", "searchTerm"], as_index=False).agg(
        clicks=("clicks", "sum"),
        orders=("orders", "sum"),
        cost=("cost", "sum"),
        sales=("sales", "sum"),
    )
    g["acos"] = g.apply(lambda r: (r["cost"] / r["sales"]) if r["sales"] > 0 else 999.0, axis=1)
    g["avgCpc"] = g.apply(lambda r: (r["cost"] / r["clicks"]) if r["clicks"] > 0 else 0.0, axis=1)

    cand = g[
        (g["clicks"] >= MIN_CLICKS_ADD) &
        (g["orders"] >= MIN_ORDERS_ADD) &
        (g["acos"] <= MAX_ACOS_TO_ADD)
    ].copy()

    if cand.empty:
        logger.info("No candidates met thresholds; exiting.")
        return

    # Match type + bid heuristic
    cand["matchType"] = cand["orders"].apply(lambda o: "EXACT" if o >= 2 else "PHRASE")
    cand["bid"] = cand["avgCpc"].apply(lambda x: round(clamp(x * 1.10, MIN_BID, MAX_BID), 2))

    # Dedupe vs existing keywords
    adgroup_ids = sorted(cand["adGroupId"].unique().tolist())
    existing_df = ads.list_keywords_by_adgroups(adgroup_ids)

    existing_key = set()
    if not existing_df.empty and {"adGroupId", "keywordText", "matchType"}.issubset(existing_df.columns):
        existing_df["keywordText"] = existing_df["keywordText"].astype(str).str.strip().str.lower()
        existing_df["matchType"] = existing_df["matchType"].astype(str).str.strip().str.upper()
        existing_key = set(
            (int(r.adGroupId), r.keywordText, r.matchType)
            for r in existing_df.itertuples(index=False)
        )

    prior = bq.query(f"""
      SELECT adGroupId, LOWER(keywordText) AS keywordText, UPPER(matchType) AS matchType
      FROM `{actions_table}`
      WHERE action='ADD_KEYWORD'
        AND ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
        AND applied = TRUE
    """).to_dataframe()

    prior_key = set((int(r.adGroupId), str(r.keywordText), str(r.matchType)) for r in prior.itertuples(index=False))

    def ok_to_add(row) -> bool:
        k = (int(row["adGroupId"]), str(row["searchTerm"]).lower(), str(row["matchType"]).upper())
        return (k not in existing_key) and (k not in prior_key)

    cand["shouldAdd"] = cand.apply(ok_to_add, axis=1)
    to_add = cand[cand["shouldAdd"]].copy()

    if to_add.empty:
        logger.info("All candidates already exist or were added recently; exiting.")
        return

    # POST /sp/keywords
    payloads = [{
        "campaignId": int(r.campaignId),
        "adGroupId": int(r.adGroupId),
        "keywordText": str(r.searchTerm),
        "matchType": str(r.matchType),
        "bid": float(r.bid),
        "state": "enabled"
    } for r in to_add.itertuples(index=False)]

    results = ads.create_keywords(payloads)

    # Write actions to BQ (append explicitly)
    actions = to_add.copy()
    actions["ts"] = pd.Timestamp.utcnow()
    actions["action"] = "ADD_KEYWORD"
    actions["keywordText"] = actions["searchTerm"]
    actions["applied"] = True

    load_cols = ["ts","action","campaignId","adGroupId","searchTerm","keywordText","matchType","bid","clicks","orders","sales","cost","acos","applied"]

    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
    bq.load_table_from_dataframe(actions[load_cols], actions_table, job_config=job_config).result()

    logger.info("✅ keyword_harvest added=%s candidates=%s adGroups=%s api_results=%s",
                len(to_add), len(cand), len(adgroup_ids), len(results))
