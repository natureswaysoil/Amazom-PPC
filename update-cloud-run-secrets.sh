#!/bin/bash

# Update Cloud Run service with correct secret configuration
# This updates the existing service without rebuilding

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-east4"
SERVICE_NAME="amazon-ppc-optimizer"
SERVICE_ACCOUNT="ppc-bigquery-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "================================================"
echo "Updating Cloud Run Service Secrets"
echo "================================================"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Service Account: ${SERVICE_ACCOUNT}"
echo ""

echo "Updating service configuration..."

# Update only the service account and secrets without rebuilding
gcloud run services update "${SERVICE_NAME}" \
  --region="${REGION}" \
  --service-account="${SERVICE_ACCOUNT}" \
  --clear-env-vars \
  --clear-secrets \
  --update-env-vars="LOG_LEVEL=INFO,PPC_DRY_RUN=false" \
  --update-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_API_KEY=dashboard-api-key:latest,DASHBOARD_URL=dashboard-url:latest" \
  --project="${PROJECT_ID}" \
  --quiet

echo ""
echo "✅ Cloud Run service updated successfully!"
echo ""

# Get service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")

echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Test the service with:"
echo ""
echo "curl -X POST ${SERVICE_URL}/optimize \\"
echo "  -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"dry_run\":true,\"features\":[\"bid_optimization\"],\"verify_sample_size\":5}'"
echo ""
