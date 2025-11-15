#!/usr/bin/env bash
# Test Amazon token exchange directly and inspect the access token
# Usage: ./test-token-exchange.sh [PROJECT_ID]

set -euo pipefail

PROJECT_ID="${1:-amazon-ppc-474902}"

echo "======================================================================"
echo "Amazon Token Exchange Tester"
echo "======================================================================"
echo ""

# Load secrets
echo "Loading secrets from Secret Manager..."
AMAZON_CLIENT_ID=$(gcloud secrets versions access latest --secret="AMAZON_CLIENT_ID" --project="${PROJECT_ID}" 2>/dev/null)
AMAZON_CLIENT_SECRET=$(gcloud secrets versions access latest --secret="AMAZON_CLIENT_SECRET" --project="${PROJECT_ID}" 2>/dev/null)
AMAZON_REFRESH_TOKEN=$(gcloud secrets versions access latest --secret="AMAZON_REFRESH_TOKEN" --project="${PROJECT_ID}" 2>/dev/null)
AMAZON_PROFILE_ID=$(gcloud secrets versions access latest --secret="AMAZON_PROFILE_ID" --project="${PROJECT_ID}" 2>/dev/null)

if [[ -z "${AMAZON_CLIENT_ID}" ]]; then
    echo "ERROR: Failed to load secrets"
    exit 1
fi

echo "✓ Secrets loaded"
echo ""

# Test token exchange
echo "Testing token exchange..."
RESPONSE=$(curl -s -X POST https://api.amazon.com/auth/o2/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=refresh_token" \
    -d "refresh_token=${AMAZON_REFRESH_TOKEN}" \
    -d "client_id=${AMAZON_CLIENT_ID}" \
    -d "client_secret=${AMAZON_CLIENT_SECRET}")

echo "Response received"
echo ""

# Parse access token
ACCESS_TOKEN=$(echo "${RESPONSE}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null || echo "")

if [[ -z "${ACCESS_TOKEN}" ]]; then
    echo "❌ Failed to get access token"
    echo "Response:"
    echo "${RESPONSE}"
    exit 1
fi

echo "✅ Access token obtained"
echo "Token length: ${#ACCESS_TOKEN} characters"
echo ""

# Check for whitespace in token
if [[ "${ACCESS_TOKEN}" =~ [[:space:]] ]]; then
    echo "❌ WARNING: Access token contains WHITESPACE!"
    echo ""
    if [[ "${ACCESS_TOKEN}" =~ " " ]]; then
        echo "  - Contains SPACES"
        SPACE_COUNT=$(echo -n "${ACCESS_TOKEN}" | tr -cd ' ' | wc -c)
        echo "  - Number of spaces: ${SPACE_COUNT}"
    fi
    if [[ "${ACCESS_TOKEN}" =~ $'\n' ]]; then
        echo "  - Contains NEWLINES"
    fi
    if [[ "${ACCESS_TOKEN}" =~ $'\t' ]]; then
        echo "  - Contains TABS"
    fi
    if [[ "${ACCESS_TOKEN}" =~ $'\r' ]]; then
        echo "  - Contains CARRIAGE RETURNS"
    fi
else
    echo "✓ No whitespace detected in access token"
fi

echo ""
echo "Token preview:"
echo "  First 30 chars: '${ACCESS_TOKEN:0:30}'"
if [[ ${#ACCESS_TOKEN} -gt 30 ]]; then
    echo "  Last 30 chars: '${ACCESS_TOKEN: -30}'"
fi

echo ""
echo "======================================================================"
echo "Testing /v2/profiles endpoint with this token..."
echo "======================================================================"
echo ""

PROFILES_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Amazon-Advertising-API-ClientId: ${AMAZON_CLIENT_ID}" \
    -H "Content-Type: application/json" \
    https://advertising-api.amazon.com/v2/profiles)

HTTP_CODE=$(echo "${PROFILES_RESPONSE}" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
PROFILES_BODY=$(echo "${PROFILES_RESPONSE}" | sed 's/HTTP_CODE:[0-9]*$//')

echo "Response code: ${HTTP_CODE}"

if [[ "${HTTP_CODE}" == "200" ]]; then
    echo "✅ Profiles endpoint succeeded"
    PROFILE_COUNT=$(echo "${PROFILES_BODY}" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "Profile count: ${PROFILE_COUNT}"
else
    echo "❌ Profiles endpoint failed"
    echo "Response:"
    echo "${PROFILES_BODY}"
fi

echo ""
echo "======================================================================"
echo "Testing /sp/campaigns endpoint with this token..."
echo "======================================================================"
echo ""

CAMPAIGNS_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Amazon-Advertising-API-ClientId: ${AMAZON_CLIENT_ID}" \
    -H "Amazon-Advertising-API-Scope: ${AMAZON_PROFILE_ID}" \
    -H "Amazon-Advertising-API-Version: v2" \
    -H "Content-Type: application/json" \
    "https://advertising-api.amazon.com/sp/campaigns?startIndex=0&count=5")

HTTP_CODE=$(echo "${CAMPAIGNS_RESPONSE}" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
CAMPAIGNS_BODY=$(echo "${CAMPAIGNS_RESPONSE}" | sed 's/HTTP_CODE:[0-9]*$//')

echo "Response code: ${HTTP_CODE}"

if [[ "${HTTP_CODE}" == "200" ]]; then
    echo "✅ Campaigns endpoint succeeded!"
    CAMPAIGN_COUNT=$(echo "${CAMPAIGNS_BODY}" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "Campaign count: ${CAMPAIGN_COUNT}"
    echo ""
    echo "SUCCESS! Campaigns are accessible."
else
    echo "❌ Campaigns endpoint failed"
    echo "Response:"
    echo "${CAMPAIGNS_BODY}"
    echo ""
    echo "This is the SAME error the optimizer is getting."
fi

echo ""
echo "======================================================================"
