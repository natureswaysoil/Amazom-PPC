#!/bin/bash
set -e

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "🔍 Checking Secrets Configuration"
echo "=================================="
echo ""

echo "Listing all secrets in project $PROJECT_ID:"
gcloud secrets list --project="$PROJECT_ID" --format="table(name,createTime)"

echo ""
echo "Checking which secrets are missing..."
echo ""

REQUIRED_SECRETS=(
  "amazon-client-id"
  "amazon-client-secret"
  "amazon-refresh-token"
  "ppc-profile-id"
  "dashboard-url"
  "dashboard-api-key"
)

MISSING_SECRETS=()

for secret in "${REQUIRED_SECRETS[@]}"; do
  if gcloud secrets describe "$secret" --project="$PROJECT_ID" &>/dev/null; then
    echo "✅ $secret exists"
  else
    echo "❌ $secret is MISSING"
    MISSING_SECRETS+=("$secret")
  fi
done

echo ""
if [ ${#MISSING_SECRETS[@]} -eq 0 ]; then
  echo "✅ All required secrets exist!"
  echo ""
  echo "Checking service account access..."
  COMPUTE_SA="${PROJECT_ID}-compute@developer.gserviceaccount.com"
  
  for secret in "${REQUIRED_SECRETS[@]}"; do
    echo ""
    echo "Access for $secret:"
    gcloud secrets get-iam-policy "$secret" --project="$PROJECT_ID" \
      --format="table(bindings.members)" 2>/dev/null | grep "$COMPUTE_SA" && echo "  ✅ Has access" || echo "  ❌ NO ACCESS"
  done
else
  echo ""
  echo "❌ Missing secrets: ${MISSING_SECRETS[*]}"
  echo ""
  echo "You need to create these secrets with their values."
  echo ""
  echo "Example:"
  echo "  echo -n 'YOUR_VALUE' | gcloud secrets create SECRET_NAME --data-file=- --project=$PROJECT_ID"
fi
