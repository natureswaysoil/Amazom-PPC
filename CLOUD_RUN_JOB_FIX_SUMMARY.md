# Cloud Run Job Fix - Summary

## Problem

The Cloud Run Job `amazon-ppc-optimizer` in `us-central1` was failing to start with the error "Application exec likely failed". The logs showed the container was trying to execute:

```bash
functions-framework --target=run_pipeline
```

However, the function `run_pipeline` **does not exist** in the codebase.

## Root Cause

The actual entry point in `main.py` is `run_optimizer`, not `run_pipeline`. This mismatch caused the container to fail immediately on startup before any application logs could be produced.

The issue occurred because:
1. Cloud Run was deployed using buildpacks (without explicit Dockerfile)
2. No `project.toml` file existed to specify the correct function target
3. The buildpack defaulted to an incorrect or missing function target

## Solution

This fix provides **three deployment options** to ensure the correct entry point is used:

### 1. Created `project.toml` (Recommended for Buildpack Deployments)

A new file that tells Google Cloud buildpacks to use the correct function target:

```toml
[[build.env]]
name = "GOOGLE_FUNCTION_TARGET"
value = "run_optimizer"
```

This file is automatically used when deploying with `gcloud run jobs deploy --source=.`

### 2. Fixed `Dockerfile.python` (Recommended for Dockerfile Deployments)

Updated the existing Python Dockerfile to:
- Include the missing `gcp_credentials.py` file
- Explicitly specify the correct entry point: `--target=run_optimizer`

### 3. Created Comprehensive Deployment Guide

Added `CLOUD_RUN_JOB_DEPLOYMENT.md` with:
- Step-by-step deployment instructions
- Three deployment methods (Dockerfile, buildpacks, pre-built image)
- Troubleshooting section for common issues
- Verification commands

## How to Deploy the Fix

### Method 1: Redeploy with Buildpacks (Easiest)

The `project.toml` file will automatically be used:

```bash
PROJECT_ID="amazon-ppc-474902"
REGION="us-central1"
JOB_NAME="amazon-ppc-optimizer"

gcloud run jobs deploy $JOB_NAME \
  --source=. \
  --region=$REGION \
  --project=$PROJECT_ID \
  --max-retries=1 \
  --task-timeout=9m \
  --memory=1Gi \
  --cpu=1 \
  --set-secrets=AMAZON_CLIENT_ID=AMAZON_CLIENT_ID:latest,AMAZON_CLIENT_SECRET=AMAZON_CLIENT_SECRET:latest,AMAZON_REFRESH_TOKEN=AMAZON_REFRESH_TOKEN:latest,AMAZON_PROFILE_ID=AMAZON_PROFILE_ID:latest,DASHBOARD_API_KEY=DASHBOARD_API_KEY:latest \
  --set-env-vars="LOG_LEVEL=INFO,MIN_RUN_INTERVAL_MINUTES=120"
```

### Method 2: Redeploy with Dockerfile

Use the fixed Python Dockerfile:

```bash
gcloud run jobs deploy $JOB_NAME \
  --source=. \
  --dockerfile=Dockerfile.python \
  --region=$REGION \
  --project=$PROJECT_ID \
  --max-retries=1 \
  --task-timeout=9m \
  --memory=1Gi \
  --cpu=1 \
  --set-secrets=AMAZON_CLIENT_ID=AMAZON_CLIENT_ID:latest,AMAZON_CLIENT_SECRET=AMAZON_CLIENT_SECRET:latest,AMAZON_REFRESH_TOKEN=AMAZON_REFRESH_TOKEN:latest,AMAZON_PROFILE_ID=AMAZON_PROFILE_ID:latest,DASHBOARD_API_KEY=DASHBOARD_API_KEY:latest \
  --set-env-vars="LOG_LEVEL=INFO,MIN_RUN_INTERVAL_MINUTES=120"
```

### Verification

After deployment, test the job:

```bash
# Execute the job
gcloud run jobs execute $JOB_NAME --region=$REGION --project=$PROJECT_ID

# Check logs (should now show application logs, not just errors)
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME" \
  --limit=50 \
  --format=json \
  --project=$PROJECT_ID
```

## Expected Outcome

After deploying with the fix:

1. ✅ The container will start successfully
2. ✅ `functions-framework` will load the `run_optimizer` function
3. ✅ Application logs will be visible in Cloud Logging
4. ✅ The optimizer will execute and process campaigns

## Files Changed

1. **`project.toml`** (NEW) - Buildpack configuration with correct function target
2. **`Dockerfile.python`** (MODIFIED) - Added missing `gcp_credentials.py`
3. **`CLOUD_RUN_JOB_DEPLOYMENT.md`** (NEW) - Comprehensive deployment guide
4. **`README.md`** (MODIFIED) - Added reference to Cloud Run Job deployment

## Alternative: Use Cloud Functions Instead

**Note**: For HTTP-triggered scheduled workloads like the PPC Optimizer, **Cloud Functions Gen2** is actually more appropriate than Cloud Run Jobs:

- Simpler deployment model
- Built-in HTTP trigger support
- Better Cloud Scheduler integration
- Automatic scaling and cold start optimization

The existing workflows in `.github/workflows/deploy-optimizer.yml` and `.github/workflows/deploy-to-cloud.yml` already deploy to Cloud Functions with the correct entry point.

## Next Steps

1. Pull the latest changes from this PR
2. Choose a deployment method (buildpacks or Dockerfile)
3. Redeploy the Cloud Run Job using the commands above
4. Verify the job executes successfully
5. Consider migrating to Cloud Functions for better integration

## Support

For detailed troubleshooting, see:
- `CLOUD_RUN_JOB_DEPLOYMENT.md` - Cloud Run Job specific guide
- `DEPLOYMENT_GUIDE.md` - Main deployment documentation
- `COMPLETE_DEPLOYMENT_GUIDE.md` - Comprehensive setup guide
