#!/bin/bash
# Deploy Cloud Function with improved logging

echo "Deploying Cloud Function with enhanced logging..."

cd /path/to/Amazom-PPC

gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python312 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --set-secrets='AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest' \
  --project=amazon-ppc-474902

echo ""
echo "Deployment complete! Testing health check..."
sleep 10

curl "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?health=true"

echo ""
echo ""
echo "Check logs for dashboard health details:"
echo "gcloud functions logs read amazon-ppc-optimizer --region=us-central1 --project=amazon-ppc-474902 --limit=30"
