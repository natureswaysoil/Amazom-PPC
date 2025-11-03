#!/bin/bash
#
# Deploy Amazon PPC Optimizer with Dashboard Integration
# Run this script from Cloud Shell or any environment with gcloud CLI configured
#

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "=========================================="
echo "Amazon PPC Optimizer - Deploy with Dashboard"
echo "=========================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Function: $FUNCTION_NAME"
echo "=========================================="
echo ""

# Set active project
echo "Setting active project..."
gcloud config set project "$PROJECT_ID"

# Deploy function with all secrets
echo ""
echo "Deploying Cloud Function (Gen2)..."
echo "This includes dashboard integration via Secret Manager"
echo ""

gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python311 \
  --region="$REGION" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest

# Get function URL
echo ""
echo "Getting function URL..."
FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
  --region="$REGION" \
  --gen2 \
  --format='value(serviceConfig.uri)')

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo "Function URL: $FUNCTION_URL"
echo ""
echo "Testing endpoints:"
echo ""
echo "1. Health Check (requires auth token):"
echo "   curl -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \\"
echo "     \"${FUNCTION_URL}?health=true\""
echo ""
echo "2. Verify Amazon Ads Connection:"
echo "   curl -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \\"
echo "     \"${FUNCTION_URL}?verify_connection=true&verify_sample_size=3\""
echo ""
echo "3. Dry Run (tests dashboard integration):"
echo "   curl -X POST -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{\"dry_run\": true, \"features\": [\"bid_optimization\"]}' \\"
echo "     \"${FUNCTION_URL}\""
echo ""
echo "=========================================="
