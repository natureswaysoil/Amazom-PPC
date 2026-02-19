#!/bin/bash
set -euo pipefail

# ==============================================================================
# Test Deployed Dashboard Endpoint
# ==============================================================================
# Sends a request to the deployed dashboard URL and prints the HTTP response
# headers and body, making it easy to confirm the dashboard is reachable and
# returning data.
#
# Usage:
#   ./scripts/test_dashboard_endpoint.sh [URL]
#
# Arguments:
#   URL  - (optional) Full URL to test. Overrides DASHBOARD_URL env var and
#          the default derived from config.json.
#
# Environment Variables (optional):
#   DASHBOARD_URL  - Base URL of the deployed dashboard
#                    (default: https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app)
# ==============================================================================

DEFAULT_DASHBOARD_URL="https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app"
DASHBOARD_URL="${1:-${DASHBOARD_URL:-${DEFAULT_DASHBOARD_URL}}}"

echo "=============================================================================="
echo "Test Dashboard Endpoint"
echo "=============================================================================="
echo "URL: ${DASHBOARD_URL}"
echo "=============================================================================="
echo ""

if ! command -v curl &>/dev/null; then
  echo "ERROR: curl not found. Please install curl."
  exit 1
fi

echo "Response headers and body:"
echo "------------------------------------------------------------------------------"
curl -sS -D - "${DASHBOARD_URL}"
echo ""
echo "------------------------------------------------------------------------------"

HTTP_STATUS=$(curl -o /dev/null -sS -w "%{http_code}" "${DASHBOARD_URL}")
echo ""
echo "HTTP status: ${HTTP_STATUS}"

if [[ "${HTTP_STATUS}" == "200" ]]; then
  echo "✅ Dashboard is reachable (HTTP 200)."
elif [[ "${HTTP_STATUS}" == "301" || "${HTTP_STATUS}" == "302" ]]; then
  echo "ℹ️  Dashboard redirected (HTTP ${HTTP_STATUS}). Follow the redirect to the final URL."
else
  echo "❌ Unexpected HTTP status ${HTTP_STATUS}."
  echo ""
  echo "Troubleshooting:"
  echo "  • Verify DASHBOARD_URL is correct."
  echo "  • Check Cloud Run / Vercel deployment logs."
  exit 1
fi
echo "=============================================================================="
