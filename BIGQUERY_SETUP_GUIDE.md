# BigQuery Integration Setup Guide

This guide explains how to set up BigQuery integration for the Amazon PPC Optimizer to ensure live data flows from the optimizer to BigQuery and can be accessed by the dashboard.

## Overview

The data flow is:
```
Optimizer → BigQuery → Dashboard
```

1. **Optimizer** writes optimization results to BigQuery tables
2. **Dashboard** reads from BigQuery to display analytics

## Prerequisites

### 1. Google Cloud Project
- A Google Cloud project with BigQuery API enabled
- Project ID (e.g., `amazon-ppc-474902`)

### 2. BigQuery Dataset
- Dataset ID: `amazon_ppc` (default)
- Location: `us-east4` (default)
- The dataset will be created automatically if it doesn't exist

### 3. Service Account Credentials
You need a Google Cloud service account with the following permissions:

**Required IAM Roles:**
- `roles/bigquery.dataEditor` - To create tables and write data
- `roles/bigquery.jobUser` - To run queries

**Create a Service Account:**
```bash
# Set your project ID (replace with your actual project)
export PROJECT_ID="YOUR_PROJECT_ID"

# Create service account
gcloud iam service-accounts create amazon-ppc-bigquery \
    --display-name="Amazon PPC BigQuery Service Account" \
    --project=${PROJECT_ID}

# Grant BigQuery permissions
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:amazon-ppc-bigquery@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:amazon-ppc-bigquery@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"

# Create and download key
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account=amazon-ppc-bigquery@${PROJECT_ID}.iam.gserviceaccount.com
```

## Configuration

### Method 1: Environment Variable (Recommended)

Set the `GCP_SERVICE_ACCOUNT_KEY` environment variable with the service account key:

#### Option A: Raw JSON (for local development)
```bash
export GCP_SERVICE_ACCOUNT_KEY='{"type":"service_account","project_id":"YOUR_PROJECT_ID",...}'
```

#### Option B: Base64-encoded (for CI/CD and Cloud Functions)
```bash
# Encode the service account key
cat service-account-key.json | base64 | tr -d '\n' > encoded-key.txt

# Set environment variable
export GCP_SERVICE_ACCOUNT_KEY="$(cat encoded-key.txt)"
```

#### For Google Cloud Functions/Cloud Run:
```bash
# Create secret in Secret Manager
gcloud secrets create GCP_SERVICE_ACCOUNT_KEY \
    --replication-policy="automatic" \
    --data-file=service-account-key.json

# Grant access to the secret (replace with your service account)
gcloud secrets add-iam-policy-binding GCP_SERVICE_ACCOUNT_KEY \
    --member="serviceAccount:YOUR_FUNCTION_SERVICE_ACCOUNT@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Method 2: File Path (Local development only)
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Enable BigQuery in config.json
```json
{
  "bigquery": {
    "enabled": true,
    "project_id": "YOUR_PROJECT_ID",
    "dataset_id": "amazon_ppc",
    "location": "us-east4"
  }
}
```

**Note:** Replace `YOUR_PROJECT_ID` with your actual Google Cloud project ID (e.g., `amazon-ppc-474902`).

## Testing the Setup

### 1. Test Credentials Loading
```bash
python3 test_data_flow.py
```

This will verify:
- ✓ GCP credentials can be loaded
- ✓ BigQuery client can be initialized
- ✓ Dataset is accessible
- ✓ Data can be read from BigQuery

### 2. Test Writing Data (Optional)
```bash
python3 test_data_flow.py --write-test-data
```

This will:
- Write a test optimization result to BigQuery
- Verify the data was written successfully
- Provide SQL commands to view and clean up the test data

### 3. Test Dashboard Health
Once the dashboard is running, check BigQuery connectivity:
```bash
curl http://localhost:8080/api/bigquery-health
```

Expected response when healthy:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "credentials": {
    "valid": true,
    "error": null
  },
  "bigquery": {
    "project_id": "YOUR_PROJECT_ID",
    "dataset_id": "amazon_ppc",
    "client_initialized": true,
    "dataset_accessible": true,
    "dataset_error": null,
    "optimization_results_count": 0
  }
}
```

## Running the Optimizer

### Local Testing
```bash
# Dry run (doesn't make actual changes)
python3 main.py

# With explicit config
python3 -c "from main import run_optimizer; run_optimizer(MockRequest())"
```

### Cloud Function
Trigger the function with:
```bash
# Health check
curl https://your-function-url.cloudfunctions.net?health=true

# Verify connection
curl https://your-function-url.cloudfunctions.net?verify_connection=true

# Run optimization (dry run)
curl "https://your-function-url.cloudfunctions.net?dry_run=true"

# Run optimization (live)
curl https://your-function-url.cloudfunctions.net
```

## Verifying Data Flow

### 1. Check Optimizer Logs
Look for these log messages when the optimizer runs:
```
✓ BigQuery client initialized for project YOUR_PROJECT_ID
Writing results to BigQuery...
✓ Successfully wrote optimization results to BigQuery (run_id: abc-123-def)
Successfully wrote 3 campaign details to BigQuery
```

### 2. Query BigQuery Directly
```sql
-- Replace YOUR_PROJECT_ID with your actual project ID

-- Check if data exists
SELECT COUNT(*) as total_runs
FROM `YOUR_PROJECT_ID.amazon_ppc.optimization_results`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY);

-- View recent runs
SELECT 
    timestamp,
    run_id,
    status,
    campaigns_analyzed,
    keywords_optimized,
    total_spend,
    total_sales,
    average_acos
FROM `YOUR_PROJECT_ID.amazon_ppc.optimization_results`
ORDER BY timestamp DESC
LIMIT 10;

-- Check campaign details
SELECT 
    timestamp,
    campaign_name,
    spend,
    sales,
    acos,
    clicks,
    conversions
FROM `YOUR_PROJECT_ID.amazon_ppc.campaign_details`
ORDER BY timestamp DESC
LIMIT 20;
```

### 3. Check Dashboard
Visit the dashboard and verify:
- Summary metrics are displayed
- Recent optimization runs are listed
- Campaign performance charts show data
- No "Failed to fetch" errors appear

## Troubleshooting

### Error: "Could not load Google Cloud credentials for BigQuery"

**Cause:** The dashboard or optimizer cannot find valid GCP credentials.

**Solutions:**
1. Verify `GCP_SERVICE_ACCOUNT_KEY` is set:
   ```bash
   echo $GCP_SERVICE_ACCOUNT_KEY | jq . # Should display JSON
   ```

2. Check the credentials are valid JSON:
   ```bash
   echo $GCP_SERVICE_ACCOUNT_KEY | jq .type
   # Should output: "service_account"
   ```

3. If using base64 encoding, verify it's correct:
   ```bash
   echo $GCP_SERVICE_ACCOUNT_KEY | base64 -d | jq .
   # Should display the service account JSON
   ```

4. Run the test script for detailed diagnostics:
   ```bash
   python3 test_data_flow.py
   ```

### Error: "Dataset not found"

**Cause:** The BigQuery dataset doesn't exist or is in a different location.

**Solution:**
```bash
# Create dataset manually (replace YOUR_PROJECT_ID)
bq mk --dataset \
    --location=us-east4 \
    --description="Amazon PPC Optimization Data" \
    YOUR_PROJECT_ID:amazon_ppc
```

### Error: "Permission denied"

**Cause:** Service account lacks required permissions.

**Solution:**
```bash
# Grant required roles (replace YOUR_PROJECT_ID and YOUR_SERVICE_ACCOUNT)
export PROJECT_ID="YOUR_PROJECT_ID"
export SERVICE_ACCOUNT="YOUR_SERVICE_ACCOUNT"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"
```

### No Data in Dashboard

**Possible causes:**
1. Optimizer hasn't run yet
2. BigQuery integration is disabled in config
3. Optimizer failed to write to BigQuery

**Solutions:**
1. Check optimizer logs for BigQuery write confirmations
2. Verify `bigquery.enabled: true` in config.json
3. Query BigQuery directly to check if data exists
4. Run optimizer manually and watch the logs

### Dashboard Shows Old Data

**Cause:** Data is being written but dashboard is caching results.

**Solution:**
1. Check the timestamp filter in dashboard queries
2. Clear browser cache
3. Query BigQuery directly to verify new data exists

## BigQuery Tables Schema

### optimization_results
Main table containing optimization run summaries:
- `timestamp` - When the optimization ran
- `run_id` - Unique identifier for the run
- `status` - success/failed
- `campaigns_analyzed` - Number of campaigns processed
- `keywords_optimized` - Number of keywords optimized
- `total_spend`, `total_sales`, `average_acos` - Performance metrics
- `campaigns`, `top_performers`, `features` - JSON fields with detailed data

### campaign_details
Detailed campaign-level metrics:
- `timestamp` - When the data was recorded
- `run_id` - Links to optimization_results
- `campaign_id`, `campaign_name` - Campaign identifiers
- `spend`, `sales`, `acos` - Performance metrics
- `impressions`, `clicks`, `conversions` - Engagement metrics
- `budget`, `status` - Campaign settings

### optimization_progress
Real-time progress updates during optimization:
- `timestamp` - Progress update time
- `run_id` - Links to optimization_results
- `status` - running/completed/failed
- `message` - Progress description
- `percent_complete` - 0-100%

### optimization_errors
Error logs from failed runs:
- `timestamp` - When error occurred
- `run_id` - Links to optimization_results
- `error_type`, `error_message` - Error details
- `traceback` - Full stack trace

### optimizer_run_events
Lifecycle events for optimizer runs:
- `timestamp` - Event time
- `run_id` - Run identifier
- `status` - started/completed/failed
- `details` - JSON with additional context

## Best Practices

1. **Use Secret Manager for credentials** in production (Cloud Functions/Cloud Run)
2. **Monitor BigQuery usage** to control costs
3. **Set up alerts** for failed optimizer runs
4. **Regular data retention policies** to manage storage
5. **Test credentials** before deploying to production
6. **Use dry_run mode** when testing changes

## Support

For additional help:
- Check Cloud Function logs: `gcloud functions logs read`
- Review BigQuery job history in Cloud Console
- Run diagnostics: `python3 test_data_flow.py`
- Test dashboard health: `curl /api/bigquery-health`
