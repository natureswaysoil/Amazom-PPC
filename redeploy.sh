#!/bin/bash

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "🔄 Redeploying with Latest Code"
echo "================================="
echo ""

# Make sure we have the latest code
git pull origin main

echo "Deploying function from current directory..."
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
  --max-instances=3 \
  --no-allow-unauthenticated \
  --set-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest" \
  --project="$PROJECT_ID"

echo ""
echo "✅ Redeployment complete!"
echo ""
echo "Test health endpoint:"
FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 --format='value(serviceConfig.uri)' --project="$PROJECT_ID")
echo ""
echo "curl -s -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \"${FUNCTION_URL}?health=true\""
