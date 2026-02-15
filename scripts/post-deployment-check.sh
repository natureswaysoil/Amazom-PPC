#!/usr/bin/env bash

################################################################################
# post-deployment-check.sh
#
# Purpose: Post-deployment health check script
# Validates deployment is successful and all services are operational
#
# Usage: ./post-deployment-check.sh [FUNCTION_URL_OR_NAME] [PROJECT_ID]
# Exit Code: 0 if healthy, 1 if issues detected
################################################################################

set -euo pipefail

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
FUNCTION_NAME="${1:-${FUNCTION_NAME:-ppc-optimizer}}"
PROJECT_ID="${2:-${PROJECT_ID:-amazon-ppc-474902}}"
FUNCTION_URL=""
TIMEOUT="${DEPLOYMENT_TIMEOUT:-300}"  # 5 minutes, configurable via DEPLOYMENT_TIMEOUT env var
POLL_INTERVAL=10  # seconds

CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_SKIPPED=0

################################################################################
# Helper Functions
################################################################################

print_header() {
  echo ""
  echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║${NC}  ${CYAN}🏥 Post-Deployment Health Check${NC}               ${BLUE}║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
  echo -e "${CYAN}Function:${NC} ${FUNCTION_NAME}"
  echo -e "${CYAN}Project:${NC} ${PROJECT_ID}"
  echo -e "${CYAN}Time:${NC} $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
  echo ""
}

check_passed() {
  local message="$1"
  echo -e "${GREEN}✅ ${message}${NC}"
  ((CHECKS_PASSED++))
}

check_failed() {
  local message="$1"
  echo -e "${RED}❌ ${message}${NC}"
  ((CHECKS_FAILED++))
}

check_skipped() {
  local message="$1"
  echo -e "${CYAN}⏭️  ${message}${NC}"
  ((CHECKS_SKIPPED++))
}

print_check_header() {
  echo ""
  echo -e "${CYAN}${1}${NC}"
  echo -e "${BLUE}─────────────────────────────────────────────────────${NC}"
}

################################################################################
# Get Function URL
################################################################################

get_function_url() {
  print_check_header "🔍 Getting Function URL"
  
  # Check if input is already a URL
  if [[ "${FUNCTION_NAME}" =~ ^https?:// ]]; then
    FUNCTION_URL="${FUNCTION_NAME}"
    check_passed "Using provided URL: ${FUNCTION_URL}"
    return 0
  fi
  
  # Try Gen2 first
  echo -e "${CYAN}Attempting to get Gen2 function URL...${NC}"
  FUNCTION_URL=$(gcloud functions describe "${FUNCTION_NAME}" \
    --project="${PROJECT_ID}" \
    --gen2 \
    --region=us-central1 \
    --format="value(serviceConfig.uri)" 2>/dev/null || echo "")
  
  # If Gen2 fails, try Gen1
  if [[ -z "${FUNCTION_URL}" ]]; then
    echo -e "${CYAN}Attempting to get Gen1 function URL...${NC}"
    FUNCTION_URL=$(gcloud functions describe "${FUNCTION_NAME}" \
      --project="${PROJECT_ID}" \
      --region=us-central1 \
      --format="value(httpsTrigger.url)" 2>/dev/null || echo "")
  fi
  
  if [[ -z "${FUNCTION_URL}" ]]; then
    check_failed "Could not retrieve function URL"
    return 1
  fi
  
  check_passed "Function URL: ${FUNCTION_URL}"
  return 0
}

################################################################################
# Wait for Function to be ACTIVE
################################################################################

wait_for_active() {
  print_check_header "⏳ Waiting for Function to be ACTIVE"
  
  local elapsed=0
  local state="UNKNOWN"
  
  echo -e "${CYAN}Timeout: ${TIMEOUT}s, checking every ${POLL_INTERVAL}s${NC}\n"
  
  while [[ ${elapsed} -lt ${TIMEOUT} ]]; do
    # Try Gen2 first
    state=$(gcloud functions describe "${FUNCTION_NAME}" \
      --project="${PROJECT_ID}" \
      --gen2 \
      --region=us-central1 \
      --format="value(state)" 2>/dev/null || echo "")
    
    # If Gen2 fails, try Gen1
    if [[ -z "${state}" ]]; then
      state=$(gcloud functions describe "${FUNCTION_NAME}" \
        --project="${PROJECT_ID}" \
        --region=us-central1 \
        --format="value(status)" 2>/dev/null || echo "UNKNOWN")
    fi
    
    echo -e "${CYAN}[${elapsed}s] State: ${state}${NC}"
    
    if [[ "${state}" == "ACTIVE" ]]; then
      check_passed "Function is ACTIVE"
      return 0
    fi
    
    if [[ "${state}" == "FAILED" || "${state}" == "DEPLOYMENT_FAILED" ]]; then
      check_failed "Function deployment failed"
      return 1
    fi
    
    sleep ${POLL_INTERVAL}
    elapsed=$((elapsed + POLL_INTERVAL))
  done
  
  check_failed "Timeout waiting for function to be ACTIVE (state: ${state})"
  return 1
}

################################################################################
# Test Health Endpoint
################################################################################

test_health_endpoint() {
  print_check_header "🏥 Testing Health Endpoint"
  
  if [[ -z "${FUNCTION_URL}" ]]; then
    check_skipped "No function URL available"
    return 1
  fi
  
  local health_url="${FUNCTION_URL}/health"
  echo -e "${CYAN}Health URL: ${health_url}${NC}\n"
  
  # Get identity token for authentication
  local id_token
  echo -e "${CYAN}Getting identity token...${NC}"
  if id_token=$(gcloud auth print-identity-token 2>/dev/null); then
    echo -e "${GREEN}✓ Token obtained${NC}\n"
  else
    echo -e "${YELLOW}⚠️  Could not get identity token, trying without auth...${NC}\n"
    id_token=""
  fi
  
  # Call health endpoint
  echo -e "${CYAN}Calling health endpoint...${NC}"
  local response
  local http_code
  
  if [[ -n "${id_token}" ]]; then
    response=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer ${id_token}" "${health_url}" 2>/dev/null || echo "error\n000")
  else
    response=$(curl -s -w "\n%{http_code}" "${health_url}" 2>/dev/null || echo "error\n000")
  fi
  
  http_code=$(echo "${response}" | tail -n1)
  response=$(echo "${response}" | head -n-1)
  
  echo -e "${CYAN}HTTP Status: ${http_code}${NC}"
  echo -e "${CYAN}Response:${NC}"
  echo "${response}" | jq '.' 2>/dev/null || echo "${response}"
  echo ""
  
  if [[ "${http_code}" == "200" ]]; then
    check_passed "Health endpoint responding (HTTP 200)"
    return 0
  else
    check_failed "Health endpoint failed (HTTP ${http_code})"
    return 1
  fi
}

################################################################################
# Verify BigQuery Connectivity
################################################################################

verify_bigquery() {
  print_check_header "💾 Verifying BigQuery Connection"
  
  local dataset="amazon_ppc"
  
  if ! command -v bq &>/dev/null; then
    check_skipped "bq command not available"
    return 0
  fi
  
  if bq show --project_id="${PROJECT_ID}" "${dataset}" &>/dev/null; then
    check_passed "BigQuery connection OK"
    
    # Check for tables
    local table_count
    table_count=$(bq ls --project_id="${PROJECT_ID}" --max_results=1000 "${dataset}" 2>/dev/null | tail -n +3 | wc -l)
    echo -e "${CYAN}  Tables found: ${table_count}${NC}"
    
    return 0
  else
    check_failed "BigQuery dataset not accessible"
    return 1
  fi
}

################################################################################
# Test Secret Manager Access
################################################################################

verify_secrets() {
  print_check_header "🔐 Verifying Secret Manager Access"
  
  local test_secrets=("amazon-client-id" "ppc-profile-id")
  local accessible=0
  
  for secret in "${test_secrets[@]}"; do
    if gcloud secrets describe "${secret}" --project="${PROJECT_ID}" &>/dev/null; then
      ((accessible++))
    fi
  done
  
  if [[ ${accessible} -eq ${#test_secrets[@]} ]]; then
    check_passed "Secrets accessible"
  else
    check_failed "Some secrets not accessible (${accessible}/${#test_secrets[@]})"
  fi
}

################################################################################
# Validate Dashboard Connectivity
################################################################################

verify_dashboard() {
  print_check_header "🌐 Validating Dashboard Connectivity"
  
  # Check if dashboard URL secret exists
  local dashboard_url
  if ! dashboard_url=$(gcloud secrets versions access latest --secret="dashboard-url" --project="${PROJECT_ID}" 2>/dev/null); then
    check_skipped "Dashboard URL not configured"
    return 0
  fi
  
  echo -e "${CYAN}Dashboard URL: ${dashboard_url}${NC}"
  
  # Test connectivity
  local http_code
  if http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${dashboard_url}" 2>/dev/null); then
    if [[ "${http_code}" == "200" ]]; then
      check_passed "Dashboard reachable (HTTP ${http_code})"
    else
      echo -e "${YELLOW}⚠️  Dashboard returned HTTP ${http_code}${NC}"
      check_passed "Dashboard reachable"
    fi
  else
    check_failed "Dashboard not reachable"
  fi
}

################################################################################
# Run Sample Dry-Run
################################################################################

run_dry_run_test() {
  print_check_header "🧪 Sample Dry-Run Test"
  
  echo -e "${YELLOW}Dry-run test is optional and may take time${NC}"
  check_skipped "Dry-run test: SKIPPED (optional)"
  
  # Uncomment below to enable dry-run testing
  # if [[ -z "${FUNCTION_URL}" ]]; then
  #   check_skipped "No function URL available"
  #   return 0
  # fi
  # 
  # local id_token
  # id_token=$(gcloud auth print-identity-token 2>/dev/null || echo "")
  # 
  # if [[ -z "${id_token}" ]]; then
  #   check_skipped "No authentication token available"
  #   return 0
  # fi
  # 
  # local response
  # response=$(curl -s -H "Authorization: Bearer ${id_token}" \
  #   -H "Content-Type: application/json" \
  #   -d '{"dry_run": true, "features": ["bid_adjustment"]}' \
  #   "${FUNCTION_URL}" 2>/dev/null || echo "error")
  # 
  # if echo "${response}" | grep -q '"success"\|"status"'; then
  #   check_passed "Dry-run test completed"
  # else
  #   check_failed "Dry-run test failed"
  # fi
}

################################################################################
# Summary
################################################################################

print_summary() {
  local total_checks=$((CHECKS_PASSED + CHECKS_FAILED))
  
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}📊 Post-Deployment Summary${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}✅ Passed:  ${CHECKS_PASSED}${NC}"
  echo -e "${RED}❌ Failed:  ${CHECKS_FAILED}${NC}"
  echo -e "${CYAN}⏭️  Skipped: ${CHECKS_SKIPPED}${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  
  if [[ ${CHECKS_FAILED} -eq 0 ]]; then
    echo -e "${GREEN}🎉 Overall Status: ✅ HEALTHY${NC}\n"
    echo -e "${CYAN}Deployment successful! Function is operational.${NC}\n"
    return 0
  else
    echo -e "${RED}🚨 Overall Status: ❌ UNHEALTHY${NC}\n"
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Review failed checks above"
    echo "2. Run ./scripts/get-deployment-logs.sh for detailed logs"
    echo "3. Run ./scripts/comprehensive-diagnostics.sh for full diagnostics"
    echo "4. Check Cloud Console for deployment errors"
    echo ""
    return 1
  fi
}

################################################################################
# Main execution
################################################################################

main() {
  print_header
  
  get_function_url || true
  wait_for_active || true
  test_health_endpoint || true
  verify_bigquery || true
  verify_secrets || true
  verify_dashboard || true
  run_dry_run_test || true
  
  print_summary
}

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
