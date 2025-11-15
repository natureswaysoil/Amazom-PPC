#!/usr/bin/env bash
# Check and fix Secret Manager secrets for Amazon API credentials
# This script helps identify whitespace corruption in secrets

set -euo pipefail

PROJECT_ID="${1:-amazon-ppc-474902}"

echo "======================================================================"
echo "Amazon API Secret Manager Validator"
echo "======================================================================"
echo ""

check_secret() {
    local secret_name="$1"
    local display_length="${2:-full}"
    
    echo "Checking secret: ${secret_name}"
    
    if ! gcloud secrets versions access latest --secret="${secret_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        echo "  ❌ Secret '${secret_name}' not found or not accessible"
        return 1
    fi
    
    # Get the secret value
    secret_value=$(gcloud secrets versions access latest --secret="${secret_name}" --project="${PROJECT_ID}" 2>/dev/null)
    
    # Check length
    secret_len=${#secret_value}
    echo "  Length: ${secret_len} characters"
    
    # Check for whitespace issues
    has_spaces=false
    has_newlines=false
    has_tabs=false
    has_carriage_return=false
    
    if [[ "${secret_value}" =~ [[:space:]] ]]; then
        if [[ "${secret_value}" =~ " " ]]; then
            has_spaces=true
            echo "  ⚠️  WARNING: Contains SPACES"
        fi
        if [[ "${secret_value}" =~ $'\n' ]]; then
            has_newlines=true
            echo "  ⚠️  WARNING: Contains NEWLINES"
        fi
        if [[ "${secret_value}" =~ $'\t' ]]; then
            has_tabs=true
            echo "  ⚠️  WARNING: Contains TABS"
        fi
        if [[ "${secret_value}" =~ $'\r' ]]; then
            has_carriage_return=true
            echo "  ⚠️  WARNING: Contains CARRIAGE RETURNS"
        fi
    else
        echo "  ✓ No whitespace detected"
    fi
    
    # Show preview
    if [[ "${display_length}" == "full" ]]; then
        echo "  First 20 chars: '${secret_value:0:20}'"
        if [[ ${secret_len} -gt 20 ]]; then
            echo "  Last 20 chars: '${secret_value: -20}'"
        fi
    else
        echo "  First 12 chars: '${secret_value:0:12}...'"
    fi
    
    # Hexdump first/last 10 bytes to show hidden characters
    echo "  Hex dump (first 40 chars):"
    echo -n "    "
    echo -n "${secret_value:0:40}" | xxd -p | fold -w 64 | head -1
    
    echo ""
    
    # Return status based on whitespace issues
    if ${has_spaces} || ${has_newlines} || ${has_tabs} || ${has_carriage_return}; then
        return 1
    else
        return 0
    fi
}

echo "Checking all Amazon API secrets..."
echo ""

all_good=true

# Check each secret
check_secret "AMAZON_CLIENT_ID" "short" || all_good=false
check_secret "AMAZON_CLIENT_SECRET" "short" || all_good=false
check_secret "AMAZON_REFRESH_TOKEN" "full" || all_good=false
check_secret "AMAZON_PROFILE_ID" "full" || all_good=false

echo "======================================================================"
if ${all_good}; then
    echo "✅ All secrets look good (no whitespace corruption detected)"
else
    echo "❌ Found whitespace corruption in one or more secrets!"
    echo ""
    echo "To fix corrupted secrets, use one of these methods:"
    echo ""
    echo "Method 1: Create new version from file (recommended)"
    echo "  echo -n 'YOUR_SECRET_VALUE' > /tmp/secret.txt"
    echo "  gcloud secrets versions add SECRET_NAME --data-file=/tmp/secret.txt --project=${PROJECT_ID}"
    echo "  rm /tmp/secret.txt"
    echo ""
    echo "Method 2: Use stdin (careful with trailing newlines)"
    echo "  echo -n 'YOUR_SECRET_VALUE' | gcloud secrets versions add SECRET_NAME --data-file=- --project=${PROJECT_ID}"
    echo ""
    echo "After fixing, redeploy the function:"
    echo "  ./deploy-with-service-account.sh"
fi
echo "======================================================================"
