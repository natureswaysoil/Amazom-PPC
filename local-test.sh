#!/bin/bash
# Local Testing Script for Amazon PPC Optimizer
# This script helps you test the optimizer locally before deploying

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if .env file exists
check_env_file() {
    print_header "Checking Environment Configuration"
    
    if [ -f ".env" ]; then
        print_success "Found .env file"
        export $(cat .env | grep -v '^#' | xargs)
    else
        print_warning ".env file not found"
        print_info "Creating .env from template..."
        
        if [ -f ".env.template" ]; then
            cp .env.template .env
            print_success "Created .env file from template"
            print_warning "Please edit .env file and add your credentials"
            print_info "Then run this script again"
            exit 0
        else
            print_error ".env.template not found"
            exit 1
        fi
    fi
    
    # Check required environment variables
    local missing_vars=()
    
    [ -z "$AMAZON_CLIENT_ID" ] && missing_vars+=("AMAZON_CLIENT_ID")
    [ -z "$AMAZON_CLIENT_SECRET" ] && missing_vars+=("AMAZON_CLIENT_SECRET")
    [ -z "$AMAZON_REFRESH_TOKEN" ] && missing_vars+=("AMAZON_REFRESH_TOKEN")
    [ -z "$AMAZON_PROFILE_ID" ] && missing_vars+=("AMAZON_PROFILE_ID")
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        print_info "Please edit .env file and add these values"
        exit 1
    fi
    
    print_success "All required environment variables set"
}

# Check Python and dependencies
check_dependencies() {
    print_header "Checking Dependencies"
    
    # Check Python version
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python 3 installed (version $PYTHON_VERSION)"
    else
        print_error "Python 3 not found. Please install Python 3.11 or later."
        exit 1
    fi
    
    # Check if virtual environment exists
    if [ -d "venv" ]; then
        print_info "Virtual environment found"
        source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
        print_success "Activated virtual environment"
    else
        print_warning "No virtual environment found"
        print_info "Creating virtual environment..."
        python3 -m venv venv
        source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
        print_success "Created and activated virtual environment"
    fi
    
    # Check if requirements are installed
    print_info "Checking Python packages..."
    if pip freeze | grep -q "functions-framework"; then
        print_success "Dependencies already installed"
    else
        print_info "Installing dependencies from requirements.txt..."
        pip install -q -r requirements.txt
        print_success "Dependencies installed"
    fi
}

# Test connection to Amazon Ads API
test_connection() {
    print_header "Testing Amazon Ads API Connection"
    
    print_info "Running connection verification..."
    python optimizer_core.py \
        --config sample_config.yaml \
        --profile-id "$AMAZON_PROFILE_ID" \
        --verify-connection \
        --verify-sample-size=3
    
    if [ $? -eq 0 ]; then
        print_success "Connection test passed!"
    else
        print_error "Connection test failed"
        exit 1
    fi
}

# Run dry-run optimization
run_dry_run() {
    print_header "Running Dry-Run Optimization"
    
    print_info "This will analyze your campaigns without making changes"
    print_warning "This may take a few minutes..."
    
    export PPC_DRY_RUN=true
    python main.py
    
    if [ $? -eq 0 ]; then
        print_success "Dry-run completed successfully!"
    else
        print_error "Dry-run failed"
        exit 1
    fi
}

# Run specific feature test
test_feature() {
    local feature=$1
    print_header "Testing Feature: $feature"
    
    export PPC_DRY_RUN=true
    export PPC_FEATURES="$feature"
    
    print_info "Running $feature optimization..."
    python main.py
    
    if [ $? -eq 0 ]; then
        print_success "$feature test completed!"
    else
        print_error "$feature test failed"
        exit 1
    fi
}

# Display menu
show_menu() {
    clear
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Amazon PPC Optimizer - Local Testing${NC}"
    echo -e "${BLUE}========================================${NC}\n"
    
    echo "Select a test to run:"
    echo ""
    echo "  1) Check environment and dependencies"
    echo "  2) Test Amazon Ads API connection"
    echo "  3) Run full dry-run optimization"
    echo "  4) Test bid optimization only"
    echo "  5) Test dayparting only"
    echo "  6) Test campaign management only"
    echo "  7) Test keyword discovery only"
    echo "  8) Test negative keywords only"
    echo "  9) Run all tests"
    echo "  0) Exit"
    echo ""
    read -p "Enter choice [0-9]: " choice
    
    case $choice in
        1)
            check_env_file
            check_dependencies
            ;;
        2)
            check_env_file
            check_dependencies
            test_connection
            ;;
        3)
            check_env_file
            check_dependencies
            run_dry_run
            ;;
        4)
            check_env_file
            check_dependencies
            test_feature "bid_optimization"
            ;;
        5)
            check_env_file
            check_dependencies
            test_feature "dayparting"
            ;;
        6)
            check_env_file
            check_dependencies
            test_feature "campaign_management"
            ;;
        7)
            check_env_file
            check_dependencies
            test_feature "keyword_discovery"
            ;;
        8)
            check_env_file
            check_dependencies
            test_feature "negative_keywords"
            ;;
        9)
            check_env_file
            check_dependencies
            test_connection
            run_dry_run
            print_success "All tests completed!"
            ;;
        0)
            print_info "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            sleep 2
            show_menu
            ;;
    esac
}

# Main execution
main() {
    # Check if running with arguments
    if [ $# -eq 0 ]; then
        # Interactive mode
        show_menu
    else
        # Command line mode
        case "$1" in
            check)
                check_env_file
                check_dependencies
                ;;
            connection)
                check_env_file
                check_dependencies
                test_connection
                ;;
            dry-run)
                check_env_file
                check_dependencies
                run_dry_run
                ;;
            feature)
                if [ -z "$2" ]; then
                    print_error "Please specify a feature name"
                    echo "Available features: bid_optimization, dayparting, campaign_management, keyword_discovery, negative_keywords"
                    exit 1
                fi
                check_env_file
                check_dependencies
                test_feature "$2"
                ;;
            all)
                check_env_file
                check_dependencies
                test_connection
                run_dry_run
                ;;
            *)
                echo "Usage: $0 {check|connection|dry-run|feature <name>|all}"
                echo ""
                echo "Commands:"
                echo "  check      - Check environment and dependencies"
                echo "  connection - Test Amazon Ads API connection"
                echo "  dry-run    - Run full dry-run optimization"
                echo "  feature    - Test specific feature (provide feature name)"
                echo "  all        - Run all tests"
                echo ""
                echo "Run without arguments for interactive menu"
                exit 1
                ;;
        esac
    fi
    
    echo ""
    print_success "Testing complete! 🎉"
    echo ""
}

# Run main function
main "$@"
