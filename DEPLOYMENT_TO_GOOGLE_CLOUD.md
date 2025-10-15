# Deployment Guide: Amazon PPC Optimizer to Google Cloud Functions

This guide covers deploying the Amazon PPC Optimizer to Google Cloud Functions after fixing the app functionality issues.

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and configured
3. **Valid Amazon Advertising API credentials**
4. **Project configured** on Google Cloud Platform

## Step 1: Prepare Your Local Environment

```bash
# Install Google Cloud SDK if not already installed
# Visit: https://cloud.google.com/sdk/docs/install

# Authenticate with Google Cloud
gcloud auth login

# Set your project ID
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

## Step 2: Verify Your Code

The recent fix in PR #5 resolved the MockRequest class issue. Verify the code works locally:

```bash
# Navigate to your repository
cd /path/to/Amazom-PPC

# Install dependencies
pip install -r requirements.txt

# Test locally (will fail on network but validates code structure)
python main.py
```

Expected output:
```
INFO - Valid Cloud Scheduler request from job: local-test
INFO - === Amazon PPC Optimizer Started at [timestamp] ===
INFO - Loading config from [path]/config.json
INFO - Environment variables set for optimizer
INFO - ✓ All required credentials present
```

## Step 3: Configure Credentials

You have two options for managing credentials:

### Option A: Environment Variables (Recommended for Production)

Create a JSON configuration and set it as an environment variable during deployment:

```bash
# Create a single-line JSON config (remove newlines)
PPC_CONFIG='{"amazon_api":{"client_id":"amzn1.application-oa2-client.xxxxx","client_secret":"amzn1.oa2-cs.v1.xxxxx","refresh_token":"Atzr|IwEBIxxxxx","profile_id":"1780498399290938","region":"NA"},"dashboard":{"url":"https://ppc-dashboard.abacusai.app"},"bid_optimization":{...}}'
```

Runtime overrides can be layered on top without redeploying by setting:

- `PPC_CONFIG_PATH` – path to a mounted YAML/JSON config file
- `AMAZON_PROFILE_ID`/`PPC_PROFILE_ID` – alternate profile scopes
- `PPC_DRY_RUN`, `PPC_FEATURES` – adjust behaviour for scheduled or manual triggers
- `PPC_VERIFY_CONNECTION`, `PPC_VERIFY_SAMPLE_SIZE` – configure the verification helper exposed by `run_optimizer`

### Option B: config.json File (For Testing)

Use the config.json file in the repository (ensure credentials are valid):

```json
{
  "amazon_api": {
    "region": "NA",
    "profile_id": "1780498399290938",
    "client_id": "amzn1.application-oa2-client.xxxxx",
    "client_secret": "amzn1.oa2-cs.v1.xxxxx",
    "refresh_token": "Atzr|IwEBIxxxxx"
  },
  "dashboard": {
    "url": "https://ppc-dashboard.abacusai.app"
  },
  "email_notifications": {
    "enabled": false
  },
  "features": {
    "enabled": ["bid_optimization", "dayparting", "campaign_management"]
  }
}
```

## Step 4: Deploy to Google Cloud Functions

### Basic Deployment

```bash
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --memory=512MB \
  --timeout=540s
```

### Deployment with Environment Variables

```bash
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --memory=512MB \
  --timeout=540s \
  --set-env-vars="PPC_CONFIG=${PPC_CONFIG}"
```

### Parameters Explained:
- `--gen2`: Uses 2nd generation Cloud Functions
- `--runtime=python311`: Python 3.11 runtime
- `--region=us-central1`: Deployment region (change as needed)
- `--entry-point=run_optimizer`: Function name in main.py
- `--trigger-http`: HTTP-triggered function
- `--no-allow-unauthenticated`: Requires authentication (recommended)
- `--memory=512MB`: Memory allocation (adjust based on needs)
- `--timeout=540s`: Maximum execution time (9 minutes)

> **Important**: Gen2 Cloud Functions use Cloud Run URLs (format: `https://FUNCTION_NAME-HASH-REGION.a.run.app`).
> The URL is NOT in the Gen1 format `https://REGION-PROJECT.cloudfunctions.net/FUNCTION_NAME`.
> After deployment, retrieve the actual URL with:
> ```bash
> gcloud functions describe amazon-ppc-optimizer --region=us-central1 --gen2 --format='value(serviceConfig.uri)'
> ```

## Step 5: Set Up Cloud Scheduler

Create a scheduled job to run the optimizer periodically:

```bash
# Create a service account for Cloud Scheduler
gcloud iam service-accounts create ppc-optimizer-scheduler \
  --display-name="PPC Optimizer Scheduler"

# Get the function URL
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)')

# Grant the service account permission to invoke the function
gcloud functions add-invoker-policy-binding amazon-ppc-optimizer \
  --region=us-central1 \
  --member="serviceAccount:ppc-optimizer-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com"

# Create Cloud Scheduler job (runs daily at 2 AM)
gcloud scheduler jobs create http ppc-optimizer-daily \
  --location=us-central1 \
  --schedule="0 2 * * *" \
  --uri="${FUNCTION_URL}" \
  --http-method=POST \
  --oidc-service-account-email="ppc-optimizer-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --oidc-token-audience="${FUNCTION_URL}"
```

### Schedule Examples:
- Daily at 2 AM: `"0 2 * * *"`
- Every 6 hours: `"0 */6 * * *"`
- Twice daily (6 AM, 6 PM): `"0 6,18 * * *"`
- Weekdays only at 8 AM: `"0 8 * * 1-5"`

## Step 6: Verify Deployment

### Get the Function URL

Gen2 Cloud Functions use Cloud Run URLs. Get your function's URL:

```bash
# Get the function URL
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)')

echo "Function URL: ${FUNCTION_URL}"
# Example output: https://amazon-ppc-optimizer-abc123xyz-uc.a.run.app
```

> **Note**: The URL will be in the format `https://amazon-ppc-optimizer-HASH-uc.a.run.app`, NOT `https://us-central1-amazon-ppc-474902.cloudfunctions.net/amazon-ppc-optimizer`.

### Test the Health Check

```bash
# Test health check endpoint
curl "${FUNCTION_URL}?health=true" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

Expected response:
```json
{
  "status": "healthy",
  "service": "amazon-ppc-optimizer",
  "timestamp": "2025-10-14T14:50:00.000Z"
}
```

### Trigger a Test Run

```bash
# Dry run (no changes made)
curl -X POST "${FUNCTION_URL}?dry_run=true" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

### View Logs

```bash
# Stream real-time logs
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --limit=50

# Filter for errors only
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --filter="severity>=ERROR" \
  --limit=20
```

## Step 7: Monitor the Function

### View Function Details

```bash
gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2
```

### Set Up Monitoring Alerts

1. Go to **Cloud Console** → **Monitoring** → **Alerting**
2. Create alert policies for:
   - Function execution errors (> 5% error rate)
   - Function timeouts
   - Memory usage (> 90%)
   - Execution time (> 8 minutes)

### Check Scheduler Status

```bash
# List all scheduler jobs
gcloud scheduler jobs list --location=us-central1

# View specific job
gcloud scheduler jobs describe ppc-optimizer-daily \
  --location=us-central1

# Manually trigger the scheduler job
gcloud scheduler jobs run ppc-optimizer-daily \
  --location=us-central1
```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors
```
Error: HTTPSConnectionPool(host='api.amazon.com', port=443): Max retries exceeded
```

**Solution**: Verify your refresh_token is valid:
- Check the token hasn't expired
- Regenerate token from Amazon Advertising Console if needed
- Update config.json or PPC_CONFIG environment variable

#### 2. Function Timeout
```
Error: Function execution took 540001 ms, finished with status: 'timeout'
```

**Solution**:
```bash
# Increase timeout to 9 minutes
gcloud functions deploy amazon-ppc-optimizer \
  --timeout=540s \
  --update-env-vars="..." \
  [other flags...]
```

#### 3. Memory Issues
```
Error: Memory limit exceeded
```

**Solution**:
```bash
# Increase memory allocation
gcloud functions deploy amazon-ppc-optimizer \
  --memory=1024MB \
  --update-env-vars="..." \
  [other flags...]
```

#### 4. Permission Denied
```
Error: (Permission denied) Caller does not have required permission
```

**Solution**:
```bash
# Ensure service account has invoker role
gcloud functions add-invoker-policy-binding amazon-ppc-optimizer \
  --region=us-central1 \
  --member="serviceAccount:ppc-optimizer-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

## Cost Optimization

### Estimated Costs (Monthly)

For a function that runs once daily with 2-minute execution time:
- **Cloud Functions**: ~$0.50/month (512MB, 30 invocations)
- **Cloud Scheduler**: $0.10/month (1 job)
- **Cloud Logging**: ~$0.10/month
- **Total**: ~$0.70/month

### Cost Reduction Tips

1. **Use appropriate memory**: Don't over-allocate (512MB is usually sufficient)
2. **Optimize schedule**: Run less frequently if daily isn't necessary
3. **Enable dry_run**: Test changes before applying them
4. **Log selectively**: Reduce verbose logging in production

## Security Best Practices

1. **Never commit credentials**: Use environment variables or Secret Manager
2. **Use authentication**: Always deploy with `--no-allow-unauthenticated`
3. **Rotate credentials**: Regularly update API keys and tokens
4. **Monitor access**: Review Cloud Audit Logs regularly
5. **Limit permissions**: Use principle of least privilege for service accounts

## Next Steps

After successful deployment:

1. **Review PR #2, #3, #4**: Consider merging additional improvements
   - PR #2: Bug fixes (authentication, logging improvements)
   - PR #3: Performance optimizations (50-70% faster)
   - PR #4: Enhanced dashboard integration

2. **Set up monitoring**: Configure alerts for failures and anomalies

3. **Test thoroughly**: Run multiple dry runs before enabling live mode

4. **Document results**: Track optimization performance over time

## Additional Resources

- [Google Cloud Functions Documentation](https://cloud.google.com/functions/docs)
- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
- [Amazon Advertising API Guide](https://advertising.amazon.com/API/docs)
- [Repository README](./README.md)

## Support

For issues or questions:
- Check Cloud Function logs for detailed error messages
- Review the repository README and documentation files
- Contact: james@natureswaysoil.com
