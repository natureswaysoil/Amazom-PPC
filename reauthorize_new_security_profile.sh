#!/usr/bin/env bash
set -euo pipefail

# Amazon Advertising API Reauthorization Script
# For Security Profile: Amazon- PPC- Bid- Optimizer
# Security Profile ID: amzn1.application.e5e766db2a154722b5aee7a7df59b796

PROJECT_ID="${1:-amazon-ppc-474902}"
REDIRECT_URI="https://natureswaysoil.com"

echo "=========================================================================="
echo "Amazon Advertising API - OAuth Reauthorization"
echo "=========================================================================="
echo ""
echo "This script will help you:"
echo "  1. Input new Client ID and Client Secret from Amazon Developer Console"
echo "  2. Generate OAuth authorization URL"
echo "  3. Exchange authorization code for refresh token"
echo "  4. Update Google Secret Manager"
echo "  5. Verify SP/SB access"
echo ""
echo "=========================================================================="
echo ""

# Step 1: Get Client Credentials
echo "Step 1: Enter New Security Profile Credentials"
echo "----------------------------------------------"
echo ""
echo "Go to: https://developer.amazon.com/loginwithamazon/console/site/lwa/overview.html"
echo "Find: 'Amazon- PPC- Bid- Optimizer' Security Profile"
echo ""
read -p "Enter NEW Client ID (amzn1.application-oa2-client.xxxxx): " NEW_CLIENT_ID
read -sp "Enter NEW Client Secret (amzn1.oa2-cs.v1.xxxxx): " NEW_CLIENT_SECRET
echo ""
echo ""

# Validate format
if [[ ! "$NEW_CLIENT_ID" =~ ^amzn1\.application-oa2-client\. ]]; then
    echo "❌ Error: Client ID must start with 'amzn1.application-oa2-client.'"
    exit 1
fi

if [[ ! "$NEW_CLIENT_SECRET" =~ ^amzn1\.oa2-cs\.v1\. ]]; then
    echo "❌ Error: Client Secret must start with 'amzn1.oa2-cs.v1.'"
    exit 1
fi

echo "✅ Credentials validated"
echo ""

# Step 2: Generate OAuth URL
echo "Step 2: Generate Authorization URL"
echo "-----------------------------------"
echo ""

SCOPES="advertising::campaign_management advertising::reporting"
ENCODED_SCOPES=$(echo -n "$SCOPES" | python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read()))")
AUTH_URL="https://www.amazon.com/ap/oa?client_id=${NEW_CLIENT_ID}&scope=${ENCODED_SCOPES}&response_type=code&redirect_uri=${REDIRECT_URI}"

echo "Authorization URL (copy this to your browser):"
echo ""
echo "$AUTH_URL"
echo ""
echo "Instructions:"
echo "  1. Copy the URL above"
echo "  2. Open it in your browser"
echo "  3. Sign in with your Amazon Advertising account"
echo "  4. Grant consent for Sponsored Products, Sponsored Brands, and Reporting"
echo "  5. After redirect, copy the 'code' parameter from the URL"
echo ""
read -p "Enter the authorization code from redirect URL: " AUTH_CODE
echo ""

if [[ -z "$AUTH_CODE" ]]; then
    echo "❌ Error: Authorization code is required"
    exit 1
fi

# Step 3: Exchange for Refresh Token
echo "Step 3: Exchange Authorization Code for Refresh Token"
echo "------------------------------------------------------"
echo ""

TOKEN_RESPONSE=$(curl -s -X POST https://api.amazon.com/auth/o2/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=authorization_code" \
    -d "code=${AUTH_CODE}" \
    -d "client_id=${NEW_CLIENT_ID}" \
    -d "client_secret=${NEW_CLIENT_SECRET}" \
    -d "redirect_uri=${REDIRECT_URI}")

# Check for errors
if echo "$TOKEN_RESPONSE" | grep -q "error"; then
    echo "❌ Token exchange failed:"
    echo "$TOKEN_RESPONSE" | python3 -m json.tool
    exit 1
fi

NEW_REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['refresh_token'])")
ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

if [[ -z "$NEW_REFRESH_TOKEN" ]]; then
    echo "❌ Error: Failed to extract refresh token"
    echo "$TOKEN_RESPONSE"
    exit 1
fi

echo "✅ Successfully obtained refresh token"
echo "   Token length: ${#NEW_REFRESH_TOKEN} chars"
echo ""

# Step 4: Test SP Access BEFORE updating secrets
echo "Step 4: Verify SP/SB Access with New Token"
echo "-------------------------------------------"
echo ""

PROFILE_ID=$(gcloud secrets versions access latest --secret=AMAZON_PROFILE_ID --project="$PROJECT_ID")

echo "Testing Sponsored Products access..."
SP_TEST=$(curl -s -w "\n%{http_code}" https://advertising-api.amazon.com/sp/campaigns \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Amazon-Advertising-API-ClientId: ${NEW_CLIENT_ID}" \
    -H "Amazon-Advertising-API-Scope: ${PROFILE_ID}")

SP_CODE=$(echo "$SP_TEST" | tail -n1)
SP_BODY=$(echo "$SP_TEST" | head -n-1)

echo "SP Campaigns Status: $SP_CODE"

if [[ "$SP_CODE" == "200" ]]; then
    echo "✅ Sponsored Products access VERIFIED"
    SP_COUNT=$(echo "$SP_BODY" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "   Found $SP_COUNT campaigns"
elif [[ "$SP_CODE" == "403" ]]; then
    echo "❌ Still getting 403 - SP scope may not be granted"
    echo "   Response: ${SP_BODY:0:200}"
    read -p "Continue anyway? (y/N): " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
        echo "Aborted. Please re-run OAuth with correct scopes."
        exit 1
    fi
else
    echo "⚠️  Unexpected status: $SP_CODE"
    echo "   Response: ${SP_BODY:0:200}"
fi

echo ""

# Step 5: Update Secret Manager
echo "Step 5: Update Google Secret Manager"
echo "-------------------------------------"
echo ""

echo "Updating AMAZON_CLIENT_ID..."
echo -n "$NEW_CLIENT_ID" | gcloud secrets versions add AMAZON_CLIENT_ID \
    --data-file=- \
    --project="$PROJECT_ID"

echo "Updating AMAZON_CLIENT_SECRET..."
echo -n "$NEW_CLIENT_SECRET" | gcloud secrets versions add AMAZON_CLIENT_SECRET \
    --data-file=- \
    --project="$PROJECT_ID"

echo "Updating AMAZON_REFRESH_TOKEN..."
echo -n "$NEW_REFRESH_TOKEN" | gcloud secrets versions add AMAZON_REFRESH_TOKEN \
    --data-file=- \
    --project="$PROJECT_ID"

echo ""
echo "✅ All secrets updated in Google Secret Manager"
echo ""

# Step 6: Final Verification
echo "Step 6: Final Verification with New Credentials"
echo "------------------------------------------------"
echo ""

echo "Running permission diagnostics..."
bash /workspaces/Amazom-PPC/run_sp_permission_diagnostics.sh "$PROJECT_ID" > /tmp/diagnostic_result.json 2>&1 || true

if [[ -f /tmp/diagnostic_result.json ]]; then
    SP_PERM=$(python3 -c "import sys, json; data=json.load(open('/tmp/diagnostic_result.json')); print(data.get('summary',{}).get('sp_permission_inference','unknown'))" 2>/dev/null || echo "unknown")
    
    echo ""
    if [[ "$SP_PERM" == "present" ]]; then
        echo "=========================================================================="
        echo "✅ SUCCESS! Sponsored Products permission is now ACTIVE"
        echo "=========================================================================="
        echo ""
        cat /tmp/diagnostic_result.json | python3 -m json.tool
    elif [[ "$SP_PERM" == "missing" ]]; then
        echo "=========================================================================="
        echo "⚠️  WARNING: SP permission still showing as missing"
        echo "=========================================================================="
        echo ""
        echo "Possible causes:"
        echo "  - OAuth consent didn't include SP scope"
        echo "  - Need to wait a few minutes for propagation"
        echo "  - Profile doesn't have SP enabled in Amazon Ads console"
        echo ""
        cat /tmp/diagnostic_result.json | python3 -m json.tool
    else
        echo "Diagnostic results saved to /tmp/diagnostic_result.json"
    fi
else
    echo "⚠️  Could not run diagnostics automatically"
    echo "   Run manually: ./run_sp_permission_diagnostics.sh $PROJECT_ID"
fi

echo ""
echo "=========================================================================="
echo "Next Steps:"
echo "=========================================================================="
echo ""
echo "1. Test the optimizer:"
echo "   curl 'https://YOUR-FUNCTION-URL?verify_connection=true'"
echo ""
echo "2. Run permission health check:"
echo "   curl 'https://YOUR-FUNCTION-URL?permission_health=true'"
echo ""
echo "3. If SP still blocked, verify in Amazon Ads console:"
echo "   - Go to https://advertising.amazon.com"
echo "   - Settings > API > Check granted permissions"
echo "   - Ensure 'Sponsored Products' is listed"
echo ""
echo "=========================================================================="
