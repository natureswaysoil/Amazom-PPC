#!/bin/bash
#
# Diagnostic script for Cloud Run Job Google Sheet Access Issues
# This script helps diagnose the natureswaysoil-video-job timeout problem
#

set -e

# Configuration
REGION="us-east4"
JOB_NAME="natureswaysoil-video-job"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Cloud Run Job Diagnostics"
echo "=========================================="
echo "Job: $JOB_NAME"
echo "Region: $REGION"
echo "=========================================="
echo ""

# Check if job exists
echo -e "${BLUE}Checking if Cloud Run Job exists...${NC}"
if ! gcloud run jobs describe "$JOB_NAME" --region="$REGION" &>/dev/null; then
    echo -e "${RED}✗ Job '$JOB_NAME' not found in region '$REGION'${NC}"
    echo ""
    echo "Available Cloud Run Jobs:"
    gcloud run jobs list --region="$REGION"
    exit 1
fi
echo -e "${GREEN}✓ Job found${NC}"
echo ""

# Get service account
echo -e "${BLUE}Service Account Information:${NC}"
SERVICE_ACCOUNT=$(gcloud run jobs describe "$JOB_NAME" \
  --region="$REGION" \
  --format='value(spec.template.spec.serviceAccountName)')

if [ -z "$SERVICE_ACCOUNT" ]; then
    PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project 2>/dev/null) \
      --format='value(projectNumber)')
    SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    echo -e "${YELLOW}Using default service account${NC}"
fi

echo "Service Account: $SERVICE_ACCOUNT"
echo ""

# Get environment variables
echo -e "${BLUE}Environment Variables:${NC}"
ENV_VARS=$(gcloud run jobs describe "$JOB_NAME" \
  --region="$REGION" \
  --format='json' | jq -r '.spec.template.spec.template.spec.containers[0].env[]? | "\(.name)=\(.value)"' 2>/dev/null)

if [ -z "$ENV_VARS" ]; then
    echo -e "${RED}✗ No environment variables found${NC}"
    CSV_URL=""
else
    echo "$ENV_VARS"
    CSV_URL=$(echo "$ENV_VARS" | grep "^CSV_URL=" | cut -d'=' -f2- || echo "")
fi
echo ""

# Check CSV_URL
if [ -z "$CSV_URL" ]; then
    echo -e "${RED}✗ CSV_URL environment variable NOT SET${NC}"
    echo "This is likely why the job is failing!"
    echo ""
    echo "To fix, run:"
    echo "  gcloud run jobs update $JOB_NAME \\"
    echo "    --region=$REGION \\"
    echo '    --set-env-vars CSV_URL="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0"'
    echo ""
else
    echo -e "${GREEN}✓ CSV_URL is set${NC}"
    echo "URL: $CSV_URL"
    echo ""
    
    # Validate URL format
    echo -e "${BLUE}Validating CSV_URL format...${NC}"
    if [[ "$CSV_URL" == *"/export?format=csv"* ]]; then
        echo -e "${GREEN}✓ URL appears to be in correct CSV export format${NC}"
    elif [[ "$CSV_URL" == *"/edit"* ]] || [[ "$CSV_URL" == *"docs.google.com/spreadsheets"* ]]; then
        echo -e "${RED}✗ URL appears to be a regular Google Sheets URL, not CSV export format${NC}"
        echo ""
        echo "Current URL: $CSV_URL"
        echo ""
        # Try to extract sheet ID
        if [[ "$CSV_URL" =~ /d/([a-zA-Z0-9_-]+) ]]; then
            SHEET_ID="${BASH_REMATCH[1]}"
            echo "Detected Sheet ID: $SHEET_ID"
            echo ""
            echo "Correct format should be:"
            echo "  https://docs.google.com/spreadsheets/d/$SHEET_ID/export?format=csv&gid=0"
            echo ""
            echo "To fix, run:"
            echo "  gcloud run jobs update $JOB_NAME \\"
            echo "    --region=$REGION \\"
            echo "    --set-env-vars CSV_URL=\"https://docs.google.com/spreadsheets/d/$SHEET_ID/export?format=csv&gid=0\""
        fi
    else
        echo -e "${YELLOW}⚠ URL format couldn't be validated${NC}"
    fi
    echo ""
    
    # Test URL accessibility
    echo -e "${BLUE}Testing URL accessibility...${NC}"
    HTTP_CODE=$(curl -s -o /tmp/sheet_test.txt -w "%{http_code}" -L "$CSV_URL" --max-time 10 || echo "000")
    
    if [ "$HTTP_CODE" = "200" ]; then
        # Check if response is HTML (error page) or CSV
        if head -n 5 /tmp/sheet_test.txt | grep -q "<!DOCTYPE html>\|<html"; then
            echo -e "${RED}✗ HTTP 200 but received HTML instead of CSV${NC}"
            echo ""
            echo "Response preview:"
            head -n 10 /tmp/sheet_test.txt
            echo ""
            echo -e "${YELLOW}This indicates:${NC}"
            echo "  - The URL might be incorrect"
            echo "  - The sheet might not exist"
            echo "  - Permissions might be blocking access"
        else
            echo -e "${GREEN}✓ URL is accessible and returns CSV data${NC}"
            echo ""
            echo "Preview of CSV data:"
            head -n 3 /tmp/sheet_test.txt
            echo "..."
        fi
    elif [ "$HTTP_CODE" = "400" ]; then
        echo -e "${RED}✗ HTTP 400 - Bad Request${NC}"
        echo "This typically means the URL is incorrect or malformed"
    elif [ "$HTTP_CODE" = "403" ]; then
        echo -e "${RED}✗ HTTP 403 - Forbidden${NC}"
        echo "The service account ($SERVICE_ACCOUNT) doesn't have access to this sheet"
        echo ""
        echo "To fix:"
        echo "1. Open the Google Sheet"
        echo "2. Click 'Share' button"
        echo "3. Add: $SERVICE_ACCOUNT"
        echo "4. Set permission to 'Viewer'"
    elif [ "$HTTP_CODE" = "404" ]; then
        echo -e "${RED}✗ HTTP 404 - Not Found${NC}"
        echo "The sheet doesn't exist at this URL"
    else
        echo -e "${RED}✗ Failed to access URL (HTTP $HTTP_CODE)${NC}"
    fi
    rm -f /tmp/sheet_test.txt
    echo ""
fi

# Check timeout settings
echo -e "${BLUE}Timeout Configuration:${NC}"
TASK_TIMEOUT=$(gcloud run jobs describe "$JOB_NAME" \
  --region="$REGION" \
  --format='value(spec.template.spec.template.spec.timeoutSeconds)' 2>/dev/null || echo "600")

echo "Task Timeout: ${TASK_TIMEOUT}s"

if [ "$TASK_TIMEOUT" = "600" ]; then
    echo -e "${YELLOW}⚠ Using default 600s timeout${NC}"
    echo "If your job legitimately needs more time, increase with:"
    echo "  gcloud run jobs update $JOB_NAME --region=$REGION --task-timeout=1800s"
fi
echo ""

# Check recent logs for errors
echo -e "${BLUE}Recent Error Logs:${NC}"
echo "Checking last 20 log entries..."
echo ""

LOGS=$(gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME AND severity>=ERROR" \
  --limit=20 \
  --format='table(timestamp,severity,textPayload)' 2>/dev/null || echo "")

if [ -z "$LOGS" ]; then
    echo -e "${GREEN}✓ No recent error logs found${NC}"
else
    echo "$LOGS"
fi
echo ""

# Check for timeout logs
echo -e "${BLUE}Recent Timeout Logs:${NC}"
TIMEOUT_LOGS=$(gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME AND textPayload=~\"timeout\"" \
  --limit=5 \
  --format='value(textPayload)' 2>/dev/null || echo "")

if [ -z "$TIMEOUT_LOGS" ]; then
    echo -e "${GREEN}✓ No recent timeout logs found${NC}"
else
    echo -e "${YELLOW}Found timeout messages:${NC}"
    echo "$TIMEOUT_LOGS"
fi
echo ""

# Check for "Page Not Found" logs
echo -e "${BLUE}Checking for 'Page Not Found' errors:${NC}"
PAGE_NOT_FOUND=$(gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME AND textPayload=~\"Page Not Found|404\"" \
  --limit=5 \
  --format='value(textPayload)' 2>/dev/null || echo "")

if [ -z "$PAGE_NOT_FOUND" ]; then
    echo -e "${GREEN}✓ No 'Page Not Found' errors found${NC}"
else
    echo -e "${RED}✗ Found 'Page Not Found' errors:${NC}"
    echo "$PAGE_NOT_FOUND"
fi
echo ""

# Summary and recommendations
echo "=========================================="
echo -e "${BLUE}SUMMARY & RECOMMENDATIONS${NC}"
echo "=========================================="
echo ""

if [ -z "$CSV_URL" ]; then
    echo -e "${RED}❌ CRITICAL: CSV_URL is not set${NC}"
    echo "   Action: Set the CSV_URL environment variable"
elif [[ "$CSV_URL" != *"/export?format=csv"* ]]; then
    echo -e "${RED}❌ CRITICAL: CSV_URL is not in correct format${NC}"
    echo "   Action: Update CSV_URL to use /export?format=csv format"
elif [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}❌ CRITICAL: Cannot access Google Sheet (HTTP $HTTP_CODE)${NC}"
    echo "   Action: Fix permissions or URL"
else
    echo -e "${GREEN}✓ CSV_URL appears to be configured correctly${NC}"
    echo "   Check application logs for other issues"
fi

echo ""
echo "Next Steps:"
echo "1. Review the issues identified above"
echo "2. Follow the recommended actions"
echo "3. See CLOUD_RUN_GOOGLE_SHEET_FIX.md for detailed instructions"
echo "4. Test changes with: gcloud run jobs execute $JOB_NAME --region=$REGION --wait"
echo ""
echo "For detailed fix instructions, see:"
echo "  cat CLOUD_RUN_GOOGLE_SHEET_FIX.md"
echo ""
