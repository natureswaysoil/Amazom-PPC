#!/bin/bash
set -euo pipefail

# ==============================================================================
# Setup Dashboard Permissions for BigQuery Access
# ==============================================================================
# This script creates or configures a service account for the PPC Dashboard
# and grants the necessary BigQuery permissions.
#
# Prerequisites:
# - gcloud CLI authenticated with admin permissions
# - Owner or Editor role on the GCP project
#
# Usage:
#   ./scripts/setup-dashboard-permissions.sh
#
# Environment Variables (optional):
#   PROJECT_ID        - Google Cloud project ID (default: amazon-ppc-474902)
#   SERVICE_ACCOUNT   - Service account email (default: auto-generated)
#   CREATE_KEY        - Create and download service account key (default: false)
# ==============================================================================

# Configuration
PROJECT_ID="${PROJECT_ID:-amazon-ppc-474902}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-ppc-dashboard}"
SERVICE_ACCOUNT_DISPLAY_NAME="Amazon PPC Dashboard"
SERVICE_ACCOUNT_DESCRIPTION="Service account for Amazon PPC Dashboard BigQuery access"
CREATE_KEY="${CREATE_KEY:-false}"

# Derived values
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=============================================================================="
echo "Dashboard Permissions Setup"
echo "=============================================================================="
echo "Project:         ${PROJECT_ID}"
echo "Service Account: ${SERVICE_ACCOUNT_EMAIL}"
echo "=============================================================================="
echo ""

# Verify gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" >/dev/null 2>&1; then
    echo "ERROR: gcloud is not authenticated. Run 'gcloud auth login' first."
    exit 1
fi

# Set project
echo "Setting project to ${PROJECT_ID}..."
if ! gcloud config set project "${PROJECT_ID}" 2>/dev/null; then
    echo "ERROR: Failed to set project. Verify PROJECT_ID is correct."
    exit 1
fi

# Check if service account already exists
echo ""
echo "Checking if service account exists..."
if gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "✅ Service account already exists: ${SERVICE_ACCOUNT_EMAIL}"
    ACCOUNT_EXISTS=true
else
    echo "ℹ️  Service account does not exist, creating..."
    ACCOUNT_EXISTS=false
    
    # Create service account
    if gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
        --project="${PROJECT_ID}" \
        --display-name="${SERVICE_ACCOUNT_DISPLAY_NAME}" \
        --description="${SERVICE_ACCOUNT_DESCRIPTION}"; then
        echo "✅ Created service account: ${SERVICE_ACCOUNT_EMAIL}"
    else
        echo "❌ ERROR: Failed to create service account"
        exit 1
    fi
fi

# Grant BigQuery Data Viewer role
echo ""
echo "Granting BigQuery Data Viewer role..."
if gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/bigquery.dataViewer" \
    --condition=None >/dev/null 2>&1; then
    echo "✅ Granted roles/bigquery.dataViewer"
else
    echo "⚠️  Warning: Failed to grant roles/bigquery.dataViewer (may already exist)"
fi

# Grant BigQuery Job User role
echo ""
echo "Granting BigQuery Job User role..."
if gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/bigquery.jobUser" \
    --condition=None >/dev/null 2>&1; then
    echo "✅ Granted roles/bigquery.jobUser"
else
    echo "⚠️  Warning: Failed to grant roles/bigquery.jobUser (may already exist)"
fi

# Verify permissions
echo ""
echo "Verifying service account permissions..."
echo "Roles assigned to ${SERVICE_ACCOUNT_EMAIL}:"
gcloud projects get-iam-policy "${PROJECT_ID}" \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --format="table(bindings.role)" 2>/dev/null || echo "Could not retrieve roles"

# Check for required roles
echo ""
MISSING_ROLES=()
if ! gcloud projects get-iam-policy "${PROJECT_ID}" \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:${SERVICE_ACCOUNT_EMAIL} AND bindings.role:roles/bigquery.dataViewer" \
    --format="value(bindings.role)" 2>/dev/null | grep -q "roles/bigquery.dataViewer"; then
    echo "❌ Missing: roles/bigquery.dataViewer"
    MISSING_ROLES+=("roles/bigquery.dataViewer")
else
    echo "✅ Confirmed: roles/bigquery.dataViewer"
fi

if ! gcloud projects get-iam-policy "${PROJECT_ID}" \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:${SERVICE_ACCOUNT_EMAIL} AND bindings.role:roles/bigquery.jobUser" \
    --format="value(bindings.role)" 2>/dev/null | grep -q "roles/bigquery.jobUser"; then
    echo "❌ Missing: roles/bigquery.jobUser"
    MISSING_ROLES+=("roles/bigquery.jobUser")
else
    echo "✅ Confirmed: roles/bigquery.jobUser"
fi

# Create service account key if requested
if [[ "${CREATE_KEY}" == "true" ]]; then
    echo ""
    echo "Creating service account key..."
    KEY_FILE="ppc-dashboard-service-account-key.json"
    
    if gcloud iam service-accounts keys create "${KEY_FILE}" \
        --iam-account="${SERVICE_ACCOUNT_EMAIL}" \
        --project="${PROJECT_ID}"; then
        echo "✅ Service account key created: ${KEY_FILE}"
        echo ""
        echo "⚠️  SECURITY WARNING:"
        echo "    This key file contains sensitive credentials!"
        echo "    - Keep it secure and never commit to version control"
        echo "    - Use it only for local development or secure environments"
        echo "    - For production, use Application Default Credentials (ADC)"
        echo ""
        echo "To use this key:"
        echo "  1. Set environment variable:"
        echo "     export GCP_SERVICE_ACCOUNT_KEY=\$(cat ${KEY_FILE})"
        echo ""
        echo "  2. Or for base64 encoding:"
        echo "     export GCP_SERVICE_ACCOUNT_KEY=\$(cat ${KEY_FILE} | base64 | tr -d '\\n')"
    else
        echo "❌ ERROR: Failed to create service account key"
    fi
else
    echo ""
    echo "ℹ️  To create a service account key for local development:"
    echo "   CREATE_KEY=true ./scripts/setup-dashboard-permissions.sh"
fi

echo ""
echo "=============================================================================="
echo "Setup Summary"
echo "=============================================================================="
if [[ ${#MISSING_ROLES[@]} -eq 0 ]]; then
    echo "✅ Service account is properly configured with all required permissions"
else
    echo "❌ Service account is missing required roles:"
    for role in "${MISSING_ROLES[@]}"; do
        echo "   - ${role}"
    done
    echo ""
    echo "Please ensure you have sufficient permissions to grant these roles."
fi

echo ""
echo "Service Account: ${SERVICE_ACCOUNT_EMAIL}"
echo "Required Roles:"
echo "  ✓ roles/bigquery.dataViewer - Read BigQuery data"
echo "  ✓ roles/bigquery.jobUser     - Execute BigQuery queries"
echo ""
echo "Next Steps:"
echo "  1. Verify BigQuery data: ./scripts/verify-bigquery-data.sh"
echo "  2. Deploy dashboard:     ./dashboard/deploy-dashboard-to-cloudrun.sh"
echo ""
echo "For Cloud Run deployment, the service will automatically use this service"
echo "account if you specify it with --service-account flag, or it will use the"
echo "default Compute Engine service account."
echo "=============================================================================="
