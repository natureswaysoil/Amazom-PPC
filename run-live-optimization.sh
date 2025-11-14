#!/bin/bash
# Run LIVE Optimization with All Features
# Run this in Google Cloud Shell
# ⚠️ WARNING: This makes REAL changes to your campaigns!

set -e

FUNCTION_URL="https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app"

echo "=========================================="
echo "⚠️  LIVE PPC OPTIMIZATION"
echo "=========================================="
echo ""
echo "This will make REAL changes to your campaigns:"
echo "  - Adjust keyword bids"
echo "  - Apply dayparting multipliers"
echo "  - Add new keywords from search terms"
echo "  - Add negative keywords"
echo "  - Pause/activate campaigns"
echo ""
read -p "Are you sure you want to proceed? (type 'YES' to continue): " confirm

if [ "$confirm" != "YES" ]; then
  echo "Cancelled."
  exit 0
fi

echo ""
echo "Getting authentication token..."
TOKEN=$(gcloud auth print-identity-token)

echo ""
echo "🚀 Running LIVE Optimization..."
echo "=========================================="
echo ""

curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": false,
    "features": ["bid_optimization", "dayparting", "keyword_discovery", "negative_keywords", "campaign_management"]
  }' \
  "$FUNCTION_URL" | python3 -m json.tool

echo ""
echo ""
echo "=========================================="
echo "✅ Optimization Complete!"
echo "=========================================="
echo ""
echo "📊 View Results:"
echo "  - BigQuery: https://console.cloud.google.com/bigquery?project=amazon-ppc-474902"
echo "  - Dashboard: https://nextjsspace-six.vercel.app"
echo ""
echo "📝 Check what changed:"
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --project=amazon-ppc-474902 \
  --limit=50 \
  --format="table(time_utc, log)" \
  2>/dev/null | grep -E "increased|decreased|added|paused|activated|Updated" | tail -20

echo ""
echo "🔍 Full logs:"
echo "gcloud functions logs read amazon-ppc-optimizer --region=us-central1 --project=amazon-ppc-474902 --limit=100"
echo ""
