#!/usr/bin/env bash
set -euo pipefail

# Find which BigQuery dataset contains the PPC performance tables.
# Uses the `bq` CLI (works well in Cloud Shell / gcloud environments).
#
# Usage:
#   ./scripts/find_perf_dataset_gcloud.sh amazon-ppc-474902
#   SAMPLE=1 DAYS=7 ./scripts/find_perf_dataset_gcloud.sh amazon-ppc-474902
#
# Output:
#   Prints datasets where any of these tables exist:
#     campaign_performance, keyword_performance, search_term_reports, sp_campaign_metrics
#   If SAMPLE=1, also prints a quick 7d aggregate (best-effort) using detected columns.

PROJECT_ID="${1:-${GCP_PROJECT:-${GOOGLE_CLOUD_PROJECT:-}}}"
if [[ -z "${PROJECT_ID}" ]]; then
  echo "Missing project id. Provide as arg or set GCP_PROJECT/GOOGLE_CLOUD_PROJECT." >&2
  exit 2
fi

DAYS="${DAYS:-7}"
SAMPLE="${SAMPLE:-0}"

TABLES=(
  campaign_performance
  keyword_performance
  search_term_reports
  sp_campaign_metrics
)

DATE_CANDIDATES=(segments_date segmentsDate report_date reportDate startDate date timestamp)
SPEND_CANDIDATES=(cost spend)
SALES_CANDIDATES=(
  attributedSales7d attributedSales14d attributedSales30d
  attributed_sales_7d attributed_sales_14d attributed_sales_30d
  sales14d sales conversion_value
)

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 3; }
}

need_cmd bq

if [[ "${SAMPLE}" == "1" ]]; then
  need_cmd jq
fi

pick_col() {
  local json_cols="$1"; shift
  local candidates=("$@");
  local cand
  for cand in "${candidates[@]}"; do
    if echo "${json_cols}" | jq -e --arg c "${cand}" 'index($c) != null' >/dev/null 2>&1; then
      echo "${cand}"
      return 0
    fi
  done
  echo ""
}

echo "Project: ${PROJECT_ID}"

# List datasets. `bq ls` output format can vary; CSV is the most scriptable.
# Note: requires permission to list datasets.
mapfile -t DATASETS < <(bq --project_id="${PROJECT_ID}" ls --format=csv --max_results=100000 2>/dev/null | tail -n +2 | cut -d, -f1)

if [[ ${#DATASETS[@]} -eq 0 ]]; then
  echo "No datasets found (or you lack permissions to list datasets)." >&2
  echo "Try: bq --project_id=${PROJECT_ID} ls" >&2
  exit 4
fi

found_any=0

for ds in "${DATASETS[@]}"; do
  for tbl in "${TABLES[@]}"; do
    # bq identifiers are project:dataset.table
    if bq --project_id="${PROJECT_ID}" show --format=prettyjson "${PROJECT_ID}:${ds}.${tbl}" >/dev/null 2>&1; then
      found_any=1
      echo ""
      echo "FOUND table '${tbl}' in dataset '${ds}'"

      if [[ "${SAMPLE}" != "1" ]]; then
        continue
      fi

      # Pull schema field names.
      schema_json=$(bq --project_id="${PROJECT_ID}" show --format=prettyjson "${PROJECT_ID}:${ds}.${tbl}")
      cols_json=$(echo "${schema_json}" | jq -c '[.schema.fields[].name]')

      date_col=$(pick_col "${cols_json}" "${DATE_CANDIDATES[@]}")
      spend_col=$(pick_col "${cols_json}" "${SPEND_CANDIDATES[@]}")
      sales_col=$(pick_col "${cols_json}" "${SALES_CANDIDATES[@]}")

      echo "  date_col=${date_col:-<none>} spend_col=${spend_col:-<none>} sales_col=${sales_col:-<none>}"

      if [[ -z "${date_col}" || -z "${spend_col}" || -z "${sales_col}" ]]; then
        echo "  sample=skipped (missing date/spend/sales columns)"
        continue
      fi

      # Best-effort aggregate. Avoid query parameters for maximum compatibility.
      # SAFE_CAST handles STRING/TIMESTAMP/DATE-ish values.
      read -r -d '' QUERY <<SQL || true
SELECT
  COUNT(1) AS row_count,
  MIN(SAFE_CAST(`${date_col}` AS DATE)) AS min_day,
  MAX(SAFE_CAST(`${date_col}` AS DATE)) AS max_day,
  SUM(COALESCE(`${spend_col}`, 0)) AS spend_${DAYS}d,
  SUM(COALESCE(`${sales_col}`, 0)) AS sales_${DAYS}d
FROM `${PROJECT_ID}.${ds}.${tbl}`
WHERE SAFE_CAST(`${date_col}` AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL ${DAYS} DAY)
SQL

      echo "  running sample query (${DAYS}d)…"
      # prettyjson -> easy to paste back here.
      if ! bq --project_id="${PROJECT_ID}" query --use_legacy_sql=false --format=prettyjson "${QUERY}"; then
        echo "  sample=failed (query error)"
      fi
    fi
  done
done

if [[ "${found_any}" != "1" ]]; then
  echo ""
  echo "No target performance tables found in any dataset." >&2
  echo "If you know the dataset already, try directly: bq show ${PROJECT_ID}:DATASET.campaign_performance" >&2
  exit 5
fi

echo ""
echo "Next step (optimizer service env var):"
echo "  BQ_PERFORMANCE_DATASET_ID=<dataset that contains campaign_performance>"
