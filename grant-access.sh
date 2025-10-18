#!/bin/bash
#
# Grant Access for Amazon PPC Optimizer
# Sets up proper IAM permissions for Cloud Function deployment and Secret Manager access
#

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "=========================================="
echo "Amazon PPC Optimizer - Grant Access"
echo "=========================================="
echo "Project: $PROJECT_ID"
echo ""

# Set active project
gcloud config set project "$PROJECT_ID"

# Get the project number (needed for default service account)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Project Number: $PROJECT_NUMBER"
echo "Default Service Account: $COMPUTE_SA"
echo ""

# 1. Enable required APIs
echo "=========================================="
echo "1. Enabling Required APIs"
echo "=========================================="
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable run.googleapis.com
echo "✅ APIs enabled"
echo ""

# 2. Grant Secret Manager access to default compute service account
echo "=========================================="
echo "2. Granting Secret Manager Access"
echo "=========================================="
echo "Granting secretAccessor role to: $COMPUTE_SA"
echo ""

# Grant access to each secret
for secret in amazon-client-id amazon-client-secret amazon-refresh-token ppc-profile-id dashboard-url dashboard-api-key; do
    echo "  - $secret"
    gcloud secrets add-iam-policy-binding "$secret" \
        --member="serviceAccount:${COMPUTE_SA}" \
        --role="roles/secretmanager.secretAccessor" \
        --condition=None 2>/dev/null || echo "    (already has access or secret doesn't exist)"
done
echo "✅ Secret Manager permissions granted"
echo ""

# 3. Create service account for Cloud Scheduler (if needed)
echo "=========================================="
echo "3. Setting Up Cloud Scheduler Access"
echo "=========================================="
SCHEDULER_SA="ppc-optimizer-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$SCHEDULER_SA" >/dev/null 2>&1; then
    echo "✅ Scheduler service account already exists"
else
    echo "Creating scheduler service account..."
    gcloud iam service-accounts create ppc-optimizer-scheduler \
        --display-name="PPC Optimizer Scheduler" \
        --description="Service account for Cloud Scheduler to invoke PPC optimizer function"
    echo "✅ Scheduler service account created"
fi
echo ""

# 4. Grant invoker permission (will be applied after deployment)
echo "=========================================="
echo "4. Cloud Function Invoker Permission"
echo "=========================================="
echo "Note: Run this command AFTER deploying the function:"
echo ""
echo "gcloud functions add-invoker-policy-binding $FUNCTION_NAME \\"
echo "  --region=$REGION \\"
echo "  --member=\"serviceAccount:${SCHEDULER_SA}\""
echo ""

# 5. Check your own permissions
echo "=========================================="
echo "5. Checking Your Deployment Permissions"
echo "=========================================="
CURRENT_USER=$(gcloud config get-value account)
echo "Current user: $CURRENT_USER"
echo ""
echo "Required roles for deployment:"
echo "  - roles/cloudfunctions.developer"
echo "  - roles/iam.serviceAccountUser"
echo "  - roles/secretmanager.secretAccessor (to use secrets)"
echo ""
echo "To grant yourself these roles (requires Project Owner or Admin):"
echo ""
echo "gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "  --member=\"user:${CURRENT_USER}\" \\"
echo "  --role=\"roles/cloudfunctions.developer\""
echo ""
echo "gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "  --member=\"user:${CURRENT_USER}\" \\"
echo "  --role=\"roles/iam.serviceAccountUser\""
echo ""

echo "=========================================="
echo "✅ Access Configuration Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run ./deploy.sh to deploy the function"
echo "2. After deployment, grant invoker permission to scheduler service account"
echo "3. Set up Cloud Scheduler job if needed"
echo ""
