#!/bin/bash
# Fix BigQuery Permissions Script
# Grants necessary BigQuery IAM roles to a service account

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       BigQuery Permissions Fix Script                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Default project ID
PROJECT_ID="${GCP_PROJECT:-amazon-ppc-474902}"

echo -e "${YELLOW}Project ID:${NC} $PROJECT_ID"
echo ""

# Try to extract service account email from environment
SERVICE_ACCOUNT_EMAIL=""

if [ -n "$GCP_SERVICE_ACCOUNT_KEY" ]; then
  echo -e "${BLUE}Detecting service account from GCP_SERVICE_ACCOUNT_KEY...${NC}"
  
  # Try to parse as JSON
  SERVICE_ACCOUNT_EMAIL=$(echo "$GCP_SERVICE_ACCOUNT_KEY" | jq -r '.client_email' 2>/dev/null || echo "")
  
  # If that failed, try base64 decoding first
  if [ -z "$SERVICE_ACCOUNT_EMAIL" ] || [ "$SERVICE_ACCOUNT_EMAIL" = "null" ]; then
    SERVICE_ACCOUNT_EMAIL=$(echo "$GCP_SERVICE_ACCOUNT_KEY" | base64 -d 2>/dev/null | jq -r '.client_email' 2>/dev/null || echo "")
  fi
  
  if [ -n "$SERVICE_ACCOUNT_EMAIL" ] && [ "$SERVICE_ACCOUNT_EMAIL" != "null" ]; then
    echo -e "${GREEN}✓${NC} Found service account: ${GREEN}$SERVICE_ACCOUNT_EMAIL${NC}"
  fi
fi

# If still not found, ask the user
if [ -z "$SERVICE_ACCOUNT_EMAIL" ] || [ "$SERVICE_ACCOUNT_EMAIL" = "null" ]; then
  echo -e "${YELLOW}Service account email not found in environment variables.${NC}"
  echo ""
  echo "Enter your service account email (e.g., my-service@project.iam.gserviceaccount.com):"
  read -r SERVICE_ACCOUNT_EMAIL
  
  if [ -z "$SERVICE_ACCOUNT_EMAIL" ]; then
    echo -e "${RED}✗ Error: Service account email is required${NC}"
    exit 1
  fi
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Configuration:${NC}"
echo -e "  Project:         ${GREEN}$PROJECT_ID${NC}"
echo -e "  Service Account: ${GREEN}$SERVICE_ACCOUNT_EMAIL${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Confirm with user
echo -e "${YELLOW}This script will grant the following roles:${NC}"
echo "  • roles/bigquery.dataViewer (read BigQuery data)"
echo "  • roles/bigquery.jobUser (run BigQuery queries)"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${YELLOW}Aborted by user${NC}"
  exit 0
fi

echo ""
echo -e "${BLUE}Granting BigQuery permissions...${NC}"
echo ""

# Function to grant a role with error handling
grant_role() {
  local role=$1
  local role_name=$2
  
  echo -e "${YELLOW}→${NC} Granting ${BLUE}$role_name${NC}..."
  
  if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="$role" \
    --condition=None \
    2>&1 | tee /tmp/grant_output.txt; then
    
    # Check if role was already granted
    if grep -q "Role.*already exists" /tmp/grant_output.txt; then
      echo -e "${YELLOW}  ⚠${NC}  Role already granted (no change needed)"
    else
      echo -e "${GREEN}  ✓${NC}  Successfully granted $role_name"
    fi
  else
    echo -e "${RED}  ✗${NC}  Failed to grant $role_name"
    return 1
  fi
}

# Grant BigQuery Data Viewer role
if grant_role "roles/bigquery.dataViewer" "BigQuery Data Viewer"; then
  VIEWER_OK=true
else
  VIEWER_OK=false
fi

echo ""

# Grant BigQuery Job User role
if grant_role "roles/bigquery.jobUser" "BigQuery Job User"; then
  JOBUSER_OK=true
else
  JOBUSER_OK=false
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

# Check results
if [ "$VIEWER_OK" = true ] && [ "$JOBUSER_OK" = true ]; then
  echo -e "${GREEN}✓ Success!${NC} All required permissions have been granted."
  echo ""
  echo -e "${YELLOW}Next steps:${NC}"
  echo "  1. Wait 1-2 minutes for IAM changes to propagate"
  echo "  2. Refresh your dashboard page"
  echo "  3. The BigQuery data should now load successfully"
  echo ""
  echo -e "${GREEN}✓ Setup complete!${NC}"
  exit 0
else
  echo -e "${RED}✗ Error:${NC} Failed to grant some permissions."
  echo ""
  echo -e "${YELLOW}Troubleshooting:${NC}"
  echo "  • Ensure you have permission to grant IAM roles (Project Owner/Admin)"
  echo "  • Check that the service account exists:"
  echo "    gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL"
  echo "  • Verify the project ID is correct: $PROJECT_ID"
  echo ""
  echo "For manual setup, see: BIGQUERY_PERMISSIONS_FIX.md"
  exit 1
fi
