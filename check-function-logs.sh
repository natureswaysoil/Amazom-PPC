#!/bin/bash
#
# Check Cloud Function logs for startup errors
#

PROJECT_ID="amazon-ppc-474902"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "Checking recent Cloud Function errors..."
echo ""

gcloud logging read \
  "resource.type=cloud_run_revision AND 
   resource.labels.service_name=$FUNCTION_NAME AND 
   severity>=ERROR" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format='table(timestamp,severity,textPayload)'

echo ""
echo "Checking startup logs..."
echo ""

gcloud logging read \
  "resource.type=cloud_run_revision AND 
   resource.labels.service_name=$FUNCTION_NAME" \
  --limit=20 \
  --project=$PROJECT_ID \
  --format='table(timestamp,severity,textPayload)'
