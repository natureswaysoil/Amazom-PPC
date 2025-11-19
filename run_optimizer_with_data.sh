#!/bin/bash
#
# run_optimizer_with_data.sh
# 
# Automated script to load credentials from Google Secret Manager,
# run the Amazon PPC optimizer, and populate BigQuery with live data.
#
# Usage:
#   ./run_optimizer_with_data.sh [options]
#
# Options:
#   --dry-run           Run optimizer in dry-run mode (no changes to campaigns)
#   --verify-only       Only verify credentials, don't run optimizer
#   --config FILE       Specify custom config file (default: config.json)
#   --start-dashboard   Start dashboard after optimizer completes
#   -h, --help          Show this help message
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DRY_RUN=""
VERIFY_ONLY=false
CONFIG_FILE="config.json"
START_DASHBOARD=false

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓ ${NC}$1"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${NC}$1"
}

print_error() {
    echo -e "${RED}✗ ${NC}$1"
}

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --verify-only)
            VERIFY_ONLY=true
            shift
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --start-dashboard)
            START_DASHBOARD=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --dry-run           Run optimizer in dry-run mode (no changes to campaigns)"
            echo "  --verify-only       Only verify credentials, don't run optimizer"
            echo "  --config FILE       Specify custom config file (default: config.json)"
            echo "  --start-dashboard   Start dashboard after optimizer completes"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Main execution
print_header "🚀 Amazon PPC Optimizer with Live Data"

# Step 1: Verify load_secrets.py exists
print_info "Checking for load_secrets.py script..."
if [ ! -f "load_secrets.py" ]; then
    print_error "load_secrets.py not found in current directory"
    echo "Please run this script from the repository root directory"
    exit 1
fi
print_success "Found load_secrets.py"

# Step 2: Load credentials from Google Secret Manager
print_header "📦 Loading Credentials from Secret Manager"
print_info "Fetching credentials from Google Secret Manager..."

# First verify credentials are accessible
if ! python load_secrets.py --verify; then
    print_error "Failed to verify credentials in Secret Manager"
    echo ""
    echo "Common issues:"
    echo "  1. Google Cloud authentication not configured"
    echo "  2. Missing required secrets in Secret Manager"
    echo "  3. Insufficient permissions to access secrets"
    echo ""
    echo "Run 'python load_secrets.py --verify' for detailed diagnostics"
    exit 1
fi

print_success "Credentials verified successfully"

# Load credentials into environment
print_info "Loading credentials into environment..."
eval $(python load_secrets.py)

if [ $? -ne 0 ]; then
    print_error "Failed to load credentials"
    exit 1
fi

# Verify key environment variables are set
if [ -z "$AMAZON_CLIENT_ID" ] || [ -z "$AMAZON_REFRESH_TOKEN" ]; then
    print_error "Required Amazon API credentials not loaded"
    echo "Expected: AMAZON_CLIENT_ID, AMAZON_REFRESH_TOKEN"
    exit 1
fi

print_success "Credentials loaded successfully"
echo "  • Amazon Client ID: ${AMAZON_CLIENT_ID:0:20}..."
echo "  • Profile ID: ${AMAZON_PROFILE_ID:-<not set>}"
echo "  • GCP Project: ${GCP_PROJECT_ID:-<not set>}"

# Exit if verify-only mode
if [ "$VERIFY_ONLY" = true ]; then
    print_success "Verification complete. Exiting (--verify-only mode)"
    exit 0
fi

# Step 3: Verify config file exists
print_header "⚙️  Configuration"
print_info "Checking configuration file..."
if [ ! -f "$CONFIG_FILE" ]; then
    print_warning "Config file '$CONFIG_FILE' not found"
    print_info "Will use default configuration or environment variables"
else
    print_success "Found config file: $CONFIG_FILE"
fi

# Step 4: Run the optimizer
print_header "🔄 Running Amazon PPC Optimizer"

if [ -n "$DRY_RUN" ]; then
    print_warning "Running in DRY-RUN mode (no changes will be made)"
fi

print_info "Starting optimizer..."
echo ""

# Build optimizer command
OPTIMIZER_CMD="python optimizer_core.py"

if [ -f "$CONFIG_FILE" ]; then
    OPTIMIZER_CMD="$OPTIMIZER_CMD --config $CONFIG_FILE"
fi

if [ -n "$DRY_RUN" ]; then
    OPTIMIZER_CMD="$OPTIMIZER_CMD $DRY_RUN"
fi

# Run the optimizer
if $OPTIMIZER_CMD; then
    echo ""
    print_success "Optimizer completed successfully"
    print_info "Data has been written to BigQuery tables"
else
    echo ""
    print_error "Optimizer failed with error code $?"
    exit 1
fi

# Step 5: Show next steps
print_header "✅ Complete"

echo "Live data is now available in BigQuery tables:"
echo "  • optimization_results"
echo "  • campaign_details"
echo "  • optimization_progress"
echo "  • optimization_errors"
echo "  • optimizer_run_events"
echo ""

# Step 6: Optionally start dashboard
if [ "$START_DASHBOARD" = true ]; then
    print_info "Starting dashboard..."
    echo ""
    cd dashboard
    python app.py
else
    print_info "To view the data in the dashboard, run:"
    echo ""
    echo "    cd dashboard && python app.py"
    echo ""
    print_info "Or run this script with --start-dashboard to auto-launch"
fi

print_success "Done! 🎉"
