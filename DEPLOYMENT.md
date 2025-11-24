# Deployment Guide - Amazon PPC Optimizer

Complete guide for deploying the Amazon PPC Optimizer to Google Cloud Functions Gen2.

## Table of Contents

- [Prerequisites](#prerequisites)
- [First-Time Setup](#first-time-setup)
- [Manual Deployment](#manual-deployment)
- [Automated Deployment (GitHub Actions)](#automated-deployment-github-actions)
- [Configuration](#configuration)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

- **gcloud CLI** (v400.0.0+): [Install Guide](https://cloud.google.com/sdk/docs/install)
- **Git**: For version control
- **Python 3.11**: For local testing (optional)

### Required GCP Permissions

Your service account needs these IAM roles:

- `roles/cloudfunctions.developer` - Deploy Cloud Functions
- `roles/iam.serviceAccountUser` - Act as service account
- `roles/secretmanager.secretAccessor` - Access secrets
- `roles/artifactregistry.writer` - Push container images (Gen2)
- `roles/logging.logWriter` - Write logs
- `roles/bigquery.dataEditor` - Write to BigQuery (if enabled)

### Amazon Advertising API Credentials

You need:

1. **Client ID** - From Amazon Advertising console
2. **Client Secret** - From Amazon Advertising console
3. **Refresh Token** - OAuth refresh token
4. **Profile ID** - Your Amazon Ads profile ID

See [ACCESS_GUIDE.md](ACCESS_GUIDE.md) for obtaining these credentials.

---

## First-Time Setup

### 1. Authenticate with Google Cloud

```bash
# Login to gcloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Verify authentication
gcloud auth list
```

### 2. Enable Required APIs

```bash
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable bigquery.googleapis.com  # If using BigQuery
```

### 3. Create Secrets in Secret Manager

```bash
# Amazon API credentials
echo -n 'YOUR_CLIENT_ID' | gcloud secrets create AMAZON_CLIENT_ID --data-file=-
echo -n 'YOUR_CLIENT_SECRET' | gcloud secrets create AMAZON_CLIENT_SECRET --data-file=-
echo -n 'YOUR_REFRESH_TOKEN' | gcloud secrets create AMAZON_REFRESH_TOKEN --data-file=-

# Dashboard API key
echo -n 'YOUR_DASHBOARD_API_KEY' | gcloud secrets create DASHBOARD_API_KEY --data-file=-

# Optional: Profile ID (can also be in config)
echo -n 'YOUR_PROFILE_ID' | gcloud secrets create AMAZON_PROFILE_ID --data-file=-
```

**Security Note**: Never commit secrets to git. Always use Secret Manager.

### 4. Grant Service Account Access to Secrets

```bash
# Get the default compute service account email
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant secret access
for SECRET in AMAZON_CLIENT_ID AMAZON_CLIENT_SECRET AMAZON_REFRESH_TOKEN DASHBOARD_API_KEY; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done
```

### 5. Verify Secrets

```bash
# List all secrets
gcloud secrets list

# Test accessing a secret
gcloud secrets versions access latest --secret=AMAZON_CLIENT_ID
```

---

## Manual Deployment

### Deploy with Script (Recommended)

```bash
# From repository root
./deploy-optimizer.sh

# With custom region
./deploy-optimizer.sh --region=us-east1

# With custom project
./deploy-optimizer.sh --project=my-project-id
```

The script will:
- ✅ Verify all required files exist
- ✅ Check that secrets are created in Secret Manager
- ✅ Deploy the function with proper configuration
- ✅ Display the function URL and test commands

### Deploy with gcloud Command (Manual)

```bash
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --region=us-central1 \
  --runtime=python311 \
  --source=. \
  --entry-point=optimizePPC \
  --trigger-http \
  --no-allow-unauthenticated \
  --min-instances=0 \
  --max-instances=3 \
  --timeout=540s \
  --memory=1024MB \
  --set-env-vars="LOG_LEVEL=INFO,MIN_RUN_INTERVAL_MINUTES=120" \
  --set-secrets="AMAZON_CLIENT_ID=projects/YOUR_PROJECT_ID/secrets/AMAZON_CLIENT_ID:latest,AMAZON_CLIENT_SECRET=projects/YOUR_PROJECT_ID/secrets/AMAZON_CLIENT_SECRET:latest,AMAZON_REFRESH_TOKEN=projects/YOUR_PROJECT_ID/secrets/AMAZON_REFRESH_TOKEN:latest,DASHBOARD_API_KEY=projects/YOUR_PROJECT_ID/secrets/DASHBOARD_API_KEY:latest" \
  --ingress-settings=all
```

### Get Function URL

```bash
gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)'
```

---

## Automated Deployment (GitHub Actions)

### Setup Workload Identity Federation (Recommended)

1. **Create Workload Identity Pool**:

```bash
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

2. **Create Workload Identity Provider**:

```bash
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

3. **Create Service Account for GitHub Actions**:

```bash
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions Deployer"
```

4. **Grant Permissions**:

```bash
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="github-actions@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudfunctions.developer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"
```

5. **Allow GitHub to impersonate service account**:

```bash
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/YOUR_GITHUB_USERNAME/Amazom-PPC"
```

### Configure GitHub Secrets

Add these secrets in GitHub: Settings → Secrets and variables → Actions

- `GCP_PROJECT_ID`: Your GCP project ID
- `GCP_WORKLOAD_IDENTITY_PROVIDER`: `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
- `GCP_SERVICE_ACCOUNT`: `github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com`

### Trigger Automatic Deployment

The GitHub Action automatically deploys when you push changes to `main` that affect:
- `main.py`
- `optimizer_core.py`
- `dashboard_client.py`
- `bigquery_client.py`
- `gcp_credentials.py`
- `requirements.txt`
- `config.json`

### Manual Workflow Trigger

1. Go to: **Actions** tab in GitHub
2. Select: **Deploy PPC Optimizer to Cloud Functions**
3. Click: **Run workflow**
4. Optional: Change region or enable dry run

---

## Configuration

### Environment Variables

Set via `--set-env-vars`:

- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR) - default: INFO
- `MIN_RUN_INTERVAL_MINUTES`: Minimum time between runs (prevents duplicate runs) - default: 120
- `PPC_CONFIG`: JSON configuration (alternative to config.json file)

### Configuration File vs Secrets

**Use Secrets for**:
- Amazon API credentials
- Dashboard API key
- Any sensitive data

**Use config.json for**:
- Feature flags
- Thresholds and tuning parameters
- Non-sensitive settings

### Update Secret Values

```bash
# Update a secret
echo -n 'NEW_VALUE' | gcloud secrets versions add SECRET_NAME --data-file=-

# View secret metadata (not value)
gcloud secrets describe SECRET_NAME

# List versions
gcloud secrets versions list SECRET_NAME
```

---

## Testing

### Health Check

```bash
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 --gen2 --format='value(serviceConfig.uri)')

curl "${FUNCTION_URL}?health=true"
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-24T...",
  "gcp_credentials_ok": true,
  "dashboard_ok": true,
  "email_ok": false,
  "environment": "cloud_function"
}
```

### Verify Amazon API Connection

```bash
curl "${FUNCTION_URL}?verify_connection=true&verify_sample_size=5"
```

Expected response:
```json
{
  "status": "success",
  "profile_id": "...",
  "campaign_count": 253,
  "sample": [...]
}
```

### Test Dry Run (Requires Authentication)

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "${FUNCTION_URL}"
```

### View Logs

```bash
# Recent logs
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=50

# Follow logs in real-time
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=50 \
  --follow

# Filter for errors
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=100 | grep ERROR
```

---

## Troubleshooting

### Deployment Fails

**Error: "Permission denied"**
```bash
# Grant yourself deployer role
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="user:YOUR_EMAIL" \
  --role="roles/cloudfunctions.developer"
```

**Error: "Secret not found"**
```bash
# Verify secret exists
gcloud secrets describe SECRET_NAME

# Create if missing
echo -n 'VALUE' | gcloud secrets create SECRET_NAME --data-file=-
```

**Error: "Service account doesn't have permission"**
```bash
# Grant secret accessor role
PROJECT_NUMBER=$(gcloud projects describe PROJECT_ID --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:${SA}" \
  --role="roles/secretmanager.secretAccessor"
```

### Runtime Errors

**401/403 from Amazon API**
- Verify credentials are correct: `gcloud secrets versions access latest --secret=AMAZON_CLIENT_ID`
- Check refresh token hasn't expired
- Confirm profile ID matches your Amazon Ads account

**Dashboard not receiving updates**
- Check `DASHBOARD_API_KEY` matches dashboard environment variable
- Verify dashboard URL in config.json is correct
- Test dashboard health: `curl https://your-dashboard.vercel.app/api/health`

**Function timeout**
- Increase timeout: `--timeout=900s` (max 540s for Gen2)
- Reduce features processed per run
- Check for slow Amazon API responses in logs

### Performance Issues

**Cold starts**
```bash
# Set minimum instances (increases cost)
gcloud functions deploy amazon-ppc-optimizer \
  --min-instances=1 \
  ... other flags ...
```

**Memory issues**
```bash
# Increase memory
gcloud functions deploy amazon-ppc-optimizer \
  --memory=2048MB \
  ... other flags ...
```

### View Detailed Metrics

```bash
# Cloud Functions metrics
gcloud logging read "resource.type=cloud_function AND resource.labels.function_name=amazon-ppc-optimizer" \
  --limit=100 \
  --format=json

# Performance metrics
gcloud monitoring time-series list \
  --filter='resource.type="cloud_function" AND resource.labels.function_name="amazon-ppc-optimizer"'
```

---

## Additional Resources

- [Cloud Functions Documentation](https://cloud.google.com/functions/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Amazon Advertising API Documentation](https://advertising.amazon.com/API/docs)

---

## Quick Reference

### Common Commands

```bash
# Deploy
./deploy-optimizer.sh

# Get URL
gcloud functions describe amazon-ppc-optimizer --region=us-central1 --gen2 --format='value(serviceConfig.uri)'

# View logs
gcloud functions logs read amazon-ppc-optimizer --region=us-central1 --limit=50

# Delete function
gcloud functions delete amazon-ppc-optimizer --region=us-central1 --gen2

# Update secret
echo -n 'NEW_VALUE' | gcloud secrets versions add SECRET_NAME --data-file=-

# Test health
curl "FUNCTION_URL?health=true"
```

### Support

For issues or questions:
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Review logs: `gcloud functions logs read amazon-ppc-optimizer --limit=100`
3. Open GitHub issue with logs and error messages

---

**Last Updated**: November 24, 2025  
**Version**: 2.0.0
