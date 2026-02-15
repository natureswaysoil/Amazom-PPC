#!/usr/bin/env bash

################################################################################
# get-deployment-logs.sh
#
# Purpose: Retrieve Cloud Build logs and Cloud Function errors
# Lists recent builds, identifies failures, and fetches detailed logs
#
# Usage: ./get-deployment-logs.sh [PROJECT_ID]
# Exit Code: 0 for success
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
OUTPUT_FILE="${OUTPUT_FILE:-/tmp/deployment-logs.txt}"

################################################################################
# Helper Functions
################################################################################

print_header() {
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}$1${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

print_main_header() {
  echo -e "\n${BLUE}╔════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║${NC}  ${CYAN}📋 Deployment Logs Retrieval${NC}                   ${BLUE}║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
  echo -e "${CYAN}Project:${NC} ${PROJECT_ID}"
  echo -e "${CYAN}Time:${NC} $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
  echo ""
}

################################################################################
# Cloud Build Logs
################################################################################

get_cloud_build_logs() {
  print_header "🏗️  Cloud Build History (Last 10 Builds)"
  
  echo -e "${CYAN}Fetching recent Cloud Build jobs...${NC}\n"
  
  # Get list of recent builds
  local builds
  if ! builds=$(gcloud builds list \
    --project="${PROJECT_ID}" \
    --limit=10 \
    --format="table(id,status,createTime.date('%Y-%m-%d %H:%M:%S'),logUrl)" 2>&1); then
    echo -e "${RED}❌ Failed to fetch Cloud Build history${NC}"
    echo "${builds}"
    return 1
  fi
  
  echo "${builds}"
  echo ""
  
  # Find most recent failed build
  echo -e "${CYAN}Looking for failed builds...${NC}"
  
  local failed_build_id
  failed_build_id=$(gcloud builds list \
    --project="${PROJECT_ID}" \
    --filter="status=FAILURE OR status=TIMEOUT OR status=INTERNAL_ERROR" \
    --limit=1 \
    --format="value(id)" 2>/dev/null || echo "")
  
  if [[ -z "${failed_build_id}" ]]; then
    echo -e "${GREEN}✅ No recent failed builds found${NC}"
    return 0
  fi
  
  echo -e "${RED}❌ Found failed build: ${failed_build_id}${NC}\n"
  
  # Get detailed logs for failed build
  print_header "📄 Failed Build Details: ${failed_build_id}"
  
  echo -e "${CYAN}Fetching complete build logs...${NC}\n"
  
  local build_log
  if build_log=$(gcloud builds log "${failed_build_id}" --project="${PROJECT_ID}" 2>&1); then
    echo "${build_log}" | tail -n 100  # Show last 100 lines
    echo ""
    echo -e "${CYAN}Full log URL:${NC}"
    gcloud builds describe "${failed_build_id}" \
      --project="${PROJECT_ID}" \
      --format="value(logUrl)" 2>/dev/null || echo "Unable to get log URL"
  else
    echo -e "${RED}❌ Failed to fetch build log${NC}"
    echo "${build_log}"
  fi
  
  echo ""
  echo -e "${YELLOW}💡 View in Cloud Console:${NC}"
  echo "https://console.cloud.google.com/cloud-build/builds/${failed_build_id}?project=${PROJECT_ID}"
}

################################################################################
# Cloud Function Logs
################################################################################

get_function_logs() {
  print_header "🔍 Cloud Function Errors (Last 24 Hours)"
  
  echo -e "${CYAN}Querying Cloud Functions logs for errors...${NC}\n"
  
  # Calculate timestamp for 24 hours ago with error handling
  local yesterday
  if yesterday=$(date -u -d '24 hours ago' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null); then
    : # GNU date succeeded
  elif yesterday=$(date -u -v-24H +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null); then
    : # BSD date succeeded  
  else
    # Fallback: use current time minus 86400 seconds
    yesterday=$(date -u -d "@$(($(date +%s) - 86400))" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo -e "${YELLOW}⚠️  Using approximate timestamp${NC}"
  fi
  
  # Query for function errors
  local log_filter="resource.type=\"cloud_function\"
severity>=ERROR
timestamp>=\"${yesterday}\""
  
  echo -e "${CYAN}Fetching errors from all Cloud Functions...${NC}\n"
  
  local error_logs
  error_logs=$(gcloud logging read "${log_filter}" \
    --project="${PROJECT_ID}" \
    --limit=20 \
    --format="table(timestamp,resource.labels.function_name,severity,textPayload.slice(0:150))" 2>/dev/null || echo "")
  
  if [[ -z "${error_logs}" || "${error_logs}" == *"Listed 0 items"* ]]; then
    echo -e "${GREEN}✅ No errors found in the last 24 hours${NC}"
    return 0
  fi
  
  echo "${error_logs}"
  echo ""
  
  # Get count by function
  echo -e "${CYAN}Error count by function:${NC}"
  gcloud logging read "${log_filter}" \
    --project="${PROJECT_ID}" \
    --limit=1000 \
    --format="value(resource.labels.function_name)" 2>/dev/null | \
    sort | uniq -c | sort -rn || echo "Unable to count errors"
  
  echo ""
  echo -e "${YELLOW}💡 View detailed logs:${NC}"
  echo "gcloud logging read '${log_filter}' --project=${PROJECT_ID} --limit=50"
}

################################################################################
# Deployment Events
################################################################################

get_deployment_events() {
  print_header "🚀 Recent Deployment Events"
  
  echo -e "${CYAN}Checking for recent function deployments...${NC}\n"
  
  local deploy_filter="resource.type=\"cloud_function\"
protoPayload.methodName=\"google.cloud.functions.v1.CloudFunctionsService.CreateFunction\" OR
protoPayload.methodName=\"google.cloud.functions.v1.CloudFunctionsService.UpdateFunction\" OR
protoPayload.methodName=\"google.cloud.functions.v2.FunctionService.CreateFunction\" OR
protoPayload.methodName=\"google.cloud.functions.v2.FunctionService.UpdateFunction\""
  
  local deploy_logs
  deploy_logs=$(gcloud logging read "${deploy_filter}" \
    --project="${PROJECT_ID}" \
    --limit=5 \
    --format="table(timestamp,protoPayload.methodName,protoPayload.resourceName,protoPayload.status.message)" 2>/dev/null || echo "")
  
  if [[ -z "${deploy_logs}" || "${deploy_logs}" == *"Listed 0 items"* ]]; then
    echo -e "${YELLOW}⚠️  No recent deployment events found${NC}"
    return 0
  fi
  
  echo "${deploy_logs}"
  echo ""
}

################################################################################
# Save Output
################################################################################

save_output() {
  echo ""
  echo -e "${CYAN}💾 Saving logs to: ${OUTPUT_FILE}${NC}"
  
  # Note: Output is already being captured if OUTPUT_FILE is set and redirected
  # This is just a notification
  
  echo -e "${GREEN}✅ Logs saved${NC}"
}

################################################################################
# Summary
################################################################################

print_summary() {
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}📊 Summary${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo -e "${YELLOW}Next Steps:${NC}"
  echo "1. Review error messages above"
  echo "2. Check build logs for compilation/deployment errors"
  echo "3. Verify function configuration and environment variables"
  echo "4. Run ./scripts/comprehensive-diagnostics.sh for full diagnostics"
  echo "5. Use ./scripts/fix-common-issues.sh to resolve common problems"
  echo ""
  echo -e "${CYAN}Useful Commands:${NC}"
  echo "  View live logs: gcloud functions logs read FUNCTION_NAME --project=${PROJECT_ID}"
  echo "  List functions: gcloud functions list --project=${PROJECT_ID}"
  echo "  Describe build: gcloud builds describe BUILD_ID --project=${PROJECT_ID}"
  echo ""
}

################################################################################
# Main execution
################################################################################

main() {
  # Redirect all output to both terminal and file
  exec > >(tee "${OUTPUT_FILE}") 2>&1
  
  print_main_header
  
  get_cloud_build_logs || true
  get_function_logs || true
  get_deployment_events || true
  
  print_summary
  
  echo -e "${GREEN}✅ Log retrieval complete${NC}"
  echo -e "${CYAN}Output saved to: ${OUTPUT_FILE}${NC}\n"
}

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
