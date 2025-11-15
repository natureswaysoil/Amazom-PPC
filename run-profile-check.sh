#!/usr/bin/env bash
# Load Amazon API secrets from Secret Manager and run check-profiles.py
# Usage: ./run-profile-check.sh [PROJECT_ID]

set -euo pipefail

PROJECT_ID="${1:-amazon-ppc-474902}"

echo "Loading secrets from Secret Manager..."
echo ""

# Load secrets into environment variables
export AMAZON_CLIENT_ID=$(gcloud secrets versions access latest --secret="AMAZON_CLIENT_ID" --project="${PROJECT_ID}" 2>/dev/null || echo "")
export AMAZON_CLIENT_SECRET=$(gcloud secrets versions access latest --secret="AMAZON_CLIENT_SECRET" --project="${PROJECT_ID}" 2>/dev/null || echo "")
export AMAZON_REFRESH_TOKEN=$(gcloud secrets versions access latest --secret="AMAZON_REFRESH_TOKEN" --project="${PROJECT_ID}" 2>/dev/null || echo "")
export AMAZON_PROFILE_ID=$(gcloud secrets versions access latest --secret="AMAZON_PROFILE_ID" --project="${PROJECT_ID}" 2>/dev/null || echo "")

# Check if secrets were loaded
if [[ -z "${AMAZON_CLIENT_ID}" ]]; then
    echo "ERROR: Failed to load AMAZON_CLIENT_ID from Secret Manager"
    echo "Make sure the secret exists and you have permission to access it."
    exit 1
fi

echo "✓ Secrets loaded successfully"
echo ""

# Run the profile checker
python3 check-profiles.py
