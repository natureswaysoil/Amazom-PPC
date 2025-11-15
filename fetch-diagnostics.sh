#!/usr/bin/env bash
# Fetch and parse auth diagnostic logs from Cloud Logging for amazon-ppc-optimizer
# Usage: ./fetch-diagnostics.sh [PROJECT_ID] [MINUTES_BACK]
# Example: ./fetch-diagnostics.sh my-project-123 30

set -euo pipefail

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null || echo '')}"
MINUTES_BACK="${2:-60}"
FUNCTION_NAME="amazon-ppc-optimizer"
REGION="us-central1"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: No project ID specified and no default project set." >&2
  echo "Usage: $0 <PROJECT_ID> [MINUTES_BACK]" >&2
  exit 1
fi

echo "=== Fetching diagnostics for ${FUNCTION_NAME} from project ${PROJECT_ID} ==="
echo "Looking back ${MINUTES_BACK} minutes..."
echo ""

# Calculate timestamp for time filter
if command -v date >/dev/null 2>&1; then
  if date --version >/dev/null 2>&1 2>&1; then
    # GNU date
    TIMESTAMP=$(date -u -d "${MINUTES_BACK} minutes ago" +"%Y-%m-%dT%H:%M:%SZ")
  else
    # BSD date (macOS)
    TIMESTAMP=$(date -u -v-${MINUTES_BACK}M +"%Y-%m-%dT%H:%M:%SZ")
  fi
  TIME_FILTER="AND timestamp>=\"${TIMESTAMP}\""
else
  TIME_FILTER=""
fi

# Query 1: Check for 403/401 errors with auth diagnostics
echo "--- 1. Auth Diagnostics (403/401 errors) ---"
gcloud logging read \
  "resource.type=\"cloud_run_revision\"
   AND resource.labels.service_name=\"${FUNCTION_NAME}\"
   AND (textPayload:\"AUTH DIAGNOSTIC\" OR textPayload:\"403\" OR textPayload:\"401\")
   ${TIME_FILTER}" \
  --limit=100 \
  --format='table(timestamp,severity,textPayload)' \
  --project="${PROJECT_ID}" 2>/dev/null || echo "No auth diagnostic logs found."

echo ""
echo "--- 2. Token Inspection Details ---"
gcloud logging read \
  "resource.type=\"cloud_run_revision\"
   AND resource.labels.service_name=\"${FUNCTION_NAME}\"
   AND (textPayload:\"token_len\" OR textPayload:\"token_start\" OR textPayload:\"has_newline\")
   ${TIME_FILTER}" \
  --limit=50 \
  --format='value(textPayload)' \
  --project="${PROJECT_ID}" 2>/dev/null | grep -E "(token_len|token_start|token_end|has_newline|auth_header_present)" || echo "No token inspection logs found."

echo ""
echo "--- 3. Campaign Fetch Errors ---"
gcloud logging read \
  "resource.type=\"cloud_run_revision\"
   AND resource.labels.service_name=\"${FUNCTION_NAME}\"
   AND textPayload:\"campaigns_analyzed\"
   ${TIME_FILTER}" \
  --limit=20 \
  --format='value(timestamp,textPayload)' \
  --project="${PROJECT_ID}" 2>/dev/null | head -20 || echo "No campaign fetch logs found."

echo ""
echo "--- 4. Verify Connection Results ---"
gcloud logging read \
  "resource.type=\"cloud_run_revision\"
   AND resource.labels.service_name=\"${FUNCTION_NAME}\"
   AND (textPayload:\"Verify Connection\" OR textPayload:\"verify_connection\" OR textPayload:\"campaign_count\")
   ${TIME_FILTER}" \
  --limit=30 \
  --format='value(timestamp,textPayload)' \
  --project="${PROJECT_ID}" 2>/dev/null | head -30 || echo "No verify connection logs found."

echo ""
echo "--- 5. Recent Amazon Ads API Requests ---"
gcloud logging read \
  "resource.type=\"cloud_run_revision\"
   AND resource.labels.service_name=\"${FUNCTION_NAME}\"
   AND (textPayload:\"Amazon Ads API\" OR textPayload:\"/sp/campaigns\" OR textPayload:\"advertising.amazon.com\")
   ${TIME_FILTER}" \
  --limit=30 \
  --format='value(timestamp,severity,textPayload)' \
  --project="${PROJECT_ID}" 2>/dev/null | head -40 || echo "No API request logs found."

echo ""
echo "=== Summary ==="
echo "If you see:"
echo "  • token_len < 100 → Token refresh may have failed"
echo "  • has_newline=True → Token corruption (encoding issue)"
echo "  • 403 Forbidden → Check profile_id scope or token permissions"
echo "  • 401 Unauthorized → Token expired or invalid client credentials"
echo ""
echo "Next steps:"
echo "  1. Verify AMAZON_PROFILE_ID matches an active Sponsored Products profile"
echo "  2. Regenerate AMAZON_REFRESH_TOKEN if token_len is suspiciously short"
echo "  3. Check Secret Manager secrets are correctly mapped (amazon-client-id, etc.)"
echo "  4. Confirm profile has Sponsored Products API access enabled"
echo ""
echo "For real-time logs: gcloud logging tail 'resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${FUNCTION_NAME}\"' --project=${PROJECT_ID}"
