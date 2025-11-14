#!/bin/bash
# Fix BigQuery permissions for ALL PPC services
# Run this in Google Cloud Shell

PROJECT_ID="amazon-ppc-474902"

echo "=========================================="
echo "Fixing BigQuery Permissions for All Services"
echo "=========================================="
echo ""

# Find all Cloud Run services
echo "1. Finding all Cloud Run services..."
SERVICES=$(gcloud run services list --project=$PROJECT_ID --format="value(metadata.name,metadata.namespace)")

if [ -z "$SERVICES" ]; then
  echo "No Cloud Run services found"
else
  echo "Found services:"
  echo "$SERVICES"
fi

echo ""

# Get or create service account
echo "2. Setting up service account..."
SA_EMAIL=$(gcloud iam service-accounts list --project=$PROJECT_ID \
  --filter="displayName:ppc-bigquery" \
  --format="value(email)" | head -1)

if [ -z "$SA_EMAIL" ]; then
  echo "Creating service account..."
  SA_EMAIL="ppc-bigquery-sa@${PROJECT_ID}.iam.gserviceaccount.com"
  
  gcloud iam service-accounts create ppc-bigquery-sa \
    --display-name="PPC BigQuery Service Account" \
    --project=$PROJECT_ID
  
  echo "✅ Created: $SA_EMAIL"
else
  echo "✅ Using existing: $SA_EMAIL"
fi

echo ""

# Grant permissions
echo "3. Granting BigQuery permissions..."

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.dataEditor" \
  --condition=None \
  --quiet

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.jobUser" \
  --condition=None \
  --quiet

echo "✅ Permissions granted"
echo ""

# Update Cloud Function
echo "4. Updating Cloud Function (amazon-ppc-optimizer)..."
if gcloud functions describe amazon-ppc-optimizer --region=us-central1 --project=$PROJECT_ID &>/dev/null; then
  gcloud functions deploy amazon-ppc-optimizer \
    --gen2 \
    --region=us-central1 \
    --service-account=$SA_EMAIL \
    --no-allow-unauthenticated \
    --project=$PROJECT_ID \
    --quiet
  echo "✅ Updated Cloud Function"
else
  echo "⚠️ Cloud Function not found in us-central1"
fi

echo ""

# Update all Cloud Run services
echo "5. Updating Cloud Run services with BigQuery permissions..."

for region in us-central1 us-east4 us-west1; do
  echo ""
  echo "Checking region: $region"
  
  SERVICES=$(gcloud run services list --region=$region --project=$PROJECT_ID --format="value(metadata.name)" 2>/dev/null)
  
  for service in $SERVICES; do
    echo "  Updating service: $service"
    
    gcloud run services update $service \
      --region=$region \
      --service-account=$SA_EMAIL \
      --project=$PROJECT_ID \
      --quiet 2>&1 | grep -v "WARNING" || true
    
    echo "  ✅ Updated $service"
  done
done

echo ""
echo "=========================================="
echo "✅ All Services Updated"
echo "=========================================="
echo ""
echo "Service account: $SA_EMAIL"
echo ""
echo "All services now have BigQuery permissions!"
echo ""
