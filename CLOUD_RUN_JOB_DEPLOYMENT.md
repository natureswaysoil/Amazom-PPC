# Cloud Run Job Deployment Guide

This guide explains how to deploy the Amazon PPC Optimizer as a Cloud Run Job.

## Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and configured
- Required secrets stored in Secret Manager (see main DEPLOYMENT_GUIDE.md)

## Important: Entry Point Configuration

The Amazon PPC Optimizer uses `functions-framework` with the entry point `run_optimizer`.

**Correct function target**: `run_optimizer`  
**Incorrect function target**: `run_pipeline` (does not exist)

## Deployment Options

### Option 1: Deploy with Dockerfile (Recommended)

Use the provided `Dockerfile.python` which has the correct configuration:

```bash
# Set your variables
PROJECT_ID="your-project-id"
REGION="us-central1"
JOB_NAME="amazon-ppc-optimizer"

# Deploy using Dockerfile
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

### Option 2: Deploy with Buildpacks

If deploying with buildpacks (no explicit Dockerfile), the `project.toml` file in the repository root specifies the correct function target.

```bash
# Deploy using buildpacks (project.toml will be used)
gcloud run jobs deploy $JOB_NAME \
  --source=. \
  --region=$REGION \
  --project=$PROJECT_ID \
  --max-retries=1 \
  --task-timeout=9m \
  --memory=1Gi \
  --cpu=1 \
  --set-secrets=AMAZON_CLIENT_ID=AMAZON_CLIENT_ID:latest,AMAZON_CLIENT_SECRET=AMAZON_CLIENT_SECRET:latest,AMAZON_REFRESH_TOKEN=AMAZON_REFRESH_TOKEN:latest,AMAZON_PROFILE_ID=AMAZON_PROFILE_ID:latest,DASHBOARD_API_KEY=DASHBOARD_API_KEY:latest \
  --set-env-vars="LOG_LEVEL=INFO,MIN_RUN_INTERVAL_MINUTES=120,GOOGLE_FUNCTION_TARGET=run_optimizer"
```

**Note**: The `GOOGLE_FUNCTION_TARGET=run_optimizer` environment variable ensures the correct function is targeted.

### Option 3: Deploy with Pre-built Container Image

If you have a container image already built:

```bash
# Deploy from container registry
gcloud run jobs deploy $JOB_NAME \
  --image=us-central1-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/$JOB_NAME:latest \
  --region=$REGION \
  --project=$PROJECT_ID \
  --max-retries=1 \
  --task-timeout=9m \
  --memory=1Gi \
  --cpu=1 \
  --set-secrets=AMAZON_CLIENT_ID=AMAZON_CLIENT_ID:latest,AMAZON_CLIENT_SECRET=AMAZON_CLIENT_SECRET:latest,AMAZON_REFRESH_TOKEN=AMAZON_REFRESH_TOKEN:latest,AMAZON_PROFILE_ID=AMAZON_PROFILE_ID:latest,DASHBOARD_API_KEY=DASHBOARD_API_KEY:latest \
  --set-env-vars="LOG_LEVEL=INFO,MIN_RUN_INTERVAL_MINUTES=120"
```

## Troubleshooting

### Issue: "Application exec likely failed"

This error occurs when the container cannot start properly. Common causes:

1. **Wrong function target**: The job is configured with `--target=run_pipeline` but should use `--target=run_optimizer`
   
   **Fix**: Redeploy with the correct configuration using one of the methods above.

2. **Missing dependencies**: The container is missing required Python packages.
   
   **Fix**: Ensure `requirements.txt` includes `functions-framework>=3.4.0`

3. **Missing files**: The container is missing required Python modules.
   
   **Fix**: Use `Dockerfile.python` which copies all necessary files, or ensure buildpack deployment includes all Python files.

### Verify Deployment

After deployment, execute the job to test:

```bash
gcloud run jobs execute $JOB_NAME --region=$REGION --project=$PROJECT_ID
```

Check the logs:

```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME" \
  --limit=50 \
  --format=json \
  --project=$PROJECT_ID
```

### Check Job Configuration

To verify the job configuration:

```bash
gcloud run jobs describe $JOB_NAME --region=$REGION --project=$PROJECT_ID
```

Look for the `command` and `args` fields. For buildpack deployments, you should see:
- `command: ["functions-framework"]`
- `args: ["--target=run_optimizer", "--port=8080"]`

## Recommended: Use Cloud Functions Instead

For scheduled HTTP-based workloads like the PPC Optimizer, **Cloud Functions Gen2** is recommended over Cloud Run Jobs:

- Simpler deployment
- Built-in HTTP trigger support
- Better integration with Cloud Scheduler
- Automatic scaling

See the main `DEPLOYMENT_GUIDE.md` for Cloud Functions deployment instructions.

## Files Reference

- `main.py`: Contains the `run_optimizer` function (entry point)
- `Dockerfile.python`: Production-ready Dockerfile with correct CMD
- `project.toml`: Buildpack configuration specifying function target
- `requirements.txt`: Python dependencies including functions-framework

## Support

If you continue to experience issues:

1. Check that `project.toml` exists and has `GOOGLE_FUNCTION_TARGET=run_optimizer`
2. Verify `Dockerfile.python` has `CMD exec functions-framework --target=run_optimizer --port=$PORT`
3. Ensure all Python files are copied in the Dockerfile
4. Redeploy using one of the methods above
5. Check logs for detailed error messages
