#!/bin/bash
# Deploy with DEBUG logging

set -e

gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --set-env-vars=LOG_LEVEL=DEBUG \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest \
  --project=amazon-ppc-474902

echo ""
echo "Deployment complete! Test with:"
echo "curl -X POST https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app -H 'Content-Type: application/json' -d '{\"dry_run\": true, \"features\": [\"verify_connection\"]}'"
