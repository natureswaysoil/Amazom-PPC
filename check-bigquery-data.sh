#!/bin/bash
# Check BigQuery Data Status
# Run this in Google Cloud Shell

PROJECT_ID="amazon-ppc-474902"
DATASET_ID="amazon_ppc"

echo "=========================================="
echo "BigQuery Data Status Check"
echo "=========================================="
echo ""

# Check if dataset exists
echo "1. Checking dataset..."
if gcloud bigquery datasets describe "$DATASET_ID" --project="$PROJECT_ID" &>/dev/null; then
  echo "✅ Dataset '$DATASET_ID' exists"
else
  echo "❌ Dataset '$DATASET_ID' not found"
  echo "Run: ./setup-bigquery.sh"
  exit 1
fi

echo ""
echo "2. Checking tables..."
TABLES=$(bq ls --project_id="$PROJECT_ID" "$DATASET_ID" 2>/dev/null | grep TABLE | awk '{print $1}')

if [ -z "$TABLES" ]; then
  echo "⚠️ No tables found in dataset"
else
  echo "Found tables:"
  echo "$TABLES"
fi

echo ""
echo "3. Checking row counts..."

for table in optimization_results campaign_details optimization_progress optimizer_run_events; do
  echo -n "  $table: "
  COUNT=$(bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=csv \
    "SELECT COUNT(*) as count FROM \`$PROJECT_ID.$DATASET_ID.$table\`" 2>/dev/null | tail -1)
  
  if [ -z "$COUNT" ]; then
    echo "❌ Table not found"
  elif [ "$COUNT" = "0" ]; then
    echo "⚠️ Empty (0 rows)"
  else
    echo "✅ $COUNT rows"
  fi
done

echo ""
echo "4. Last optimization run..."
LAST_RUN=$(bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --format=prettyjson \
  "SELECT timestamp, run_id, status, keywords_optimized, campaigns_analyzed 
   FROM \`$PROJECT_ID.$DATASET_ID.optimization_results\` 
   ORDER BY timestamp DESC 
   LIMIT 1" 2>/dev/null)

if [ -z "$LAST_RUN" ] || echo "$LAST_RUN" | grep -q "^\[\]$"; then
  echo "⚠️ No optimization runs found"
  echo ""
  echo "To populate data:"
  echo "  1. Run: ./test-all-features.sh (dry run)"
  echo "  2. Or: ./run-live-optimization.sh (live changes)"
else
  echo "$LAST_RUN" | python3 -m json.tool
fi

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "Dashboard: https://nextjsspace-six.vercel.app"
echo "BigQuery Console: https://console.cloud.google.com/bigquery?project=$PROJECT_ID"
echo ""
