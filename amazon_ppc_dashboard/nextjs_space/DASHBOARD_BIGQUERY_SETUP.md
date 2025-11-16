# Amazon PPC Dashboard - BigQuery Setup Guide

This guide will help you set up the dashboard to display live optimization data from BigQuery.

## Quick Overview

The dashboard connects to Google BigQuery to retrieve and display:
- Recent optimization runs and their results
- Campaign-level performance metrics
- Keyword optimization statistics
- Historical trends and summaries

**Setup Time:** ~5 minutes  
**Requirements:** Google Cloud service account with BigQuery access

---

## Prerequisites

Before starting, ensure you have:

1. ✅ A Google Cloud project with BigQuery enabled
2. ✅ The Amazon PPC Optimizer deployed and running
3. ✅ At least one optimization run completed (so data exists in BigQuery)
4. ✅ Access to your deployment platform (Vercel, Netlify, etc.)

---

## Step 1: Create Service Account (2 minutes)

### 1.1 Go to Google Cloud Console

Visit: https://console.cloud.google.com/iam-admin/serviceaccounts

Select your project (e.g., `amazon-ppc-474902`)

### 1.2 Create or Select Service Account

**Option A - Create New Service Account:**
1. Click "Create Service Account"
2. Name: `amazon-ppc-dashboard` (or any name you prefer)
3. Description: "Service account for Amazon PPC Dashboard BigQuery access"
4. Click "Create and Continue"

**Option B - Use Existing Service Account:**
1. Select an existing service account from the list
2. Continue to Step 1.3

### 1.3 Download JSON Key

1. Click on your service account
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Select "JSON" format
5. Click "Create"
6. Save the downloaded JSON file securely

**Important:** This JSON file contains sensitive credentials. Never commit it to version control!

---

## Step 2: Grant BigQuery Permissions (1 minute)

Your service account needs two roles to read BigQuery data:

### Via Google Cloud Console (Recommended)

1. Go to: https://console.cloud.google.com/iam-admin/iam
2. Find your service account in the list (e.g., `amazon-ppc-dashboard@...`)
3. Click the "Edit" button (pencil icon)
4. Click "Add Another Role"
5. Add these two roles:
   - **BigQuery Data Viewer** (`roles/bigquery.dataViewer`)
   - **BigQuery Job User** (`roles/bigquery.jobUser`)
6. Click "Save"

### Via gcloud CLI (Alternative)

```bash
# Set your project ID and service account email
PROJECT_ID="amazon-ppc-474902"
SERVICE_ACCOUNT_EMAIL="amazon-ppc-dashboard@amazon-ppc-474902.iam.gserviceaccount.com"

# Grant BigQuery Data Viewer role
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataViewer"

# Grant BigQuery Job User role  
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.jobUser"
```

**Note:** Permission changes may take 1-2 minutes to propagate.

---

## Step 3: Configure Dashboard Environment (2 minutes)

### 3.1 Prepare Your Credentials

You have two options for providing credentials:

#### Option A: Raw JSON (Recommended)

1. Open the downloaded service account JSON file
2. Copy the entire contents (everything from `{` to `}`)
3. The JSON should look like:
```json
{
  "type": "service_account",
  "project_id": "amazon-ppc-474902",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "amazon-ppc-dashboard@amazon-ppc-474902.iam.gserviceaccount.com",
  ...
}
```

#### Option B: Base64 Encoded (Alternative)

If raw JSON causes issues in your deployment platform:

```bash
# On macOS/Linux
cat service-account.json | base64 | tr -d '\n' > credentials-base64.txt

# The dashboard automatically detects and decodes base64 credentials
```

### 3.2 Set Environment Variables

In your deployment platform (Vercel, Netlify, Cloud Run, etc.):

#### Required Variables:

```bash
# Service Account Credentials (choose one method)
GCP_SERVICE_ACCOUNT_KEY=<paste JSON here or base64 string>

# OR use component credentials
GCP_CLIENT_EMAIL=amazon-ppc-dashboard@amazon-ppc-474902.iam.gserviceaccount.com
GCP_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
```

#### Recommended Variables:

```bash
# Google Cloud Project ID
GCP_PROJECT=amazon-ppc-474902
GOOGLE_CLOUD_PROJECT=amazon-ppc-474902

# BigQuery Configuration
BQ_DATASET_ID=amazon_ppc
BQ_LOCATION=us-east4
```

### 3.3 Deploy

After setting environment variables:

1. **Vercel:** Variables are applied on next deployment
   ```bash
   vercel --prod
   ```

2. **Cloud Run:** Redeploy with new environment
   ```bash
   gcloud run deploy amazon-ppc-dashboard \
     --set-env-vars GCP_SERVICE_ACCOUNT_KEY="$(cat service-account.json)"
   ```

3. **Other Platforms:** Follow your platform's environment variable update process

---

## Step 4: Verify Setup (1 minute)

### 4.1 Check Configuration

Visit your dashboard's config check endpoint:
```
https://your-dashboard-url.vercel.app/api/config-check
```

Look for:
- ✅ GCP credentials are configured
- ✅ Project ID is set
- ✅ No error messages

### 4.2 Test BigQuery Connection

Test the BigQuery connection directly:
```
https://your-dashboard-url.vercel.app/api/bigquery-data?table=optimization_results&limit=1
```

**Success Response:**
```json
{
  "success": true,
  "data": [...],
  "metadata": {
    "projectId": "amazon-ppc-474902",
    "datasetId": "amazon_ppc",
    "table": "optimization_results",
    "rowCount": 1
  }
}
```

**If you see errors:**
- Check `/api/setup-guide` for step-by-step diagnostics
- See troubleshooting section below

### 4.3 View Dashboard

Visit your dashboard homepage:
```
https://your-dashboard-url.vercel.app/
```

You should see:
- ✅ Optimization run statistics
- ✅ Recent optimization results table
- ✅ Performance metrics (spend, sales, ACOS)
- ✅ No error messages

---

## Troubleshooting

### Error: "Could not load Google Cloud credentials for BigQuery"

**Cause:** Credentials not properly configured or invalid

**Solutions:**
1. Verify `GCP_SERVICE_ACCOUNT_KEY` is set in environment variables
2. Check the JSON is valid: `cat service-account.json | jq .`
3. Try base64 encoding: `cat service-account.json | base64 | tr -d '\n'`
4. Ensure no extra spaces or newlines in the environment variable
5. Redeploy after changing environment variables
6. Check `/api/config-check` for detailed diagnostics

### Error: "Access Denied" or "Permission Denied"

**Cause:** Service account lacks BigQuery permissions

**Solutions:**
1. Grant `roles/bigquery.dataViewer` role to service account
2. Grant `roles/bigquery.jobUser` role to service account
3. Wait 1-2 minutes for permissions to propagate
4. Verify you're using the correct project ID
5. Check IAM permissions in Cloud Console

### Error: "Not found: Dataset/Table not found"

**Cause:** BigQuery dataset or tables don't exist yet

**Solutions:**
1. Ensure the optimizer has run at least once
2. The optimizer automatically creates tables on first run
3. Check if optimizer is configured to write to BigQuery (`bigquery.enabled: true` in config)
4. Manually create dataset/tables using provided schema (see BIGQUERY_INTEGRATION.md)

### Dashboard Shows "No optimization runs found"

**Cause:** No data in BigQuery tables

**Solutions:**
1. Trigger an optimization run from the Cloud Function
2. Verify optimizer is writing to BigQuery (check optimizer logs)
3. Query BigQuery directly to confirm data exists:
   ```sql
   SELECT * FROM `amazon-ppc-474902.amazon_ppc.optimization_results` LIMIT 10
   ```
4. Check optimizer configuration has `bigquery.enabled: true`

### Credentials Work Locally But Not on Vercel

**Cause:** File paths don't work in serverless environments

**Solutions:**
1. Use `GCP_SERVICE_ACCOUNT_KEY` with JSON content (not file path)
2. Don't use `GOOGLE_APPLICATION_CREDENTIALS` with file paths on Vercel
3. Use raw JSON or base64 encoding for credentials
4. See `.env.example` for correct format

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Amazon PPC Optimizer (Cloud Function)                       │
│  - Runs optimization on schedule                             │
│  - Writes results to BigQuery                                │
│  - Creates/updates tables automatically                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Google BigQuery                                              │
│  Dataset: amazon_ppc                                          │
│  Tables:                                                      │
│  - optimization_results (main metrics)                        │
│  - campaign_details (campaign breakdowns)                     │
│  - optimizer_run_events (run history)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Dashboard API Routes (Next.js)                               │
│  - /api/bigquery-data (fetch optimization data)              │
│  - /api/config-check (verify configuration)                  │
│  - /api/setup-guide (interactive setup assistance)           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Dashboard UI (React)                                         │
│  - Displays optimization results                             │
│  - Shows performance metrics                                 │
│  - Auto-refreshes every 5 minutes                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Environment Variables Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `GCP_SERVICE_ACCOUNT_KEY` | Service account JSON credentials | `{"type":"service_account",...}` |

### Recommended

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT` | Google Cloud project ID | `amazon-ppc-474902` |
| `GOOGLE_CLOUD_PROJECT` | Alternative project ID variable | `amazon-ppc-474902` |
| `BQ_DATASET_ID` | BigQuery dataset name | `amazon_ppc` |
| `BQ_LOCATION` | BigQuery dataset location | `us-east4` |

### Alternative Credential Methods

| Variable | Description | Notes |
|----------|-------------|-------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON | Can be JSON string or path (local only) |
| `GCP_CLIENT_EMAIL` | Service account email | Must be used with `GCP_PRIVATE_KEY` |
| `GCP_PRIVATE_KEY` | Service account private key | Escape newlines as `\n` |

---

## Helpful Commands

### Test Credentials Locally

```bash
# Verify JSON is valid
cat service-account.json | jq .

# Test credentials with gcloud
gcloud auth activate-service-account --key-file=service-account.json
gcloud auth list

# Query BigQuery
bq query --use_legacy_sql=false \
  'SELECT * FROM `amazon-ppc-474902.amazon_ppc.optimization_results` LIMIT 10'
```

### Check Dashboard Endpoints

```bash
# Health check
curl https://your-dashboard-url.vercel.app/api/health

# Configuration check
curl https://your-dashboard-url.vercel.app/api/config-check | jq .

# Setup guide
curl https://your-dashboard-url.vercel.app/api/setup-guide | jq .

# Test BigQuery data
curl https://your-dashboard-url.vercel.app/api/bigquery-data?limit=1 | jq .
```

---

## Security Best Practices

1. **Never commit service account keys to Git**
   - Add `*.json` to `.gitignore`
   - Use environment variables for credentials
   - Rotate keys periodically

2. **Use least privilege access**
   - Grant only required BigQuery roles
   - Don't use project owner/editor roles
   - Create dedicated service accounts for each service

3. **Monitor access logs**
   - Enable Cloud Audit Logs
   - Review BigQuery access patterns
   - Set up alerts for unusual activity

4. **Rotate credentials regularly**
   - Create new keys every 90 days
   - Delete old keys after migration
   - Test new keys before deleting old ones

---

## Additional Resources

- [Google Cloud Service Accounts](https://cloud.google.com/iam/docs/service-accounts)
- [BigQuery IAM Permissions](https://cloud.google.com/bigquery/docs/access-control)
- [Vercel Environment Variables](https://vercel.com/docs/projects/environment-variables)
- [Dashboard Integration Documentation](../DASHBOARD_INTEGRATION.md)
- [BigQuery Integration Guide](../../../BIGQUERY_INTEGRATION.md)

---

## Getting Help

If you're still experiencing issues:

1. Check `/api/setup-guide` for interactive diagnostics
2. Review `/api/config-check` for configuration status
3. Check optimizer logs for BigQuery write errors
4. See [TROUBLESHOOTING.md](../../../TROUBLESHOOTING.md) for common issues
5. Review [DATA_FLOW_SUMMARY.md](../../../DATA_FLOW_SUMMARY.md) for data architecture

---

**Last Updated:** November 2025  
**Version:** 2.0.0
