#!/usr/bin/env python3
"""Find which BigQuery dataset holds the PPC performance tables.

This is a diagnostic helper for the live dashboard "all zeros" issue.
It scans datasets in a project looking for known performance tables such as
`campaign_performance` and `keyword_performance`, then prints:
- Dataset + table found
- Candidate date/spend/sales columns detected
- Optional quick aggregate over the last N days (best-effort)

Auth:
- Uses Application Default Credentials, or GOOGLE_APPLICATION_CREDENTIALS, or
  GCP_SERVICE_ACCOUNT_KEY/GOOGLE_APPLICATION_CREDENTIALS_JSON if your
  environment is already set up for the optimizer.

Examples:
  python scripts/find_bigquery_perf_tables.py --project amazon-ppc-474902
  python scripts/find_bigquery_perf_tables.py --project amazon-ppc-474902 --sample --days 7

If you find performance tables in dataset "ppc_data", set:
  BQ_PERFORMANCE_DATASET_ID=ppc_data
on the optimizer service.
"""

from __future__ import annotations

import argparse
import os
from typing import Iterable, Optional, Sequence

from google.cloud import bigquery


DEFAULT_TARGET_TABLES = (
    "campaign_performance",
    "keyword_performance",
    "search_term_reports",
    "sp_campaign_metrics",
)

DATE_CANDIDATES = (
    "segments_date",
    "segmentsDate",
    "report_date",
    "reportDate",
    "startDate",
    "date",
    "timestamp",
)

SPEND_CANDIDATES = (
    "cost",
    "spend",
)

SALES_CANDIDATES = (
    "attributedSales7d",
    "attributedSales14d",
    "attributedSales30d",
    "attributed_sales_7d",
    "attributed_sales_14d",
    "attributed_sales_30d",
    "sales14d",
    "sales",
    "conversion_value",
)


def _pick_column(available: Sequence[str], candidates: Iterable[str]) -> Optional[str]:
    lowered = {c.lower(): c for c in available}
    for cand in candidates:
        key = str(cand).lower()
        if key in lowered:
            return lowered[key]
    return None


def _print_kv(label: str, value: object) -> None:
    print(f"  - {label}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Locate PPC performance tables across BigQuery datasets")
    parser.add_argument(
        "--project",
        default=os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT"),
        help="GCP project id (defaults to env GCP_PROJECT/GOOGLE_CLOUD_PROJECT)",
    )
    parser.add_argument(
        "--tables",
        nargs="*",
        default=list(DEFAULT_TARGET_TABLES),
        help=f"Tables to search for (default: {', '.join(DEFAULT_TARGET_TABLES)})",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run a small aggregate query to show recent spend/sales (best-effort)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days back for the sample aggregate (default: 7)",
    )

    args = parser.parse_args()

    if not args.project:
        raise SystemExit("Missing --project (or set GCP_PROJECT/GOOGLE_CLOUD_PROJECT)")

    client = bigquery.Client(project=args.project)

    target_tables = {str(t).strip() for t in (args.tables or []) if str(t).strip()}
    if not target_tables:
        raise SystemExit("No tables specified")

    print(f"Project: {args.project}")
    print(f"Looking for tables: {', '.join(sorted(target_tables))}")

    datasets = list(client.list_datasets(args.project))
    if not datasets:
        print("No datasets found (or no permissions).")
        return 2

    any_found = False

    for ds in sorted(datasets, key=lambda d: d.dataset_id):
        dataset_id = ds.dataset_id
        dataset_ref = f"{args.project}.{dataset_id}"

        try:
            table_items = list(client.list_tables(dataset_ref))
        except Exception as exc:
            print(f"\nDataset: {dataset_id} (skipped: {exc})")
            continue

        table_ids = {t.table_id for t in table_items}
        found = sorted(table_ids.intersection(target_tables))
        if not found:
            continue

        any_found = True
        print(f"\nDataset: {dataset_id}")

        for table_id in found:
            table_fqn = f"{dataset_ref}.{table_id}"
            print(f"\nTable: {table_fqn}")

            try:
                table = client.get_table(table_fqn)
            except Exception as exc:
                _print_kv("error", f"failed to get table schema: {exc}")
                continue

            cols = [field.name for field in (table.schema or [])]
            date_col = _pick_column(cols, DATE_CANDIDATES)
            spend_col = _pick_column(cols, SPEND_CANDIDATES)
            sales_col = _pick_column(cols, SALES_CANDIDATES)
            has_profile = any(c.lower() == "profile_id" for c in cols)

            _print_kv("columns", len(cols))
            _print_kv("date_col", date_col)
            _print_kv("spend_col", spend_col)
            _print_kv("sales_col", sales_col)
            _print_kv("has_profile_id", has_profile)

            if not args.sample:
                continue

            if not (date_col and spend_col and sales_col):
                _print_kv("sample", "skipped (missing date/spend/sales columns)")
                continue

            days = max(1, min(int(args.days), 365))
            query = f"""
            SELECT
                            COUNT(1) AS row_count,
              MIN(SAFE_CAST(`{date_col}` AS DATE)) AS min_day,
              MAX(SAFE_CAST(`{date_col}` AS DATE)) AS max_day,
              SUM(COALESCE(`{spend_col}`, 0)) AS spend_{days}d,
              SUM(COALESCE(`{sales_col}`, 0)) AS sales_{days}d
            FROM `{table_fqn}`
            WHERE SAFE_CAST(`{date_col}` AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("days", "INT64", days),
                ]
            )

            try:
                rows = list(client.query(query, job_config=job_config).result(timeout=30))
                if not rows:
                    _print_kv("sample", "no rows")
                    continue
                row = rows[0]
                _print_kv("sample_row_count", row.get("row_count"))
                _print_kv("sample_min_day", row.get("min_day"))
                _print_kv("sample_max_day", row.get("max_day"))
                _print_kv(f"sample_spend_{days}d", row.get(f"spend_{days}d"))
                _print_kv(f"sample_sales_{days}d", row.get(f"sales_{days}d"))
            except Exception as exc:
                _print_kv("sample", f"failed: {exc}")

    if not any_found:
        print("\nNo target tables found in any dataset.")
        print("If you know your dataset name, rerun with --tables <table> and ensure your service account has BigQuery Metadata Viewer + Job User.")
        return 3

    print("\nNext step:")
    print("- Set BQ_PERFORMANCE_DATASET_ID to the dataset where campaign_performance lives.")
    print("- Optionally set PPC_DEBUG_BIGQUERY=true on the optimizer to log which table/columns are selected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
