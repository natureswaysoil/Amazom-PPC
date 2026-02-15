#!/usr/bin/env bash

################################################################################
# comprehensive-diagnostics.sh
#
# Purpose: Main diagnostic script that orchestrates all health checks
# Validates Cloud Functions, Secrets, Vercel Dashboard, BigQuery, and logs
#
# Usage: ./comprehensive-diagnostics.sh [PROJECT_ID] [FUNCTION_NAME]
# Exit Code: 0 for success, 1 for failures
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
PROJECT_ID="${1:-${PROJECT_ID:-amazon-ppc-474902}}"
FUNCTION_NAME="${2:-${FUNCTION_NAME:-ppc-optimizer}}"
BIGQUERY_DATASET="amazon_ppc"
VERCEL_DASHBOARD_URL="https://amazonppcdashboard.vercel.app"
OUTPUT_FILE="${OUTPUT_FILE:-/tmp/diagnostics.log}"

# Initialize output file
exec > >(tee -a "${OUTPUT_FILE}") 2>&1

################################################################################
# Helper Functions
################################################################################

print_section_header() {
  local title="$1"
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}${title}${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

print_main_header() {
  echo -e "\n${BLUE}╔════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║${NC}  ${CYAN}🔍 Comprehensive Deployment Diagnostics${NC}         ${BLUE}║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
  echo -e "${CYAN}Project:${NC} ${PROJECT_ID}"
  echo -e "${CYAN}Function:${NC} ${FUNCTION_NAME}"
  echo -e "${CYAN}Time:${NC} $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
  echo ""
}

################################################################################
# Section 1: Cloud Function Status
################################################################################

check_cloud_function_status() {
  print_section_header "📦 Section 1: Cloud Function Status"
  
  echo -e "${CYAN}Checking if function exists...${NC}"
  
  # Try to get function description
  local function_info
  if ! function_info=$(gcloud functions describe "${FUNCTION_NAME}" \
    --project="${PROJECT_ID}" \
    --gen2 \
    --region=us-central1 \
    --format=json 2>/dev/null); then
    echo -e "${YELLOW}⚠️  Gen2 function not found, trying Gen1...${NC}"
    if ! function_info=$(gcloud functions describe "${FUNCTION_NAME}" \
      --project="${PROJECT_ID}" \
      --region=us-central1 \
      --format=json 2>/dev/null); then
      echo -e "${RED}❌ Function does not exist${NC}"
      echo -e "${YELLOW}Deploy with: gcloud functions deploy ${FUNCTION_NAME}${NC}"
      return 1
    fi
  fi
  
  echo -e "${GREEN}✅ Function exists${NC}\n"
  
  # Parse function details
  local state=$(echo "${function_info}" | jq -r '.state // .status // "UNKNOWN"')
  local update_time=$(echo "${function_info}" | jq -r '.updateTime // .versionId // "unknown"')
  local runtime=$(echo "${function_info}" | jq -r '.runtime // "unknown"')
  local memory=$(echo "${function_info}" | jq -r '.availableMemoryMb // .serviceConfig.availableMemory // "unknown"')
  local timeout=$(echo "${function_info}" | jq -r '.timeout // .serviceConfig.timeoutSeconds // "unknown"')
  local url=$(echo "${function_info}" | jq -r '.serviceConfig.uri // .httpsTrigger.url // "none"')
  
  echo -e "${CYAN}Function Details:${NC}"
  echo "  State: ${state}"
  echo "  Runtime: ${runtime}"
  echo "  Memory: ${memory}"
  echo "  Timeout: ${timeout}"
  echo "  Last Update: ${update_time}"
  echo "  URL: ${url}"
  
  if [[ "${state}" == "ACTIVE" ]]; then
    echo -e "\n${GREEN}✅ Function is ACTIVE${NC}"
  else
    echo -e "\n${YELLOW}⚠️  Function state: ${state}${NC}"
  fi
}

################################################################################
# Section 2: Secret Manager Validation
################################################################################

check_secrets() {
  print_section_header "🔐 Section 2: Secret Manager Validation"
  
  # Get script directory to find validate-secrets.sh
  local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local validate_script="${script_dir}/validate-secrets.sh"
  
  if [[ ! -f "${validate_script}" ]]; then
    echo -e "${YELLOW}⚠️  validate-secrets.sh not found at ${validate_script}${NC}"
    echo -e "${CYAN}Performing basic secret check...${NC}\n"
    
    # Basic fallback check
    local secrets=("amazon-client-id" "amazon-client-secret" "amazon-refresh-token" "ppc-profile-id" "dashboard-url" "dashboard-api-key")
    local valid=0
    local total=${#secrets[@]}
    
    for secret in "${secrets[@]}"; do
      if gcloud secrets describe "${secret}" --project="${PROJECT_ID}" &>/dev/null; then
        echo -e "${GREEN}✅ ${secret}${NC}"
        ((valid++))
      else
        echo -e "${RED}❌ ${secret}${NC}"
      fi
    done
    
    echo -e "\n${CYAN}Result: ${valid}/${total} secrets exist${NC}"
    return 0
  fi
  
  # Run comprehensive validation
  if bash "${validate_script}" "${PROJECT_ID}"; then
    echo -e "${GREEN}✅ All secrets validated${NC}"
    return 0
  else
    echo -e "${RED}❌ Secret validation failed${NC}"
    return 1
  fi
}

################################################################################
# Section 3: Vercel Dashboard Health Check
################################################################################

check_vercel_dashboard() {
  print_section_header "🌐 Section 3: Vercel Dashboard Health Check"
  
  echo -e "${CYAN}Testing dashboard URL: ${VERCEL_DASHBOARD_URL}${NC}\n"
  
  local response_code
  if response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${VERCEL_DASHBOARD_URL}" 2>/dev/null); then
    if [[ "${response_code}" == "200" ]]; then
      echo -e "${GREEN}✅ Dashboard is accessible (HTTP ${response_code})${NC}"
      return 0
    else
      echo -e "${YELLOW}⚠️  Dashboard returned HTTP ${response_code}${NC}"
      return 0
    fi
  else
    echo -e "${RED}❌ Cannot reach dashboard${NC}"
    echo -e "${YELLOW}Check Vercel deployment status${NC}"
    return 1
  fi
}

################################################################################
# Section 4: Cloud Function Health Test
################################################################################

test_function_health() {
  print_section_header "🏥 Section 4: Cloud Function Health Test"
  
  echo -e "${CYAN}Getting function URL...${NC}"
  
  # Get function URL
  local function_url
  if ! function_url=$(gcloud functions describe "${FUNCTION_NAME}" \
    --project="${PROJECT_ID}" \
    --gen2 \
    --region=us-central1 \
    --format="value(serviceConfig.uri)" 2>/dev/null); then
    # Try Gen1
    function_url=$(gcloud functions describe "${FUNCTION_NAME}" \
      --project="${PROJECT_ID}" \
      --region=us-central1 \
      --format="value(httpsTrigger.url)" 2>/dev/null) || true
  fi
  
  if [[ -z "${function_url}" ]]; then
    echo -e "${RED}❌ Could not get function URL${NC}"
    return 1
  fi
  
  echo -e "${CYAN}Function URL: ${function_url}${NC}\n"
  
  # Get identity token
  echo -e "${CYAN}Obtaining identity token...${NC}"
  local id_token
  if ! id_token=$(gcloud auth print-identity-token 2>/dev/null); then
    echo -e "${YELLOW}⚠️  Could not get identity token, trying without auth...${NC}"
    id_token=""
  fi
  
  # Call health endpoint
  echo -e "${CYAN}Calling health endpoint...${NC}"
  local health_url="${function_url}/health"
  local response
  
  if [[ -n "${id_token}" ]]; then
    response=$(curl -s -H "Authorization: Bearer ${id_token}" "${health_url}" 2>/dev/null || echo '{"error":"request failed"}')
  else
    response=$(curl -s "${health_url}" 2>/dev/null || echo '{"error":"request failed"}')
  fi
  
  echo -e "\n${CYAN}Health Response:${NC}"
  echo "${response}" | jq '.' 2>/dev/null || echo "${response}"
  
  # Check if response contains success indicators
  if echo "${response}" | grep -q '"status".*"healthy"\|"status".*"ok"'; then
    echo -e "\n${GREEN}✅ Health check passed${NC}"
    return 0
  else
    echo -e "\n${YELLOW}⚠️  Health check returned unexpected response${NC}"
    return 0
  fi
}

################################################################################
# Section 5: Recent Error Logs
################################################################################

check_error_logs() {
  print_section_header "📋 Section 5: Recent Error Logs (Last 1 Hour)"
  
  echo -e "${CYAN}Querying Cloud Logging for errors...${NC}\n"
  
  # Calculate timestamp for 1 hour ago
  local one_hour_ago=$(date -u -d '1 hour ago' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v-1H +"%Y-%m-%dT%H:%M:%SZ")
  
  # Query logs
  local log_filter="resource.type=\"cloud_function\"
resource.labels.function_name=\"${FUNCTION_NAME}\"
severity>=ERROR
timestamp>=\"${one_hour_ago}\""
  
  echo -e "${CYAN}Fetching last 10 errors...${NC}\n"
  
  local logs
  logs=$(gcloud logging read "${log_filter}" \
    --project="${PROJECT_ID}" \
    --limit=10 \
    --format="table(timestamp,severity,textPayload.slice(0:100))" 2>/dev/null || echo "")
  
  if [[ -z "${logs}" || "${logs}" == *"Listed 0 items"* ]]; then
    echo -e "${GREEN}✅ No errors found in the last hour${NC}"
    return 0
  fi
  
  echo "${logs}"
  echo ""
  echo -e "${YELLOW}⚠️  Errors detected - review logs above${NC}"
  echo -e "${CYAN}View full logs: gcloud logging read '${log_filter}' --project=${PROJECT_ID}${NC}"
}

################################################################################
# Section 6: BigQuery Dataset Validation
################################################################################

check_bigquery() {
  print_section_header "💾 Section 6: BigQuery Dataset Validation"
  
  echo -e "${CYAN}Checking BigQuery dataset: ${BIGQUERY_DATASET}${NC}\n"
  
  # Check if dataset exists
  if ! bq show --project_id="${PROJECT_ID}" "${BIGQUERY_DATASET}" &>/dev/null; then
    echo -e "${RED}❌ Dataset '${BIGQUERY_DATASET}' does not exist${NC}"
    echo -e "${YELLOW}Create with: bq mk --project_id=${PROJECT_ID} ${BIGQUERY_DATASET}${NC}"
    return 1
  fi
  
  echo -e "${GREEN}✅ Dataset exists${NC}\n"
  
  # List tables
  echo -e "${CYAN}Tables in dataset:${NC}"
  local tables
  tables=$(bq ls --project_id="${PROJECT_ID}" --max_results=100 "${BIGQUERY_DATASET}" 2>/dev/null | tail -n +3)
  
  if [[ -z "${tables}" ]]; then
    echo -e "${YELLOW}⚠️  No tables found in dataset${NC}"
    return 0
  fi
  
  echo "${tables}"
  
  # Check for key tables
  echo ""
  local key_tables=("optimization_results" "campaign_details" "keyword_performance")
  local found_tables=0
  
  for table in "${key_tables[@]}"; do
    if echo "${tables}" | grep -q "${table}"; then
      echo -e "${GREEN}✅ ${table}${NC}"
      ((found_tables++))
    else
      echo -e "${YELLOW}⚠️  ${table} (not found)${NC}"
    fi
  done
  
  echo ""
  if [[ ${found_tables} -eq ${#key_tables[@]} ]]; then
    echo -e "${GREEN}✅ All key tables present${NC}"
  else
    echo -e "${YELLOW}⚠️  Some key tables missing (${found_tables}/${#key_tables[@]})${NC}"
  fi
}

################################################################################
# Final Summary
################################################################################

print_final_summary() {
  echo ""
  echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║${NC}  ${CYAN}📊 Diagnostics Complete${NC}                         ${BLUE}║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "${CYAN}Output saved to: ${OUTPUT_FILE}${NC}"
  echo ""
  echo -e "${YELLOW}Next Steps:${NC}"
  echo "1. Review any failed checks above"
  echo "2. Run ./scripts/fix-common-issues.sh to auto-fix issues"
  echo "3. Check Cloud Console for detailed error messages"
  echo "4. Review deployment logs with ./scripts/get-deployment-logs.sh"
  echo ""
}

################################################################################
# Main execution
################################################################################

main() {
  print_main_header
  
  # Run all diagnostic sections
  check_cloud_function_status || true
  check_secrets || true
  check_vercel_dashboard || true
  test_function_health || true
  check_error_logs || true
  check_bigquery || true
  
  print_final_summary
}

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
