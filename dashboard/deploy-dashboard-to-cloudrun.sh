#!/bin/bash
set -euo pipefail

# ==============================================================================
# Deploy Amazon PPC Dashboard to Cloud Run with BigQuery Configuration
# ==============================================================================
# This script builds and deploys the Next.js dashboard to Google Cloud Run
# with proper environment variables for BigQuery access.
#
# Prerequisites:
# - gcloud CLI authenticated and configured
# - BigQuery dataset 'amazon_ppc_data' exists in project
# - Service account with BigQuery permissions (created via setup-dashboard-permissions.sh)
#
# Usage:
#   ./dashboard/deploy-dashboard-to-cloudrun.sh
#
# Environment Variables (optional):
#   PROJECT_ID        - Google Cloud project ID (default: amazon-ppc-474902)
#   REGION           - Cloud Run region (default: us-central1)
#   SERVICE_NAME     - Cloud Run service name (default: ppc-dashboard-nextjs)
# ==============================================================================

# Configuration
PROJECT_ID="${PROJECT_ID:-amazon-ppc-474902}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-ppc-dashboard-nextjs}"
BIGQUERY_DATASET="${BIGQUERY_DATASET:-amazon_ppc_data}"
BIGQUERY_LOCATION="${BIGQUERY_LOCATION:-us-east4}"

# Derived values
DASHBOARD_DIR="amazon_ppc_dashboard/nextjs_space"
SERVICE_URL="https://${SERVICE_NAME}-1009540130231.${REGION}.run.app"

echo "=============================================================================="
echo "Deploying Amazon PPC Dashboard to Cloud Run"
echo "=============================================================================="
echo "Project:          ${PROJECT_ID}"
echo "Region:           ${REGION}"
echo "Service:          ${SERVICE_NAME}"
echo "BigQuery Dataset: ${BIGQUERY_DATASET}"
echo "BigQuery Location: ${BIGQUERY_LOCATION}"
echo "Source Directory: ${DASHBOARD_DIR}"
echo "=============================================================================="

# Verify gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" >/dev/null 2>&1; then
    echo "ERROR: gcloud is not authenticated. Run 'gcloud auth login' first."
    exit 1
fi

# Verify project exists and set it
echo ""
echo "Setting gcloud project to ${PROJECT_ID}..."
if ! gcloud config set project "${PROJECT_ID}" 2>/dev/null; then
    echo "ERROR: Failed to set project ${PROJECT_ID}. Verify the project ID is correct."
    exit 1
fi

# Verify dashboard directory exists
if [[ ! -d "${DASHBOARD_DIR}" ]]; then
    echo "ERROR: Dashboard directory not found: ${DASHBOARD_DIR}"
    exit 1
fi

# Build environment variables for Cloud Run
echo ""
echo "Configuring environment variables..."
ENV_VARS=(
    "GCP_PROJECT=${PROJECT_ID}"
    "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
    "BIGQUERY_DATASET=${BIGQUERY_DATASET}"
    "BQ_DATASET_ID=${BIGQUERY_DATASET}"
    "BIGQUERY_LOCATION=${BIGQUERY_LOCATION}"
    "BQ_LOCATION=${BIGQUERY_LOCATION}"
    "NEXT_PUBLIC_API_URL=${SERVICE_URL}"
    "NEXT_PUBLIC_GCP_PROJECT=${PROJECT_ID}"
    "NEXT_PUBLIC_BIGQUERY_DATASET=${BIGQUERY_DATASET}"
    "NEXT_PUBLIC_BIGQUERY_LOCATION=${BIGQUERY_LOCATION}"
)

# Check if dashboard API key secret exists, add it if available
SECRET_FLAGS=()
if gcloud secrets describe dashboard-api-key --project "${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Found dashboard-api-key secret, configuring access..."
    SECRET_FLAGS+=("--set-secrets=DASHBOARD_API_KEY=dashboard-api-key:latest")
else
    echo "Warning: dashboard-api-key secret not found. Dashboard API authentication will be disabled."
fi

# Deploy to Cloud Run
echo ""
echo "Deploying to Cloud Run (this may take 3-5 minutes)..."
pushd "${DASHBOARD_DIR}" >/dev/null

gcloud run deploy "${SERVICE_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    --source . \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --min-instances 0 \
    --max-instances 10 \
    --update-env-vars "$(IFS=,; echo "${ENV_VARS[*]}")" \
    ${SECRET_FLAGS[@]+"${SECRET_FLAGS[@]}"}

popd >/dev/null

# Get the deployed service URL
DEPLOYED_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --format="value(status.url)" 2>/dev/null || echo "${SERVICE_URL}")

echo ""
echo "=============================================================================="
echo "Deployment Complete!"
echo "=============================================================================="
echo "Service URL: ${DEPLOYED_URL}"
echo ""
echo "Verify the deployment:"
echo "  1. Health check:         curl ${DEPLOYED_URL}/api/health"
echo "  2. Config check:         curl ${DEPLOYED_URL}/api/config-check | jq ."
echo "  3. BigQuery test:        curl ${DEPLOYED_URL}/api/bigquery-data?table=campaigns&limit=5 | jq ."
echo "  4. Keyword data:         curl ${DEPLOYED_URL}/api/bigquery-data?table=keywords&limit=5 | jq ."
echo "  5. Performance data:     curl ${DEPLOYED_URL}/api/bigquery-data?table=keyword_performance&limit=5 | jq ."
echo ""
echo "Open in browser: ${DEPLOYED_URL}"
echo "=============================================================================="
echo ""
echo "Next Steps:"
echo "  - Run 'scripts/verify-bigquery-data.sh' to verify BigQuery data"
echo "  - Check Cloud Run logs: gcloud run services logs read ${SERVICE_NAME} --project ${PROJECT_ID} --region ${REGION}"
echo "  - See dashboard/DEPLOYMENT.md for troubleshooting"
echo "=============================================================================="
