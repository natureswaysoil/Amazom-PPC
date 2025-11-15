#!/usr/bin/env bash
# Ultra-minimal test - just show what we're sending
set -euo pipefail

PROJECT_ID="${1:-amazon-ppc-474902}"

AMAZON_CLIENT_ID=$(gcloud secrets versions access latest --secret="AMAZON_CLIENT_ID" --project="${PROJECT_ID}" 2>/dev/null)
AMAZON_REFRESH_TOKEN=$(gcloud secrets versions access latest --secret="AMAZON_REFRESH_TOKEN" --project="${PROJECT_ID}" 2>/dev/null)
AMAZON_CLIENT_SECRET=$(gcloud secrets versions access latest --secret="AMAZON_CLIENT_SECRET" --project="${PROJECT_ID}" 2>/dev/null)
AMAZON_PROFILE_ID=$(gcloud secrets versions access latest --secret="AMAZON_PROFILE_ID" --project="${PROJECT_ID}" 2>/dev/null)

TOKEN_RESPONSE=$(curl -s -X POST https://api.amazon.com/auth/o2/token \
    -d "grant_type=refresh_token&refresh_token=${AMAZON_REFRESH_TOKEN}&client_id=${AMAZON_CLIENT_ID}&client_secret=${AMAZON_CLIENT_SECRET}")

ACCESS_TOKEN=$(echo "${TOKEN_RESPONSE}" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Calling campaigns endpoint..."
echo ""

# Use -v to see headers, but filter to just the request portion
curl -v "https://advertising-api.amazon.com/sp/campaigns?startIndex=0&count=5" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Amazon-Advertising-API-ClientId: ${AMAZON_CLIENT_ID}" \
    -H "Amazon-Advertising-API-Scope: ${AMAZON_PROFILE_ID}" \
    -H "Amazon-Advertising-API-Version: v2" \
    -H "Content-Type: application/json" \
    2>&1 | tee /tmp/curl_output.txt

echo ""
echo "======================================================================"
echo "Analyzing request headers sent:"
grep "^>" /tmp/curl_output.txt || echo "No request headers captured"

echo ""
echo "======================================================================"
echo "Response body:"
grep "^{" /tmp/curl_output.txt || echo "No JSON response"
