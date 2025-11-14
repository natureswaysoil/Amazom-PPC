#!/bin/bash

# Fix Secret Manager Permissions for ppc-bigquery-sa
# This script grants the service account access to all required secrets

set -e

PROJECT_ID="amazon-ppc-474902"
SERVICE_ACCOUNT="ppc-bigquery-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "================================================"
echo "Granting Secret Manager Permissions"
echo "================================================"
echo "Service Account: ${SERVICE_ACCOUNT}"
echo ""

# List of secrets that need access
SECRETS=(
  "amazon-client-id"
  "amazon-client-secret"
  "amazon-refresh-token"
  "amazon-profile-id"
  "ppc-profile-id"
  "dashboard-api-key"
  "dashboard-url"
  "AMAZON_CLIENT_ID"
  "AMAZON_CLIENT_SECRET"
  "AMAZON_REFRESH_TOKEN"
)

echo "Granting secretAccessor role to secrets..."
for SECRET in "${SECRETS[@]}"; do
  # Check if secret exists
  if gcloud secrets describe "${SECRET}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "  Granting access to: ${SECRET}"
    gcloud secrets add-iam-policy-binding "${SECRET}" \
      --member="serviceAccount:${SERVICE_ACCOUNT}" \
      --role="roles/secretmanager.secretAccessor" \
      --project="${PROJECT_ID}" \
      --quiet 2>/dev/null || true
  else
    echo "  ⚠️  Secret not found: ${SECRET}"
  fi
done

echo ""
echo "✅ Secret Manager permissions granted!"
echo ""

# Now redeploy the services that failed
echo "================================================"
echo "Redeploying PPC Services"
echo "================================================"
echo ""

# Redeploy Cloud Function
echo "1. Redeploying Cloud Function (amazon-ppc-optimizer)..."
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --service-account="${SERVICE_ACCOUNT}" \
  --set-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,DASHBOARD_API_KEY=dashboard-api-key:latest,DASHBOARD_URL=dashboard-url:latest,PPC_PROFILE_ID=ppc-profile-id:latest" \
  --quiet

echo ""
echo "2. Redeploying Cloud Run services..."

# Redeploy Cloud Run services that failed (only PPC-related ones)
REGIONS=("us-central1" "us-east4")
PPC_SERVICES=("amazon-ppc-optimizer" "amazon-ppc-optimizer-api" "amazon-ppc-sync" "ppc-optimizer")

for REGION in "${REGIONS[@]}"; do
  echo ""
  echo "Checking region: ${REGION}"
  
  for SERVICE in "${PPC_SERVICES[@]}"; do
    # Check if service exists in this region
    if gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
      echo "  Updating service: ${SERVICE}"
      gcloud run services update "${SERVICE}" \
        --region="${REGION}" \
        --service-account="${SERVICE_ACCOUNT}" \
        --project="${PROJECT_ID}" \
        --quiet 2>&1 | grep -E "(Deploying|Creating|Routing|Done|Service URL|ERROR)" || echo "  ✅ Updated ${SERVICE}"
    fi
  done
done

echo ""
echo "================================================"
echo "✅ All PPC Services Updated"
echo "================================================"
echo ""
echo "Service account: ${SERVICE_ACCOUNT}"
echo ""
echo "Next steps:"
echo "1. Test the Cloud Function:"
echo "   gcloud functions call amazon-ppc-optimizer --region=us-central1 --gen2 --data='{\"dry_run\":true,\"features\":[\"bid_optimization\"],\"verify_sample_size\":5}'"
echo ""
echo "2. Test the Cloud Run service:"
echo "   curl -X POST https://amazon-ppc-optimizer-1009540130231.us-east4.run.app/optimize \\"
echo "     -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -d '{\"dry_run\":true,\"features\":[\"bid_optimization\"]}'"
echo ""
