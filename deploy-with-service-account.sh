#!/usr/bin/env bash
# Deploy Amazon PPC Optimizer (Cloud Functions Gen2) with explicit service account.
# Usage: ./deploy-with-service-account.sh <GCP_PROJECT_ID> [REGION]
# Example: ./deploy-with-service-account.sh my-project us-central1
# Requires: gcloud (authenticated), Secret Manager secrets created, IAM permissions to create service accounts/roles.

set -euo pipefail
PROJECT_ID="${1:-}"
REGION="${2:-us-central1}"
FUNCTION_NAME="amazon-ppc-optimizer"
SERVICE_ACCOUNT_NAME="ppc-optimizer-runner"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
LOG_LEVEL="DEBUG"
BUILD_TS="$(date +%s)"
RUNTIME="python311"
TIMEOUT="540s"
MEMORY="512MB"
CPU="1"
# Set to 0 for scale-to-zero; raise if you want warm instance.
MIN_INSTANCES="0"
MAX_INSTANCES="5"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: GCP project ID required as first argument." >&2
  exit 1
fi

echo "== Enabling required services (idempotent) =="
gcloud services enable cloudfunctions.googleapis.com run.googleapis.com secretmanager.googleapis.com logging.googleapis.com --project "${PROJECT_ID}"

echo "== Creating/ensuring service account =="
if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
    --display-name "Amazon PPC Optimizer Runner" \
    --project "${PROJECT_ID}"
fi

echo "== Assigning IAM roles to service account (least privilege) =="
# Logging and invocation
ROLES=( \
  roles/run.invoker \
  roles/logging.logWriter \
  roles/secretmanager.secretAccessor \
  roles/cloudfunctions.invoker \
)
for role in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member "serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role "${role}" \
    --quiet >/dev/null || true
done

echo "== Checking required secrets existence =="
REQUIRED_SECRETS=(amazon-client-id amazon-client-secret amazon-refresh-token amazon-profile-id)
for sec in "${REQUIRED_SECRETS[@]}"; do
  if ! gcloud secrets describe "${sec}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    echo "ERROR: Secret '${sec}' not found in project '${PROJECT_ID}'. Create it before deploying." >&2
    exit 1
  fi
done

echo "== Deploying Cloud Function Gen2 '${FUNCTION_NAME}' =="
# Note: Use latest secret versions or pin to numbered versions for deterministic deploys.
# Add PPC_CONFIG secret if you store full config there; otherwise rely on config.json fallback.

gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --runtime="${RUNTIME}" \
  --region="${REGION}" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout="${TIMEOUT}" \
  --memory="${MEMORY}" \
  --cpu="${CPU}" \
  --min-instances="${MIN_INSTANCES}" \
  --max-instances="${MAX_INSTANCES}" \
  --service-account="${SERVICE_ACCOUNT_EMAIL}" \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=amazon-profile-id:latest \
  --set-env-vars=BUILD_TS="${BUILD_TS}",LOG_LEVEL="${LOG_LEVEL}",PPC_FEATURES="bid_optimization,dayparting" \
  --project="${PROJECT_ID}"

echo "== Fetching deployed URL =="
FUNCTION_URL=$(gcloud functions describe "${FUNCTION_NAME}" --region "${REGION}" --gen2 --project "${PROJECT_ID}" --format='value(serviceConfig.uri)')
if [[ -z "${FUNCTION_URL}" ]]; then
  echo "ERROR: Could not retrieve function URL." >&2
  exit 1
fi

echo "Deployed URL: ${FUNCTION_URL}" 

echo "== Test health endpoint =="
curl -s "${FUNCTION_URL}?health=true" | jq . || echo "Install jq for pretty output"

echo "== Test verify connection (sample size 5) =="
curl -s "${FUNCTION_URL}?verify_connection=true&verify_sample_size=5" | jq . || echo "Install jq for pretty output"

echo "== Next Steps =="
echo "1. Review Cloud Logging for auth diagnostics (403/401)." 
echo "2. Adjust PPC_FEATURES or add PPC_CONFIG secret if needed." 
echo "3. Increase min instances if cold starts are problematic (cost trade-off)." 

echo "Done."