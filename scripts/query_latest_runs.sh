#!/bin/bash
set -euo pipefail

# ==============================================================================
# Query Latest Optimizer Runs from BigQuery
# ==============================================================================
# Retrieves the 5 most recent rows from the optimization_results table to
# confirm that the optimizer is writing data to BigQuery.
#
# Usage:
#   ./scripts/query_latest_runs.sh
#
# Environment Variables (optional):
#   PROJECT_ID  - Google Cloud project ID (default: amazon-ppc-474902)
#   DATASET     - BigQuery dataset ID (default: amazon_ppc)
#   LIMIT       - Number of rows to return (default: 5)
# ==============================================================================

PROJECT_ID="${PROJECT_ID:-amazon-ppc-474902}"
DATASET="${DATASET:-amazon_ppc}"
LIMIT="${LIMIT:-5}"

echo "=============================================================================="
echo "Query Latest Optimizer Runs"
echo "=============================================================================="
echo "Project: ${PROJECT_ID}"
echo "Dataset: ${DATASET}"
echo "Limit:   ${LIMIT}"
echo "=============================================================================="
echo ""

if ! command -v bq &>/dev/null; then
  echo "ERROR: bq not found. Install the Google Cloud SDK (BigQuery component) first."
  exit 1
fi

QUERY="SELECT * FROM \`${PROJECT_ID}.${DATASET}.optimization_results\` LIMIT ${LIMIT}"

echo "Query: ${QUERY}"
echo "------------------------------------------------------------------------------"

if result=$(bq --project_id="${PROJECT_ID}" query --use_legacy_sql=false "${QUERY}" 2>&1); then
  echo "${result}"
  echo ""
  ROW_COUNT=$(echo "${result}" | grep -c "^|" || true)
  if [[ "${ROW_COUNT}" -gt 1 ]]; then
    echo "✅ Data found in optimization_results — optimizer is writing to BigQuery."
  else
    echo "⚠️  No rows returned."
    echo "   The optimizer may not have run yet, or BigQuery writes may be disabled."
    echo "   Ensure 'bigquery.enabled: true' is set in your optimizer config."
  fi
else
  echo "ERROR: Query failed."
  echo "${result}"
  echo ""
  echo "Troubleshooting:"
  echo "  • Confirm the dataset and table exist: scripts/list_tables.sh"
  echo "  • Confirm IAM permissions: scripts/check_iam_bindings.sh"
  exit 1
fi
echo "=============================================================================="
