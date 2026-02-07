#!/bin/bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-ppc-dashboard-nextjs}"
REGION="${REGION:-us-central1}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: PROJECT_ID not set and no default gcloud project configured."
  echo "Set PROJECT_ID=... and re-run."
  exit 1
fi

# Dashboard runtime config
BQ_DATASET_ID="${BQ_DATASET_ID:-amazon_ppc}"
BQ_LOCATION="${BQ_LOCATION:-us-east4}"
PPC_OPTIMIZER_URL="${PPC_OPTIMIZER_URL:-}"

DASHBOARD_DIR="amazon_ppc_dashboard/nextjs_space"

echo "Deploying Next.js dashboard to Cloud Run"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Service:  ${SERVICE_NAME}"
echo "  Source:   ${DASHBOARD_DIR}"

echo ""
echo "Building + deploying (forces rebuild from source)..."

pushd "${DASHBOARD_DIR}" >/dev/null

# Optional optimizer URL env var
ENV_VARS=(
  "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
  "GCP_PROJECT=${PROJECT_ID}"
  "BQ_DATASET_ID=${BQ_DATASET_ID}"
  "BQ_LOCATION=${BQ_LOCATION}"
)

if [[ -n "${PPC_OPTIMIZER_URL}" ]]; then
  ENV_VARS+=("PPC_OPTIMIZER_URL=${PPC_OPTIMIZER_URL}")
fi

# Prefer Secret Manager for the shared API key if present.
SECRET_FLAGS=()
if gcloud secrets describe dashboard-api-key --project "${PROJECT_ID}" >/dev/null 2>&1; then
  SECRET_FLAGS+=("--set-secrets=DASHBOARD_API_KEY=dashboard-api-key:latest")
fi

gcloud run deploy "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --source . \
  --update-env-vars "$(IFS=,; echo "${ENV_VARS[*]}")" \
  "${SECRET_FLAGS[@]}"

popd >/dev/null

echo ""
echo "Done. Verify endpoints:" 
echo "  curl -sS 'https://<YOUR_URL>/api/config-check' | jq ."
echo "  curl -sS 'https://<YOUR_URL>/api/bigquery-data?table=optimization_results&limit=1' | jq ."
