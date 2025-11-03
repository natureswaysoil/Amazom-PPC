#!/bin/bash
set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "🔧 Fixing Dashboard Secrets"
echo "============================"

# Set the correct dashboard URL
DASHBOARD_URL="https://amazonppcdashboard.vercel.app"

echo ""
echo "Setting dashboard URL to: $DASHBOARD_URL"

# Update dashboard-url secret
echo -n "$DASHBOARD_URL" | gcloud secrets versions add dashboard-url \
  --data-file=- \
  --project="$PROJECT_ID"

echo "✅ Updated dashboard-url"

# Get API key
echo ""
read -p "Enter your Dashboard API Key: " DASHBOARD_API_KEY

if [ -z "$DASHBOARD_API_KEY" ]; then
  echo "❌ Error: Dashboard API key is required"
  exit 1
fi

# Update dashboard-api-key secret
echo -n "$DASHBOARD_API_KEY" | gcloud secrets versions add dashboard-api-key \
  --data-file=- \
  --project="$PROJECT_ID"

echo "✅ Updated dashboard-api-key"

# Grant access to secrets
echo ""
echo "Granting access to secrets..."

COMPUTE_SA="${PROJECT_ID}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding dashboard-url \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" \
  --quiet 2>/dev/null || true

gcloud secrets add-iam-policy-binding dashboard-api-key \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" \
  --quiet 2>/dev/null || true

echo "✅ Granted access"

# Redeploy function
echo ""
echo "Redeploying function with dashboard integration..."

gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python311 \
  --region="$REGION" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --timeout=540s \
  --memory=512MB \
  --max-instances=3 \
  --no-allow-unauthenticated \
  --set-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest" \
  --project="$PROJECT_ID"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🎯 Dashboard integration is now active!"
echo ""
echo "Your optimizer will post to: $DASHBOARD_URL"
echo ""
echo "Test with a dry run:"
FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --gen2 --format='value(serviceConfig.uri)' --project="$PROJECT_ID")
echo ""
echo "curl -X POST \\"
echo "  -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"dry_run\": true, \"features\": [\"bid_optimization\"]}' \\"
echo "  \"$FUNCTION_URL\""
