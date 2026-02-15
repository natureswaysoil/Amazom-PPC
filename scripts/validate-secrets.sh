#!/usr/bin/env bash

################################################################################
# validate-secrets.sh
#
# Purpose: Comprehensive secret validation for Amazon PPC Optimizer
# Validates all required secrets exist in Google Cloud Secret Manager
# Checks secret versions are enabled and values are not empty or placeholders
#
# Usage: ./validate-secrets.sh [PROJECT_ID]
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

# Required secrets to validate
REQUIRED_SECRETS=(
  "amazon-client-id"
  "amazon-client-secret"
  "amazon-refresh-token"
  "ppc-profile-id"
  "dashboard-url"
  "dashboard-api-key"
)

# Counters
MISSING_COUNT=0
INVALID_COUNT=0
VALID_COUNT=0

################################################################################
# Functions
################################################################################

print_header() {
  echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}🔍 Secret Manager Validation${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}Project:${NC} ${PROJECT_ID}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

check_gcloud_auth() {
  echo -e "${CYAN}Checking gcloud authentication...${NC}"
  if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &>/dev/null; then
    echo -e "${RED}❌ Not authenticated with gcloud${NC}"
    echo -e "${YELLOW}Run: gcloud auth login${NC}"
    exit 1
  fi
  echo -e "${GREEN}✅ gcloud authenticated${NC}\n"
}

check_project_access() {
  echo -e "${CYAN}Verifying project access...${NC}"
  if ! gcloud projects describe "${PROJECT_ID}" &>/dev/null; then
    echo -e "${RED}❌ Cannot access project: ${PROJECT_ID}${NC}"
    echo -e "${YELLOW}Check project ID and permissions${NC}"
    exit 1
  fi
  echo -e "${GREEN}✅ Project access confirmed${NC}\n"
}

validate_secret() {
  local secret_name="$1"
  echo -e "${CYAN}Validating secret:${NC} ${secret_name}"
  
  # Check if secret exists
  if ! gcloud secrets describe "${secret_name}" --project="${PROJECT_ID}" &>/dev/null; then
    echo -e "${RED}  ❌ Secret does not exist${NC}"
    echo -e "${YELLOW}  Create with: gcloud secrets create ${secret_name} --project=${PROJECT_ID}${NC}\n"
    ((MISSING_COUNT++))
    return 1
  fi
  
  # Check if secret has enabled version
  local latest_version
  latest_version=$(gcloud secrets versions list "${secret_name}" \
    --project="${PROJECT_ID}" \
    --filter="state:ENABLED" \
    --limit=1 \
    --format="value(name)" 2>/dev/null)
  
  if [[ -z "${latest_version}" ]]; then
    echo -e "${RED}  ❌ No enabled version found${NC}"
    echo -e "${YELLOW}  Add version: echo 'value' | gcloud secrets versions add ${secret_name} --data-file=- --project=${PROJECT_ID}${NC}\n"
    ((INVALID_COUNT++))
    return 1
  fi
  
  # Access secret value and check if not empty or placeholder
  local secret_value
  if ! secret_value=$(gcloud secrets versions access "${latest_version}" \
    --secret="${secret_name}" \
    --project="${PROJECT_ID}" 2>/dev/null); then
    echo -e "${RED}  ❌ Cannot access secret value${NC}"
    echo -e "${YELLOW}  Check IAM permissions${NC}\n"
    ((INVALID_COUNT++))
    return 1
  fi
  
  # Check if value is empty
  if [[ -z "${secret_value}" ]]; then
    echo -e "${RED}  ❌ Secret value is empty${NC}"
    echo -e "${YELLOW}  Update with: echo 'value' | gcloud secrets versions add ${secret_name} --data-file=- --project=${PROJECT_ID}${NC}\n"
    ((INVALID_COUNT++))
    return 1
  fi
  
  # Check if value is a placeholder (starts with YOUR_)
  if [[ "${secret_value}" =~ ^YOUR_ ]]; then
    echo -e "${RED}  ❌ Secret contains placeholder value: ${secret_value}${NC}"
    echo -e "${YELLOW}  Update with actual value: echo 'actual_value' | gcloud secrets versions add ${secret_name} --data-file=- --project=${PROJECT_ID}${NC}\n"
    ((INVALID_COUNT++))
    return 1
  fi
  
  # Check value length to provide feedback
  local value_length=${#secret_value}
  echo -e "${GREEN}  ✅ Valid (${value_length} characters, version: ${latest_version})${NC}\n"
  ((VALID_COUNT++))
  return 0
}

print_summary() {
  local total_count=${#REQUIRED_SECRETS[@]}
  local failed_count=$((MISSING_COUNT + INVALID_COUNT))
  
  echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}📋 Validation Summary${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}✅ Valid secrets:    ${VALID_COUNT}/${total_count}${NC}"
  echo -e "${RED}❌ Missing secrets:  ${MISSING_COUNT}/${total_count}${NC}"
  echo -e "${YELLOW}⚠️  Invalid secrets:  ${INVALID_COUNT}/${total_count}${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
  
  if [[ ${failed_count} -gt 0 ]]; then
    echo -e "${RED}🚨 Secret validation failed!${NC}\n"
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Create missing secrets using the commands shown above"
    echo "2. Update placeholder values with actual credentials"
    echo "3. Ensure you have secretmanager.secrets.get permission"
    echo "4. Re-run this script to verify fixes"
    echo ""
    echo -e "${CYAN}Quick fix command template:${NC}"
    echo "  echo 'YOUR_VALUE' | gcloud secrets create SECRET_NAME --data-file=- --project=${PROJECT_ID}"
    echo "  echo 'YOUR_VALUE' | gcloud secrets versions add SECRET_NAME --data-file=- --project=${PROJECT_ID}"
    echo ""
    return 1
  else
    echo -e "${GREEN}🎉 All secrets validated successfully!${NC}\n"
    return 0
  fi
}

################################################################################
# Main execution
################################################################################

main() {
  print_header
  check_gcloud_auth
  check_project_access
  
  echo -e "${CYAN}Validating ${#REQUIRED_SECRETS[@]} required secrets...${NC}\n"
  
  for secret in "${REQUIRED_SECRETS[@]}"; do
    validate_secret "${secret}" || true  # Continue on failure
  done
  
  print_summary
}

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
