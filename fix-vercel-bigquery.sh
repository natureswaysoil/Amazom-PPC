#!/bin/bash
# Fix Vercel Dashboard BigQuery Permissions
# Run this in Google Cloud Shell

PROJECT_ID="amazon-ppc-474902"
DATASET_ID="amazon_ppc"

echo "=========================================="
echo "Vercel Dashboard - BigQuery Setup"
echo "=========================================="
echo ""

# Step 1: Get service account email
echo "Step 1: Finding service account..."
SA_EMAIL=$(gcloud iam service-accounts list --project=$PROJECT_ID \
  --filter="displayName:ppc OR displayName:bigquery OR displayName:dashboard" \
  --format="value(email)" | head -1)

if [ -z "$SA_EMAIL" ]; then
  echo "No existing service account found. Creating new one..."
  SA_EMAIL="ppc-dashboard-sa@${PROJECT_ID}.iam.gserviceaccount.com"
  
  gcloud iam service-accounts create ppc-dashboard-sa \
    --display-name="PPC Dashboard Service Account" \
    --project=$PROJECT_ID
  
  echo "✅ Created service account: $SA_EMAIL"
else
  echo "✅ Found service account: $SA_EMAIL"
fi

echo ""

# Step 2: Grant BigQuery permissions
echo "Step 2: Granting BigQuery permissions..."

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.dataViewer" \
  --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.jobUser" \
  --condition=None

echo "✅ Permissions granted"
echo ""

# Step 3: Create and download key
echo "Step 3: Creating service account key..."
KEY_FILE="/tmp/ppc-dashboard-key.json"

gcloud iam service-accounts keys create "$KEY_FILE" \
  --iam-account="$SA_EMAIL" \
  --project=$PROJECT_ID

echo "✅ Key created: $KEY_FILE"
echo ""

# Step 4: Show the key content
echo "=========================================="
echo "Step 4: Configure Vercel Environment Variables"
echo "=========================================="
echo ""
echo "Go to: https://vercel.com/natureswaysoil/nextjsspace-six/settings/environment-variables"
echo ""
echo "Add these variables:"
echo ""
echo "1. GCP_PROJECT"
echo "   Value: $PROJECT_ID"
echo ""
echo "2. GCP_SERVICE_ACCOUNT_KEY"
echo "   Value: (copy the JSON below)"
echo ""
echo "=========================================="
echo "SERVICE ACCOUNT KEY JSON:"
echo "=========================================="
cat "$KEY_FILE"
echo ""
echo "=========================================="
echo ""
echo "Or as base64 (alternative):"
echo "=========================================="
base64 -w 0 "$KEY_FILE"
echo ""
echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Copy the JSON above"
echo "2. Go to Vercel: https://vercel.com/natureswaysoil/nextjsspace-six/settings/environment-variables"
echo "3. Add GCP_PROJECT = $PROJECT_ID"
echo "4. Add GCP_SERVICE_ACCOUNT_KEY = (paste JSON)"
echo "5. Click 'Save'"
echo "6. Redeploy: Go to Deployments tab and click 'Redeploy'"
echo "7. Wait 2-3 minutes for deployment"
echo "8. Refresh dashboard: https://nextjsspace-six.vercel.app"
echo ""

# Cleanup
echo "Cleaning up temporary files..."
rm -f "$KEY_FILE"
echo "✅ Done!"
echo ""
