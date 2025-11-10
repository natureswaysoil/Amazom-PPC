#!/bin/bash
# Quick deployment script for Amazon PPC Optimizer

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "=========================================="
echo "Deploying Amazon PPC Optimizer"
echo "=========================================="
echo ""

# Pull latest code
echo "Pulling latest code..."
git pull origin main
echo ""

# Deploy function
echo "Deploying to Cloud Functions..."
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
  --set-env-vars=LOG_LEVEL=INFO \
  --set-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest" \
  --project="$PROJECT_ID"

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""

# Get function URL
FUNC_URL=$(gcloud functions describe "$FUNCTION_NAME" \
  --region="$REGION" --gen2 \
  --format='value(serviceConfig.uri)' \
  --project="$PROJECT_ID")

echo "Function URL: $FUNC_URL"
echo ""

# Test health
echo "Testing health endpoint..."
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$FUNC_URL?health=true" | python3 -m json.tool

echo ""
echo ""
echo "To view logs:"
echo "  gcloud functions logs read $FUNCTION_NAME --region=$REGION --project=$PROJECT_ID --limit=50"
