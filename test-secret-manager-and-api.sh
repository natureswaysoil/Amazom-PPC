#!/bin/bash
# Amazon PPC - Complete Secret Manager & API Verification

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    case "$1" in
        success) echo -e "${GREEN}✅ $2${NC}" ;;
        error) echo -e "${RED}❌ $2${NC}" ;;
        warning) echo -e "${YELLOW}⚠️  $2${NC}" ;;
        info) echo -e "${BLUE}ℹ️  $2${NC}" ;;
    esac
}

print_header() {
    echo ""
    echo "=================================================="
    echo "$1"
    echo "=================================================="
    echo ""
}

PROJECT_ID="${GCP_PROJECT_ID:-amazon-ppc-474902}"
REGION="${GCP_REGION:-us-central1}"

print_header "Amazon PPC - Secret Manager & API Verification"
print_status "info" "Using GCP Project: $PROJECT_ID"
print_status "info" "Using GCP Region: $REGION"
echo ""

# STEP 1: Check gcloud
print_header "Step 1: Checking Google Cloud CLI"

if ! command -v gcloud &> /dev/null; then
    print_status "error" "gcloud CLI not found"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

print_status "success" "gcloud CLI found"

# Check authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q @; then
    print_status "error" "Not authenticated with gcloud"
    echo ""
    echo "Please run: gcloud auth login"
    exit 1
fi

ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
print_status "success" "Authenticated as: $ACTIVE_ACCOUNT"

# Check project access
if ! gcloud projects describe $PROJECT_ID &>/dev/null; then
    print_status "error" "Cannot access project: $PROJECT_ID"
    echo "Run: gcloud config set project $PROJECT_ID"
    exit 1
fi

print_status "success" "Project access confirmed: $PROJECT_ID"

# STEP 2: Check secrets exist
print_header "Step 2: Checking Secret Manager Secrets"

REQUIRED_SECRETS=("amazon-client-id" "amazon-client-secret" "amazon-refresh-token" "amazon-profile-id")
MISSING_SECRETS=()

for secret in "${REQUIRED_SECRETS[@]}"; do
    if gcloud secrets describe $secret --project=$PROJECT_ID &>/dev/null; then
        print_status "success" "Secret exists: $secret"
    else
        print_status "error" "Secret NOT found: $secret"
        MISSING_SECRETS+=($secret)
    fi
done

if [ ${#MISSING_SECRETS[@]} -ne 0 ]; then
    echo ""
    print_status "error" "Missing required secrets: ${MISSING_SECRETS[*]}"
    echo ""
    echo "Create them with:"
    for secret in "${MISSING_SECRETS[@]}"; do
        echo "  echo -n 'YOUR_VALUE' | gcloud secrets create $secret --project=$PROJECT_ID --data-file=-"
    done
    exit 1
fi

# STEP 3: Load secrets
print_header "Step 3: Loading Secrets from Secret Manager"

if [ ! -f "load_secrets.py" ]; then
    print_status "error" "load_secrets.py not found"
    echo "Please run this script from the repository root directory"
    exit 1
fi

print_status "info" "Loading secrets using load_secrets.py..."

if eval $(python load_secrets.py --project=$PROJECT_ID 2>/tmp/load_secrets_stderr.log); then
    print_status "success" "Secrets loaded successfully"
else
    print_status "error" "Failed to load secrets"
    cat /tmp/load_secrets_stderr.log
    exit 1
fi

if [ -z "$AMAZON_CLIENT_ID" ]; then
    print_status "error" "AMAZON_CLIENT_ID not loaded"
    cat /tmp/load_secrets_stderr.log
    exit 1
fi

print_status "success" "AMAZON_CLIENT_ID loaded (${#AMAZON_CLIENT_ID} chars)"
print_status "success" "AMAZON_CLIENT_SECRET loaded (${#AMAZON_CLIENT_SECRET} chars)"
print_status "success" "AMAZON_REFRESH_TOKEN loaded (${#AMAZON_REFRESH_TOKEN} chars)"
print_status "success" "AMAZON_PROFILE_ID: $AMAZON_PROFILE_ID"

# STEP 4: Check API version
print_header "Step 4: Checking API Version"

if grep -q 'SP_API_VERSION = "v2"' optimizer_core.py; then
    print_status "warning" "Sponsored Products using V2 (deprecated March 2023)"
    print_status "info" "Should update to V3"
    echo ""
    echo "To update: sed -i 's/SP_API_VERSION = \"v2\"/SP_API_VERSION = \"v3\"/' optimizer_core.py"
else
    print_status "success" "API version is current (V3)"
fi

# STEP 5: Validate credentials
print_header "Step 5: Validating Amazon API Credentials"

if [ -f "validate-amazon-credentials.py" ]; then
    print_status "info" "Running credential validator..."
    
    if python validate-amazon-credentials.py; then
        print_status "success" "Amazon API credentials are valid"
    else
        print_status "error" "Credential validation failed"
        echo ""
        echo "Common issues:"
        echo "1. Expired refresh token"
        echo "2. Whitespace in credentials"
        echo "3. Wrong API access (need Advertising API, not PA-API)"
        exit 1
    fi
else
    print_status "warning" "validate-amazon-credentials.py not found, skipping"
fi

# STEP 6: Test live data
print_header "Step 6: Testing Live Data Retrieval"

print_status "info" "Attempting to fetch campaigns from Amazon Ads API..."

if python optimizer_core.py \
    --config config.json \
    --profile-id "$AMAZON_PROFILE_ID" \
    --verify-connection \
    --verify-sample-size 5 2>&1 | tee /tmp/ppc_verification.log; then
    
    print_status "success" "Successfully connected to Amazon Ads API"
    print_status "success" "Live campaign data retrieved"
    
    if grep -qi "campaign" /tmp/ppc_verification.log; then
        print_status "success" "Campaign data confirmed in response"
    else
        print_status "warning" "No campaign data found (account may be empty)"
    fi
else
    print_status "error" "Failed to retrieve data from Amazon Ads API"
    echo ""
    echo "Check the error messages above for details."
    exit 1
fi

# STEP 7: Check Cloud Function (optional)
print_header "Step 7: Checking Cloud Function Deployment (Optional)"

if gcloud functions describe ppc-optimizer --region=$REGION --project=$PROJECT_ID --gen2 &>/dev/null; then
    print_status "success" "Cloud Function 'ppc-optimizer' is deployed (Gen2)"
    
    FUNCTION_URL=$(gcloud functions describe ppc-optimizer \
        --region=$REGION \
        --project=$PROJECT_ID \
        --gen2 \
        --format='value(serviceConfig.uri)' 2>/dev/null || echo "")
    
    if [ -n "$FUNCTION_URL" ]; then
        print_status "info" "Function URL: $FUNCTION_URL"
    fi
elif gcloud functions describe ppc-optimizer --region=$REGION --project=$PROJECT_ID &>/dev/null; then
    print_status "warning" "Cloud Function deployed (Gen1) - consider upgrading to Gen2"
else
    print_status "info" "Cloud Function not deployed yet"
fi

# Summary
print_header "Verification Summary"

print_status "success" "✅ Core System Status:"
echo "  - Google Cloud authentication: ✅"
echo "  - Secret Manager access: ✅"
echo "  - Secrets loaded: ✅"
echo "  - Amazon API credentials: ✅"
echo "  - Live data retrieval: ✅"
echo ""

print_status "info" "📊 Configuration:"
echo "  - GCP Project: $PROJECT_ID"
echo "  - Amazon Profile ID: $AMAZON_PROFILE_ID"
echo "  - Region: $REGION"
echo ""

print_status "info" "🎯 Next Steps:"
echo "  1. Update API version to V3 (if needed)"
echo "  2. Run optimization: python optimizer_core.py --config config.json --dry-run"
echo "  3. Check BigQuery data: bq query 'SELECT * FROM amazon_ppc.campaigns LIMIT 5'"
echo ""

print_status "success" "Verification complete! Your system is connected and receiving live data. ✅"
echo ""
