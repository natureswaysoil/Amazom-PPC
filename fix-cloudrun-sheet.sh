#!/bin/bash
#
# Quick fix script for Cloud Run Job Google Sheet access issues
# This script applies common fixes for the CSV_URL problem
#

set -e

# Configuration
REGION="us-east4"
JOB_NAME="natureswaysoil-video-job"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "Cloud Run Job - Google Sheet Access Fix"
echo "=========================================="
echo ""

# Function to extract sheet ID from URL
extract_sheet_id() {
    local url="$1"
    if [[ "$url" =~ /d/([a-zA-Z0-9_-]+) ]]; then
        echo "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

# Get current CSV_URL
echo -e "${BLUE}Fetching current configuration...${NC}"
CURRENT_URL=$(gcloud run jobs describe "$JOB_NAME" \
  --region="$REGION" \
  --format='json' | jq -r '.spec.template.spec.template.spec.containers[0].env[]? | select(.name=="CSV_URL") | .value' 2>/dev/null || echo "")

if [ -z "$CURRENT_URL" ]; then
    echo -e "${YELLOW}No CSV_URL currently set${NC}"
    echo ""
    echo "Please provide the Google Sheet URL:"
    echo "(Example: https://docs.google.com/spreadsheets/d/1ABC.../edit#gid=0)"
    read -p "URL: " INPUT_URL
    CURRENT_URL="$INPUT_URL"
fi

echo "Current URL: $CURRENT_URL"
echo ""

# Check if URL is already in correct format
if [[ "$CURRENT_URL" == *"/export?format=csv"* ]]; then
    echo -e "${GREEN}✓ URL is already in correct CSV export format${NC}"
    NEW_URL="$CURRENT_URL"
else
    # Extract sheet ID and convert to export format
    SHEET_ID=$(extract_sheet_id "$CURRENT_URL")
    
    if [ -z "$SHEET_ID" ]; then
        echo -e "${RED}✗ Could not extract sheet ID from URL${NC}"
        echo "Please enter the sheet ID manually:"
        read -p "Sheet ID: " SHEET_ID
    fi
    
    # Ask for GID (tab ID)
    echo ""
    echo "Which tab/sheet do you want to export?"
    echo "(Press Enter for default first tab, or enter gid number)"
    read -p "GID [0]: " GID
    GID=${GID:-0}
    
    NEW_URL="https://docs.google.com/spreadsheets/d/${SHEET_ID}/export?format=csv&gid=${GID}"
    
    echo ""
    echo -e "${BLUE}Converted URL:${NC}"
    echo "Old: $CURRENT_URL"
    echo "New: $NEW_URL"
fi

echo ""
echo -e "${BLUE}Testing URL accessibility...${NC}"

# Test the URL
HTTP_CODE=$(curl -s -o /tmp/sheet_test.txt -w "%{http_code}" -L "$NEW_URL" --max-time 10 || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    if head -n 5 /tmp/sheet_test.txt | grep -q "<!DOCTYPE html>\|<html"; then
        echo -e "${RED}✗ URL returns HTML (error page) instead of CSV${NC}"
        echo ""
        echo "Response preview:"
        head -n 10 /tmp/sheet_test.txt
        echo ""
        echo -e "${YELLOW}Possible issues:${NC}"
        echo "1. Sheet doesn't exist at this URL"
        echo "2. Sheet is private and needs permission"
        echo "3. GID (tab ID) is incorrect"
        echo ""
        read -p "Do you want to continue anyway? (y/N): " CONTINUE
        if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
            echo "Aborted."
            rm -f /tmp/sheet_test.txt
            exit 1
        fi
    else
        echo -e "${GREEN}✓ URL is accessible and returns CSV data${NC}"
        echo ""
        echo "Preview:"
        head -n 3 /tmp/sheet_test.txt
        echo "..."
    fi
elif [ "$HTTP_CODE" = "403" ]; then
    echo -e "${RED}✗ HTTP 403 - Permission denied${NC}"
    echo ""
    echo "The sheet is private. You need to:"
    echo "1. Open the Google Sheet"
    echo "2. Click 'Share'"
    echo "3. Either:"
    echo "   a) Make it public: 'Anyone with the link' can view"
    echo "   b) Share with service account (see below)"
    echo ""
    
    SERVICE_ACCOUNT=$(gcloud run jobs describe "$JOB_NAME" \
      --region="$REGION" \
      --format='value(spec.template.spec.serviceAccountName)' || echo "")
    
    if [ -z "$SERVICE_ACCOUNT" ]; then
        PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project 2>/dev/null) \
          --format='value(projectNumber)')
        SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    fi
    
    echo "Service account to share with:"
    echo "  $SERVICE_ACCOUNT"
    echo ""
    read -p "Have you fixed the permissions? (y/N): " FIXED
    if [[ ! "$FIXED" =~ ^[Yy]$ ]]; then
        echo "Please fix permissions and run this script again."
        rm -f /tmp/sheet_test.txt
        exit 1
    fi
else
    echo -e "${RED}✗ Cannot access URL (HTTP $HTTP_CODE)${NC}"
    echo ""
    read -p "Do you want to continue anyway? (y/N): " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        rm -f /tmp/sheet_test.txt
        exit 1
    fi
fi

rm -f /tmp/sheet_test.txt
echo ""

# Apply the fix
echo -e "${BLUE}Updating Cloud Run Job...${NC}"
echo ""

gcloud run jobs update "$JOB_NAME" \
  --region="$REGION" \
  --set-env-vars "CSV_URL=$NEW_URL"

echo ""
echo -e "${GREEN}✓ Successfully updated CSV_URL${NC}"
echo ""

# Optional: Update timeout
echo "Current task timeout: $(gcloud run jobs describe "$JOB_NAME" --region="$REGION" --format='value(spec.template.spec.template.spec.timeoutSeconds)' || echo 600)s"
echo ""
read -p "Do you want to change the timeout? (y/N): " CHANGE_TIMEOUT

if [[ "$CHANGE_TIMEOUT" =~ ^[Yy]$ ]]; then
    read -p "Enter new timeout in seconds [1800]: " NEW_TIMEOUT
    NEW_TIMEOUT=${NEW_TIMEOUT:-1800}
    
    gcloud run jobs update "$JOB_NAME" \
      --region="$REGION" \
      --task-timeout="${NEW_TIMEOUT}s"
    
    echo -e "${GREEN}✓ Timeout updated to ${NEW_TIMEOUT}s${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}FIX APPLIED${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test the job:"
echo "   gcloud run jobs execute $JOB_NAME --region=$REGION --wait"
echo ""
echo "2. Monitor logs:"
echo "   gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME' --limit=50"
echo ""
echo "3. If issues persist, run diagnostics:"
echo "   ./diagnose-cloudrun-job.sh"
echo ""
