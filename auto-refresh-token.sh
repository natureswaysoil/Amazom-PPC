#!/bin/bash
# Auto-refresh Amazon Ads API token and update Cloud Function

echo "=========================================="
echo "Amazon Ads API Token Auto-Refresh"
echo "=========================================="
echo ""

# Get credentials from secrets
echo "Fetching credentials from Secret Manager..."
REFRESH_TOKEN=$(gcloud secrets versions access latest --secret=amazon-refresh-token --project=1009540130231)
CLIENT_ID=$(gcloud secrets versions access latest --secret=amazon-client-id --project=1009540130231)
CLIENT_SECRET=$(gcloud secrets versions access latest --secret=amazon-client-secret --project=1009540130231)

echo "Requesting new access token from Amazon..."
RESPONSE=$(curl -s -X POST https://api.amazon.com/auth/o2/token \
  -d "grant_type=refresh_token" \
  -d "refresh_token=$REFRESH_TOKEN" \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_SECRET")

echo ""
echo "Response from Amazon:"
echo "$RESPONSE"
echo ""

# Extract new refresh token if present
NEW_REFRESH_TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('refresh_token', ''))" 2>/dev/null)

if [ ! -z "$NEW_REFRESH_TOKEN" ] && [ "$NEW_REFRESH_TOKEN" != "None" ]; then
  echo "✅ SUCCESS! Got new refresh token"
  echo ""
  echo "Updating secret in Secret Manager..."
  gcloud secrets versions add amazon-refresh-token \
    --data-file=- \
    --project=1009540130231 \
    <<< "$NEW_REFRESH_TOKEN"
  
  echo ""
  echo "Restarting Cloud Function to pick up new token..."
  gcloud run services update amazon-ppc-optimizer \
    --update-env-vars=LAST_UPDATED=$(date +%s) \
    --region=us-central1 \
    --project=amazon-ppc-474902
  
  echo ""
  echo "Waiting 30 seconds for service to restart..."
  sleep 30
  
  echo ""
  echo "Testing health check..."
  curl "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?health=true"
  echo ""
  echo ""
  echo "=========================================="
  echo "✅ DONE! Check if dashboard_ok is now true"
  echo "=========================================="
else
  echo "❌ FAILED to get new token"
  echo ""
  echo "The refresh token is invalid or expired."
  echo ""
  echo "You need to generate a NEW refresh token from Amazon Advertising Console:"
  echo ""
  echo "1. Go to: https://advertising.amazon.com/"
  echo "2. Navigate to: Settings → API → OAuth 2.0"
  echo "3. Generate a new refresh token"
  echo "4. Run this command with the new token:"
  echo ""
  echo "   gcloud secrets versions add amazon-refresh-token \\"
  echo "     --data-file=- \\"
  echo "     --project=1009540130231 \\"
  echo "     <<< \"YOUR_NEW_REFRESH_TOKEN\""
  echo ""
  echo "5. Then restart the function:"
  echo ""
  echo "   gcloud run services update amazon-ppc-optimizer \\"
  echo "     --update-env-vars=LAST_UPDATED=\$(date +%s) \\"
  echo "     --region=us-central1 \\"
  echo "     --project=amazon-ppc-474902"
  echo ""
fi
