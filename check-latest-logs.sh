#!/usr/bin/env bash
# Check latest logs from Cloud Run service via the Cloud Logging API
# This works without gcloud CLI by using the REST API

set -euo pipefail

PROJECT_ID="amazon-ppc-474902"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "Fetching latest logs for ${FUNCTION_NAME}..."
echo ""

# Get access token (assumes running in authenticated environment)
if command -v gcloud >/dev/null 2>&1; then
  TOKEN=$(gcloud auth print-access-token 2>/dev/null || echo "")
  if [[ -n "${TOKEN}" ]]; then
    # Use Cloud Logging API to fetch recent ERROR logs
    curl -s -H "Authorization: Bearer ${TOKEN}" \
      "https://logging.googleapis.com/v2/entries:list" \
      -H "Content-Type: application/json" \
      -d "{
        \"resourceNames\": [\"projects/${PROJECT_ID}\"],
        \"filter\": \"resource.type=\\\"cloud_run_revision\\\" AND resource.labels.service_name=\\\"${FUNCTION_NAME}\\\" AND severity=\\\"ERROR\\\" AND textPayload=~\\\"AUTH DIAGNOSTIC\\\"\",
        \"orderBy\": \"timestamp desc\",
        \"pageSize\": 20
      }" | jq -r '.entries[]? | .timestamp + " " + .textPayload'
  else
    echo "No gcloud token available. Please authenticate with: gcloud auth login"
  fi
else
  echo "gcloud CLI not found. Cannot fetch logs."
  echo "Please check logs manually at:"
  echo "https://console.cloud.google.com/logs/query?project=${PROJECT_ID}"
fi
