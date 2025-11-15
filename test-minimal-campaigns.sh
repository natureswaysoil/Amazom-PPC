#!/usr/bin/env bash
# Minimal test with verbose output to see exact HTTP headers sent
# Usage: ./test-minimal-campaigns.sh [PROJECT_ID]

set -euo pipefail

PROJECT_ID="${1:-amazon-ppc-474902}"

echo "Loading secrets..."
AMAZON_CLIENT_ID=$(gcloud secrets versions access latest --secret="AMAZON_CLIENT_ID" --project="${PROJECT_ID}" 2>/dev/null)
AMAZON_REFRESH_TOKEN=$(gcloud secrets versions access latest --secret="AMAZON_REFRESH_TOKEN" --project="${PROJECT_ID}" 2>/dev/null)
AMAZON_CLIENT_SECRET=$(gcloud secrets versions access latest --secret="AMAZON_CLIENT_SECRET" --project="${PROJECT_ID}" 2>/dev/null)
AMAZON_PROFILE_ID=$(gcloud secrets versions access latest --secret="AMAZON_PROFILE_ID" --project="${PROJECT_ID}" 2>/dev/null)

echo "Getting access token..."
TOKEN_RESPONSE=$(curl -s -X POST https://api.amazon.com/auth/o2/token \
    -d "grant_type=refresh_token&refresh_token=${AMAZON_REFRESH_TOKEN}&client_id=${AMAZON_CLIENT_ID}&client_secret=${AMAZON_CLIENT_SECRET}")

ACCESS_TOKEN=$(echo "${TOKEN_RESPONSE}" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Access token length: ${#ACCESS_TOKEN}"
echo ""

# Test 1: Campaigns with ALL headers (verbose)
echo "======================================================================"
echo "Test 1: Full headers with verbose output"
echo "======================================================================"
curl -v \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Amazon-Advertising-API-ClientId: ${AMAZON_CLIENT_ID}" \
    -H "Amazon-Advertising-API-Scope: ${AMAZON_PROFILE_ID}" \
    -H "Amazon-Advertising-API-Version: v2" \
    -H "Content-Type: application/json" \
    "https://advertising-api.amazon.com/sp/campaigns?startIndex=0&count=5" 2>&1 | head -50

echo ""
echo "======================================================================"
echo "Test 2: Trying with different header order"
echo "======================================================================"
curl -s \
    -H "Amazon-Advertising-API-ClientId: ${AMAZON_CLIENT_ID}" \
    -H "Amazon-Advertising-API-Scope: ${AMAZON_PROFILE_ID}" \
    -H "Amazon-Advertising-API-Version: v2" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    "https://advertising-api.amazon.com/sp/campaigns?startIndex=0&count=5"

echo ""
echo "======================================================================"
echo "Test 3: Trying without Content-Type header"
echo "======================================================================"
curl -s \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Amazon-Advertising-API-ClientId: ${AMAZON_CLIENT_ID}" \
    -H "Amazon-Advertising-API-Scope: ${AMAZON_PROFILE_ID}" \
    -H "Amazon-Advertising-API-Version: v2" \
    "https://advertising-api.amazon.com/sp/campaigns?startIndex=0&count=5"

echo ""
echo "======================================================================"
echo "Test 4: Check if it's the Scope header value format"
echo "======================================================================"
echo "Profile ID value: '${AMAZON_PROFILE_ID}'"
echo "Profile ID length: ${#AMAZON_PROFILE_ID}"
echo "Profile ID has spaces: $( [[ "${AMAZON_PROFILE_ID}" =~ [[:space:]] ]] && echo "YES" || echo "NO" )"
