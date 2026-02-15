#!/usr/bin/env bash

################################################################################
# fix-common-issues.sh
#
# Purpose: Automated fix script for common deployment problems
# Interactively detects and fixes issues with secrets, IAM, APIs, and more
#
# Usage: ./fix-common-issues.sh [PROJECT_ID]
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
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}"
ISSUES_FIXED=0
ISSUES_DETECTED=0

################################################################################
# Helper Functions
################################################################################

print_header() {
  echo ""
  echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║${NC}  ${CYAN}🔧 Fix Common Deployment Issues${NC}               ${BLUE}║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
  echo -e "${CYAN}Project:${NC} ${PROJECT_ID}"
  echo -e "${CYAN}Time:${NC} $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
  echo ""
}

print_section() {
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}${1}${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

confirm() {
  local message="$1"
  printf "${YELLOW}%s (y/N): ${NC}" "${message}"
  read -r response
  [[ "${response}" =~ ^[Yy]$ ]]
}

issue_detected() {
  ((ISSUES_DETECTED++))
}

issue_fixed() {
  ((ISSUES_FIXED++))
  echo -e "${GREEN}✅ Fixed${NC}\n"
}

################################################################################
# Fix 1: Recreate Missing Secrets
################################################################################

fix_missing_secrets() {
  print_section "Fix 1: Missing Secrets"
  
  local required_secrets=(
    "amazon-client-id"
    "amazon-client-secret"
    "amazon-refresh-token"
    "ppc-profile-id"
    "dashboard-url"
    "dashboard-api-key"
  )
  
  local missing_secrets=()
  
  echo -e "${CYAN}Checking for missing secrets...${NC}\n"
  
  for secret in "${required_secrets[@]}"; do
    if ! gcloud secrets describe "${secret}" --project="${PROJECT_ID}" &>/dev/null; then
      echo -e "${RED}❌ Missing: ${secret}${NC}"
      missing_secrets+=("${secret}")
      issue_detected
    else
      echo -e "${GREEN}✅ Exists: ${secret}${NC}"
    fi
  done
  
  if [[ ${#missing_secrets[@]} -eq 0 ]]; then
    echo -e "\n${GREEN}All secrets exist${NC}"
    return 0
  fi
  
  echo ""
  if ! confirm "Create ${#missing_secrets[@]} missing secret(s)?"; then
    echo -e "${YELLOW}Skipped${NC}"
    return 0
  fi
  
  for secret in "${missing_secrets[@]}"; do
    echo ""
    echo -e "${CYAN}Creating secret: ${secret}${NC}"
    printf "${YELLOW}Enter value for %s (input hidden): ${NC}" "${secret}"
    read -rs secret_value
    echo ""
    
    if [[ -z "${secret_value}" ]]; then
      echo -e "${YELLOW}⚠️  Empty value, skipping${NC}"
      continue
    fi
    
    if echo "${secret_value}" | gcloud secrets create "${secret}" \
      --project="${PROJECT_ID}" \
      --replication-policy="automatic" \
      --data-file=- 2>/dev/null; then
      issue_fixed
    else
      echo -e "${RED}❌ Failed to create secret${NC}"
    fi
  done
}

################################################################################
# Fix 2: Grant IAM Permissions
################################################################################

fix_iam_permissions() {
  print_section "Fix 2: IAM Permissions"
  
  echo -e "${CYAN}Checking IAM permissions...${NC}\n"
  
  # Get service account
  if [[ -z "${SERVICE_ACCOUNT}" ]]; then
    # Try to find Cloud Functions default service account
    local project_number
    project_number=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)" 2>/dev/null || echo "")
    
    if [[ -n "${project_number}" ]]; then
      SERVICE_ACCOUNT="${project_number}-compute@developer.gserviceaccount.com"
      echo -e "${CYAN}Using default service account: ${SERVICE_ACCOUNT}${NC}\n"
    else
      echo -e "${YELLOW}⚠️  Could not determine service account${NC}"
      printf "${YELLOW}Please provide service account email: ${NC}"
      read -r SERVICE_ACCOUNT
      
      if [[ -z "${SERVICE_ACCOUNT}" ]]; then
        echo -e "${YELLOW}Skipped${NC}"
        return 0
      fi
    fi
  fi
  
  # Check if service account exists
  if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT}" --project="${PROJECT_ID}" &>/dev/null; then
    echo -e "${RED}❌ Service account does not exist: ${SERVICE_ACCOUNT}${NC}"
    issue_detected
    return 1
  fi
  
  echo -e "${GREEN}✅ Service account exists${NC}\n"
  
  # Required roles
  local required_roles=(
    "roles/secretmanager.secretAccessor"
    "roles/bigquery.dataEditor"
    "roles/bigquery.jobUser"
  )
  
  if ! confirm "Grant required IAM roles to service account?"; then
    echo -e "${YELLOW}Skipped${NC}"
    return 0
  fi
  
  for role in "${required_roles[@]}"; do
    echo ""
    echo -e "${CYAN}Granting ${role}...${NC}"
    
    if gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${SERVICE_ACCOUNT}" \
      --role="${role}" \
      --condition=None \
      &>/dev/null; then
      issue_fixed
    else
      echo -e "${YELLOW}⚠️  Already granted or failed${NC}"
    fi
  done
}

################################################################################
# Fix 3: Enable Required APIs
################################################################################

fix_required_apis() {
  print_section "Fix 3: Required APIs"
  
  local required_apis=(
    "cloudfunctions.googleapis.com"
    "cloudbuild.googleapis.com"
    "secretmanager.googleapis.com"
    "bigquery.googleapis.com"
    "logging.googleapis.com"
  )
  
  echo -e "${CYAN}Checking required APIs...${NC}\n"
  
  local disabled_apis=()
  
  for api in "${required_apis[@]}"; do
    if gcloud services list --enabled --project="${PROJECT_ID}" --filter="name:${api}" --format="value(name)" 2>/dev/null | grep -q "${api}"; then
      echo -e "${GREEN}✅ Enabled: ${api}${NC}"
    else
      echo -e "${RED}❌ Disabled: ${api}${NC}"
      disabled_apis+=("${api}")
      issue_detected
    fi
  done
  
  if [[ ${#disabled_apis[@]} -eq 0 ]]; then
    echo -e "\n${GREEN}All required APIs are enabled${NC}"
    return 0
  fi
  
  echo ""
  if ! confirm "Enable ${#disabled_apis[@]} disabled API(s)?"; then
    echo -e "${YELLOW}Skipped${NC}"
    return 0
  fi
  
  for api in "${disabled_apis[@]}"; do
    echo ""
    echo -e "${CYAN}Enabling ${api}...${NC}"
    
    if gcloud services enable "${api}" --project="${PROJECT_ID}" 2>/dev/null; then
      issue_fixed
    else
      echo -e "${RED}❌ Failed to enable API${NC}"
    fi
  done
}

################################################################################
# Fix 4: Clear Cloud Functions Cache
################################################################################

fix_function_cache() {
  print_section "Fix 4: Cloud Functions Cache"
  
  echo -e "${CYAN}Cloud Functions sometimes cache old code or configurations.${NC}"
  echo -e "${CYAN}This can be resolved by redeploying with a new name or clearing build cache.${NC}\n"
  
  if ! confirm "Clear build cache and redeploy?"; then
    echo -e "${YELLOW}Skipped${NC}"
    return 0
  fi
  
  echo ""
  echo -e "${CYAN}Steps to clear cache:${NC}"
  echo "1. Delete the function:"
  echo "   gcloud functions delete ppc-optimizer --region=us-central1 --project=${PROJECT_ID}"
  echo ""
  echo "2. Wait 30 seconds for cleanup"
  echo ""
  echo "3. Redeploy the function with the same or different name"
  echo ""
  echo -e "${YELLOW}Note: This requires manual execution${NC}"
  echo -e "${YELLOW}Automated deletion skipped for safety${NC}"
}

################################################################################
# Fix 5: Sync Dashboard API Key
################################################################################

fix_dashboard_api_key() {
  print_section "Fix 5: Dashboard API Key Sync"
  
  echo -e "${CYAN}Ensuring dashboard API key is synchronized between Secret Manager and Vercel...${NC}\n"
  
  # Check if dashboard-api-key exists
  if ! gcloud secrets describe "dashboard-api-key" --project="${PROJECT_ID}" &>/dev/null; then
    echo -e "${YELLOW}⚠️  dashboard-api-key secret does not exist${NC}"
    
    if confirm "Create dashboard-api-key secret?"; then
      printf "${YELLOW}Enter API key value (input hidden): ${NC}"
      read -rs api_key_value
      echo ""
      
      if [[ -n "${api_key_value}" ]]; then
        if echo "${api_key_value}" | gcloud secrets create "dashboard-api-key" \
          --project="${PROJECT_ID}" \
          --replication-policy="automatic" \
          --data-file=- 2>/dev/null; then
          issue_fixed
        fi
      fi
    fi
    return 0
  fi
  
  # Get current API key
  local api_key
  if api_key=$(gcloud secrets versions access latest --secret="dashboard-api-key" --project="${PROJECT_ID}" 2>/dev/null); then
    echo -e "${GREEN}✅ API key retrieved from Secret Manager${NC}"
    echo -e "${CYAN}API Key (first 10 chars): ${api_key:0:10}...${NC}\n"
    
    echo -e "${YELLOW}💡 To sync with Vercel:${NC}"
    echo "1. Log in to Vercel dashboard"
    echo "2. Navigate to your project settings"
    echo "3. Go to Environment Variables"
    echo "4. Update DASHBOARD_API_KEY with the value from Secret Manager"
    echo "5. Redeploy the Vercel app"
    echo ""
  else
    echo -e "${RED}❌ Could not retrieve API key${NC}"
  fi
}

################################################################################
# Fix 6: BigQuery Permissions
################################################################################

fix_bigquery_permissions() {
  print_section "Fix 6: BigQuery Dataset Permissions"
  
  echo -e "${CYAN}Checking BigQuery dataset permissions...${NC}\n"
  
  local dataset="amazon_ppc"
  
  # Check if dataset exists
  if ! bq show --project_id="${PROJECT_ID}" "${dataset}" &>/dev/null; then
    echo -e "${RED}❌ Dataset does not exist: ${dataset}${NC}"
    issue_detected
    
    if confirm "Create BigQuery dataset?"; then
      if bq mk --project_id="${PROJECT_ID}" --location=US "${dataset}" 2>/dev/null; then
        echo -e "${GREEN}✅ Dataset created${NC}\n"
        issue_fixed
      else
        echo -e "${RED}❌ Failed to create dataset${NC}"
        return 1
      fi
    else
      return 0
    fi
  fi
  
  echo -e "${GREEN}✅ Dataset exists${NC}\n"
  
  # Grant permissions to service account
  if [[ -n "${SERVICE_ACCOUNT}" ]]; then
    if confirm "Grant BigQuery permissions to ${SERVICE_ACCOUNT}?"; then
      echo ""
      echo -e "${CYAN}Granting dataset access...${NC}"
      
      # This requires manual IAM binding at dataset level
      echo -e "${YELLOW}Run this command:${NC}"
      echo "bq update --project_id=${PROJECT_ID} \\"
      echo "  --dataset_id=${dataset} \\"
      echo "  --access_role=WRITER \\"
      echo "  --service_account=${SERVICE_ACCOUNT}"
      echo ""
      echo -e "${YELLOW}Note: Automated execution not supported by bq CLI for dataset IAM${NC}"
    fi
  fi
}

################################################################################
# Summary
################################################################################

print_summary() {
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}📊 Fix Summary${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${YELLOW}Issues Detected: ${ISSUES_DETECTED}${NC}"
  echo -e "${GREEN}Issues Fixed:    ${ISSUES_FIXED}${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  
  if [[ ${ISSUES_FIXED} -gt 0 ]]; then
    echo -e "${GREEN}🎉 Fixed ${ISSUES_FIXED} issue(s)${NC}\n"
  fi
  
  echo -e "${YELLOW}Next Steps:${NC}"
  echo "1. Run ./scripts/validate-secrets.sh to verify secrets"
  echo "2. Run ./scripts/pre-deployment-check.sh before deploying"
  echo "3. Deploy the function"
  echo "4. Run ./scripts/post-deployment-check.sh to verify"
  echo ""
}

################################################################################
# Main execution
################################################################################

main() {
  print_header
  
  echo -e "${CYAN}This script will help you fix common deployment issues.${NC}"
  echo -e "${CYAN}You will be prompted before each fix is applied.${NC}\n"
  
  fix_missing_secrets || true
  fix_iam_permissions || true
  fix_required_apis || true
  fix_function_cache || true
  fix_dashboard_api_key || true
  fix_bigquery_permissions || true
  
  print_summary
}

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
