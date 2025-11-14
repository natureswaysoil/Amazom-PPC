#!/bin/bash
# Test Amazon Ads API endpoints directly

set -e

PROJECT_ID="amazon-ppc-474902"

echo "=========================================="
echo "Amazon Ads API Endpoint Test"
echo "=========================================="
echo ""

# Get credentials
CLIENT_ID=$(gcloud secrets versions access latest --secret=amazon-client-id --project="$PROJECT_ID")
CLIENT_SECRET=$(gcloud secrets versions access latest --secret=amazon-client-secret --project="$PROJECT_ID")
REFRESH_TOKEN=$(gcloud secrets versions access latest --secret=amazon-refresh-token --project="$PROJECT_ID")
PROFILE_ID=$(gcloud secrets versions access latest --secret=ppc-profile-id --project="$PROJECT_ID")

# Get access token
echo "Getting access token..."
ACCESS_TOKEN=$(curl -s -X POST https://api.amazon.com/auth/o2/token \
  -d grant_type=refresh_token \
  -d "refresh_token=$REFRESH_TOKEN" \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_SECRET" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "✅ Access token obtained"
echo ""

# Test various endpoints
echo "Testing API endpoints..."
echo "=========================================="

# Test 1: Get campaigns
echo ""
echo "1. GET /v2/sp/campaigns"
echo "---"
CAMPAIGNS_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Amazon-Advertising-API-ClientId: $CLIENT_ID" \
  -H "Amazon-Advertising-API-Scope: $PROFILE_ID" \
  -H "Content-Type: application/json" \
  https://advertising-api.amazon.com/v2/sp/campaigns)

HTTP_CODE=$(echo "$CAMPAIGNS_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$CAMPAIGNS_RESPONSE" | sed '/HTTP_CODE:/d')

echo "Status: $HTTP_CODE"
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ SUCCESS"
    echo "$BODY" | python3 -m json.tool | head -20
    CAMPAIGN_COUNT=$(echo "$BODY" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "Total campaigns: $CAMPAIGN_COUNT"
else
    echo "❌ FAILED"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
fi

# Test 2: Get portfolios (if campaigns fail, portfolios might work)
echo ""
echo "2. GET /v2/portfolios"
echo "---"
PORTFOLIOS_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Amazon-Advertising-API-ClientId: $CLIENT_ID" \
  -H "Amazon-Advertising-API-Scope: $PROFILE_ID" \
  -H "Content-Type: application/json" \
  https://advertising-api.amazon.com/v2/portfolios)

HTTP_CODE=$(echo "$PORTFOLIOS_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$PORTFOLIOS_RESPONSE" | sed '/HTTP_CODE:/d')

echo "Status: $HTTP_CODE"
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ SUCCESS"
    echo "$BODY" | python3 -m json.tool | head -20
else
    echo "❌ FAILED"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
fi

echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="
echo ""
echo "If campaigns returned 404 but profile exists:"
echo "  - Your account may not have any Sponsored Products campaigns created yet"
echo "  - You need to create campaigns in Amazon Seller Central first"
echo "  - Go to: https://advertising.amazon.com/ → Create Campaign"
