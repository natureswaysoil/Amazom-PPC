#!/bin/bash
# Deploy Dashboard to Google Cloud Run

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"nature-way-soils"}
REGION=${REGION:-"us-east4"}
SERVICE_NAME=${SERVICE_NAME:-"ppc-dashboard"}
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "================================"
echo "Dashboard Deployment to Cloud Run"
echo "================================"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI is not installed"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set the project
echo "Setting GCP project..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable bigquery.googleapis.com

# Build the container
echo ""
echo "Building container image..."
cd "$(dirname "$0")"

# Create a temporary build directory
BUILD_DIR=$(mktemp -d)
cp -r . ${BUILD_DIR}/
cp ../gcp_credentials.py ${BUILD_DIR}/

# Update Dockerfile to copy from current directory
cat > ${BUILD_DIR}/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy gcp_credentials.py
COPY gcp_credentials.py .

# Copy dashboard application
COPY app.py .
COPY templates templates/
COPY static static/

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "app:app"]
EOF

# Build with Cloud Build
gcloud builds submit --tag ${IMAGE_NAME} ${BUILD_DIR}

# Clean up temp directory
rm -rf ${BUILD_DIR}

# Deploy to Cloud Run
echo ""
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},BIGQUERY_DATASET=amazon_ppc"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format='value(status.url)')

echo ""
echo "================================"
echo "Deployment Complete!"
echo "================================"
echo "Dashboard URL: ${SERVICE_URL}"
echo ""
echo "You can now access your dashboard at the URL above."
echo ""
echo "To view logs:"
echo "  gcloud logs tail --project=${PROJECT_ID} --service=${SERVICE_NAME}"
echo ""
