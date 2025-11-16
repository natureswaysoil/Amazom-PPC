# Dashboard BigQuery Integration Setup Guide

## Overview

This guide explains how to connect the Amazon PPC Dashboard to BigQuery so it can display live optimization data.

### Architecture

```
┌─────────────────┐         ┌─────────────┐         ┌──────────────────┐
│  PPC Optimizer  │────────▶│  BigQuery   │◀────────│  Next.js         │
│ (Cloud Function)│         │  (Data      │         │  Dashboard       │
│                 │         │   Storage)  │         │  (Vercel)        │
└─────────────────┘         └─────────────┘         └──────────────────┘
      Writes data                Stores data            Queries data
```

**Data Flow:**
1. **Optimizer** runs optimization and collects metrics
2. **Optimizer** writes results to BigQuery tables
3. **Dashboard** queries BigQuery to display data
4. **User** views live data in the dashboard UI

## Prerequisites

- [ ] Google Cloud project with billing enabled
- [ ] Service account with BigQuery permissions
- [ ] Optimizer deployed to Google Cloud Functions
- [ ] Dashboard deployed to Vercel (or similar platform)

## Step 1: Create Service Account & Download Key

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **IAM & Admin** → **Service Accounts**
3. Click **Create Service Account**
   - Name: `ppc-dashboard-bigquery`
   - Description: `Service account for PPC Dashboard to query BigQuery`
4. Click **Create and Continue**
5. Grant roles:
   - `BigQuery Data Viewer` (to read data)
   - `BigQuery Job User` (to run queries)
6. Click **Continue** → **Done**
7. Find the new service account in the list and click on it
8. Go to the **Keys** tab
9. Click **Add Key** → **Create new key**
10. Choose **JSON** format
11. Click **Create** → The key file downloads automatically

**Save this file securely!** It contains sensitive credentials.

## Step 2: Verify the Service Account Key

Before using the key, verify it's valid JSON:

```bash
# Test that the file is valid JSON
cat service-account.json | jq .

# You should see formatted JSON output with these fields:
# - type: "service_account"
# - project_id: "your-project-id"
# - private_key_id: "abc123..."
# - private_key: "-----BEGIN PRIVATE KEY-----\n..."
# - client_email: "ppc-dashboard-bigquery@..."
```

## Step 3: Configure Dashboard Environment Variables

### Option A: Raw JSON (Recommended)

Set `GCP_SERVICE_ACCOUNT_KEY` to the **entire contents** of the JSON file:

**For Vercel:**
1. Go to your Vercel project → **Settings** → **Environment Variables**
2. Add a new variable:
   - **Name:** `GCP_SERVICE_ACCOUNT_KEY`
   - **Value:** Paste the entire JSON file contents (no modifications!)
   - **Environments:** Production, Preview, Development
3. Click **Save**
4. Redeploy your dashboard

**For other platforms:**
```bash
export GCP_SERVICE_ACCOUNT_KEY='{"type":"service_account","project_id":"...","private_key":"...","client_email":"..."}'
```

### Option B: Base64 Encoding (Alternative)

Some platforms have issues with special characters. Use base64 encoding:

```bash
# Encode the service account key to base64 (no line breaks)
cat service-account.json | base64 | tr -d '\n' > service-account-b64.txt

# Copy the contents of service-account-b64.txt
cat service-account-b64.txt

# Set as environment variable
export GCP_SERVICE_ACCOUNT_KEY="<paste-base64-here>"
```

**Important:** Use `tr -d '\n'` to remove line breaks from base64 output.

## Step 4: Set Additional Environment Variables

Set these environment variables in your dashboard deployment:

```bash
# Google Cloud project ID
GCP_PROJECT=your-project-id
GOOGLE_CLOUD_PROJECT=your-project-id

# BigQuery configuration
BQ_DATASET_ID=amazon_ppc        # Default dataset name
BQ_LOCATION=us-east4            # Default location

# Dashboard API key (must match optimizer)
DASHBOARD_API_KEY=your-secret-key-here
```

## Step 5: Verify Configuration

Visit the diagnostic endpoints to verify everything is configured correctly:

### Test 1: Credentials Debug

```bash
# Visit this endpoint in your browser or curl
curl https://your-dashboard.vercel.app/api/credentials-debug
```

**Expected output:**
```json
{
  "status": "ok",
  "message": "Valid GCP credentials detected",
  "diagnostics": [
    "✅ GCP_SERVICE_ACCOUNT_KEY: Valid service account JSON detected"
  ]
}
```

### Test 2: Config Check

```bash
curl https://your-dashboard.vercel.app/api/config-check
```

**Expected output:**
```json
{
  "status": "ok",
  "message": "Configuration appears correct",
  "checks": {
    "configuration": {
      "gcp_project": { "set": true },
      "credentials": {
        "gcp_service_account_key": {
          "set": true,
          "valid_json": true,
          "has_required_fields": true
        }
      }
    }
  }
}
```

### Test 3: BigQuery Connection

```bash
curl https://your-dashboard.vercel.app/api/bigquery-data?table=optimization_results&limit=1
```

**Expected output:**
```json
{
  "success": true,
  "data": [
    {
      "timestamp": "2024-01-15T10:30:00.000Z",
      "run_id": "abc-123-def",
      "campaigns_analyzed": 10,
      "keywords_optimized": 50
    }
  ],
  "metadata": {
    "projectId": "your-project-id",
    "datasetId": "amazon_ppc",
    "table": "optimization_results",
    "rowCount": 1
  }
}
```

## Step 6: Ensure Optimizer Writes to BigQuery

Verify the optimizer is configured to write to BigQuery:

### Check Optimizer Configuration

In your Cloud Function environment variables or config file:

```json
{
  "bigquery": {
    "enabled": true,
    "project_id": "your-project-id",
    "dataset_id": "amazon_ppc",
    "location": "us-east4"
  }
}
```

### Run a Test Optimization

Trigger the optimizer with dry_run mode:

```bash
# Get your Cloud Function URL
FUNCTION_URL="https://your-function-url"

# Get authentication token
TOKEN=$(gcloud auth print-identity-token)

# Run optimization in dry_run mode
curl -X POST "$FUNCTION_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

### Verify Data in BigQuery

Check that data was written to BigQuery:

```bash
# List tables in the dataset
bq ls your-project-id:amazon_ppc

# Query the latest results
bq query --use_legacy_sql=false \
  'SELECT timestamp, run_id, campaigns_analyzed, keywords_optimized 
   FROM `your-project-id.amazon_ppc.optimization_results` 
   ORDER BY timestamp DESC 
   LIMIT 5'
```

## Troubleshooting

### Issue: "GCP_SERVICE_ACCOUNT_KEY was successfully base64 decoded but does not contain valid JSON"

**Cause:** The base64 string decodes to something that's not valid JSON.

**Solution:**
1. Verify your source JSON is valid:
   ```bash
   cat service-account.json | jq .
   ```

2. Re-encode properly:
   ```bash
   cat service-account.json | base64 | tr -d '\n' > encoded.txt
   ```

3. Test locally:
   ```bash
   # Decode and parse to verify
   cat encoded.txt | base64 -d | jq .
   ```

4. **Recommended:** Use raw JSON instead of base64:
   - Copy the entire JSON file contents
   - Paste directly into `GCP_SERVICE_ACCOUNT_KEY`
   - No encoding needed!

### Issue: "No Google Cloud credentials configured"

**Cause:** Environment variable not set or not detected.

**Solution:**
1. Check variable name: Must be exactly `GCP_SERVICE_ACCOUNT_KEY`
2. Verify value is set: Visit `/api/credentials-debug`
3. Ensure no trailing spaces or newlines
4. Redeploy after setting the variable

### Issue: "Access Denied" or "bigquery.jobs.create permission"

**Cause:** Service account lacks required BigQuery permissions.

**Solution:**
```bash
# Get service account email from your credentials
SA_EMAIL="ppc-dashboard-bigquery@your-project.iam.gserviceaccount.com"

# Grant required roles
gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.jobUser"
```

### Issue: "Dataset not found" or "Table not found"

**Cause:** BigQuery tables haven't been created yet.

**Solution:**
1. Ensure optimizer has run at least once
2. Run setup script:
   ```bash
   ./setup-bigquery.sh your-project-id amazon_ppc us-east4
   ```
3. Verify tables exist:
   ```bash
   bq ls your-project-id:amazon_ppc
   ```

### Issue: Dashboard shows "Loading..." but no data appears

**Possible causes:**
1. **No data in BigQuery:**
   - Run optimizer at least once
   - Check BigQuery tables have data

2. **Permissions issue:**
   - Check service account has BigQuery roles
   - Visit `/api/credentials-debug` to verify

3. **Wrong project/dataset:**
   - Verify `GCP_PROJECT` matches your actual project
   - Verify `BQ_DATASET_ID` matches where optimizer writes

4. **Dashboard not querying:**
   - Check browser console for errors
   - Test API endpoint directly: `/api/bigquery-data`

## Testing the Complete Flow

### 1. Test Optimizer → BigQuery

```bash
# Trigger optimizer
curl -X POST "$FUNCTION_URL" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d '{"dry_run": true}'

# Verify data was written
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as count FROM `your-project-id.amazon_ppc.optimization_results`'
```

### 2. Test Dashboard → BigQuery

```bash
# Test dashboard can query BigQuery
curl https://your-dashboard.vercel.app/api/bigquery-data?table=optimization_results&limit=1
```

### 3. Test Complete End-to-End

1. Open dashboard in browser: `https://your-dashboard.vercel.app`
2. You should see optimization data displayed
3. Check that data is recent (matches last optimizer run)
4. Verify metrics are accurate

## Security Best Practices

- ✅ **DO** store credentials in secret management (Vercel Environment Variables, Secret Manager)
- ✅ **DO** use separate service accounts for dev/staging/prod
- ✅ **DO** grant minimum required permissions (Data Viewer + Job User)
- ✅ **DO** rotate service account keys every 90 days
- ✅ **DO** monitor service account usage via Cloud Audit Logs
- ❌ **DON'T** commit credentials to Git
- ❌ **DON'T** share credentials via email/chat
- ❌ **DON'T** use Owner or Editor roles (too broad)
- ❌ **DON'T** reuse the same credentials across multiple projects

## Additional Resources

- [Google Cloud BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-for-securing-service-accounts)
- [Vercel Environment Variables](https://vercel.com/docs/concepts/projects/environment-variables)
- Repository README: `README.md` (section on GCP credentials)
- Configuration checker: `/api/config-check`
- Credentials debugger: `/api/credentials-debug`

## Support

If you're still experiencing issues:

1. Visit `/api/credentials-debug` and copy the output
2. Visit `/api/config-check` and copy the output
3. Check Cloud Function logs for errors
4. Check Vercel deployment logs
5. Verify service account has correct permissions

For more help, see:
- `BIGQUERY_INTEGRATION.md` - BigQuery setup guide
- `DASHBOARD_INTEGRATION.md` - Dashboard integration guide
- `README.md` - Main project documentation
