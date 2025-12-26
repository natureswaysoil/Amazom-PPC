import os
import time
import gzip
import json
import logging
from io import BytesIO
from typing import Dict, List, Tuple

import pandas as pd
import requests
from google.cloud import bigquery

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "14"))
MIN_CLICKS_ADD = int(os.getenv("MIN_CLICKS_ADD", "12"))
MIN_ORDERS_ADD = int(os.getenv("MIN_ORDERS_ADD", "1"))
MAX_ACOS_TO_ADD = float(os.getenv("MAX_ACOS_TO_ADD", "0.35"))

MIN_BID = float(os.getenv("MIN_BID", "0.35"))
MAX_BID = float(os.getenv("MAX_BID", "5.00"))

BQ_PROJECT = os.getenv("BQ_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
BQ_DATASET = os.getenv("BQ_DATASET", "amazon_ppc")

def clamp(x, lo, hi): return max(lo, min(hi, x))

def _parse_gzip_json_lines(raw: bytes) -> pd.DataFrame:
    with gzip.GzipFile(fileobj=BytesIO(raw)) as gz:
        lines = gz.read().splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    return pd.DataFrame(rows)

def _download_report_file(url: str) -> pd.DataFrame:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    # v3 commonly returns GZIP_JSON when requested; handle both.
    if r.content[:2] == b"\x1f\x8b":  # gzip magic
        return _parse_gzip_json_lines(r.content)
    # fallback: try JSONL then CSV
    try:
        return pd.read_json(BytesIO(r.content), lines=True)
    except Exception:
        return pd.read_csv(BytesIO(r.content))

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

    logger.info("🚀 Starting keyword harvest")

    # 1) Create SP Search Term report (v3)
    # NOTE: reportTypeId names can vary; this is the correct *pattern*.
    # If Amazon returns 400 invalid reportTypeId, we’ll switch to your account’s supported ID.
    start_date = (pd.Timestamp.utcnow().date() - pd.Timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end_date = (pd.Timestamp.utcnow().date() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    payload = {
        "name": f"sp_search_terms_{LOOKBACK_DAYS}d",
        "startDate": start_date,
        "endDate": end_date,
        "configuration": {
            "adProduct": "SPONSORED_PRODUCTS",
            "reportTypeId": "spSearchTerm",   # if this fails, we’ll adjust
            "timeUnit": "DAILY",
            "format": "GZIP_JSON"
        }
    }

    report_id = create_report(ads, payload)
    url = wait_report_success_get_url(ads, report_id, timeout_s=900)
    df = _download_report_file(url)

    if df.empty:
        logger.info("No rows in search term report; exiting.")
        return

    # 2) Normalize column names (best-effort)
    # Common fields seen: campaignId, adGroupId, customerSearchTerm, clicks, cost, sales, purchases/orders
    col_map = {}
    for c in df.columns:
        lc = c.lower()
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
        raise RuntimeError(f"Search term report missing columns: {missing}. Columns present: {list(df.columns)[:40]}")

    df["clicks"] = df["clicks"].fillna(0).astype(int)
    df["orders"] = df["orders"].fillna(0).astype(int)
    df["cost"] = df["cost"].fillna(0.0).astype(float)
    df["sales"] = df["sales"].fillna(0.0).astype(float)
    df["searchTerm"] = df["searchTerm"].astype(str).str.strip()

    # 3) Aggregate at (adGroupId, searchTerm)
    g = df.groupby(["campaignId", "adGroupId", "searchTerm"], as_index=False).agg(
        clicks=("clicks", "sum"),
        orders=("orders", "sum"),
        cost=("cost", "sum"),
        sales=("sales", "sum"),
    )
    g["acos"] = g.apply(lambda r: (r["cost"]/r["sales"]) if r["sales"] > 0 else 999.0, axis=1)
    g["avgCpc"] = g.apply(lambda r: (r["cost"]/r["clicks"]) if r["clicks"] > 0 else 0.0, axis=1)

    # Candidate filter (safe MVP)
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

    # 4) Dedupe vs existing keywords in those adGroups
    adgroup_ids = sorted(cand["adGroupId"].unique().tolist())
    existing_df = ads.list_keywords_by_adgroups(adgroup_ids)

    existing_key = set()
    if not existing_df.empty:
        existing_df["keywordText"] = existing_df["keywordText"].astype(str).str.strip().str.lower()
        existing_df["matchType"] = existing_df["matchType"].astype(str).str.strip().str.upper()
        existing_key = set(
            (int(r.adGroupId), r.keywordText, r.matchType)
            for r in existing_df.itertuples(index=False)
        )

    # Dedupe vs prior harvest actions in BQ (90d)
    prior = bq.query(f"""
      SELECT adGroupId, LOWER(keywordText) AS keywordText, UPPER(matchType) AS matchType
      FROM `{BQ_PROJECT}.{BQ_DATASET}.keyword_harvest_actions`
      WHERE action='ADD_KEYWORD'
        AND ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
        AND applied = TRUE
    """).to_dataframe()

    prior_key = set((int(r.adGroupId), str(r.keywordText), str(r.matchType)) for r in prior.itertuples(index=False))

    def ok_to_add(row) -> bool:
        k = (int(row.adGroupId), str(row.searchTerm).lower(), str(row.matchType).upper())
        return (k not in existing_key) and (k not in prior_key)

    cand["shouldAdd"] = cand.apply(ok_to_add, axis=1)
    to_add = cand[cand["shouldAdd"]].copy()

    if to_add.empty:
        logger.info("All candidates already exist or were added recently; exiting.")
        return

    # 5) POST /sp/keywords (batch)
    payloads = []
    for r in to_add.itertuples(index=False):
        payloads.append({
            "campaignId": int(r.campaignId),
            "adGroupId": int(r.adGroupId),
            "keywordText": str(r.searchTerm),
            "matchType": str(r.matchType),
            "bid": float(r.bid),
            "state": "enabled"
        })

    results = ads.create_keywords(payloads)

    # 6) Write actions to BigQuery
    actions = to_add.copy()
    actions["ts"] = pd.Timestamp.utcnow()
    actions["action"] = "ADD_KEYWORD"
    actions["keywordText"] = actions["searchTerm"]
    actions["applied"] = True
    # If you want, parse results to mark failures; MVP sets applied=True if API call returned 200.

    load_cols = ["ts","action","campaignId","adGroupId","searchTerm","keywordText","matchType","bid","clicks","orders","sales","cost","acos","applied"]
    bq.load_table_from_dataframe(actions[load_cols], f"{BQ_PROJECT}.{BQ_DATASET}.keyword_harvest_actions").result()

    logger.info(f"✅ keyword_harvest added={len(to_add)} candidates={len(cand)} adGroups={len(adgroup_ids)} api_results={len(results)}")
