#!/usr/bin/env bash
set -euo pipefail

# Run Sponsored Products permission diagnostics using secrets from Google Secret Manager.
#
# Usage:
#  ./run_sp_permission_diagnostics.sh <GCP_PROJECT_ID>
#
# Prerequisites:
#  - gcloud CLI authenticated ("gcloud auth login" or service account)
#  - Secrets exist: AMAZON_CLIENT_ID, AMAZON_CLIENT_SECRET, AMAZON_REFRESH_TOKEN, AMAZON_PROFILE_ID (or PPC_PROFILE_ID)
#  - diagnose_sp_permissions.py present in repository root.
#
# Optional env overrides:
#  SECRET_PREFIX  : Prefix for secret names (default: none)
#  PROFILE_SECRET : Override profile secret name
#  DRY_RUN        : If set, just print planned commands

PROJECT_ID="${1:-${GCP_PROJECT_ID:-}}"
SECRET_PREFIX="${SECRET_PREFIX:-}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: Project ID not provided. Pass as first arg or set GCP_PROJECT_ID." >&2
  exit 1
fi

fetch_secret() {
  local name="$1"
  local full_name="${SECRET_PREFIX}${name}"
  if ! gcloud secrets describe "${full_name}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    echo "WARN: Secret '${full_name}' not found" >&2
    return 1
  fi
  gcloud secrets versions access latest --secret "${full_name}" --project "${PROJECT_ID}" 2>/dev/null
}

export AMAZON_CLIENT_ID="$(fetch_secret AMAZON_CLIENT_ID || echo)"
export AMAZON_CLIENT_SECRET="$(fetch_secret AMAZON_CLIENT_SECRET || echo)"
export AMAZON_REFRESH_TOKEN="$(fetch_secret AMAZON_REFRESH_TOKEN || echo)"
export AMAZON_PROFILE_ID="$(fetch_secret AMAZON_PROFILE_ID || fetch_secret PPC_PROFILE_ID || echo)"

missing=()
[[ -z "$AMAZON_CLIENT_ID" ]] && missing+=(AMAZON_CLIENT_ID)
[[ -z "$AMAZON_CLIENT_SECRET" ]] && missing+=(AMAZON_CLIENT_SECRET)
[[ -z "$AMAZON_REFRESH_TOKEN" ]] && missing+=(AMAZON_REFRESH_TOKEN)
[[ -z "$AMAZON_PROFILE_ID" ]] && missing+=(AMAZON_PROFILE_ID/PPC_PROFILE_ID)

if (( ${#missing[@]} > 0 )); then
  echo "ERROR: Missing required secrets: ${missing[*]}" >&2
  exit 2
fi

if [[ -n "${DRY_RUN:-}" ]]; then
  echo "DRY_RUN set; would run: python diagnose_sp_permissions.py" >&2
  exit 0
fi

python diagnose_sp_permissions.py || true
