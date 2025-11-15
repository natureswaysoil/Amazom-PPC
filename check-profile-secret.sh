#!/usr/bin/env bash
# Check if AMAZON_PROFILE_ID secret exists and has correct value
# Usage: ./check-profile-secret.sh [PROJECT_ID]

set -euo pipefail

PROJECT_ID="${1:-amazon-ppc-474902}"
EXPECTED_PROFILE_ID="1780498399290938"

echo "Checking AMAZON_PROFILE_ID secret in Secret Manager..."
echo ""

if gcloud secrets describe AMAZON_PROFILE_ID --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "✓ Secret AMAZON_PROFILE_ID exists"
    
    CURRENT_VALUE=$(gcloud secrets versions access latest --secret="AMAZON_PROFILE_ID" --project="${PROJECT_ID}" 2>/dev/null)
    
    if [[ -z "${CURRENT_VALUE}" ]]; then
        echo "❌ Secret is EMPTY!"
        echo ""
        echo "Creating secret with value: ${EXPECTED_PROFILE_ID}"
        echo -n "${EXPECTED_PROFILE_ID}" | gcloud secrets versions add AMAZON_PROFILE_ID \
            --data-file=- \
            --project="${PROJECT_ID}"
        echo "✓ Secret updated successfully"
    elif [[ "${CURRENT_VALUE}" == "${EXPECTED_PROFILE_ID}" ]]; then
        echo "✓ Secret has correct value: ${CURRENT_VALUE}"
    else
        echo "⚠️  Secret has different value: ${CURRENT_VALUE}"
        echo "   Expected: ${EXPECTED_PROFILE_ID}"
        echo ""
        read -p "Update to ${EXPECTED_PROFILE_ID}? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -n "${EXPECTED_PROFILE_ID}" | gcloud secrets versions add AMAZON_PROFILE_ID \
                --data-file=- \
                --project="${PROJECT_ID}"
            echo "✓ Secret updated successfully"
        fi
    fi
else
    echo "❌ Secret AMAZON_PROFILE_ID does NOT exist"
    echo ""
    echo "Creating secret with value: ${EXPECTED_PROFILE_ID}"
    
    # Create the secret
    gcloud secrets create AMAZON_PROFILE_ID \
        --replication-policy="automatic" \
        --project="${PROJECT_ID}"
    
    # Add the value
    echo -n "${EXPECTED_PROFILE_ID}" | gcloud secrets versions add AMAZON_PROFILE_ID \
        --data-file=- \
        --project="${PROJECT_ID}"
    
    echo "✓ Secret created successfully"
fi

echo ""
echo "Verifying secret value..."
FINAL_VALUE=$(gcloud secrets versions access latest --secret="AMAZON_PROFILE_ID" --project="${PROJECT_ID}" 2>/dev/null)
echo "Current value: ${FINAL_VALUE}"
echo "Expected value: ${EXPECTED_PROFILE_ID}"

if [[ "${FINAL_VALUE}" == "${EXPECTED_PROFILE_ID}" ]]; then
    echo "✅ Secret is correct!"
else
    echo "❌ Secret value mismatch!"
    exit 1
fi
