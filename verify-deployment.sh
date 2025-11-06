#!/bin/bash
# Production Deployment Verification Script
# This script verifies that all components of the deployment are working correctly

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT:-amazon-ppc-474902}"
REGION="${REGION:-us-central1}"
DATASET_ID="${DATASET_ID:-amazon_ppc}"
FUNCTION_NAME="amazon-ppc-optimizer"

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0

# Utility functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_test() {
    echo -e "${CYAN}▶ $1${NC}"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
}

print_success() {
    echo -e "${GREEN}  ✅ $1${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
}

print_fail() {
    echo -e "${RED}  ❌ $1${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
}

print_warning() {
    echo -e "${YELLOW}  ⚠️  $1${NC}"
    WARNINGS=$((WARNINGS + 1))
}

print_info() {
    echo -e "${BLUE}  ℹ️  $1${NC}"
}

# Verification functions

verify_gcloud_auth() {
    print_header "1. Verifying Google Cloud Authentication"
    
    print_test "Checking gcloud authentication"
    if gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "@"; then
        ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
        print_success "Authenticated as: $ACCOUNT"
    else
        print_fail "Not authenticated to Google Cloud"
        print_info "Run: gcloud auth login"
        return 1
    fi
    
    print_test "Checking project configuration"
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ "$CURRENT_PROJECT" = "$PROJECT_ID" ]; then
        print_success "Project configured: $PROJECT_ID"
    else
        print_warning "Project mismatch. Current: $CURRENT_PROJECT, Expected: $PROJECT_ID"
        print_info "Run: gcloud config set project $PROJECT_ID"
    fi
}

verify_apis_enabled() {
    print_header "2. Verifying Google Cloud APIs"
    
    local required_apis=(
        "cloudfunctions.googleapis.com"
        "cloudbuild.googleapis.com"
        "cloudscheduler.googleapis.com"
        "secretmanager.googleapis.com"
        "bigquery.googleapis.com"
        "bigquerystorage.googleapis.com"
    )
    
    for api in "${required_apis[@]}"; do
        print_test "Checking if $api is enabled"
        if gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "$api"; then
            print_success "$api is enabled"
        else
            print_fail "$api is not enabled"
            print_info "Run: gcloud services enable $api"
        fi
    done
}

verify_bigquery_setup() {
    print_header "3. Verifying BigQuery Infrastructure"
    
    print_test "Checking if dataset exists"
    if bq ls "$PROJECT_ID:" 2>/dev/null | grep -q "$DATASET_ID"; then
        print_success "Dataset $DATASET_ID exists"
        
        # Check tables
        local required_tables=(
            "optimization_results"
            "campaign_details"
            "optimization_progress"
            "optimization_errors"
        )
        
        for table in "${required_tables[@]}"; do
            print_test "Checking table: $table"
            if bq ls "$PROJECT_ID:$DATASET_ID" 2>/dev/null | grep -q "$table"; then
                print_success "Table $table exists"
            else
                print_fail "Table $table not found"
                print_info "Run: ./setup-bigquery.sh $PROJECT_ID $DATASET_ID us-east4"
            fi
        done
    else
        print_fail "Dataset $DATASET_ID not found"
        print_info "Run: ./setup-bigquery.sh $PROJECT_ID $DATASET_ID us-east4"
    fi
    
    print_test "Checking BigQuery permissions"
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null)
    SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    
    if gcloud projects get-iam-policy "$PROJECT_ID" --flatten="bindings[].members" --filter="bindings.members:$SERVICE_ACCOUNT AND bindings.role:roles/bigquery.dataEditor" --format="value(bindings.role)" | grep -q "bigquery"; then
        print_success "BigQuery permissions configured"
    else
        print_warning "BigQuery permissions may not be configured"
        print_info "Grant permissions with grant-access.sh or deployment script"
    fi
}

verify_secrets() {
    print_header "4. Verifying Secret Manager"
    
    local required_secrets=(
        "amazon-client-id"
        "amazon-client-secret"
        "amazon-refresh-token"
        "amazon-profile-id"
    )
    
    local optional_secrets=(
        "dashboard-api-key"
        "dashboard-url"
    )
    
    print_info "Checking required secrets..."
    for secret in "${required_secrets[@]}"; do
        print_test "Checking secret: $secret"
        if gcloud secrets describe "$secret" &>/dev/null; then
            print_success "Secret $secret exists"
            
            # Check if service account has access
            PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null)
            SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
            
            if gcloud secrets get-iam-policy "$secret" --format="value(bindings.members)" 2>/dev/null | grep -q "$SA_EMAIL"; then
                print_success "Service account has access to $secret"
            else
                print_warning "Service account may not have access to $secret"
            fi
        else
            print_fail "Secret $secret not found"
            print_info "Create with: echo -n 'VALUE' | gcloud secrets create $secret --data-file=-"
        fi
    done
    
    print_info "Checking optional secrets..."
    for secret in "${optional_secrets[@]}"; do
        print_test "Checking optional secret: $secret"
        if gcloud secrets describe "$secret" &>/dev/null; then
            print_success "Secret $secret exists"
        else
            print_warning "Optional secret $secret not configured"
        fi
    done
}

verify_cloud_function() {
    print_header "5. Verifying Cloud Function Deployment"
    
    print_test "Checking if function exists"
    if gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 &>/dev/null; then
        print_success "Function $FUNCTION_NAME exists"
        
        # Get function URL
        FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
            --region="$REGION" \
            --gen2 \
            --format='value(serviceConfig.uri)' 2>/dev/null)
        print_info "Function URL: $FUNCTION_URL"
        
        # Check function configuration
        print_test "Checking function runtime"
        RUNTIME=$(gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 --format='value(buildConfig.runtime)' 2>/dev/null)
        if [ "$RUNTIME" = "python311" ]; then
            print_success "Runtime: $RUNTIME"
        else
            print_warning "Runtime: $RUNTIME (expected python311)"
        fi
        
        print_test "Checking function timeout"
        TIMEOUT=$(gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 --format='value(serviceConfig.timeoutSeconds)' 2>/dev/null)
        if [ "$TIMEOUT" -ge 540 ]; then
            print_success "Timeout: ${TIMEOUT}s"
        else
            print_warning "Timeout: ${TIMEOUT}s (recommended: 540s or more)"
        fi
        
        print_test "Checking function memory"
        MEMORY=$(gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 --format='value(serviceConfig.availableMemory)' 2>/dev/null)
        print_success "Memory: $MEMORY"
        
        # Test health check
        print_test "Testing health check endpoint"
        TOKEN=$(gcloud auth print-identity-token 2>/dev/null)
        if [ -n "$TOKEN" ]; then
            HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer ${TOKEN}" "${FUNCTION_URL}?health=true" 2>/dev/null || echo "FAILED\n000")
            HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
            BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)
            
            if [ "$HTTP_CODE" = "200" ]; then
                print_success "Health check passed (HTTP $HTTP_CODE)"
                if echo "$BODY" | grep -q "healthy"; then
                    print_success "Response contains 'healthy'"
                fi
            else
                print_fail "Health check failed (HTTP $HTTP_CODE)"
                print_info "Response: $BODY"
            fi
        else
            print_warning "Could not get identity token for testing"
        fi
        
    else
        print_fail "Function $FUNCTION_NAME not found"
        print_info "Deploy with: ./deploy-complete.sh or gcloud functions deploy"
    fi
}

verify_cloud_scheduler() {
    print_header "6. Verifying Cloud Scheduler"
    
    print_test "Checking if scheduler jobs exist"
    JOB_COUNT=$(gcloud scheduler jobs list --location="$REGION" 2>/dev/null | grep -c "$FUNCTION_NAME" || echo "0")
    
    if [ "$JOB_COUNT" -gt 0 ]; then
        print_success "Found $JOB_COUNT scheduler job(s)"
        
        # Check specific jobs
        if gcloud scheduler jobs describe "${FUNCTION_NAME}-daily" --location="$REGION" &>/dev/null; then
            print_success "Daily production job exists"
            
            SCHEDULE=$(gcloud scheduler jobs describe "${FUNCTION_NAME}-daily" --location="$REGION" --format='value(schedule)' 2>/dev/null)
            print_info "Schedule: $SCHEDULE"
        else
            print_warning "Daily production job not found"
        fi
        
        if gcloud scheduler jobs describe "${FUNCTION_NAME}-dryrun" --location="$REGION" &>/dev/null; then
            print_success "Dry-run test job exists"
        else
            print_warning "Dry-run test job not found"
        fi
        
    else
        print_fail "No scheduler jobs found"
        print_info "Create with: ./deploy-complete.sh scheduler"
    fi
}

verify_iam_permissions() {
    print_header "7. Verifying IAM Permissions"
    
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null)
    SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    
    print_info "Service Account: $SERVICE_ACCOUNT"
    
    local required_roles=(
        "roles/bigquery.dataEditor"
        "roles/bigquery.jobUser"
    )
    
    for role in "${required_roles[@]}"; do
        print_test "Checking role: $role"
        if gcloud projects get-iam-policy "$PROJECT_ID" --flatten="bindings[].members" --filter="bindings.members:$SERVICE_ACCOUNT AND bindings.role:$role" --format="value(bindings.role)" 2>/dev/null | grep -q "$role"; then
            print_success "Role $role assigned"
        else
            print_fail "Role $role not assigned"
            print_info "Grant with: gcloud projects add-iam-policy-binding $PROJECT_ID --member='serviceAccount:$SERVICE_ACCOUNT' --role='$role'"
        fi
    done
    
    # Check scheduler service account
    print_test "Checking scheduler service account"
    if gcloud iam service-accounts describe "ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" &>/dev/null; then
        print_success "Scheduler service account exists"
    else
        print_warning "Scheduler service account not found"
        print_info "Create with: gcloud iam service-accounts create ppc-scheduler"
    fi
}

verify_logs() {
    print_header "8. Verifying Logs and Monitoring"
    
    print_test "Checking for recent function logs"
    LOG_COUNT=$(gcloud functions logs read "$FUNCTION_NAME" --region="$REGION" --limit=10 2>/dev/null | wc -l || echo "0")
    
    if [ "$LOG_COUNT" -gt 0 ]; then
        print_success "Found $LOG_COUNT recent log entries"
        
        # Check for errors in recent logs
        ERROR_COUNT=$(gcloud functions logs read "$FUNCTION_NAME" --region="$REGION" --limit=50 2>/dev/null | grep -ci "error" || echo "0")
        if [ "$ERROR_COUNT" -eq 0 ]; then
            print_success "No errors in recent logs"
        else
            print_warning "Found $ERROR_COUNT error entries in recent logs"
            print_info "Review with: gcloud functions logs read $FUNCTION_NAME --region=$REGION --limit=50 | grep -i error"
        fi
    else
        print_warning "No recent log entries found (function may not have been invoked yet)"
    fi
}

verify_github_actions() {
    print_header "9. Verifying GitHub Actions Configuration"
    
    print_test "Checking if GitHub Actions workflow exists"
    if [ -f ".github/workflows/deploy-to-cloud.yml" ]; then
        print_success "Deploy workflow exists"
    else
        print_fail "Deploy workflow not found"
        print_info "Create workflow from template"
    fi
    
    print_test "Checking if health check workflow exists"
    if [ -f ".github/workflows/health-check.yml" ]; then
        print_success "Health check workflow exists"
    else
        print_warning "Health check workflow not found"
    fi
    
    print_info "GitHub Secrets should be configured:"
    echo "    - GCP_PROJECT_ID"
    echo "    - GCP_SA_KEY"
    echo "    - AMAZON_CLIENT_ID"
    echo "    - AMAZON_CLIENT_SECRET"
    echo "    - AMAZON_REFRESH_TOKEN"
    echo "    - AMAZON_PROFILE_ID"
    echo "    - GMAIL_USER (optional)"
    echo "    - GMAIL_PASS (optional)"
    echo "    - DASHBOARD_API_KEY (optional)"
    print_info "See GITHUB_SECRETS_SETUP.md for details"
}

test_end_to_end() {
    print_header "10. End-to-End Integration Test"
    
    print_test "Testing Amazon Ads API connection through deployed function"
    
    FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
        --region="$REGION" \
        --gen2 \
        --format='value(serviceConfig.uri)' 2>/dev/null)
    
    if [ -z "$FUNCTION_URL" ]; then
        print_fail "Could not get function URL"
        return 1
    fi
    
    TOKEN=$(gcloud auth print-identity-token 2>/dev/null)
    if [ -z "$TOKEN" ]; then
        print_fail "Could not get identity token"
        return 1
    fi
    
    VERIFY_RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer ${TOKEN}" "${FUNCTION_URL}?verify_connection=true&verify_sample_size=3" 2>/dev/null || echo "FAILED\n000")
    HTTP_CODE=$(echo "$VERIFY_RESPONSE" | tail -n1)
    BODY=$(echo "$VERIFY_RESPONSE" | head -n-1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        print_success "Connection verification passed (HTTP $HTTP_CODE)"
        if echo "$BODY" | grep -q "success"; then
            print_success "Amazon Ads API connection successful"
        fi
    else
        print_warning "Connection verification failed (HTTP $HTTP_CODE)"
        print_info "Response: $BODY"
        print_info "This may be expected if credentials are not yet configured"
    fi
}

generate_report() {
    print_header "Verification Summary Report"
    
    echo -e "${BLUE}Total Tests Run:${NC} $TOTAL_TESTS"
    echo -e "${GREEN}Passed:${NC} $PASSED_TESTS"
    echo -e "${RED}Failed:${NC} $FAILED_TESTS"
    echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
    echo ""
    
    local success_rate=0
    if [ $TOTAL_TESTS -gt 0 ]; then
        success_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    fi
    
    echo -e "${BLUE}Success Rate:${NC} ${success_rate}%"
    echo ""
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${GREEN}✅ All critical tests passed!${NC}"
        echo -e "${GREEN}Your deployment is ready for production.${NC}"
    elif [ $FAILED_TESTS -le 3 ]; then
        echo -e "${YELLOW}⚠️  Some tests failed, but deployment may still be functional.${NC}"
        echo -e "${YELLOW}Review failed tests and warnings above.${NC}"
    else
        echo -e "${RED}❌ Multiple tests failed.${NC}"
        echo -e "${RED}Your deployment requires attention before production use.${NC}"
    fi
    
    echo ""
    print_header "Next Steps"
    
    if [ $FAILED_TESTS -gt 0 ]; then
        echo "1. Review failed tests above"
        echo "2. Follow the suggested commands to fix issues"
        echo "3. Run this verification script again"
        echo "4. Review documentation: COMPLETE_DEPLOYMENT_GUIDE.md"
    else
        echo "1. Run a test optimization:"
        echo "   TOKEN=\$(gcloud auth print-identity-token)"
        echo "   curl -X POST -H \"Authorization: Bearer \$TOKEN\" \\"
        echo "     -H \"Content-Type: application/json\" \\"
        echo "     -d '{\"dry_run\": true}' \\"
        echo "     \"$FUNCTION_URL\""
        echo ""
        echo "2. Monitor the first few scheduler runs"
        echo "3. Check dashboard for live data"
        echo "4. Set up additional monitoring and alerts"
    fi
}

# Main execution
main() {
    clear
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Amazon PPC Optimizer - Deployment Verification${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "This script will verify your deployment is configured correctly."
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo ""
    
    # Run all verification steps
    verify_gcloud_auth || true
    verify_apis_enabled || true
    verify_bigquery_setup || true
    verify_secrets || true
    verify_cloud_function || true
    verify_cloud_scheduler || true
    verify_iam_permissions || true
    verify_logs || true
    verify_github_actions || true
    test_end_to_end || true
    
    # Generate summary report
    generate_report
    
    echo ""
    echo -e "${BLUE}Verification complete!${NC}"
    echo ""
}

# Run main function
main "$@"
