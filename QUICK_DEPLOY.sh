#!/bin/bash
#
# Quick Deploy Script for Amazon PPC Optimizer to Google Cloud Functions
# 
# Usage: ./QUICK_DEPLOY.sh YOUR_PROJECT_ID [REGION]
#
# This script automates the deployment of the Amazon PPC Optimizer to Google Cloud Functions.
# Make sure you have the gcloud CLI installed and authenticated before running this script.
#

set -e  # Exit on error

# Check if project ID is provided
if [ -z "$1" ]; then
    echo "Error: Project ID is required"
    echo "Usage: $0 YOUR_PROJECT_ID [REGION]"
    exit 1
fi

PROJECT_ID="$1"
REGION="${2:-us-central1}"  # Default to us-central1 if not specified
FUNCTION_NAME="amazon-ppc-optimizer"
SERVICE_ACCOUNT_NAME="ppc-optimizer-scheduler"

echo "=============================================="
echo "Amazon PPC Optimizer - Quick Deployment"
echo "=============================================="
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Function Name: $FUNCTION_NAME"
echo "=============================================="

# Set the project
echo ""
echo "📋 Setting project to: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo ""
echo "🔌 Enabling required Google Cloud APIs..."
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Deploy the function
echo ""
echo "🚀 Deploying Cloud Function..."
echo "   This may take 2-3 minutes..."

# Check if config.json exists and has credentials
if [ -f "config.json" ]; then
    echo "   ✓ Found config.json"
    
    # Deploy function
    gcloud functions deploy "$FUNCTION_NAME" \
        --gen2 \
        --runtime=python311 \
        --region="$REGION" \
        --source=. \
        --entry-point=run_optimizer \
        --trigger-http \
        --no-allow-unauthenticated \
        --memory=512MB \
        --timeout=540s
else
    echo "   ⚠ config.json not found!"
    echo "   Please ensure config.json exists with valid Amazon API credentials"
    exit 1
fi

# Get function URL (Gen2 functions use Cloud Run URLs)
echo ""
echo "🔗 Getting function URL..."
FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
    --region="$REGION" \
    --gen2 \
    --format='value(serviceConfig.uri)')

echo "   Function URL: $FUNCTION_URL"
echo "   Note: Gen2 uses Cloud Run URL format (https://FUNCTION-HASH-REGION.a.run.app)"

# Create service account if it doesn't exist
echo ""
echo "👤 Setting up service account..."
if gcloud iam service-accounts describe "${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    echo "   ✓ Service account already exists"
else
    echo "   Creating service account..."
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name="PPC Optimizer Scheduler"
fi

# Grant invoker permission
echo ""
echo "🔐 Granting function invoker permission..."
gcloud functions add-invoker-policy-binding "$FUNCTION_NAME" \
    --region="$REGION" \
    --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Create Cloud Scheduler job
echo ""
echo "⏰ Setting up Cloud Scheduler job..."
SCHEDULER_JOB_NAME="ppc-optimizer-daily"

if gcloud scheduler jobs describe "$SCHEDULER_JOB_NAME" --location="$REGION" >/dev/null 2>&1; then
    echo "   Scheduler job already exists, updating..."
    gcloud scheduler jobs update http "$SCHEDULER_JOB_NAME" \
        --location="$REGION" \
        --schedule="0 2 * * *" \
        --uri="$FUNCTION_URL" \
        --http-method=POST \
        --oidc-service-account-email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --oidc-token-audience="$FUNCTION_URL"
else
    echo "   Creating new scheduler job (runs daily at 2 AM)..."
    gcloud scheduler jobs create http "$SCHEDULER_JOB_NAME" \
        --location="$REGION" \
        --schedule="0 2 * * *" \
        --uri="$FUNCTION_URL" \
        --http-method=POST \
        --oidc-service-account-email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --oidc-token-audience="$FUNCTION_URL"
fi

# Test health check
echo ""
echo "🏥 Testing health check endpoint..."
HEALTH_RESPONSE=$(curl -s "${FUNCTION_URL}?health=true" \
    -H "Authorization: Bearer $(gcloud auth print-identity-token)")

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "   ✅ Health check passed!"
    echo "   Response: $HEALTH_RESPONSE"
else
    echo "   ⚠ Health check returned unexpected response:"
    echo "   $HEALTH_RESPONSE"
fi

# Summary
echo ""
echo "=============================================="
echo "✅ Deployment Complete!"
echo "=============================================="
echo ""
echo "📝 Summary:"
echo "   Function Name: $FUNCTION_NAME"
echo "   Function URL: $FUNCTION_URL"
echo "   Region: $REGION"
echo "   Schedule: Daily at 2:00 AM UTC"
echo "   Memory: 512 MB"
echo "   Timeout: 9 minutes"
echo ""
echo "🔍 Next Steps:"
echo "   1. Test with dry run:"
echo "      curl -X POST \"${FUNCTION_URL}?dry_run=true\" \\"
echo "        -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\""
echo ""
echo "   2. View logs:"
echo "      gcloud functions logs read $FUNCTION_NAME --region=$REGION --gen2 --limit=50"
echo ""
echo "   3. Trigger scheduler manually:"
echo "      gcloud scheduler jobs run $SCHEDULER_JOB_NAME --location=$REGION"
echo ""
echo "   4. Monitor in Cloud Console:"
echo "      https://console.cloud.google.com/functions/details/$REGION/$FUNCTION_NAME"
echo ""
echo "=============================================="
