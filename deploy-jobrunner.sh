#!/usr/bin/env bash

set -euo pipefail

# Build and deploy the Cloud Run Job runner image.
#
# This script builds a minimal Python image using Dockerfile.jobrunner via Cloud Build,
# then optionally updates an existing Cloud Run Job to use the new image.
#
# Required:
#   gcloud auth login / gcloud auth application-default login (as appropriate)
#
# Optional env overrides:
#   PROJECT_ID, REGION, AR_LOCATION, AR_REPO, IMAGE_NAME, TAG
#   JOB_NAME (if set, will update the job)
#   SERVICE_ACCOUNT (for job update)
#   JOB_TYPE (keyword_harvest | optimize | diagnose_permissions)
#   PPC_DRY_RUN (true/false)
#   SET_SECRETS (custom --set-secrets string)

: "${PROJECT_ID:=amazon-ppc-474902}"
: "${REGION:=us-central1}"
: "${AR_LOCATION:=us-central1}"
: "${AR_REPO:=ppc-automation}"
: "${IMAGE_NAME:=amazon-ppc-automation}"

if [[ -z "${TAG:-}" ]]; then
  TAG="jobrunner-$(date +%Y%m%d-%H%M%S)"
fi

IMAGE="${AR_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:${TAG}"

echo "================================================"
echo "Cloud Run Jobrunner Deploy"
echo "================================================"
echo "PROJECT_ID=${PROJECT_ID}"
echo "REGION=${REGION}"
echo "IMAGE=${IMAGE}"
echo ""

if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud CLI not found. Install Google Cloud SDK and authenticate."
  exit 1
fi

echo "1) Building + pushing image with Cloud Build..."
gcloud builds submit \
  --project="${PROJECT_ID}" \
  --config="cloudbuild-jobrunner.yaml" \
  --substitutions="_IMAGE=${IMAGE}" \
  --timeout="20m" \
  .

echo ""
echo "Built image: ${IMAGE}"

# Save the last image tag to a local note for convenience.
mkdir -p .copilot >/dev/null 2>&1 || true
echo "${IMAGE}" > .copilot/latest_jobrunner_image.txt || true

JOB_NAME="${JOB_NAME:-}"
if [[ -z "${JOB_NAME}" ]]; then
  echo ""
  echo "2) Skipping Cloud Run Job update (JOB_NAME not set)."
  echo "   To update a job, run: JOB_NAME=<your-job> $0"
  exit 0
fi

: "${JOB_TYPE:=optimize}"
: "${PPC_DRY_RUN:=false}"

if [[ -z "${SET_SECRETS:-}" ]]; then
  # Defaults align with other deploy scripts in this repo.
  SET_SECRETS="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_API_KEY=dashboard-api-key:latest,DASHBOARD_URL=dashboard-url:latest"
fi

echo ""
echo "2) Updating Cloud Run Job '${JOB_NAME}' to use new image..."

UPDATE_ARGS=(
  run jobs update "${JOB_NAME}"
  --image="${IMAGE}"
  --region="${REGION}"
  --project="${PROJECT_ID}"
  --set-env-vars="JOB_TYPE=${JOB_TYPE},PPC_DRY_RUN=${PPC_DRY_RUN}"
  --set-secrets="${SET_SECRETS}"
)

if [[ -n "${SERVICE_ACCOUNT:-}" ]]; then
  UPDATE_ARGS+=(--service-account="${SERVICE_ACCOUNT}")
fi

gcloud "${UPDATE_ARGS[@]}" --quiet

echo ""
echo "✅ Job updated. To run it:"
echo "gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID} --wait"
