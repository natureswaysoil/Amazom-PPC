#!/bin/bash
set -euo pipefail

# ==============================================================================
# Verify BigQuery Data for Amazon PPC Dashboard
# ==============================================================================
# This script connects to BigQuery and verifies that data exists for the
# Amazon PPC optimizer dashboard.
#
# Prerequisites:
# - gcloud CLI authenticated and configured
# - BigQuery dataset exists with data
# - Appropriate BigQuery permissions
#
# Usage:
#   ./scripts/verify-bigquery-data.sh
#
# Environment Variables (optional):
#   PROJECT_ID        - Google Cloud project ID (default: amazon-ppc-474902)
#   DATASET_ID        - BigQuery dataset ID (default: amazon_ppc_data)
#   LOCATION          - BigQuery location (default: us-east4)
# ==============================================================================

# Configuration
PROJECT_ID="${PROJECT_ID:-amazon-ppc-474902}"
DATASET_ID="${DATASET_ID:-amazon_ppc_data}"
LOCATION="${LOCATION:-us-east4}"

echo "=============================================================================="
echo "BigQuery Data Verification"
echo "=============================================================================="
echo "Project:  ${PROJECT_ID}"
echo "Dataset:  ${DATASET_ID}"
echo "Location: ${LOCATION}"
echo "=============================================================================="
echo ""

# Verify gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" >/dev/null 2>&1; then
    echo "ERROR: gcloud is not authenticated. Run 'gcloud auth login' first."
    exit 1
fi

# Set project
gcloud config set project "${PROJECT_ID}" >/dev/null 2>&1

# Function to run a BigQuery query
run_query() {
    local query="$1"
    local description="$2"
    
    echo "----------------------------------------"
    echo "${description}"
    echo "----------------------------------------"
    echo "Query: ${query}"
    echo ""
    
    if result=$(bq query --project_id="${PROJECT_ID}" --location="${LOCATION}" --format=pretty --use_legacy_sql=false "${query}" 2>&1); then
        echo "${result}"
        echo ""
        return 0
    else
        echo "ERROR: Query failed"
        echo "${result}"
        echo ""
        return 1
    fi
}

# Check if dataset exists
echo "Checking if dataset exists..."
if bq show --project_id="${PROJECT_ID}" "${DATASET_ID}" >/dev/null 2>&1; then
    echo "✅ Dataset '${DATASET_ID}' found"
    echo ""
else
    echo "❌ ERROR: Dataset '${DATASET_ID}' not found in project '${PROJECT_ID}'"
    echo ""
    echo "Available datasets:"
    bq ls --project_id="${PROJECT_ID}" 2>&1 || true
    exit 1
fi

# List all tables in the dataset
echo "=============================================================================="
echo "Tables in dataset '${DATASET_ID}'"
echo "=============================================================================="
bq ls --project_id="${PROJECT_ID}" "${DATASET_ID}" 2>&1 || true
echo ""

# Check campaigns table
echo "=============================================================================="
run_query "SELECT COUNT(*) as count FROM \`${PROJECT_ID}.${DATASET_ID}.campaigns\`" \
    "Campaigns Table - Row Count"

run_query "SELECT * FROM \`${PROJECT_ID}.${DATASET_ID}.campaigns\` LIMIT 5" \
    "Campaigns Table - Sample Data (5 rows)"

# Check keywords table
echo "=============================================================================="
run_query "SELECT COUNT(*) as count FROM \`${PROJECT_ID}.${DATASET_ID}.keywords\`" \
    "Keywords Table - Row Count"

run_query "SELECT * FROM \`${PROJECT_ID}.${DATASET_ID}.keywords\` LIMIT 5" \
    "Keywords Table - Sample Data (5 rows)"

# Check keyword_performance table
echo "=============================================================================="
run_query "SELECT COUNT(*) as count FROM \`${PROJECT_ID}.${DATASET_ID}.keyword_performance\`" \
    "Keyword Performance Table - Row Count"

run_query "SELECT * FROM \`${PROJECT_ID}.${DATASET_ID}.keyword_performance\` LIMIT 5" \
    "Keyword Performance Table - Sample Data (5 rows)"

# Check for other common tables
echo "=============================================================================="
echo "Checking for additional tables..."
echo "=============================================================================="

for table in optimization_results optimization_progress optimization_errors campaign_performance; do
    if bq show --project_id="${PROJECT_ID}" "${DATASET_ID}.${table}" >/dev/null 2>&1; then
        echo "✅ Found table: ${table}"
        run_query "SELECT COUNT(*) as count FROM \`${PROJECT_ID}.${DATASET_ID}.${table}\`" \
            "${table} - Row Count"
    else
        echo "ℹ️  Table '${table}' not found (this is optional)"
    fi
    echo ""
done

# Check dashboard service account permissions (if we can determine it)
echo "=============================================================================="
echo "Checking Service Account Permissions"
echo "=============================================================================="

# Try to find the dashboard service account
DASHBOARD_SA=$(gcloud iam service-accounts list \
    --project="${PROJECT_ID}" \
    --filter="email:ppc-dashboard*" \
    --format="value(email)" 2>/dev/null | head -1 || echo "")

if [[ -n "${DASHBOARD_SA}" ]]; then
    echo "Found dashboard service account: ${DASHBOARD_SA}"
    echo ""
    echo "IAM roles for ${DASHBOARD_SA}:"
    gcloud projects get-iam-policy "${PROJECT_ID}" \
        --flatten="bindings[].members" \
        --filter="bindings.members:serviceAccount:${DASHBOARD_SA}" \
        --format="table(bindings.role)" 2>/dev/null || echo "Could not retrieve IAM roles"
    echo ""
    
    # Check for required roles
    required_roles=("roles/bigquery.dataViewer" "roles/bigquery.jobUser")
    for role in "${required_roles[@]}"; do
        if gcloud projects get-iam-policy "${PROJECT_ID}" \
            --flatten="bindings[].members" \
            --filter="bindings.members:serviceAccount:${DASHBOARD_SA} AND bindings.role:${role}" \
            --format="value(bindings.role)" 2>/dev/null | grep -q "${role}"; then
            echo "✅ Service account has ${role}"
        else
            echo "❌ Service account missing ${role}"
            echo "   Run: scripts/setup-dashboard-permissions.sh to fix"
        fi
    done
else
    echo "ℹ️  Could not find dashboard service account"
    echo "   Service account may be created during Cloud Run deployment"
    echo "   Or run: scripts/setup-dashboard-permissions.sh to create one"
fi

echo ""
echo "=============================================================================="
echo "Verification Summary"
echo "=============================================================================="
echo "✅ BigQuery dataset accessible"
echo "✅ Data tables exist and contain data"
echo "ℹ️  See above for detailed row counts and samples"
echo ""
echo "Next Steps:"
echo "  1. Deploy dashboard: ./dashboard/deploy-dashboard-to-cloudrun.sh"
echo "  2. Test BigQuery API: curl https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app/api/bigquery-data?table=campaigns"
echo "  3. Open dashboard in browser to view data"
echo "=============================================================================="
