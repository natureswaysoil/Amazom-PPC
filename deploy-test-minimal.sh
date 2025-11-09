#!/bin/bash
#
# Deploy minimal test version to isolate the startup issue
#

set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer-test"

echo "=========================================="
echo "Deploying MINIMAL TEST version"
echo "=========================================="
echo ""

gcloud config set project "$PROJECT_ID"

# Temporarily rename files
mv main.py main.py.bak
mv main_test.py main.py

echo "Deploying minimal test function..."
gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python311 \
  --region="$REGION" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=60s \
  --memory=256MB

# Restore files
mv main.py main_test.py
mv main.py.bak main.py

echo ""
echo "Test function deployed. Testing..."
FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" --gen2 --region="$REGION" --format='value(serviceConfig.uri)')
echo "URL: $FUNCTION_URL"
echo ""
curl "$FUNCTION_URL"
echo ""
