#!/bin/bash

# Check BigQuery data and run comprehensive optimizer test

set -e

PROJECT_ID="amazon-ppc-474902"
DATASET="amazon_ppc"

echo "================================================"
echo "BigQuery Data Verification"
echo "================================================"
echo ""

echo "1. Checking optimization_results table..."
RESULTS_COUNT=$(bq query --use_legacy_sql=false --format=csv --project_id="${PROJECT_ID}" \
  "SELECT COUNT(*) as count FROM \`${PROJECT_ID}.${DATASET}.optimization_results\`" | tail -n 1)
echo "   Rows in optimization_results: ${RESULTS_COUNT}"

echo ""
echo "2. Checking campaign_details table..."
CAMPAIGN_COUNT=$(bq query --use_legacy_sql=false --format=csv --project_id="${PROJECT_ID}" \
  "SELECT COUNT(*) as count FROM \`${PROJECT_ID}.${DATASET}.campaign_details\`" 2>/dev/null | tail -n 1 || echo "0")
echo "   Rows in campaign_details: ${CAMPAIGN_COUNT}"

echo ""
echo "3. Recent optimization runs..."
bq query --use_legacy_sql=false --format=pretty --project_id="${PROJECT_ID}" \
  "SELECT 
    timestamp,
    feature_name,
    action_type,
    entity_id,
    old_value,
    new_value
   FROM \`${PROJECT_ID}.${DATASET}.optimization_results\`
   ORDER BY timestamp DESC
   LIMIT 10"

echo ""
echo "================================================"
echo "Cloud Function Test"
echo "================================================"
echo ""

echo "Testing Cloud Function with all features..."
FUNCTION_URL="https://us-central1-${PROJECT_ID}.cloudfunctions.net/amazon-ppc-optimizer"

gcloud functions call amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --data='{
    "dry_run": true,
    "force": true,
    "features": ["bid_optimization", "keyword_discovery", "negative_keywords", "campaign_management", "dayparting"],
    "verify_sample_size": 10
  }'

echo ""
echo "================================================"
echo "Service URLs"
echo "================================================"
echo ""
echo "Cloud Function: ${FUNCTION_URL}"
echo ""
echo "Cloud Run Services:"
gcloud run services list --project="${PROJECT_ID}" --format="table(metadata.name,status.url)" | grep -E "amazon-ppc|ppc-optimizer"

echo ""
