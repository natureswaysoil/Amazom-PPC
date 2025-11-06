#!/bin/bash
# Complete CI/CD Deployment Automation Script
# This script automates the entire deployment process from setup to production

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
# IMPORTANT: Set GCP_PROJECT environment variable before running this script
# Example: export GCP_PROJECT=your-project-id
PROJECT_ID="${GCP_PROJECT:-}"
REGION="${REGION:-us-central1}"
BIGQUERY_LOCATION="${BIGQUERY_LOCATION:-us-east4}"
DATASET_ID="${DATASET_ID:-amazon_ppc}"
FUNCTION_NAME="amazon-ppc-optimizer"

# Validate required configuration
if [ -z "$PROJECT_ID" ]; then
    print_error "GCP_PROJECT environment variable is not set"
    print_info "Please set your Google Cloud Project ID:"
    print_info "  export GCP_PROJECT=your-project-id"
    print_info "  ./deploy-complete.sh"
    exit 1
fi

# Function to print colored output
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to verify prerequisites
check_prerequisites() {
    print_header "Step 0: Checking Prerequisites"
    
    local all_ok=true
    
    # Check gcloud
    if command_exists gcloud; then
        print_success "gcloud CLI installed"
    else
        print_error "gcloud CLI not found. Please install Google Cloud SDK."
        all_ok=false
    fi
    
    # Check bq
    if command_exists bq; then
        print_success "bq command-line tool installed"
    else
        print_error "bq tool not found. Please install BigQuery command-line tools."
        all_ok=false
    fi
    
    # Check python
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python installed (version $PYTHON_VERSION)"
    else
        print_error "Python 3 not found. Please install Python 3.11 or later."
        all_ok=false
    fi
    
    # Check git
    if command_exists git; then
        print_success "git installed"
    else
        print_error "git not found. Please install git."
        all_ok=false
    fi
    
    if [ "$all_ok" = false ]; then
        print_error "Prerequisites check failed. Please install missing tools."
        exit 1
    fi
    
    print_success "All prerequisites met!"
}

# Function to set up Google Cloud project
setup_gcp_project() {
    print_header "Step 1: Setting up Google Cloud Project"
    
    print_info "Setting project to: $PROJECT_ID"
    gcloud config set project "$PROJECT_ID"
    
    print_info "Enabling required APIs..."
    gcloud services enable cloudfunctions.googleapis.com
    gcloud services enable cloudbuild.googleapis.com
    gcloud services enable cloudscheduler.googleapis.com
    gcloud services enable logging.googleapis.com
    gcloud services enable secretmanager.googleapis.com
    gcloud services enable bigquery.googleapis.com
    gcloud services enable bigquerystorage.googleapis.com
    gcloud services enable bigquerydatatransfer.googleapis.com
    
    print_success "Google Cloud project configured!"
}

# Function to set up BigQuery
setup_bigquery() {
    print_header "Step 2: Setting up BigQuery Infrastructure"
    
    if [ -f "./setup-bigquery.sh" ]; then
        chmod +x ./setup-bigquery.sh
        print_info "Running BigQuery setup script..."
        ./setup-bigquery.sh "$PROJECT_ID" "$DATASET_ID" "$BIGQUERY_LOCATION"
    else
        print_warning "setup-bigquery.sh not found in current directory"
        print_info "Creating BigQuery dataset manually..."
        
        bq mk --location="$BIGQUERY_LOCATION" \
            --description="Amazon PPC Optimization data" \
            --dataset \
            "$PROJECT_ID:$DATASET_ID" 2>/dev/null || print_warning "Dataset already exists"
    fi
    
    # Grant permissions to compute service account
    print_info "Granting BigQuery permissions to service account..."
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
    SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SERVICE_ACCOUNT}" \
        --role="roles/bigquery.dataEditor" --quiet
    
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SERVICE_ACCOUNT}" \
        --role="roles/bigquery.jobUser" --quiet
    
    print_success "BigQuery infrastructure set up!"
}

# Function to set up Secret Manager
setup_secrets() {
    print_header "Step 3: Setting up Secret Manager"
    
    print_info "Note: You'll need to provide values for secrets."
    print_warning "Secrets should be stored securely. Use environment variables or prompt for input."
    
    # Check if secrets already exist
    print_info "Checking existing secrets..."
    
    local secrets=(
        "amazon-client-id"
        "amazon-client-secret"
        "amazon-refresh-token"
        "amazon-profile-id"
        "dashboard-api-key"
        "dashboard-url"
    )
    
    for secret in "${secrets[@]}"; do
        if gcloud secrets describe "$secret" &>/dev/null; then
            print_success "Secret exists: $secret"
        else
            print_warning "Secret not found: $secret"
            print_info "To create this secret, run:"
            echo "    echo -n 'YOUR_VALUE' | gcloud secrets create $secret --data-file=-"
        fi
    done
    
    # Grant secret access to compute service account
    print_info "Granting secret access to service account..."
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
    SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    
    for secret in "${secrets[@]}"; do
        if gcloud secrets describe "$secret" &>/dev/null; then
            gcloud secrets add-iam-policy-binding "$secret" \
                --member="serviceAccount:${SA_EMAIL}" \
                --role="roles/secretmanager.secretAccessor" --quiet 2>/dev/null || true
        fi
    done
    
    print_success "Secret Manager configured!"
}

# Function to deploy Cloud Function
deploy_function() {
    print_header "Step 4: Deploying Cloud Function"
    
    print_info "Deploying $FUNCTION_NAME to region $REGION..."
    
    gcloud functions deploy "$FUNCTION_NAME" \
        --gen2 \
        --runtime=python311 \
        --region="$REGION" \
        --source=. \
        --entry-point=run_optimizer \
        --trigger-http \
        --no-allow-unauthenticated \
        --timeout=540s \
        --memory=512MB \
        --min-instances=0 \
        --max-instances=1 \
        --set-secrets='AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=amazon-profile-id:latest,DASHBOARD_API_KEY=dashboard-api-key:latest,DASHBOARD_URL=dashboard-url:latest' \
        --set-env-vars="GCP_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
    
    # Get function URL
    FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
        --region="$REGION" \
        --gen2 \
        --format='value(serviceConfig.uri)')
    
    print_success "Cloud Function deployed!"
    print_info "Function URL: $FUNCTION_URL"
    
    # Save URL to file for later use
    echo "$FUNCTION_URL" > .function_url
}

# Function to set up Cloud Scheduler
setup_scheduler() {
    print_header "Step 5: Setting up Cloud Scheduler"
    
    # Create service account for scheduler if it doesn't exist
    print_info "Creating scheduler service account..."
    gcloud iam service-accounts create ppc-scheduler \
        --display-name="PPC Optimizer Scheduler Service Account" 2>/dev/null || print_warning "Service account already exists"
    
    # Grant invoker permission
    print_info "Granting invoker permission to function..."
    gcloud functions add-iam-policy-binding "$FUNCTION_NAME" \
        --region="$REGION" \
        --member="serviceAccount:ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/cloudfunctions.invoker" --quiet
    
    # Get function URL
    FUNCTION_URL=$(cat .function_url 2>/dev/null || gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 --format='value(serviceConfig.uri)')
    
    # Create daily production job
    print_info "Creating daily production scheduler job..."
    gcloud scheduler jobs create http "${FUNCTION_NAME}-daily" \
        --location="$REGION" \
        --schedule="0 3 * * *" \
        --uri="${FUNCTION_URL}" \
        --http-method=POST \
        --time-zone="America/New_York" \
        --oidc-service-account-email="ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
        --oidc-token-audience="${FUNCTION_URL}" \
        --headers="Content-Type=application/json" \
        --message-body='{"dry_run": false}' 2>/dev/null || print_warning "Daily job already exists"
    
    # Create dry-run test job
    print_info "Creating dry-run scheduler job (every 4 hours)..."
    gcloud scheduler jobs create http "${FUNCTION_NAME}-dryrun" \
        --location="$REGION" \
        --schedule="0 */4 * * *" \
        --uri="${FUNCTION_URL}" \
        --http-method=POST \
        --time-zone="America/New_York" \
        --oidc-service-account-email="ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
        --oidc-token-audience="${FUNCTION_URL}" \
        --headers="Content-Type=application/json" \
        --message-body='{"dry_run": true}' 2>/dev/null || print_warning "Dry-run job already exists"
    
    print_success "Cloud Scheduler configured!"
}

# Function to verify deployment
verify_deployment() {
    print_header "Step 6: Verifying Deployment"
    
    # Get function URL
    FUNCTION_URL=$(cat .function_url 2>/dev/null || gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 --format='value(serviceConfig.uri)')
    
    print_info "Testing health check endpoint..."
    TOKEN=$(gcloud auth print-identity-token)
    
    HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer ${TOKEN}" "${FUNCTION_URL}?health=true" || echo "FAILED")
    HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
    BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)
    
    if [ "$HTTP_CODE" = "200" ]; then
        print_success "Health check passed!"
        print_info "Response: $BODY"
    else
        print_error "Health check failed! HTTP $HTTP_CODE"
        print_info "Response: $BODY"
    fi
    
    # Test connection verification
    print_info "Testing Amazon Ads API connection..."
    VERIFY_RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer ${TOKEN}" "${FUNCTION_URL}?verify_connection=true&verify_sample_size=3" || echo "FAILED")
    VERIFY_CODE=$(echo "$VERIFY_RESPONSE" | tail -n1)
    VERIFY_BODY=$(echo "$VERIFY_RESPONSE" | head -n-1)
    
    if [ "$VERIFY_CODE" = "200" ]; then
        print_success "Amazon Ads API connection verified!"
        print_info "Response: $VERIFY_BODY"
    else
        print_warning "Connection verification failed or not fully configured"
        print_info "HTTP $VERIFY_CODE: $VERIFY_BODY"
    fi
    
    # Check BigQuery tables
    print_info "Verifying BigQuery tables..."
    if bq ls "$PROJECT_ID:$DATASET_ID" &>/dev/null; then
        print_success "BigQuery dataset accessible"
        TABLE_COUNT=$(bq ls "$PROJECT_ID:$DATASET_ID" | grep -c "TABLE" || echo "0")
        print_info "Found $TABLE_COUNT tables in dataset"
    else
        print_warning "Could not access BigQuery dataset"
    fi
    
    # Check scheduler jobs
    print_info "Verifying Cloud Scheduler jobs..."
    JOB_COUNT=$(gcloud scheduler jobs list --location="$REGION" 2>/dev/null | grep -c "$FUNCTION_NAME" || echo "0")
    if [ "$JOB_COUNT" -gt 0 ]; then
        print_success "Found $JOB_COUNT scheduler jobs"
    else
        print_warning "No scheduler jobs found"
    fi
    
    print_success "Deployment verification complete!"
}

# Function to display summary
display_summary() {
    print_header "Deployment Summary"
    
    FUNCTION_URL=$(cat .function_url 2>/dev/null || gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 --format='value(serviceConfig.uri)' 2>/dev/null || echo "Not deployed")
    
    echo "Project ID:       $PROJECT_ID"
    echo "Region:           $REGION"
    echo "Function Name:    $FUNCTION_NAME"
    echo "Function URL:     $FUNCTION_URL"
    echo "BigQuery Dataset: $PROJECT_ID:$DATASET_ID"
    echo "BigQuery Location: $BIGQUERY_LOCATION"
    echo ""
    
    print_header "Next Steps"
    echo "1. Verify secrets are configured:"
    echo "   gcloud secrets list"
    echo ""
    echo "2. Test the function manually:"
    echo "   TOKEN=\$(gcloud auth print-identity-token)"
    echo "   curl -H \"Authorization: Bearer \$TOKEN\" \"$FUNCTION_URL?health=true\""
    echo ""
    echo "3. Trigger a dry-run optimization:"
    echo "   curl -X POST -H \"Authorization: Bearer \$TOKEN\" \\"
    echo "     -H \"Content-Type: application/json\" \\"
    echo "     -d '{\"dry_run\": true}' \\"
    echo "     \"$FUNCTION_URL\""
    echo ""
    echo "4. View logs:"
    echo "   gcloud functions logs read $FUNCTION_NAME --region=$REGION --limit=50"
    echo ""
    echo "5. Monitor scheduler jobs:"
    echo "   gcloud scheduler jobs list --location=$REGION"
    echo ""
    echo "6. Check dashboard:"
    echo "   https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app"
    echo ""
    
    print_success "Deployment completed successfully! 🎉"
}

# Main execution flow
main() {
    clear
    
    print_header "Amazon PPC Optimizer - Complete Deployment"
    print_info "Starting automated deployment process..."
    print_info "Project: $PROJECT_ID"
    print_info "Region: $REGION"
    echo ""
    
    # Confirm with user
    read -p "Continue with deployment? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Deployment cancelled by user"
        exit 0
    fi
    
    # Execute deployment steps
    check_prerequisites
    setup_gcp_project
    setup_bigquery
    setup_secrets
    deploy_function
    setup_scheduler
    verify_deployment
    display_summary
    
    # Cleanup temporary files
    rm -f .function_url
}

# Handle script arguments
case "${1:-all}" in
    check)
        check_prerequisites
        ;;
    gcp)
        setup_gcp_project
        ;;
    bigquery)
        setup_bigquery
        ;;
    secrets)
        setup_secrets
        ;;
    function)
        deploy_function
        ;;
    scheduler)
        setup_scheduler
        ;;
    verify)
        verify_deployment
        ;;
    all)
        main
        ;;
    *)
        echo "Usage: $0 {check|gcp|bigquery|secrets|function|scheduler|verify|all}"
        echo ""
        echo "Commands:"
        echo "  check     - Check prerequisites only"
        echo "  gcp       - Set up Google Cloud project"
        echo "  bigquery  - Set up BigQuery infrastructure"
        echo "  secrets   - Set up Secret Manager"
        echo "  function  - Deploy Cloud Function"
        echo "  scheduler - Set up Cloud Scheduler"
        echo "  verify    - Verify deployment"
        echo "  all       - Run complete deployment (default)"
        exit 1
        ;;
esac
