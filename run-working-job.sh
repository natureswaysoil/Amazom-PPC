#!/usr/bin/env bash

set -euo pipefail

# Helper script to re-run a known working Cloud Run Job and show status.
# Defaults can be overridden via environment variables.

: "${JOB_NAME:=suggested-bid-optimizer-5flhn}"
: "${REGION:=us-central1}"
: "${PROJECT:=amazon-ppc}"

echo "Using PROJECT=${PROJECT} REGION=${REGION} JOB_NAME=${JOB_NAME}"

# Verify gcloud is available
if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud CLI not found. Install Google Cloud SDK and authenticate."
  exit 1
fi

# Set active project (non-interactive)
gcloud config set project "${PROJECT}" --quiet || {
  echo "WARNING: Failed to set project. Ensure you are authenticated and have access."
}

echo "Describing Cloud Run Job..."
if ! gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" >/dev/null 2>&1; then
  echo "ERROR: Job '${JOB_NAME}' not found in region '${REGION}'."
  echo "Hint: List jobs with: gcloud run jobs list --region=${REGION}"
  exit 1
fi

echo "Executing job and waiting for completion..."
gcloud run jobs execute "${JOB_NAME}" --region="${REGION}" --wait

echo "Fetching latest execution details..."
LATEST_EXEC=$(gcloud run jobs executions list --job="${JOB_NAME}" --region="${REGION}" --format="value(name)" --limit=1)
if [[ -n "${LATEST_EXEC}" ]]; then
  echo "Latest execution: ${LATEST_EXEC}"
  gcloud run jobs executions describe "${LATEST_EXEC}" --region="${REGION}"
else
  echo "No executions found for job '${JOB_NAME}'."
fi

echo "Done. For logs, check Cloud Logging for resource type 'cloud_run_job' and job '${JOB_NAME}'."
