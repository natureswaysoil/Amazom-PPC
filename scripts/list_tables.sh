#!/bin/bash
set -euo pipefail

# ==============================================================================
# List Tables in a BigQuery Dataset
# ==============================================================================
# Lists all tables in the specified BigQuery dataset and checks for the three
# tables required by the Amazon PPC Optimizer.
#
# Expected tables:
#   - optimization_results
#   - campaign_details
#   - optimizer_run_events
#
# Usage:
#   ./scripts/list_tables.sh
#
# Environment Variables (optional):
#   PROJECT_ID  - Google Cloud project ID (default: amazon-ppc-474902)
#   DATASET     - BigQuery dataset ID (default: amazon_ppc)
# ==============================================================================

PROJECT_ID="${PROJECT_ID:-amazon-ppc-474902}"
DATASET="${DATASET:-amazon_ppc}"

echo "=============================================================================="
echo "List BigQuery Tables"
echo "=============================================================================="
echo "Project: ${PROJECT_ID}"
echo "Dataset: ${DATASET}"
echo "=============================================================================="
echo ""

if ! command -v bq &>/dev/null; then
  echo "ERROR: bq not found. Install the Google Cloud SDK (BigQuery component) first."
  exit 1
fi

# Check that the dataset exists first
if ! bq --project_id="${PROJECT_ID}" show "${PROJECT_ID}:${DATASET}" &>/dev/null; then
  echo "ERROR: Dataset '${DATASET}' not found in project '${PROJECT_ID}'."
  echo "  Run scripts/list_datasets.sh to see available datasets."
  exit 1
fi

echo "Tables in '${PROJECT_ID}:${DATASET}':"
echo "------------------------------------------------------------------------------"
bq --project_id="${PROJECT_ID}" ls "${PROJECT_ID}:${DATASET}"
echo ""

# Check for required tables
REQUIRED_TABLES=("optimization_results" "campaign_details" "optimizer_run_events")
ALL_OK=true

echo "Checking required tables:"
for table in "${REQUIRED_TABLES[@]}"; do
  if bq --project_id="${PROJECT_ID}" show "${PROJECT_ID}:${DATASET}.${table}" &>/dev/null; then
    echo "  ✅ ${table}"
  else
    echo "  ❌ ${table} — MISSING"
    ALL_OK=false
  fi
done

echo ""
if [[ "${ALL_OK}" == "true" ]]; then
  echo "✅ All required tables are present."
  echo "   Run scripts/query_latest_runs.sh to check for data."
else
  echo "⚠️  Some tables are missing."
  echo "   Trigger an optimizer run so tables are auto-created, or run ./setup-bigquery.sh."
fi
echo "=============================================================================="
