#!/bin/bash
set -euo pipefail

# ==============================================================================
# List BigQuery Datasets
# ==============================================================================
# Lists all BigQuery datasets in the specified GCP project.
# Use this to confirm that the 'amazon_ppc' dataset has been created.
#
# Usage:
#   ./scripts/list_datasets.sh
#
# Environment Variables (optional):
#   PROJECT_ID  - Google Cloud project ID (default: amazon-ppc-474902)
# ==============================================================================

PROJECT_ID="${PROJECT_ID:-amazon-ppc-474902}"

echo "=============================================================================="
echo "List BigQuery Datasets"
echo "=============================================================================="
echo "Project: ${PROJECT_ID}"
echo "=============================================================================="
echo ""

if ! command -v bq &>/dev/null; then
  echo "ERROR: bq not found. Install the Google Cloud SDK (BigQuery component) first."
  exit 1
fi

echo "Datasets in project '${PROJECT_ID}':"
echo "------------------------------------------------------------------------------"
bq --project_id="${PROJECT_ID}" ls
echo ""

# Check whether the expected dataset exists
EXPECTED_DATASET="amazon_ppc"
if bq --project_id="${PROJECT_ID}" show "${PROJECT_ID}:${EXPECTED_DATASET}" &>/dev/null; then
  echo "✅ Dataset '${EXPECTED_DATASET}' exists."
else
  echo "⚠️  Dataset '${EXPECTED_DATASET}' not found."
  echo ""
  echo "Possible causes:"
  echo "  • The optimizer has not run yet (tables are auto-created on first run)."
  echo "  • Tables were created in a different project or dataset."
  echo ""
  echo "To create the dataset and tables run: ./setup-bigquery.sh"
fi
echo "=============================================================================="
