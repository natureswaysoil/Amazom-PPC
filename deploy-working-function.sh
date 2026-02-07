#!/usr/bin/env bash

set -euo pipefail

# Redeploy the Cloud Functions Gen2 service using the known working entry point
# and bundled config resolution. Secrets must already exist in Secret Manager.

: "${PROJECT:=amazon-ppc}"
: "${REGION:=us-central1}"
: "${FUNCTION_NAME:=amazon-ppc-optimizer}"

echo "Deploying Cloud Function: ${FUNCTION_NAME} in ${PROJECT}/${REGION}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud CLI not found. Install Google Cloud SDK and authenticate."
  exit 1
fi

gcloud config set project "${PROJECT}" --quiet || {
  echo "WARNING: Failed to set project. Ensure you are authenticated and have access."
}

# Deploy using Python 3.12 runtime, HTTPS trigger, and the entry point `run_optimizer` in main.py
gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --region="${REGION}" \
  --runtime=python312 \
  --source=. \
  --trigger-http \
  --no-allow-unauthenticated \
  --entry-point=run_optimizer \
  --timeout=1800s \
  --memory=1Gi \
  --set-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest" \
  --quiet

echo "Deployment complete. Fetching service URL..."
URL=$(gcloud functions describe "${FUNCTION_NAME}" --region="${REGION}" --format='value(serviceConfig.uri)')
if [[ -n "${URL}" ]]; then
  echo "Service URL: ${URL}"
  echo "Health: ${URL}?health=true"
  echo "Verify connection: ${URL}?verify_connection=true&verify_sample_size=5"
  echo "Run (POST): curl -s -X POST -H 'Content-Type: application/json' \"${URL}\" -d '{"profile_id":"...","dry_run":true}'"
else
  echo "Unable to retrieve function URL. Check gcloud output above."
fi
