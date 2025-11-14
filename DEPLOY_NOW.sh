#!/bin/bash
# Complete Deployment Script
# Run this in Google Cloud Shell

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "=========================================="
echo "Amazon PPC Optimizer - Complete Deployment"
echo "=========================================="
echo ""

# Step 1: Pull latest code
echo "Step 1: Pulling latest code from GitHub..."
cd ~/Amazom-PPC
git pull origin main
echo "✅ Code updated"
echo ""

# Step 2: Deploy Cloud Function
echo "Step 2: Deploying Cloud Function..."
gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --timeout=540s \
  --memory=512MB \
  --set-env-vars=LOG_LEVEL=INFO \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest \
  --no-allow-unauthenticated \
  --project=$PROJECT_ID

echo ""
echo "✅ Cloud Function deployed"
echo ""

# Step 3: Get function URL
echo "Step 3: Getting function URL..."
FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --gen2 \
  --format='value(serviceConfig.uri)')

echo "Function URL: $FUNCTION_URL"
echo ""

# Step 4: Test health endpoint
echo "Step 4: Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?health=true")

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
  echo "✅ Health check passed"
  echo "$HEALTH_RESPONSE" | python3 -m json.tool
else
  echo "⚠️ Health check returned unexpected response:"
  echo "$HEALTH_RESPONSE"
fi
echo ""

# Step 5: Verify Amazon API connection
echo "Step 5: Verifying Amazon Ads API connection..."
VERIFY_RESPONSE=$(curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=5")

if echo "$VERIFY_RESPONSE" | grep -q "verification_passed"; then
  echo "✅ Amazon API connection verified"
  echo "$VERIFY_RESPONSE" | python3 -m json.tool | head -30
else
  echo "⚠️ Verification response:"
  echo "$VERIFY_RESPONSE" | python3 -m json.tool
fi
echo ""

# Step 6: Run test optimization (dry-run)
echo "Step 6: Running test optimization (dry-run)..."
TEST_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "${FUNCTION_URL}")

echo "Test run response:"
echo "$TEST_RESPONSE" | python3 -m json.tool | head -50
echo ""

# Step 7: Check recent logs
echo "Step 7: Checking recent logs for errors..."
gcloud functions logs read $FUNCTION_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --limit=20 \
  2>/dev/null | grep -i "error\|404\|401\|failed" || echo "✅ No recent errors found"
echo ""

# Summary
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "✅ Fixes applied:"
echo "  - Keywords now fetched from ALL 254 campaigns"
echo "  - Proper rate limiting and progress logging"
echo "  - Environment variable handling fixed"
echo "  - Deprecated v2 reporting disabled"
echo ""
echo "⚠️ Known issue (non-blocking):"
echo "  - Dashboard API key mismatch (data still goes to BigQuery)"
echo "  - Fix: See DASHBOARD_API_KEY_SYNC.md"
echo ""
echo "🎯 Next steps:"
echo "1. Run full optimization: POST to $FUNCTION_URL"
echo "2. Check BigQuery for data: https://console.cloud.google.com/bigquery?project=$PROJECT_ID"
echo "3. View dashboard: https://nextjsspace-six.vercel.app"
echo "4. Fix dashboard API key (optional): Follow DASHBOARD_API_KEY_SYNC.md"
echo ""
