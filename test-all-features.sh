#!/bin/bash
# Test All Optimization Features
# Run this in Google Cloud Shell

set -e

FUNCTION_URL="https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app"

echo "=========================================="
echo "Testing All PPC Optimization Features"
echo "=========================================="
echo ""

# Get authentication token
echo "Getting authentication token..."
TOKEN=$(gcloud auth print-identity-token)

# Test 1: Health Check
echo "1. Health Check"
echo "----------------------------------------"
curl -s -H "Authorization: Bearer $TOKEN" \
  "${FUNCTION_URL}?health=true" | python3 -m json.tool
echo ""
echo ""

# Test 2: Verify API Connection
echo "2. Verify Amazon Ads API Connection"
echo "----------------------------------------"
curl -s -H "Authorization: Bearer $TOKEN" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=3" | python3 -m json.tool
echo ""
echo ""

# Test 3: Run Full Optimization (DRY RUN)
echo "3. Running FULL Optimization with ALL Features (DRY RUN)"
echo "----------------------------------------"
echo "Features: bid_optimization, dayparting, keyword_discovery, negative_keywords, campaign_management"
echo ""

curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": true,
    "features": ["bid_optimization", "dayparting", "keyword_discovery", "negative_keywords", "campaign_management"]
  }' \
  "$FUNCTION_URL" | python3 -m json.tool

echo ""
echo ""

# Test 4: Check logs for errors
echo "4. Checking Recent Logs"
echo "----------------------------------------"
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --project=amazon-ppc-474902 \
  --limit=30 \
  --format="table(time_utc, log)" \
  2>/dev/null | tail -20

echo ""
echo ""

# Summary
echo "=========================================="
echo "Test Complete!"
echo "=========================================="
echo ""
echo "✅ Features Tested:"
echo "  1. Bid Optimization - Adjusts bids based on ACOS"
echo "  2. Dayparting - Time-based bid multipliers"
echo "  3. Keyword Discovery - Finds profitable search terms"
echo "  4. Negative Keywords - Blocks wasteful spend"
echo "  5. Campaign Management - Auto pause/activate"
echo ""
echo "📊 Check Results:"
echo "  - BigQuery: https://console.cloud.google.com/bigquery?project=amazon-ppc-474902"
echo "  - Dashboard: https://nextjsspace-six.vercel.app"
echo ""
echo "🚀 Ready for Production Run?"
echo "  Remove 'dry_run: true' to apply changes to your campaigns"
echo ""
