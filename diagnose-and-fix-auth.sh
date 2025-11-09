#!/bin/bash
# Diagnose and fix Amazon Ads API authentication issue

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "=========================================="
echo "Amazon PPC Optimizer - Auth Diagnostics"
echo "=========================================="
echo ""

# Step 1: Check recent error logs
echo "1. Checking recent error logs..."
echo "----------------------------------------"
gcloud functions logs read "$FUNCTION_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --limit=20 \
  --format="table(TIME_UTC,LOG)" \
  | grep -i "error\|fail\|exception" || echo "No recent errors in last 20 logs"

echo ""
echo ""

# Step 2: Test Amazon token endpoint directly
echo "2. Testing Amazon token endpoint with current secrets..."
echo "----------------------------------------"
CLIENT_ID=$(gcloud secrets versions access latest --secret=amazon-client-id --project="$PROJECT_ID")
CLIENT_SECRET=$(gcloud secrets versions access latest --secret=amazon-client-secret --project="$PROJECT_ID")
REFRESH_TOKEN=$(gcloud secrets versions access latest --secret=amazon-refresh-token --project="$PROJECT_ID")

echo "Client ID prefix: ${CLIENT_ID:0:15}..."
echo ""

TOKEN_RESPONSE=$(curl -s -X POST https://api.amazon.com/auth/o2/token \
  -d grant_type=refresh_token \
  -d "refresh_token=$REFRESH_TOKEN" \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_SECRET")

echo "Token endpoint response:"
echo "$TOKEN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TOKEN_RESPONSE"
echo ""

# Check if we got an access token
if echo "$TOKEN_RESPONSE" | grep -q '"access_token"'; then
    echo "✅ Token endpoint SUCCESS - credentials are valid!"
    echo ""
    
    # Check if there's a new refresh token
    NEW_REFRESH=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('refresh_token', ''))" 2>/dev/null)
    
    if [ ! -z "$NEW_REFRESH" ] && [ "$NEW_REFRESH" != "None" ]; then
        echo "⚠️  Amazon returned a ROTATED refresh token"
        echo "   Storing the new token in Secret Manager..."
        echo -n "$NEW_REFRESH" | gcloud secrets versions add amazon-refresh-token \
            --data-file=- \
            --project="$PROJECT_ID"
        echo "   ✅ New refresh token stored"
        echo ""
    fi
    
    echo "3. Pulling latest code and redeploying function..."
    echo "----------------------------------------"
    cd ~/Amazom-PPC
    git pull origin main || echo "Already up to date"
    echo ""
    
    gcloud functions deploy "$FUNCTION_NAME" \
      --gen2 \
      --runtime=python311 \
      --region="$REGION" \
      --source=. \
      --entry-point=run_optimizer \
      --trigger-http \
      --timeout=540s \
      --memory=512MB \
      --no-allow-unauthenticated \
      --set-env-vars=LOG_LEVEL=DEBUG \
      --set-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest" \
      --project="$PROJECT_ID"
    
    echo ""
    echo "4. Testing verify_connection endpoint..."
    echo "----------------------------------------"
    sleep 5
    
    FUNC_URL=$(gcloud functions describe "$FUNCTION_NAME" \
        --region="$REGION" --gen2 \
        --format='value(serviceConfig.uri)' \
        --project="$PROJECT_ID")
    
    curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
        "$FUNC_URL?verify_connection=true&verify_sample_size=5" | python3 -m json.tool
    
    echo ""
    echo ""
    echo "=========================================="
    echo "✅ COMPLETE - Check the verify_connection output above"
    echo "=========================================="
    
else
    echo "❌ Token endpoint FAILED - credentials are invalid"
    echo ""
    echo "ACTION REQUIRED:"
    echo "----------------------------------------"
    echo "1. Go to Amazon Advertising Console: https://advertising.amazon.com/"
    echo "2. Navigate to: Settings → API → OAuth 2.0"
    echo "3. Generate a NEW refresh token"
    echo "4. Store it with this command:"
    echo ""
    echo "   echo -n 'PASTE_NEW_TOKEN_HERE' | gcloud secrets versions add amazon-refresh-token \\"
    echo "     --data-file=- \\"
    echo "     --project=$PROJECT_ID"
    echo ""
    echo "5. Then run this script again"
    echo ""
fi
