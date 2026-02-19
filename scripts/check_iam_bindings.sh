#!/bin/bash
set -euo pipefail

# ==============================================================================
# Check IAM Bindings for a Service Account
# ==============================================================================
# Lists all IAM roles currently bound to the given service account on the
# specified GCP project and checks that required BigQuery roles are present.
#
# Usage:
#   ./scripts/check_iam_bindings.sh
#
# Environment Variables (optional):
#   PROJECT_ID  - Google Cloud project ID (default: amazon-ppc-474902)
#   SA_EMAIL    - Service account email to check
# ==============================================================================

PROJECT_ID="${PROJECT_ID:-amazon-ppc-474902}"
SA_EMAIL="${SA_EMAIL:-}"

echo "=============================================================================="
echo "Check IAM Bindings"
echo "=============================================================================="
echo "Project: ${PROJECT_ID}"
echo "=============================================================================="
echo ""

# Resolve service account email
if [[ -z "${SA_EMAIL}" ]]; then
  if [[ -n "${GCP_SERVICE_ACCOUNT_KEY:-}" ]]; then
    SA_EMAIL=$(echo "${GCP_SERVICE_ACCOUNT_KEY}" | jq -r '.client_email' 2>/dev/null || true)
    if [[ -z "${SA_EMAIL}" || "${SA_EMAIL}" == "null" ]]; then
      SA_EMAIL=$(echo "${GCP_SERVICE_ACCOUNT_KEY}" | base64 -d 2>/dev/null | jq -r '.client_email' 2>/dev/null || true)
    fi
  fi
fi

if [[ -z "${SA_EMAIL}" || "${SA_EMAIL}" == "null" ]]; then
  echo "Enter the service account email to check:"
  read -r SA_EMAIL
fi

if [[ -z "${SA_EMAIL}" ]]; then
  echo "ERROR: SA_EMAIL is required."
  exit 1
fi

echo "Service Account: ${SA_EMAIL}"
echo ""

if ! command -v gcloud &>/dev/null; then
  echo "ERROR: gcloud not found. Install the Google Cloud SDK first."
  exit 1
fi

echo "Current IAM bindings for ${SA_EMAIL}:"
echo "------------------------------------------------------------------------------"
gcloud projects get-iam-policy "${PROJECT_ID}" \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:${SA_EMAIL}" \
  --format="table(bindings.role)"
echo ""

# Check required BigQuery roles
REQUIRED_ROLES=("roles/bigquery.dataViewer" "roles/bigquery.jobUser")
ALL_OK=true

echo "Checking required BigQuery roles:"
for role in "${REQUIRED_ROLES[@]}"; do
  if gcloud projects get-iam-policy "${PROJECT_ID}" \
       --flatten="bindings[].members" \
       --filter="bindings.members:serviceAccount:${SA_EMAIL} AND bindings.role:${role}" \
       --format="value(bindings.role)" 2>/dev/null | grep -q "${role}"; then
    echo "  ✅ ${role}"
  else
    echo "  ❌ ${role} — MISSING"
    ALL_OK=false
  fi
done

echo ""
if [[ "${ALL_OK}" == "true" ]]; then
  echo "✅ All required BigQuery roles are present."
else
  echo "❌ Some required roles are missing."
  echo "   Run scripts/grant_bigquery_roles.sh to fix."
  exit 1
fi
echo "=============================================================================="
