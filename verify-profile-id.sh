#!/bin/bash
# List Amazon Ads profiles to verify profile_id

set -e

PROJECT_ID="amazon-ppc-474902"

echo "=========================================="
echo "Amazon Ads Profile Verification"
echo "=========================================="
echo ""

# Get credentials
CLIENT_ID=$(gcloud secrets versions access latest --secret=amazon-client-id --project="$PROJECT_ID")
CLIENT_SECRET=$(gcloud secrets versions access latest --secret=amazon-client-secret --project="$PROJECT_ID")
REFRESH_TOKEN=$(gcloud secrets versions access latest --secret=amazon-refresh-token --project="$PROJECT_ID")
CURRENT_PROFILE_ID=$(gcloud secrets versions access latest --secret=ppc-profile-id --project="$PROJECT_ID")

echo "Current Profile ID in secrets: $CURRENT_PROFILE_ID"
echo ""

# Get access token
echo "Getting access token..."
TOKEN_RESPONSE=$(curl -s -X POST https://api.amazon.com/auth/o2/token \
  -d grant_type=refresh_token \
  -d "refresh_token=$REFRESH_TOKEN" \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_SECRET")

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$ACCESS_TOKEN" ]; then
    echo "❌ Failed to get access token"
    echo "$TOKEN_RESPONSE"
    exit 1
fi

echo "✅ Access token obtained"
echo ""

# List all profiles
echo "Listing all available profiles..."
echo "=========================================="
PROFILES=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Amazon-Advertising-API-ClientId: $CLIENT_ID" \
  -H "Content-Type: application/json" \
  https://advertising-api.amazon.com/v2/profiles)

echo "$PROFILES" | python3 -m json.tool

echo ""
echo "=========================================="
echo "Profile Analysis"
echo "=========================================="

# Check if current profile ID exists in the list
if echo "$PROFILES" | grep -q "\"profileId\": $CURRENT_PROFILE_ID"; then
    echo "✅ Current profile ID ($CURRENT_PROFILE_ID) FOUND in available profiles"
    echo ""
    echo "Profile details:"
    echo "$PROFILES" | python3 -c "
import sys, json
profiles = json.load(sys.stdin)
for p in profiles:
    if str(p.get('profileId')) == '$CURRENT_PROFILE_ID':
        print(f\"  Profile ID: {p.get('profileId')}\")
        print(f\"  Country: {p.get('countryCode')}\")
        print(f\"  Currency: {p.get('currencyCode')}\")
        print(f\"  Marketplace: {p.get('marketplace')}\")
        print(f\"  Type: {p.get('accountInfo', {}).get('type')}\")
        print(f\"  Account ID: {p.get('accountInfo', {}).get('id')}\")
" 2>/dev/null || echo "  (Could not parse profile details)"
else
    echo "❌ Current profile ID ($CURRENT_PROFILE_ID) NOT FOUND in available profiles"
    echo ""
    echo "Available profile IDs:"
    echo "$PROFILES" | python3 -c "
import sys, json
try:
    profiles = json.load(sys.stdin)
    for p in profiles:
        print(f\"  - {p.get('profileId')} ({p.get('countryCode')}, {p.get('accountInfo', {}).get('type')})\")
except:
    print('  (Could not parse profiles)')
"
    echo ""
    echo "To fix, update the profile_id secret:"
    echo "  echo -n 'CORRECT_PROFILE_ID' | gcloud secrets versions add ppc-profile-id --data-file=- --project=$PROJECT_ID"
fi

echo ""
