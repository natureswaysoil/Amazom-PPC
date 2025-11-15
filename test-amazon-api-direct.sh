#!/bin/bash

# Test Amazon Ads API authentication directly
# This helps diagnose the 403 error

set -e

PROJECT_ID="amazon-ppc-474902"

echo "================================================"
echo "Testing Amazon Ads API Authentication"
echo "================================================"
echo ""

echo "1. Getting credentials from Secret Manager..."
CLIENT_ID=$(gcloud secrets versions access latest --secret="amazon-client-id" --project="${PROJECT_ID}")
CLIENT_SECRET=$(gcloud secrets versions access latest --secret="amazon-client-secret" --project="${PROJECT_ID}")
REFRESH_TOKEN=$(gcloud secrets versions access latest --secret="amazon-refresh-token" --project="${PROJECT_ID}")
PROFILE_ID=$(gcloud secrets versions access latest --secret="ppc-profile-id" --project="${PROJECT_ID}")

echo "Client ID: ${CLIENT_ID:0:20}..."
echo "Client Secret: ${CLIENT_SECRET:0:15}..."
echo "Refresh Token: ${REFRESH_TOKEN:0:15}..."
echo "Profile ID: $PROFILE_ID"
echo ""

echo "2. Getting access token from Amazon..."
TOKEN_RESPONSE=$(curl -s -X POST https://api.amazon.com/auth/o2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=${REFRESH_TOKEN}" \
  -d "client_id=${CLIENT_ID}" \
  -d "client_secret=${CLIENT_SECRET}")

echo "Token response:"
echo "$TOKEN_RESPONSE" | jq .

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')

if [ "$ACCESS_TOKEN" == "null" ] || [ -z "$ACCESS_TOKEN" ]; then
  echo ""
  echo "❌ Failed to get access token!"
  exit 1
fi

echo ""
echo "✅ Access token obtained: ${ACCESS_TOKEN:0:20}..."
echo "Token length: ${#ACCESS_TOKEN}"
echo ""

echo "3. Testing Amazon Ads API with profiles endpoint..."
PROFILES_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Amazon-Advertising-API-ClientId: ${CLIENT_ID}" \
  -H "Content-Type: application/json" \
  https://advertising-api.amazon.com/v2/profiles)

HTTP_STATUS=$(echo "$PROFILES_RESPONSE" | grep "HTTP_STATUS" | cut -d':' -f2)
RESPONSE_BODY=$(echo "$PROFILES_RESPONSE" | sed '/HTTP_STATUS/d')

echo "HTTP Status: $HTTP_STATUS"
echo "Response:"
echo "$RESPONSE_BODY" | jq . 2>/dev/null || echo "$RESPONSE_BODY"
echo ""

if [ "$HTTP_STATUS" != "200" ]; then
  echo "❌ Profiles API call failed with status $HTTP_STATUS"
else
  echo "✅ Profiles API call successful!"
fi

echo ""
echo "4. Testing campaigns endpoint (with API version)..."
CAMPAIGNS_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Amazon-Advertising-API-ClientId: ${CLIENT_ID}" \
  -H "Amazon-Advertising-API-Scope: ${PROFILE_ID}" \
  -H "Content-Type: application/json" \
  https://advertising-api.amazon.com/sp/campaigns/2024-05-01)

HTTP_STATUS=$(echo "$CAMPAIGNS_RESPONSE" | grep "HTTP_STATUS" | cut -d':' -f2)
RESPONSE_BODY=$(echo "$CAMPAIGNS_RESPONSE" | sed '/HTTP_STATUS/d')

echo "HTTP Status: $HTTP_STATUS"
echo "Response (first 500 chars):"
echo "$RESPONSE_BODY" | cut -c1-500
echo ""

if [ "$HTTP_STATUS" != "200" ]; then
  echo "❌ Campaigns API call failed with status $HTTP_STATUS"
  echo ""
  echo "Full error response:"
  echo "$RESPONSE_BODY" | jq . 2>/dev/null || echo "$RESPONSE_BODY"
else
  echo "✅ Campaigns API call successful!"
  CAMPAIGN_COUNT=$(echo "$RESPONSE_BODY" | jq '. | length' 2>/dev/null || echo "0")
  echo "Number of campaigns returned: $CAMPAIGN_COUNT"
fi

echo ""
echo "================================================"
echo "Diagnosis Complete"
echo "================================================"
