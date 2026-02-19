#!/bin/bash
set -euo pipefail

# ==============================================================================
# Show BigQuery Dataset Details (including location)
# ==============================================================================
# Displays the full metadata for a BigQuery dataset in JSON format.
# Check the "location" field to confirm the dataset is in the expected region.
#
# Usage:
#   ./scripts/show_dataset.sh
#
# Environment Variables (optional):
#   PROJECT_ID  - Google Cloud project ID (default: amazon-ppc-474902)
#   DATASET     - BigQuery dataset ID (default: amazon_ppc)
# ==============================================================================

PROJECT_ID="${PROJECT_ID:-amazon-ppc-474902}"
DATASET="${DATASET:-amazon_ppc}"

echo "=============================================================================="
echo "Show BigQuery Dataset Details"
echo "=============================================================================="
echo "Project: ${PROJECT_ID}"
echo "Dataset: ${DATASET}"
echo "=============================================================================="
echo ""

if ! command -v bq &>/dev/null; then
  echo "ERROR: bq not found. Install the Google Cloud SDK (BigQuery component) first."
  exit 1
fi

echo "Dataset metadata (first 120 lines):"
echo "------------------------------------------------------------------------------"
bq --project_id="${PROJECT_ID}" show --format=prettyjson "${PROJECT_ID}:${DATASET}" | sed -n '1,120p'
echo ""

# Extract and display the location clearly
LOCATION=$(bq --project_id="${PROJECT_ID}" show --format=prettyjson "${PROJECT_ID}:${DATASET}" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('location','unknown'))" 2>/dev/null || echo "unknown")

echo "Dataset location: ${LOCATION}"

if [[ "${LOCATION}" == "us-east4" ]]; then
  echo "✅ Location matches expected value (us-east4)."
else
  echo "⚠️  Location '${LOCATION}' does not match expected 'us-east4'."
  echo "   Ensure all services writing to this dataset are in the same region."
fi
echo "=============================================================================="
