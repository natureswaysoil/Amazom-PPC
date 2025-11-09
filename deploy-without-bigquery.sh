#!/bin/bash
#
# Deploy without BigQuery to see if that's the issue
#

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "Testing deployment without BigQuery..."

# Temporarily comment out BigQuery import
cd ~/Amazom-PPC
cp main.py main.py.backup

# Comment out the BigQuery import line
sed -i 's/^from bigquery_client import BigQueryClient$/# from bigquery_client import BigQueryClient/' main.py

# Comment out any BigQuery usage
sed -i 's/bigquery_client = BigQueryClient/# bigquery_client = BigQueryClient/g' main.py

echo "Modified main.py to disable BigQuery temporarily"
echo "Deploying..."

gcloud config set project "$PROJECT_ID"

gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python311 \
  --region="$REGION" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest

# Restore original file
mv main.py.backup main.py

echo ""
echo "Test complete. If this works, BigQuery was the issue."
