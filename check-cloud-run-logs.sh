#!/bin/bash

# Check Cloud Run logs for the most recent execution
# Look for Amazon API calls and any errors

echo "Fetching recent Cloud Run logs for amazon-ppc-optimizer..."
echo "================================================"

# Get logs from the last 5 minutes
gcloud logging read "resource.type=cloud_run_revision 
  AND resource.labels.service_name=amazon-ppc-optimizer 
  AND timestamp>\"$(date -u -d '5 minutes ago' --iso-8601=seconds)\"" \
  --limit 100 \
  --format json \
  --project amazon-ppc-474902 | \
  jq -r '.[] | "\(.timestamp) [\(.severity)] \(.textPayload // .jsonPayload.message // "")"' | \
  sort

echo ""
echo "================================================"
echo "Searching for key patterns:"
echo "================================================"

# Search for specific patterns
gcloud logging read "resource.type=cloud_run_revision 
  AND resource.labels.service_name=amazon-ppc-optimizer 
  AND timestamp>\"$(date -u -d '5 minutes ago' --iso-8601=seconds)\"
  AND (textPayload=~\"campaigns\" OR textPayload=~\"403\" OR textPayload=~\"Amazon\" OR textPayload=~\"API\")" \
  --limit 50 \
  --format json \
  --project amazon-ppc-474902 | \
  jq -r '.[] | "\(.timestamp) [\(.severity)] \(.textPayload // .jsonPayload.message // "")"' | \
  sort

echo ""
echo "Done!"
