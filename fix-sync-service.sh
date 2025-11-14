#!/bin/bash
# Fix and redeploy amazon-ppc-sync Cloud Run service
# Updates to Node.js 20 and refreshes secrets

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-east4"
SERVICE_NAME="amazon-ppc-sync"

echo "=========================================="
echo "Fixing amazon-ppc-sync Cloud Run Service"
echo "=========================================="
echo ""

cd ~/Amazom-PPC

# Check if package.json specifies the engine
if grep -q '"node":' package.json; then
  echo "✅ Node version specified in package.json"
else
  echo "⚠️ Adding Node 20 to package.json..."
  # Backup original
  cp package.json package.json.bak
  
  # Add engines field if not present
  if ! grep -q '"engines"' package.json; then
    sed -i 's/"name"/"engines": {"node": ">=20.0.0"},\n  "name"/' package.json
    echo "✅ Added Node 20 requirement"
  fi
fi

echo ""
echo "Deploying updated service..."
echo ""

gcloud run deploy $SERVICE_NAME \
  --region=$REGION \
  --source=. \
  --platform=managed \
  --clear-base-image \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest \
  --allow-unauthenticated \
  --timeout=540s \
  --memory=512Mi \
  --min-instances=0 \
  --max-instances=10 \
  --project=$PROJECT_ID

echo ""
echo "=========================================="
echo "✅ Deployment Complete"
echo "=========================================="
echo ""
echo "Service URL:"
gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(status.url)"

echo ""
echo "Test the service:"
echo "curl \$(gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID --format='value(status.url)')"
echo ""
