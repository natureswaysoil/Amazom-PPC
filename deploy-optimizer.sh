#!/bin/bash
set -e

# =============================================================================
# Amazon PPC Optimizer Cloud Function Deployment Script
# =============================================================================
# Deploys the optimizer as a Cloud Functions Gen2 (Cloud Run backed) HTTP function
# with secrets from Google Secret Manager and environment configuration.
#
# Prerequisites:
# - gcloud CLI authenticated: gcloud auth login
# - Project set: gcloud config set project YOUR_PROJECT_ID
# - Secrets created in Secret Manager (see DEPLOYMENT.md)
# - Service account with required permissions
#
# Usage:
#   ./deploy-optimizer.sh [--region REGION] [--project PROJECT_ID]
#
# =============================================================================

# Default configuration
DEFAULT_REGION="us-central1"
DEFAULT_FUNCTION_NAME="amazon-ppc-optimizer"
DEFAULT_RUNTIME="python311"
DEFAULT_ENTRY_POINT="optimizePPC"
DEFAULT_MEMORY="1024MB"
DEFAULT_TIMEOUT="540s"
DEFAULT_MAX_INSTANCES="3"
DEFAULT_MIN_INSTANCES="0"

# Parse command line arguments
REGION="${REGION:-$DEFAULT_REGION}"
PROJECT_ID="${PROJECT_ID}"
FUNCTION_NAME="${FUNCTION_NAME:-$DEFAULT_FUNCTION_NAME}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --region)
      REGION="$2"
      shift 2
      ;;
    --project)
      PROJECT_ID="$2"
      shift 2
      ;;
    --function-name)
      FUNCTION_NAME="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --region REGION         GCP region (default: us-central1)"
      echo "  --project PROJECT_ID    GCP project ID (uses gcloud config if not set)"
      echo "  --function-name NAME    Function name (default: amazon-ppc-optimizer)"
      echo "  --help                  Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage information"
      exit 1
      ;;
  esac
done

# Get project ID from gcloud config if not provided
if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
  if [ -z "$PROJECT_ID" ]; then
    echo "❌ ERROR: Project ID not set"
    echo "Set with: gcloud config set project YOUR_PROJECT_ID"
    echo "Or use: ./deploy-optimizer.sh --project YOUR_PROJECT_ID"
    exit 1
  fi
fi

echo "=================================================="
echo "Amazon PPC Optimizer Deployment"
echo "=================================================="
echo "Project:       $PROJECT_ID"
echo "Region:        $REGION"
echo "Function Name: $FUNCTION_NAME"
echo "Runtime:       $DEFAULT_RUNTIME"
echo "=================================================="
echo ""

# Verify required files exist
if [ ! -f "main.py" ]; then
  echo "❌ ERROR: main.py not found in current directory"
  exit 1
fi

if [ ! -f "requirements.txt" ]; then
  echo "❌ ERROR: requirements.txt not found"
  exit 1
fi

if [ ! -f "optimizer_core.py" ]; then
  echo "❌ ERROR: optimizer_core.py not found"
  exit 1
fi

if [ ! -f "dashboard_client.py" ]; then
  echo "❌ ERROR: dashboard_client.py not found"
  exit 1
fi

echo "✓ Required files found"
echo ""

# Verify secrets exist in Secret Manager
echo "Checking required secrets in Secret Manager..."
REQUIRED_SECRETS=(
  "AMAZON_CLIENT_ID"
  "AMAZON_CLIENT_SECRET"
  "AMAZON_REFRESH_TOKEN"
  "DASHBOARD_API_KEY"
)

MISSING_SECRETS=()
for SECRET in "${REQUIRED_SECRETS[@]}"; do
  if gcloud secrets describe "$SECRET" --project="$PROJECT_ID" &>/dev/null; then
    echo "  ✓ $SECRET"
  else
    echo "  ❌ $SECRET (missing)"
    MISSING_SECRETS+=("$SECRET")
  fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
  echo ""
  echo "❌ ERROR: Missing required secrets: ${MISSING_SECRETS[*]}"
  echo ""
  echo "Create secrets with:"
  for SECRET in "${MISSING_SECRETS[@]}"; do
    echo "  echo -n 'YOUR_${SECRET}_VALUE' | gcloud secrets create $SECRET --data-file=- --project=$PROJECT_ID"
  done
  echo ""
  echo "See DEPLOYMENT.md for detailed setup instructions"
  exit 1
fi

echo ""
echo "✓ All required secrets found"
echo ""

# Optional: Check for profile ID secret
if gcloud secrets describe "AMAZON_PROFILE_ID" --project="$PROJECT_ID" &>/dev/null; then
  echo "✓ Optional AMAZON_PROFILE_ID secret found"
  PROFILE_ID_SECRET=",AMAZON_PROFILE_ID=projects/$PROJECT_ID/secrets/AMAZON_PROFILE_ID:latest"
else
  echo "ℹ️  AMAZON_PROFILE_ID not in Secret Manager (will use config.json or PPC_CONFIG env)"
  PROFILE_ID_SECRET=""
fi

echo ""
echo "=================================================="
echo "Deploying Cloud Function..."
echo "=================================================="
echo ""

# Deploy function with secrets and environment variables
gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --region="$REGION" \
  --runtime="$DEFAULT_RUNTIME" \
  --source=. \
  --entry-point="$DEFAULT_ENTRY_POINT" \
  --trigger-http \
  --no-allow-unauthenticated \
  --min-instances="$DEFAULT_MIN_INSTANCES" \
  --max-instances="$DEFAULT_MAX_INSTANCES" \
  --timeout="$DEFAULT_TIMEOUT" \
  --memory="$DEFAULT_MEMORY" \
  --set-env-vars="LOG_LEVEL=INFO,MIN_RUN_INTERVAL_MINUTES=120,BQ_PERFORMANCE_DATASET_ID=${BQ_PERFORMANCE_DATASET_ID:-amazon_ppc}" \
  --set-secrets="AMAZON_CLIENT_ID=projects/$PROJECT_ID/secrets/AMAZON_CLIENT_ID:latest,AMAZON_CLIENT_SECRET=projects/$PROJECT_ID/secrets/AMAZON_CLIENT_SECRET:latest,AMAZON_REFRESH_TOKEN=projects/$PROJECT_ID/secrets/AMAZON_REFRESH_TOKEN:latest,DASHBOARD_API_KEY=projects/$PROJECT_ID/secrets/DASHBOARD_API_KEY:latest${PROFILE_ID_SECRET}" \
  --ingress-settings=all \
  --project="$PROJECT_ID"

DEPLOY_EXIT_CODE=$?

echo ""
if [ $DEPLOY_EXIT_CODE -eq 0 ]; then
  echo "=================================================="
  echo "✅ Deployment Successful!"
  echo "=================================================="
  echo ""
  
  # Get function URL
  FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --gen2 \
    --format='value(serviceConfig.uri)')
  
  echo "Function URL: $FUNCTION_URL"
  echo ""
  echo "Test commands:"
  echo "-------------"
  echo ""
  echo "# Health check:"
  echo "curl \"$FUNCTION_URL?health=true\""
  echo ""
  echo "# Verify connection:"
  echo "curl \"$FUNCTION_URL?verify_connection=true\""
  echo ""
  echo "# Dry run (requires authentication):"
  echo "curl -X POST -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" \\"
  echo "  -H \"Content-Type: application/json\" \\"
  echo "  -d '{\"dry_run\": true}' \\"
  echo "  \"$FUNCTION_URL\""
  echo ""
  echo "=================================================="
else
  echo "=================================================="
  echo "❌ Deployment Failed"
  echo "=================================================="
  echo ""
  echo "Check logs with:"
  echo "gcloud functions logs read $FUNCTION_NAME --region=$REGION --project=$PROJECT_ID --limit=50"
  echo ""
  exit 1
fi
