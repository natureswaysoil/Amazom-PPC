#!/bin/bash
# Check deployment status and verify connection

PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
FUNCTION_NAME="amazon-ppc-optimizer"

echo "=========================================="
echo "Checking Function Status & Verification"
echo "=========================================="
echo ""

echo "1. Checking function deployment status..."
echo "----------------------------------------"
gcloud functions describe "$FUNCTION_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format="table(state,updateTime,serviceConfig.revision)" || echo "Function not found or error"

echo ""
echo ""

echo "2. Getting function URL..."
echo "----------------------------------------"
FUNC_URL=$(gcloud functions describe "$FUNCTION_NAME" \
    --region="$REGION" --gen2 \
    --format='value(serviceConfig.uri)' \
    --project="$PROJECT_ID" 2>/dev/null)

if [ -z "$FUNC_URL" ]; then
    echo "❌ Could not retrieve function URL"
    exit 1
fi

echo "Function URL: $FUNC_URL"
echo ""

echo "3. Testing health endpoint..."
echo "----------------------------------------"
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
    "$FUNC_URL?health=true" | python3 -m json.tool

echo ""
echo ""

echo "4. Testing verify_connection endpoint..."
echo "----------------------------------------"
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
    "$FUNC_URL?verify_connection=true&verify_sample_size=5" | python3 -m json.tool

echo ""
echo ""

echo "5. Checking recent logs for errors..."
echo "----------------------------------------"
gcloud functions logs read "$FUNCTION_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --limit=10 \
  --format="table(TIME_UTC,SEVERITY,LOG)"

echo ""
echo "=========================================="
echo "Status check complete"
echo "=========================================="
