#!/bin/bash

# Update US Cloud Run services with correct secret configuration

set -e

PROJECT_ID="amazon-ppc-474902"
SERVICE_ACCOUNT="ppc-bigquery-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "================================================"
echo "Updating US Cloud Run Services"
echo "================================================"
echo ""

# US regions only
US_REGIONS=("us-central1" "us-east1" "us-east4" "us-west1")

for REGION in "${US_REGIONS[@]}"; do
  echo "Checking region: ${REGION}"
  
  # List all services in this region
  SERVICES=$(gcloud run services list --region="${REGION}" --project="${PROJECT_ID}" --format="value(metadata.name)" 2>/dev/null || echo "")
  
  if [ -z "$SERVICES" ]; then
    echo "  No services found in ${REGION}"
    continue
  fi
  
  # Update each PPC-related service
  for SERVICE in $SERVICES; do
    if [[ "$SERVICE" == *"ppc"* ]] || [[ "$SERVICE" == *"amazon"* ]]; then
      echo "  Updating service: ${SERVICE}"
      
      gcloud run services update "${SERVICE}" \
        --region="${REGION}" \
        --service-account="${SERVICE_ACCOUNT}" \
        --set-env-vars="LOG_LEVEL=INFO,PPC_DRY_RUN=false" \
        --set-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_API_KEY=dashboard-api-key:latest,DASHBOARD_URL=dashboard-url:latest" \
        --project="${PROJECT_ID}" \
        --quiet 2>&1 | grep -E "(Deploying|Creating|Done|Service URL|ERROR)" || echo "    ✅ Updated"
    fi
  done
  echo ""
done

echo "================================================"
echo "Getting Service URLs"
echo "================================================"
echo ""

# List all PPC services and their URLs
for REGION in "${US_REGIONS[@]}"; do
  SERVICES=$(gcloud run services list --region="${REGION}" --project="${PROJECT_ID}" --format="value(metadata.name)" 2>/dev/null || echo "")
  
  for SERVICE in $SERVICES; do
    if [[ "$SERVICE" == *"ppc"* ]] || [[ "$SERVICE" == *"amazon"* ]]; then
      URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)" 2>/dev/null || echo "")
      if [ -n "$URL" ]; then
        echo "${SERVICE} (${REGION}): ${URL}"
      fi
    fi
  done
done

echo ""
echo "✅ All US services updated!"
echo ""
