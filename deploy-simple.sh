#!/bin/bash
#
# Simple deployment script for Amazon PPC Optimizer
# Use this if the full deployment script has issues
#

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "=========================================="
echo "Simple Deployment - Amazon PPC Optimizer"
echo "=========================================="
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# Deploy with minimal flags first to test
echo "Deploying function..."
echo ""

gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python311 \
  --region="$REGION" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Test with:"
echo "  curl \$(gcloud functions describe $FUNCTION_NAME --gen2 --region=$REGION --format='value(serviceConfig.uri)')/health"
echo ""
