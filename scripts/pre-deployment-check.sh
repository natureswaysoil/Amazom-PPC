#!/usr/bin/env bash

################################################################################
# pre-deployment-check.sh
#
# Purpose: Pre-deployment validation to run BEFORE deploying
# Validates git status, secrets, authentication, files, and dependencies
#
# Usage: ./pre-deployment-check.sh [PROJECT_ID]
# Exit Code: 0 if all checks pass, 1 if any fail
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
FAILED_CHECKS=0
PASSED_CHECKS=0

################################################################################
# Helper Functions
################################################################################

print_header() {
  echo ""
  echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║${NC}  ${CYAN}🔍 Pre-Deployment Validation${NC}                   ${BLUE}║${NC}"
  echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
  echo -e "${CYAN}Project:${NC} ${PROJECT_ID}"
  echo -e "${CYAN}Time:${NC} $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
  echo ""
}

check_passed() {
  local message="$1"
  echo -e "${GREEN}✅ ${message}${NC}"
  ((PASSED_CHECKS++))
}

check_failed() {
  local message="$1"
  local remedy="${2:-}"
  echo -e "${RED}❌ ${message}${NC}"
  if [[ -n "${remedy}" ]]; then
    echo -e "${YELLOW}   Fix: ${remedy}${NC}"
  fi
  ((FAILED_CHECKS++))
}

print_check_header() {
  echo -e "\n${CYAN}${1}${NC}"
  echo -e "${BLUE}─────────────────────────────────────────────────────${NC}"
}

################################################################################
# Check 1: Git Status
################################################################################

check_git_status() {
  print_check_header "Check 1: Git Repository Status"
  
  # Check if in a git repository
  if ! git rev-parse --git-dir &>/dev/null; then
    check_failed "Not in a git repository"
    return
  fi
  
  # Check current branch
  local current_branch
  current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  
  if [[ "${current_branch}" == "main" || "${current_branch}" == "master" ]]; then
    check_passed "On main branch (${current_branch})"
  else
    echo -e "${YELLOW}⚠️  On branch: ${current_branch} (not main/master)${NC}"
    echo -e "${YELLOW}   Consider deploying from main branch${NC}"
  fi
  
  # Check for uncommitted changes
  if git diff-index --quiet HEAD -- 2>/dev/null; then
    check_passed "No uncommitted changes"
  else
    check_failed "Uncommitted changes detected" "Commit or stash changes: git add . && git commit"
  fi
  
  # Check if branch is up to date with remote
  if git remote get-url origin &>/dev/null; then
    local local_commit=$(git rev-parse HEAD 2>/dev/null)
    local remote_commit=$(git rev-parse origin/"${current_branch}" 2>/dev/null || echo "unknown")
    
    if [[ "${local_commit}" == "${remote_commit}" ]]; then
      check_passed "Branch is up to date with remote"
    elif [[ "${remote_commit}" == "unknown" ]]; then
      echo -e "${YELLOW}⚠️  Cannot verify remote status${NC}"
    else
      check_failed "Branch is not up to date with remote" "Pull latest changes: git pull"
    fi
  fi
}

################################################################################
# Check 2: Validate Secrets
################################################################################

check_secrets() {
  print_check_header "Check 2: Secret Manager Validation"
  
  # Get script directory
  local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local validate_script="${script_dir}/validate-secrets.sh"
  
  if [[ ! -f "${validate_script}" ]]; then
    echo -e "${YELLOW}⚠️  validate-secrets.sh not found, skipping detailed check${NC}"
    
    # Basic check
    local required_secrets=("amazon-client-id" "amazon-client-secret" "amazon-refresh-token" "ppc-profile-id")
    local all_exist=true
    
    for secret in "${required_secrets[@]}"; do
      if ! gcloud secrets describe "${secret}" --project="${PROJECT_ID}" &>/dev/null; then
        all_exist=false
        break
      fi
    done
    
    if ${all_exist}; then
      check_passed "Basic secret check passed"
    else
      check_failed "Some required secrets missing" "Run ./scripts/validate-secrets.sh"
    fi
    return
  fi
  
  # Run comprehensive validation
  if bash "${validate_script}" "${PROJECT_ID}" &>/dev/null; then
    check_passed "All secrets validated"
  else
    check_failed "Secret validation failed" "Run ./scripts/validate-secrets.sh for details"
  fi
}

################################################################################
# Check 3: gcloud Authentication
################################################################################

check_gcloud_auth() {
  print_check_header "Check 3: gcloud Authentication"
  
  if ! command -v gcloud &>/dev/null; then
    check_failed "gcloud CLI not installed" "Install from: https://cloud.google.com/sdk/docs/install"
    return
  fi
  
  check_passed "gcloud CLI installed"
  
  # Check if authenticated
  if gcloud auth list --filter=status:ACTIVE --format="value(account)" &>/dev/null; then
    local account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -n1)
    check_passed "Authenticated as: ${account}"
  else
    check_failed "Not authenticated" "Run: gcloud auth login"
  fi
  
  # Check application default credentials
  if gcloud auth application-default print-access-token &>/dev/null; then
    check_passed "Application default credentials configured"
  else
    echo -e "${YELLOW}⚠️  Application default credentials not set${NC}"
    echo -e "${YELLOW}   May be needed for local testing: gcloud auth application-default login${NC}"
  fi
}

################################################################################
# Check 4: gcloud Project
################################################################################

check_gcloud_project() {
  print_check_header "Check 4: gcloud Project Configuration"
  
  local current_project
  current_project=$(gcloud config get-value project 2>/dev/null || echo "")
  
  if [[ -z "${current_project}" ]]; then
    check_failed "No project configured" "Set project: gcloud config set project ${PROJECT_ID}"
    return
  fi
  
  if [[ "${current_project}" == "${PROJECT_ID}" ]]; then
    check_passed "Project set correctly: ${PROJECT_ID}"
  else
    echo -e "${YELLOW}⚠️  Project mismatch: configured=${current_project}, expected=${PROJECT_ID}${NC}"
    echo -e "${YELLOW}   Fix: gcloud config set project ${PROJECT_ID}${NC}"
  fi
  
  # Verify project access
  if gcloud projects describe "${PROJECT_ID}" &>/dev/null; then
    check_passed "Project access verified"
  else
    check_failed "Cannot access project: ${PROJECT_ID}" "Check project ID and permissions"
  fi
}

################################################################################
# Check 5: Required Files
################################################################################

check_required_files() {
  print_check_header "Check 5: Required Files"
  
  local required_files=(
    "main.py"
    "requirements.txt"
    "optimizer_core.py"
    "dashboard_client.py"
    "bigquery_client.py"
  )
  
  local all_present=true
  
  for file in "${required_files[@]}"; do
    if [[ -f "${file}" ]]; then
      check_passed "${file} exists"
    else
      check_failed "${file} not found"
      all_present=false
    fi
  done
  
  if ${all_present}; then
    echo ""
    check_passed "All required files present"
  fi
}

################################################################################
# Check 6: Entry Point Function
################################################################################

check_entry_point() {
  print_check_header "Check 6: Python Entry Point"
  
  if [[ ! -f "main.py" ]]; then
    check_failed "main.py not found"
    return
  fi
  
  # Check for run_optimizer function
  if grep -q "^def run_optimizer" main.py; then
    check_passed "run_optimizer function found in main.py"
  else
    check_failed "run_optimizer function not found in main.py"
  fi
  
  # Check for run_health_check function
  if grep -q "^def run_health_check" main.py; then
    check_passed "run_health_check function found in main.py"
  else
    echo -e "${YELLOW}⚠️  run_health_check function not found (optional)${NC}"
  fi
  
  # Check for functions_framework decorator
  if grep -q "@functions_framework" main.py; then
    check_passed "functions_framework decorators found"
  else
    echo -e "${YELLOW}⚠️  No functions_framework decorators found${NC}"
  fi
}

################################################################################
# Check 7: Requirements.txt Syntax
################################################################################

check_requirements() {
  print_check_header "Check 7: requirements.txt Validation"
  
  if [[ ! -f "requirements.txt" ]]; then
    check_failed "requirements.txt not found"
    return
  fi
  
  check_passed "requirements.txt exists"
  
  # Check for common issues
  if grep -q $'\r' requirements.txt; then
    check_failed "Windows line endings detected" "Convert to Unix: dos2unix requirements.txt"
    return
  fi
  
  check_passed "No Windows line endings"
  
  # Check for empty lines or comments only
  if grep -v "^#" requirements.txt | grep -v "^$" | grep -q .; then
    check_passed "requirements.txt has dependencies"
  else
    echo -e "${YELLOW}⚠️  requirements.txt appears empty${NC}"
  fi
  
  # Try dry-run install (requires Python)
  if command -v pip &>/dev/null; then
    echo -e "${CYAN}Testing pip install --dry-run...${NC}"
    if pip install --dry-run -r requirements.txt &>/dev/null; then
      check_passed "requirements.txt syntax valid (pip dry-run passed)"
    else
      check_failed "requirements.txt has errors" "Check syntax: pip install --dry-run -r requirements.txt"
    fi
  else
    echo -e "${YELLOW}⚠️  pip not available, skipping syntax test${NC}"
  fi
}

################################################################################
# Check 8: Common Issues
################################################################################

check_common_issues() {
  print_check_header "Check 8: Common Deployment Issues"
  
  # Check for __pycache__ in git
  if git ls-files | grep -q "__pycache__"; then
    check_failed "__pycache__ in version control" "Add to .gitignore and remove: git rm -r --cached __pycache__"
  else
    check_passed "No __pycache__ in version control"
  fi
  
  # Check for .env files in git
  if git ls-files | grep -q "^\.env$"; then
    check_failed ".env file in version control" "Remove: git rm --cached .env"
  else
    check_passed "No .env file in version control"
  fi
  
  # Check for large files
  local large_files
  large_files=$(git ls-files | xargs -I {} sh -c 'if [ -f "{}" ]; then stat -f%z "{}" 2>/dev/null || stat -c%s "{}"; fi' | awk '$1 > 10485760' | wc -l)
  
  if [[ ${large_files} -gt 0 ]]; then
    echo -e "${YELLOW}⚠️  ${large_files} file(s) larger than 10MB detected${NC}"
    echo -e "${YELLOW}   Consider using .gcloudignore${NC}"
  else
    check_passed "No large files (>10MB) in repository"
  fi
  
  # Check .gcloudignore exists
  if [[ -f ".gcloudignore" ]]; then
    check_passed ".gcloudignore file exists"
  else
    echo -e "${YELLOW}⚠️  .gcloudignore not found (recommended)${NC}"
  fi
}

################################################################################
# Summary
################################################################################

print_summary() {
  local total_checks=$((PASSED_CHECKS + FAILED_CHECKS))
  
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}📊 Pre-Deployment Summary${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}✅ Passed: ${PASSED_CHECKS}${NC}"
  echo -e "${RED}❌ Failed: ${FAILED_CHECKS}${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  
  if [[ ${FAILED_CHECKS} -eq 0 ]]; then
    echo -e "${GREEN}🎉 All checks passed! Ready to deploy.${NC}\n"
    echo -e "${CYAN}Deploy with:${NC}"
    echo "  gcloud functions deploy ppc-optimizer --gen2 \\"
    echo "    --runtime=python311 \\"
    echo "    --region=us-central1 \\"
    echo "    --source=. \\"
    echo "    --entry-point=run_optimizer \\"
    echo "    --trigger-http \\"
    echo "    --allow-unauthenticated \\"
    echo "    --project=${PROJECT_ID}"
    echo ""
    return 0
  else
    echo -e "${RED}🚫 Deployment not recommended - fix issues above first${NC}\n"
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Review and fix all ❌ failed checks above"
    echo "2. Re-run this script to verify fixes"
    echo "3. Use ./scripts/fix-common-issues.sh for automated fixes"
    echo ""
    return 1
  fi
}

################################################################################
# Main execution
################################################################################

main() {
  print_header
  
  check_git_status
  check_secrets
  check_gcloud_auth
  check_gcloud_project
  check_required_files
  check_entry_point
  check_requirements
  check_common_issues
  
  print_summary
}

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
