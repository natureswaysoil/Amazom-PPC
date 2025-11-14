#!/bin/bash
# Full deployment verification script
# Tests: Cloud Function status, Amazon API, Dashboard, End-to-end flow

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"
DASHBOARD_URL="https://nextjsspace-six.vercel.app"

echo "======================================"
echo "PPC Optimizer Deployment Verification"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check Cloud Function Status
echo "1. Checking Cloud Function status..."
FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --gen2 \
  --format='value(serviceConfig.uri)' 2>/dev/null)

if [ -z "$FUNCTION_URL" ]; then
  echo -e "${RED}✗ Cloud Function not found${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Cloud Function found${NC}"
echo "  URL: $FUNCTION_URL"
echo ""

# 2. Test Health Endpoint
echo "2. Testing Cloud Function health endpoint..."
HEALTH_RESPONSE=$(curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?health=true")

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
  echo -e "${GREEN}✓ Health check passed${NC}"
  echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
  echo -e "${RED}✗ Health check failed${NC}"
  echo "$HEALTH_RESPONSE"
fi
echo ""

# 3. Test Amazon API Connection
echo "3. Testing Amazon Ads API connection..."
VERIFY_RESPONSE=$(curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=5")

if echo "$VERIFY_RESPONSE" | grep -q "verification_passed"; then
  echo -e "${GREEN}✓ Amazon API connection verified${NC}"
  echo "$VERIFY_RESPONSE" | python3 -m json.tool 2>/dev/null | head -20
else
  echo -e "${YELLOW}⚠ Amazon API verification incomplete${NC}"
  echo "$VERIFY_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$VERIFY_RESPONSE"
fi
echo ""

# 4. Check Dashboard Status
echo "4. Checking dashboard status..."
DASHBOARD_HEALTH=$(curl -s "${DASHBOARD_URL}/api/health")

if echo "$DASHBOARD_HEALTH" | grep -q "ok"; then
  echo -e "${GREEN}✓ Dashboard is online${NC}"
  echo "$DASHBOARD_HEALTH" | python3 -m json.tool 2>/dev/null
else
  echo -e "${RED}✗ Dashboard health check failed${NC}"
  echo "$DASHBOARD_HEALTH"
fi
echo ""

# 5. Check Recent Logs
echo "5. Checking recent Cloud Function logs..."
echo "Recent errors (if any):"
gcloud functions logs read $FUNCTION_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --limit=20 \
  --format="table(time_utc, log)" \
  2>/dev/null | grep -i "error\|404\|401\|failed" || echo "  No recent errors found"
echo ""

# 6. Test Dry Run
echo "6. Running test optimization (dry-run)..."
TEST_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "${FUNCTION_URL}")

if echo "$TEST_RESPONSE" | grep -q "success\|completed"; then
  echo -e "${GREEN}✓ Test optimization completed${NC}"
  echo "$TEST_RESPONSE" | python3 -m json.tool 2>/dev/null | head -30
else
  echo -e "${YELLOW}⚠ Test optimization returned unexpected response${NC}"
  echo "$TEST_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TEST_RESPONSE"
fi
echo ""

# Summary
echo "======================================"
echo "Verification Summary"
echo "======================================"
echo "Cloud Function: $FUNCTION_URL"
echo "Dashboard: $DASHBOARD_URL"
echo ""
echo "Next steps:"
echo "1. Review any errors above"
echo "2. Check dashboard at: ${DASHBOARD_URL}"
echo "3. Run full optimization: ./deploy-quick.sh"
echo ""
