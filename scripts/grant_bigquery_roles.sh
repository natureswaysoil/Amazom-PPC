#!/bin/bash
set -euo pipefail

# ==============================================================================
# Grant BigQuery IAM Roles to a Service Account (project-level)
# ==============================================================================
# Grants roles/bigquery.dataViewer and roles/bigquery.jobUser to the given
# service account on the specified GCP project.
#
# Usage:
#   ./scripts/grant_bigquery_roles.sh
#
# Environment Variables (optional):
#   PROJECT_ID  - Google Cloud project ID (default: amazon-ppc-474902)
#   SA_EMAIL    - Service account email to grant roles to
# ==============================================================================

PROJECT_ID="${PROJECT_ID:-amazon-ppc-474902}"
SA_EMAIL="${SA_EMAIL:-}"

echo "=============================================================================="
echo "Grant BigQuery Roles"
echo "=============================================================================="
echo "Project: ${PROJECT_ID}"
echo "=============================================================================="
echo ""

# Resolve service account email
if [[ -z "${SA_EMAIL}" ]]; then
  # Try to derive from GCP_SERVICE_ACCOUNT_KEY if available
  if [[ -n "${GCP_SERVICE_ACCOUNT_KEY:-}" ]]; then
    SA_EMAIL=$(echo "${GCP_SERVICE_ACCOUNT_KEY}" | jq -r '.client_email' 2>/dev/null || true)
    if [[ -z "${SA_EMAIL}" || "${SA_EMAIL}" == "null" ]]; then
      SA_EMAIL=$(echo "${GCP_SERVICE_ACCOUNT_KEY}" | base64 -d 2>/dev/null | jq -r '.client_email' 2>/dev/null || true)
    fi
  fi
fi

if [[ -z "${SA_EMAIL}" || "${SA_EMAIL}" == "null" ]]; then
  echo "Enter the service account email (e.g. my-sa@${PROJECT_ID}.iam.gserviceaccount.com):"
  read -r SA_EMAIL
fi

if [[ -z "${SA_EMAIL}" ]]; then
  echo "ERROR: SA_EMAIL is required."
  exit 1
fi

echo "Service Account: ${SA_EMAIL}"
echo ""

# Verify gcloud is available and authenticated
if ! command -v gcloud &>/dev/null; then
  echo "ERROR: gcloud not found. Install the Google Cloud SDK first."
  exit 1
fi

grant_role() {
  local role="$1"
  echo "  Granting ${role} ..."
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --quiet
  echo "  ✅ ${role} granted"
}

grant_role "roles/bigquery.dataViewer"
grant_role "roles/bigquery.jobUser"

echo ""
echo "✅ All required BigQuery roles have been granted to ${SA_EMAIL}."
echo ""
echo "Next Steps:"
echo "  1. Wait ~60 seconds for IAM changes to propagate."
echo "  2. Run scripts/check_iam_bindings.sh to verify the bindings took effect."
echo "=============================================================================="
