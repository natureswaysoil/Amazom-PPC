# Dashboard Deployment Guide - BigQuery Configuration

This guide provides step-by-step instructions for deploying the Amazon PPC Dashboard to Cloud Run with BigQuery connectivity.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Step-by-Step Deployment](#step-by-step-deployment)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

## Overview

The Amazon PPC Dashboard connects to BigQuery to display:
- Campaign data (266 rows)
- Keywords data (6,516 rows)
- Keyword performance metrics (2,267 rows)

**BigQuery Configuration:**
- Project: `amazon-ppc-474902`
- Dataset: `amazon_ppc_data`
- Location: `us-east4`

**Cloud Run Service:**
- Name: `ppc-dashboard-nextjs`
- Region: `us-central1`
- URL: `https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app`

## Prerequisites

### Required
- ✅ Google Cloud project with BigQuery enabled
- ✅ gcloud CLI installed and authenticated
- ✅ BigQuery dataset `amazon_ppc_data` with data
- ✅ Appropriate IAM permissions (Project Editor or Owner)

### Verify Prerequisites
```bash
# Check gcloud authentication
gcloud auth list

# Check active project
gcloud config get-value project

# Verify BigQuery dataset exists
bq show amazon-ppc-474902:amazon_ppc_data
```

## Quick Start

For experienced users, run these commands in order:

```bash
# 1. Setup service account permissions
./scripts/setup-dashboard-permissions.sh

# 2. Verify BigQuery data
./scripts/verify-bigquery-data.sh

# 3. Deploy dashboard to Cloud Run
./dashboard/deploy-dashboard-to-cloudrun.sh

# 4. Test the deployment
curl https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app/api/health
```

## Step-by-Step Deployment

### Step 1: Setup Service Account Permissions

Create a service account with BigQuery access:

```bash
cd /path/to/Amazom-PPC
./scripts/setup-dashboard-permissions.sh
```

**What this does:**
- Creates service account: `ppc-dashboard@amazon-ppc-474902.iam.gserviceaccount.com`
- Grants `roles/bigquery.dataViewer` - Read BigQuery data
- Grants `roles/bigquery.jobUser` - Execute BigQuery queries

**Expected Output:**
```
✅ Service account already exists: ppc-dashboard@amazon-ppc-474902.iam.gserviceaccount.com
✅ Granted roles/bigquery.dataViewer
✅ Granted roles/bigquery.jobUser
✅ Service account is properly configured with all required permissions
```

**Optional:** Create service account key for local development:
```bash
CREATE_KEY=true ./scripts/setup-dashboard-permissions.sh
```

### Step 2: Verify BigQuery Data

Confirm that data exists in BigQuery:

```bash
./scripts/verify-bigquery-data.sh
```

**What this does:**
- Connects to BigQuery dataset `amazon_ppc_data`
- Queries each table for row counts
- Displays sample data from each table
- Verifies service account permissions

**Expected Output:**
```
✅ Dataset 'amazon_ppc_data' found

Campaigns Table - Row Count
+-------+
| count |
+-------+
|   266 |
+-------+

Keywords Table - Row Count
+-------+
| count |
+-------+
|  6516 |
+-------+

Keyword Performance Table - Row Count
+-------+
| count |
+-------+
|  2267 |
+-------+
```

**If verification fails:**
- Check that you're using the correct project ID
- Verify BigQuery dataset exists: https://console.cloud.google.com/bigquery
- Confirm data sync from optimizer is working

### Step 3: Deploy Dashboard to Cloud Run

Deploy the Next.js dashboard with BigQuery configuration:

```bash
./dashboard/deploy-dashboard-to-cloudrun.sh
```

**What this does:**
- Builds Next.js dashboard from source
- Configures environment variables:
  - `GCP_PROJECT=amazon-ppc-474902`
  - `BIGQUERY_DATASET=amazon_ppc_data`
  - `BIGQUERY_LOCATION=us-east4`
  - `NEXT_PUBLIC_API_URL=https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app`
- Deploys to Cloud Run region `us-central1`
- Configures service with 512Mi memory, 1 CPU
- Sets up secret access for `DASHBOARD_API_KEY` (if exists)

**Deployment time:** 3-5 minutes

**Expected Output:**
```
Deploying to Cloud Run (this may take 3-5 minutes)...
✓ Deploying... Done.
✓ Creating Revision...
✓ Routing traffic...
Done.
Service [ppc-dashboard-nextjs] revision [ppc-dashboard-nextjs-00001] has been deployed.
```

**Environment Variables Set:**
```bash
GCP_PROJECT=amazon-ppc-474902
GOOGLE_CLOUD_PROJECT=amazon-ppc-474902
BIGQUERY_DATASET=amazon_ppc_data
BQ_DATASET_ID=amazon_ppc_data
BIGQUERY_LOCATION=us-east4
BQ_LOCATION=us-east4
NEXT_PUBLIC_API_URL=https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app
NEXT_PUBLIC_GCP_PROJECT=amazon-ppc-474902
NEXT_PUBLIC_BIGQUERY_DATASET=amazon_ppc_data
NEXT_PUBLIC_BIGQUERY_LOCATION=us-east4
```

### Step 4: Verify Deployment

Test that the dashboard can connect to BigQuery:

```bash
# Health check
curl https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app/api/health

# Configuration check
curl https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app/api/config-check | jq .

# Test BigQuery connection - Campaigns
curl "https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app/api/bigquery-data?table=campaigns&limit=5" | jq .

# Test BigQuery connection - Keywords
curl "https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app/api/bigquery-data?table=keywords&limit=5" | jq .

# Test BigQuery connection - Performance
curl "https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app/api/bigquery-data?table=keyword_performance&limit=5" | jq .
```

**Expected Response (campaigns):**
```json
{
  "ok": true,
  "projectId": "amazon-ppc-474902",
  "datasetId": "amazon_ppc_data",
  "location": "us-east4",
  "table": "campaigns",
  "rowCount": 5,
  "rows": [
    { "campaignId": "...", "name": "...", ... }
  ]
}
```

## Verification

### 1. Web Browser Test
Open the dashboard in your browser:
```
https://ppc-dashboard-nextjs-1009540130231.us-central1.run.app
```

You should see:
- ✅ Dashboard loads successfully
- ✅ Campaign data displays correctly
- ✅ Keywords data displays correctly
- ✅ Performance metrics are visible

### 2. Cloud Console Verification

**Cloud Run Service:**
https://console.cloud.google.com/run/detail/us-central1/ppc-dashboard-nextjs

Verify:
- ✅ Service is deployed and serving traffic
- ✅ Latest revision is active
- ✅ No error logs in recent deployments

**BigQuery Dataset:**
https://console.cloud.google.com/bigquery?project=amazon-ppc-474902&ws=!1m4!1m3!3m2!1samazon-ppc-474902!2samazon_ppc_data

Verify:
- ✅ Dataset exists in `us-east4`
- ✅ Tables: `campaigns`, `keywords`, `keyword_performance`
- ✅ Data is present in all tables

### 3. Service Account Verification

Check service account permissions:
```bash
# View service account
gcloud iam service-accounts describe ppc-dashboard@amazon-ppc-474902.iam.gserviceaccount.com

# View IAM roles
gcloud projects get-iam-policy amazon-ppc-474902 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:ppc-dashboard@amazon-ppc-474902.iam.gserviceaccount.com" \
  --format="table(bindings.role)"
```

Expected roles:
- ✅ `roles/bigquery.dataViewer`
- ✅ `roles/bigquery.jobUser`

## Troubleshooting

### Issue: "Not found: Dataset"

**Symptoms:**
```json
{
  "error": "Dataset or table not found in BigQuery",
  "message": "Not found: Dataset amazon-ppc-474902:amazon_ppc_data"
}
```

**Solution:**
1. Verify dataset exists:
   ```bash
   bq show amazon-ppc-474902:amazon_ppc_data
   ```
2. Check dataset location matches `us-east4`
3. Verify project ID is correct: `amazon-ppc-474902`

### Issue: "Permission denied"

**Symptoms:**
```json
{
  "error": "Failed to query BigQuery",
  "message": "Permission denied on dataset"
}
```

**Solution:**
1. Re-run permissions setup:
   ```bash
   ./scripts/setup-dashboard-permissions.sh
   ```
2. Verify service account has roles:
   ```bash
   gcloud projects get-iam-policy amazon-ppc-474902 \
     --filter="bindings.members:serviceAccount:ppc-dashboard*"
   ```
3. Wait 1-2 minutes for IAM changes to propagate

### Issue: "Failed to resolve GCP credentials"

**Symptoms:**
Dashboard can't authenticate with BigQuery in Cloud Run.

**Solution:**
1. Check Cloud Run service account:
   ```bash
   gcloud run services describe ppc-dashboard-nextjs \
     --region us-central1 \
     --format="value(spec.template.spec.serviceAccountName)"
   ```
2. If using custom service account, redeploy with:
   ```bash
   # Add to deployment script
   --service-account=ppc-dashboard@amazon-ppc-474902.iam.gserviceaccount.com
   ```

### Issue: Empty or no data displayed

**Symptoms:**
Dashboard loads but shows no data or empty tables.

**Solution:**
1. Verify data exists in BigQuery:
   ```bash
   ./scripts/verify-bigquery-data.sh
   ```
2. Check optimizer is syncing data to BigQuery
3. Verify table names match expected schema

### Issue: Deployment fails

**Symptoms:**
```
ERROR: (gcloud.run.deploy) PERMISSION_DENIED
```

**Solution:**
1. Verify you have sufficient permissions:
   ```bash
   gcloud projects get-iam-policy amazon-ppc-474902 \
     --filter="bindings.members:user:$(gcloud config get-value account)"
   ```
2. Required roles: `roles/editor` or `roles/owner`
3. Enable required APIs:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com
   ```

### Viewing Logs

**Cloud Run Logs:**
```bash
# Recent logs
gcloud run services logs read ppc-dashboard-nextjs \
  --region us-central1 \
  --limit 50

# Follow logs in real-time
gcloud run services logs tail ppc-dashboard-nextjs \
  --region us-central1
```

**BigQuery Query Logs:**
View in Cloud Console:
https://console.cloud.google.com/bigquery?project=amazon-ppc-474902&ws=!1m5!1m4!4m3!1samazon-ppc-474902!2sbquxjob_*

## Advanced Configuration

### Custom Environment Variables

To customize deployment, set environment variables before running the script:

```bash
# Use different project
PROJECT_ID=my-project ./dashboard/deploy-dashboard-to-cloudrun.sh

# Use different region
REGION=us-east1 ./dashboard/deploy-dashboard-to-cloudrun.sh

# Use different service name
SERVICE_NAME=my-dashboard ./dashboard/deploy-dashboard-to-cloudrun.sh

# Use different dataset
BIGQUERY_DATASET=my_dataset ./dashboard/deploy-dashboard-to-cloudrun.sh
```

### Using a Custom Service Account

Deploy with a specific service account:

```bash
# Edit the deployment script and add:
--service-account=ppc-dashboard@amazon-ppc-474902.iam.gserviceaccount.com
```

### Local Development

For local development with BigQuery:

1. Create service account key:
   ```bash
   CREATE_KEY=true ./scripts/setup-dashboard-permissions.sh
   ```

2. Set environment variables:
   ```bash
   export GCP_SERVICE_ACCOUNT_KEY=$(cat ppc-dashboard-service-account-key.json)
   export GCP_PROJECT=amazon-ppc-474902
   export BIGQUERY_DATASET=amazon_ppc_data
   export BIGQUERY_LOCATION=us-east4
   ```

3. Run locally:
   ```bash
   cd amazon_ppc_dashboard/nextjs_space
   npm install
   npm run dev
   ```

4. Test at: http://localhost:3000

### Updating the Dashboard

To update the dashboard after code changes:

```bash
# Simply re-run the deployment script
./dashboard/deploy-dashboard-to-cloudrun.sh
```

Cloud Run will automatically build and deploy the new version.

## Support Resources

### Documentation Links
- [BigQuery Setup Guide](../BIGQUERY_SETUP_GUIDE.md)
- [Dashboard Integration](../DASHBOARD_INTEGRATION.md)
- [Main README](../README.md)

### Cloud Console Links
- [Cloud Run Dashboard](https://console.cloud.google.com/run?project=amazon-ppc-474902)
- [BigQuery Console](https://console.cloud.google.com/bigquery?project=amazon-ppc-474902)
- [IAM & Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts?project=amazon-ppc-474902)
- [Secret Manager](https://console.cloud.google.com/security/secret-manager?project=amazon-ppc-474902)

### Useful Commands

```bash
# Check Cloud Run service status
gcloud run services describe ppc-dashboard-nextjs --region us-central1

# Update environment variables
gcloud run services update ppc-dashboard-nextjs \
  --region us-central1 \
  --set-env-vars "NEW_VAR=value"

# View all environment variables
gcloud run services describe ppc-dashboard-nextjs \
  --region us-central1 \
  --format="value(spec.template.spec.containers[0].env)"

# Delete service
gcloud run services delete ppc-dashboard-nextjs --region us-central1
```

---

## Success Criteria

Your deployment is successful when:

- ✅ Scripts run without errors
- ✅ Service account has proper permissions
- ✅ Dashboard deploys to Cloud Run
- ✅ BigQuery queries return data
- ✅ Dashboard displays campaigns, keywords, and performance data
- ✅ No errors in Cloud Run logs

If all criteria are met, your dashboard is ready to use! 🎉
