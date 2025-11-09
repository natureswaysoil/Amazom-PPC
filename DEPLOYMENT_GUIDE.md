
# Amazon PPC Optimizer - Deployment Guide

Complete guide for deploying the Amazon PPC Optimizer to Google Cloud Functions with automatic token refresh.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [API Credentials Setup](#api-credentials-setup)
3. [Google Cloud Setup](#google-cloud-setup)
4. [Deployment Steps](#deployment-steps)
5. [Environment Variables](#environment-variables)
6. [Scheduling](#scheduling)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software
- [gcloud CLI](https://cloud.google.com/sdk/docs/install)
- Git
- Python 3.11+

### Required Accounts
- Google Cloud account with billing enabled
- Amazon Advertising API access

## API Credentials Setup

### Amazon Advertising API

You need these credentials:

1. **Client ID**: `amzn1.application-oa2-client.xxxxx`
2. **Client Secret**: `amzn1.oa2-cs.v1.xxxxx`
3. **Refresh Token**: `Atzr|IwEBIxxxxx` (long-lived, doesn't expire)
4. **Profile ID**: Your Amazon Ads profile ID

**Important**: The access token is automatically refreshed by the optimizer using the refresh_token. You only need to provide the refresh_token, not the access_token.

### Obtaining Credentials

If you don't have these credentials:

1. Visit [Amazon Advertising API](https://advertising.amazon.com/API/docs/en-us/setting-up/overview)
2. Register your application
3. Complete OAuth authorization flow to get refresh_token
4. Get your Profile ID from Amazon Advertising Console

## Google Cloud Setup

### 1. Create a Google Cloud Project

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Create new project (or use existing)
gcloud projects create $PROJECT_ID

# Set as active project
gcloud config set project $PROJECT_ID
```

### 2. Enable Required APIs

```bash
# Enable Cloud Functions API
gcloud services enable cloudfunctions.googleapis.com

# Enable Cloud Build API
gcloud services enable cloudbuild.googleapis.com

# Enable Cloud Scheduler API (for scheduled runs)
gcloud services enable cloudscheduler.googleapis.com

# Enable Cloud Logging API
gcloud services enable logging.googleapis.com
```

### 3. Set Up Billing

Ensure billing is enabled for your project:
```bash
gcloud beta billing accounts list
gcloud beta billing projects link $PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
```

## Deployment Steps

### Prerequisites: Set Up Secret Manager (Recommended)

Before deploying, store your credentials securely in Google Secret Manager:

```bash
# Create secrets for Amazon API credentials
echo -n "YOUR_CLIENT_ID" | gcloud secrets create amazon-client-id --data-file=-
echo -n "YOUR_CLIENT_SECRET" | gcloud secrets create amazon-client-secret --data-file=-
echo -n "YOUR_REFRESH_TOKEN" | gcloud secrets create amazon-refresh-token --data-file=-

# Grant the Cloud Functions service account access to secrets
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding amazon-client-id \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding amazon-client-secret \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding amazon-refresh-token \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Method 1: Deploy with Secret Manager (RECOMMENDED - Secure)

```bash
# Clone the repository
git clone https://github.com/natureswaysoil/Amazom-PPC.git
cd Amazom-PPC

# Deploy to Cloud Functions with Secret Manager
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

# If this prints "(unset)", set your active project first:
# gcloud config set project YOUR_PROJECT_ID

gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --project="$PROJECT_ID" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --min-instances=0 \
  --max-instances=1 \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest
```

**Important**: 
- ✅ Uses `--no-allow-unauthenticated` to prevent HTTP 429 rate limiting issues
- ✅ Credentials stored securely in Secret Manager
- ✅ Requires Cloud Scheduler authentication setup (see below)

### Method 2: Deploy with Environment Variables (Development Only)

**⚠️ Warning**: This method is less secure and should only be used for development/testing.

```bash
# Deploy with environment variables
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

# If this prints "(unset)", set your active project first:
# gcloud config set project YOUR_PROJECT_ID

gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --project="$PROJECT_ID" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --min-instances=0 \
  --max-instances=1 \
  --set-env-vars AMAZON_CLIENT_ID="YOUR_CLIENT_ID",AMAZON_CLIENT_SECRET="YOUR_CLIENT_SECRET",AMAZON_REFRESH_TOKEN="YOUR_REFRESH_TOKEN"
```

**Note**: Even for development, use `--no-allow-unauthenticated` to avoid rate limiting issues.

### Deployment Parameters Explained

- `--gen2`: Use Cloud Functions 2nd generation
- `--runtime=python311`: Python 3.11 runtime
- `--region=us-central1`: Deployment region (change as needed)
- `--entry-point=run_optimizer`: Function name to call
- `--trigger-http`: HTTP trigger (for Cloud Scheduler)
- `--no-allow-unauthenticated`: **CRITICAL** - Requires authentication, prevents HTTP 429 rate limiting
- `--timeout=540s`: 9-minute timeout (optimizer may take several minutes)
- `--memory=512MB`: Allocated memory
- `--min-instances=0`: Scale to zero when not in use
- `--max-instances=1`: Only one concurrent execution
- `--set-secrets`: Mount secrets from Secret Manager (secure credential storage)

## Environment Variables

### Required Environment Variables

The optimizer requires these environment variables (set during deployment):

```bash
AMAZON_CLIENT_ID=amzn1.application-oa2-client.xxxxx
AMAZON_CLIENT_SECRET=amzn1.oa2-cs.v1.xxxxx
AMAZON_REFRESH_TOKEN=Atzr|IwEBIxxxxx
```

**OR** a single combined variable:

```bash
PPC_CONFIG='{"amazon_api": {...}, "bid_optimization": {...}}'
```

### Updating Environment Variables

To update environment variables after deployment:

```bash
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

# If this prints "(unset)", set your active project first:
# gcloud config set project YOUR_PROJECT_ID

gcloud functions deploy amazon-ppc-optimizer \
  --project="$PROJECT_ID" \
  --update-env-vars AMAZON_REFRESH_TOKEN="new_refresh_token"
```

## Scheduling

### Set Up Service Account for Cloud Scheduler

Create a service account with permission to invoke the function:

```bash
# Create service account
gcloud iam service-accounts create ppc-scheduler \
  --display-name="PPC Optimizer Scheduler"

# Grant the service account permission to invoke the function
gcloud functions add-iam-policy-binding amazon-ppc-optimizer \
  --region=us-central1 \
  --member="serviceAccount:ppc-scheduler@YOUR-PROJECT.iam.gserviceaccount.com" \
  --role="roles/cloudfunctions.invoker"
```

### Set Up Cloud Scheduler with Authentication

Run the optimizer automatically on a schedule with proper authentication:

```bash
# First, get the actual function URL (Gen2 functions use Cloud Run URLs)
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)')

# Create a Cloud Scheduler job (runs daily at 3 AM) with authentication
gcloud scheduler jobs create http amazon-ppc-optimizer-daily \
  --location=us-central1 \
  --schedule="0 3 * * *" \
  --uri="${FUNCTION_URL}" \
  --http-method=GET \
  --time-zone="America/New_York" \
  --oidc-service-account-email="ppc-scheduler@YOUR-PROJECT.iam.gserviceaccount.com" \
  --oidc-token-audience="${FUNCTION_URL}"

# For dry-run mode (testing without changes)
gcloud scheduler jobs create http amazon-ppc-optimizer-dryrun \
  --location=us-central1 \
  --schedule="0 */4 * * *" \
  --uri="${FUNCTION_URL}?dry_run=true" \
  --http-method=GET \
  --time-zone="America/New_York" \
  --oidc-service-account-email="ppc-scheduler@YOUR-PROJECT.iam.gserviceaccount.com" \
  --oidc-token-audience="${FUNCTION_URL}"
```

> **Note**: Gen2 Cloud Functions use Cloud Run URLs (format: `https://FUNCTION_NAME-HASH-REGION.a.run.app`), not the Gen1 format (`https://REGION-PROJECT.cloudfunctions.net/FUNCTION_NAME`). Always retrieve the actual URL using the `gcloud functions describe` command.

**Important**: The `--oidc-service-account-email` and `--oidc-token-audience` flags are required when the function uses `--no-allow-unauthenticated`.

### Schedule Examples

- Daily at 3 AM: `"0 3 * * *"`
- Every 6 hours: `"0 */6 * * *"`
- Twice daily (9 AM, 9 PM): `"0 9,21 * * *"`
- Weekdays only at noon: `"0 12 * * 1-5"`

### Manually Trigger

```bash
# Trigger the function manually via Cloud Scheduler
gcloud scheduler jobs run amazon-ppc-optimizer-daily --location=us-central1

# Or via authenticated curl (requires token)
# First get the function URL
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)')

curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}"
```

### Health Check Endpoint

The function includes a lightweight health check endpoint for monitoring:

```bash
# Use health check (doesn't trigger optimization)
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)')

curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?health=true"

# Response: {"status": "healthy", "service": "amazon-ppc-optimizer", "timestamp": "..."}
```

### Uptime Monitoring Best Practices

To avoid HTTP 429 errors from uptime checks:

1. **Use the health check endpoint**: Add `?health=true` to the URL
2. **Reduce check frequency**: Set interval to 5-10 minutes (not every 5-6 seconds)
3. **Configure authentication**: Ensure uptime checks use proper authentication
4. **Disable unnecessary checks**: The function is triggered by Cloud Scheduler, not continuous traffic

Example uptime check configuration:
- **URL**: `https://YOUR-FUNCTION-URL?health=true`
- **Interval**: 5 minutes
- **Timeout**: 10 seconds
- **Authentication**: Use service account with `roles/cloudfunctions.invoker`

## Monitoring

### Configure Uptime Checks (Optional)

If you want to monitor function availability, configure uptime checks properly:

```bash
# Create uptime check using health endpoint
gcloud monitoring uptime create amazon-ppc-health \
  --display-name="Amazon PPC Optimizer Health Check" \
  --resource-type=uptime-url \
  --timeout=10s \
  --check-interval=5m \
  --path="/?health=true" \
  --matcher-content="healthy"
```

**Important Notes**:
- Use `?health=true` parameter to avoid triggering optimization
- Set check interval to 5+ minutes (NOT every 5-6 seconds)
- Configure authentication if function uses `--no-allow-unauthenticated`
- Frequent checks can cause HTTP 429 rate limiting

**Alternative**: Since Cloud Scheduler triggers the function, you may not need uptime checks. Instead, monitor Cloud Scheduler job execution status.

### View Logs

```bash
# View recent logs
gcloud functions logs read amazon-ppc-optimizer --limit=50

# Follow logs in real-time
gcloud functions logs read amazon-ppc-optimizer --follow

# View logs in Cloud Console
gcloud functions describe amazon-ppc-optimizer --gen2 --region=us-central1

# Filter for errors
gcloud functions logs read amazon-ppc-optimizer --limit=50 | grep ERROR

# Check for rate limiting issues
gcloud functions logs read amazon-ppc-optimizer --limit=50 | grep "429"
```

### Key Log Messages to Monitor

- ✅ "Successfully authenticated with Amazon Ads API"
- ✅ "Optimization completed successfully"
- ✅ "Dashboard updated successfully"
- ❌ "Authentication failed"
- ❌ "Optimization failed"

### Dashboard Monitoring

Check the dashboard for results:
https://ppc-dashboard.abacusai.app

## Troubleshooting

### HTTP 429 Rate Limiting Errors

**Error**: "HTTP 429 Too Many Requests" or "Quota exceeded"

**Root Causes**:
1. Function deployed with `--allow-unauthenticated` flag
2. Uptime checks hitting the function too frequently (every 5-6 seconds)
3. No authentication protection, triggering rate limits before function executes
4. Logs show 0ms duration and 14B response size

**Solutions**:

1. **Redeploy with authentication** (CRITICAL):
   ```bash
   PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

   # If this prints "(unset)", set your active project first:
   # gcloud config set project YOUR_PROJECT_ID

   gcloud functions deploy amazon-ppc-optimizer \
     --gen2 \
     --runtime=python311 \
     --region=us-central1 \
     --project="$PROJECT_ID" \
     --source=. \
     --entry-point=run_optimizer \
     --trigger-http \
     --no-allow-unauthenticated \
     --timeout=540s \
     --memory=512MB \
     --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest
   ```

2. **Configure Cloud Scheduler with authentication**:
   - Create service account: `ppc-scheduler`
   - Grant invoker role to the service account
   - Add `--oidc-service-account-email` to scheduler job

3. **Update uptime checks**:
   - Use health check endpoint: `?health=true`
   - Reduce frequency to 5-10 minutes
   - Configure proper authentication for checks

4. **Verify the fix**:
   ```bash
   # Check recent logs - should show execution time > 0ms
   gcloud functions logs read amazon-ppc-optimizer --limit=10
   
   # Successful requests will show:
   # - "=== Amazon PPC Optimizer Started at ..."
   # - Execution duration > 0ms
   # - Response size > 14B
   ```

### Authentication Errors

**Error**: "Authentication failed"

**Solutions**:
1. Verify refresh_token is correct in Secret Manager
2. Check client_id and client_secret
3. Ensure Amazon Ads API access is still active
4. Token may have been revoked - regenerate in Amazon console
5. Check Secret Manager IAM permissions

**Error**: "Unauthorized" or "401 Forbidden"

**Solutions**:
1. Ensure Cloud Scheduler is using OIDC authentication
2. Verify service account has `roles/cloudfunctions.invoker` role
3. Check that `--oidc-token-audience` matches function URL

### Timeout Errors

**Error**: "Function timeout exceeded"

**Solutions**:
1. Increase timeout: `--timeout=900s` (15 minutes max)
2. Optimize lookback_days in config
3. Reduce number of enabled features

### Memory Errors

**Error**: "Exceeded memory limit"

**Solutions**:
1. Increase memory: `--memory=1GB`
2. Reduce lookback_days
3. Process fewer campaigns per run

### Rate Limit Errors

**Error**: "Too many requests"

**Solutions**:
- The optimizer has built-in rate limiting
- Amazon API: 10 requests/second (handled automatically)
- If errors persist, reduce frequency of scheduled runs

### Deployment Errors

**Error**: "Build failed"

**Solutions**:
1. Check requirements.txt syntax
2. Verify all files are included (.gcloudignore)
3. Ensure Python 3.11 compatibility

### Token Not Refreshing

**Issue**: "Access token expired" errors

**Check**:
1. Verify refresh_token is set correctly
2. Check logs for token refresh attempts
3. The optimizer calls `_refresh_auth_if_needed()` before each API call

## Testing

### Test Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export AMAZON_CLIENT_ID="your_client_id"
export AMAZON_CLIENT_SECRET="your_client_secret"
export AMAZON_REFRESH_TOKEN="your_refresh_token"

# Run locally
python main.py
```

### Test on Cloud (Dry Run)

```bash
# Dry run - no changes will be made
curl "https://YOUR-FUNCTION-URL?dry_run=true"
```

### Verify Token Refresh

Check logs for these messages:
```
"Successfully authenticated with Amazon Ads API"
"Access token expired, refreshing..."
```

## Cost Optimization

### Minimize Costs

1. **Use min-instances=0**: Scale to zero when not running
2. **Optimize memory**: Start with 512MB, increase only if needed
3. **Scheduled execution**: Run only when needed (e.g., once or twice daily)
4. **Timeout optimization**: Set appropriate timeout to avoid long-running failures

### Estimated Costs

- **Cloud Functions**: ~$0.01 per run (512MB, 3-5 min execution)
- **Cloud Scheduler**: $0.10/month for one job
- **Total**: ~$0.50/month for daily runs

## Security Best Practices

1. **Never commit credentials** to Git
2. **Use Secret Manager** for production (REQUIRED - see deployment instructions)
3. **Use `--no-allow-unauthenticated`** flag (prevents rate limiting and unauthorized access)
4. **Configure Cloud Scheduler authentication** with OIDC service account
5. **Rotate tokens** regularly
6. **Monitor logs** for unauthorized access attempts
7. **Use service accounts** with minimal required permissions
8. **Audit IAM policies** regularly to ensure proper access control

### Why Authentication Matters

- **Prevents HTTP 429 errors**: Authenticated functions have higher rate limits
- **Security**: Only authorized services can trigger the function
- **Cost control**: Prevents abuse and unexpected charges
- **Compliance**: Better audit trail for who/what triggered executions

## Next Steps

After successful deployment:

1. ✅ Test with dry-run mode
2. ✅ Monitor logs for first few runs
3. ✅ Check dashboard for results
4. ✅ Fine-tune optimization rules based on performance
5. ✅ Set up alerting (Cloud Monitoring)

## Support

For issues or questions:
- Check Cloud Function logs first
- Review error messages in this guide
- Contact: james@natureswaysoil.com

---

**Last Updated**: October 13, 2025
**Version**: 2.0.0
