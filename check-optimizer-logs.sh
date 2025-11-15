#!/bin/bash

# Check optimizer logs to diagnose why campaigns aren't being analyzed

set -e

PROJECT_ID="amazon-ppc-474902"
SERVICE_NAME="amazon-ppc-optimizer"
REGION="us-central1"

echo "================================================"
echo "Checking Recent Cloud Run Logs"
echo "================================================"
echo ""

echo "Fetching logs from last 10 minutes..."
gcloud logging read "resource.type=cloud_run_revision 
  AND resource.labels.service_name=${SERVICE_NAME}
  AND resource.labels.location=${REGION}
  AND timestamp>=\"$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)Z\"" \
  --project="${PROJECT_ID}" \
  --limit=50 \
  --format="table(timestamp,severity,textPayload)" \
  --order=asc

echo ""
echo "================================================"
echo "Checking for Errors"
echo "================================================"
echo ""

gcloud logging read "resource.type=cloud_run_revision 
  AND resource.labels.service_name=${SERVICE_NAME}
  AND resource.labels.location=${REGION}
  AND severity>=ERROR
  AND timestamp>=\"$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)Z\"" \
  --project="${PROJECT_ID}" \
  --limit=20 \
  --format="table(timestamp,severity,textPayload)"

echo ""
echo "================================================"
echo "Test with Verbose Logging"
echo "================================================"
echo ""

echo "Running optimizer with sample size to see detailed output..."

curl -X POST https://${SERVICE_NAME}-nucguq3dba-uc.a.run.app/optimize \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": true,
    "force": true,
    "features": ["bid_optimization"],
    "verify_sample_size": 10
  }' | jq .

echo ""
echo "Waiting 5 seconds for logs to flush..."
sleep 5

echo ""
echo "Recent logs from this test run:"
gcloud logging read "resource.type=cloud_run_revision 
  AND resource.labels.service_name=${SERVICE_NAME}
  AND resource.labels.location=${REGION}
  AND timestamp>=\"$(date -u -d '1 minute ago' +%Y-%m-%dT%H:%M:%S)Z\"" \
  --project="${PROJECT_ID}" \
  --limit=30 \
  --format="value(textPayload)" \
  --order=asc | grep -E "(campaign|keyword|ERROR|WARNING|fetching|analyzing)" || echo "No relevant logs found"

echo ""
