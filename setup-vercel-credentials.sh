#!/bin/bash
# Setup Vercel Environment Variables for Dashboard
# Run this in Google Cloud Shell

PROJECT_ID="amazon-ppc-474902"

echo "=========================================="
echo "Vercel Dashboard Environment Setup"
echo "=========================================="
echo ""

echo "Step 1: Get Service Account Key"
echo "----------------------------------------"
echo "Creating/downloading service account key..."

# Check if service account exists
SA_EMAIL="ppc-dashboard@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
  echo "✅ Service account exists: $SA_EMAIL"
else
  echo "Creating service account..."
  gcloud iam service-accounts create ppc-dashboard \
    --display-name="PPC Dashboard Service Account" \
    --project="$PROJECT_ID"
  
  # Grant BigQuery permissions
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/bigquery.dataViewer"
  
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/bigquery.jobUser"
fi

# Create key
KEY_FILE="/tmp/ppc-dashboard-key.json"
gcloud iam service-accounts keys create "$KEY_FILE" \
  --iam-account="$SA_EMAIL" \
  --project="$PROJECT_ID"

echo "✅ Service account key created: $KEY_FILE"
echo ""

echo "Step 2: Encode Key for Vercel"
echo "----------------------------------------"
# Base64 encode for easy copying (optional, can also use raw JSON)
ENCODED_KEY=$(cat "$KEY_FILE" | base64 -w 0)

echo "✅ Key encoded"
echo ""

echo "Step 3: Set Environment Variables in Vercel"
echo "=========================================="
echo ""
echo "Go to: https://vercel.com/natureswaysoil/nextjsspace-six/settings/environment-variables"
echo ""
echo "Add these environment variables:"
echo ""
echo "1. GCP_SERVICE_ACCOUNT_KEY"
echo "   Value: (paste the JSON below)"
echo "   Environment: Production, Preview, Development"
echo ""
cat "$KEY_FILE"
echo ""
echo ""
echo "2. GCP_PROJECT"
echo "   Value: $PROJECT_ID"
echo "   Environment: Production, Preview, Development"
echo ""
echo ""
echo "3. BQ_DATASET_ID"
echo "   Value: amazon_ppc"
echo "   Environment: Production, Preview, Development"
echo ""
echo ""
echo "4. BQ_LOCATION"
echo "   Value: us-east4"
echo "   Environment: Production, Preview, Development"
echo ""
echo ""

echo "=========================================="
echo "Alternative: Use Base64 Encoded Key"
echo "=========================================="
echo ""
echo "If the JSON is too large, use base64 encoding:"
echo ""
echo "Variable: GCP_SERVICE_ACCOUNT_KEY"
echo "Value:"
echo "$ENCODED_KEY"
echo ""
echo ""

echo "=========================================="
echo "Step 4: Redeploy Dashboard"
echo "=========================================="
echo ""
echo "After adding variables in Vercel:"
echo "1. Go to: https://vercel.com/natureswaysoil/nextjsspace-six"
echo "2. Click 'Deployments' tab"
echo "3. Click the three dots on latest deployment"
echo "4. Click 'Redeploy'"
echo ""
echo "Or trigger via CLI:"
echo "  vercel --prod"
echo ""
echo ""

echo "=========================================="
echo "Cleanup"
echo "=========================================="
echo ""
echo "⚠️ The service account key is saved at: $KEY_FILE"
echo "After setting up Vercel, delete it for security:"
echo "  rm $KEY_FILE"
echo ""

echo "✅ Setup Complete!"
echo ""
echo "After redeploying, the dashboard should show data from BigQuery!"
echo ""
