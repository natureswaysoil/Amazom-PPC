#!/bin/bash

# Force rebuild and redeploy Cloud Run services
# This bypasses Docker layer caching

set -e

PROJECT_ID="amazon-ppc-474902"
SERVICE_ACCOUNT="ppc-bigquery-sa@${PROJECT_ID}.iam.gserviceaccount.com"
REGION="us-central1"

echo "================================================"
echo "Force Rebuild & Redeploy US Services"
echo "================================================"
echo ""

# Add a timestamp to force cache invalidation
TIMESTAMP=$(date +%s)
echo "Build timestamp: $TIMESTAMP"
echo ""

# Create a temporary build marker file to invalidate cache
echo "$TIMESTAMP" > .build-timestamp

echo "1. Building fresh container image..."
# Use Cloud Build to create a fresh image (bypasses cache)
IMAGE_NAME="gcr.io/${PROJECT_ID}/amazon-ppc-optimizer:${TIMESTAMP}"

gcloud builds submit --tag="${IMAGE_NAME}" \
  --file=Dockerfile.python \
  --project="${PROJECT_ID}" \
  --timeout=10m

echo ""
echo "2. Deploying amazon-ppc-optimizer with new image..."
gcloud run deploy amazon-ppc-optimizer \
  --image="${IMAGE_NAME}" \
  --region="${REGION}" \
  --platform=managed \
  --service-account="${SERVICE_ACCOUNT}" \
  --no-allow-unauthenticated \
  --timeout=540 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --set-env-vars="LOG_LEVEL=INFO,PPC_DRY_RUN=false,BUILD_TS=${TIMESTAMP}" \
  --set-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_API_KEY=dashboard-api-key:latest,DASHBOARD_URL=dashboard-url:latest" \
  --project="${PROJECT_ID}" \
  --quiet

echo ""
echo "✅ Deployment complete!"
echo ""

# Clean up build marker
rm -f .build-timestamp

# Get service URL
SERVICE_URL=$(gcloud run services describe amazon-ppc-optimizer \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")

echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Test with:"
echo ""
echo "curl -X POST ${SERVICE_URL}/optimize \\"
echo "  -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"dry_run\":true,\"features\":[\"bid_optimization\"],\"force\":true}'"
echo ""
