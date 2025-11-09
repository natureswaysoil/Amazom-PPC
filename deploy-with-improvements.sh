#!/bin/bash
#
# Deploy Amazon PPC Optimizer with HTTP Client Improvements
# Run this script in Google Cloud Shell
#

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "=========================================="
echo "Amazon PPC Optimizer - Deploy with HTTP Improvements"
echo "=========================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Function: $FUNCTION_NAME"
echo "=========================================="
echo ""

# Set active project
echo "Setting active project..."
gcloud config set project "$PROJECT_ID"

# Verify we're in the right directory
if [ ! -f "optimizer_core.py" ] || [ ! -f "main.py" ]; then
    echo "ERROR: Must run from repository root directory"
    echo "Current directory: $(pwd)"
    exit 1
fi

echo ""
echo "Files to deploy:"
ls -lh *.py requirements.txt 2>/dev/null || true
echo ""

# Deploy function with all secrets
echo "Deploying Cloud Function (Gen2) with enhanced HTTP logging..."
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
  --set-env-vars=LOG_LEVEL=INFO \
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
echo "✅ DEPLOYMENT SUCCESSFUL"
echo "=========================================="
echo ""
echo "Function URL: $FUNCTION_URL"
echo ""
echo "Next Steps:"
echo ""
echo "1. Test the deployment:"
echo "   gcloud functions call $FUNCTION_NAME --gen2 --region=$REGION --data '{\"dry_run\":true,\"features\":[\"verify_connection\"]}'"
echo ""
echo "2. Monitor logs (in real-time):"
echo "   gcloud logging tail 'resource.type=\"cloud_function\" AND resource.labels.function_name=\"$FUNCTION_NAME\"' --project=$PROJECT_ID"
echo ""
echo "3. View recent errors:"
echo "   gcloud logging read 'resource.type=\"cloud_function\" AND resource.labels.function_name=\"$FUNCTION_NAME\" AND severity>=ERROR' --limit=50 --project=$PROJECT_ID"
echo ""
echo "4. Test HTTP error logging:"
echo "   # Trigger an optimization run and watch for detailed request/response logs"
echo "   gcloud functions call $FUNCTION_NAME --gen2 --region=$REGION --data '{\"dry_run\":true}'"
echo ""
echo "=========================================="
echo ""
