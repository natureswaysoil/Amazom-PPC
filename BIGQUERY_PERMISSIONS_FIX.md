# BigQuery Permission Error Fix Guide

## Problem

When accessing the dashboard, you see this error:

```
⚠️ Error Loading Data:
Failed to fetch optimization results: Access Denied: Project amazon-ppc-474902: 
User does not have bigquery.jobs.create permission in project amazon-ppc-474902.
```

## Root Cause

The service account being used for BigQuery access does not have the necessary IAM roles to:
1. Read data from BigQuery datasets/tables
2. Create and run query jobs

## Solution

### Step 1: Identify Your Service Account

First, find the email address of the service account being used:

**Option A: If using Vercel/environment variables**
```bash
# View your service account credentials
echo "$GCP_SERVICE_ACCOUNT_KEY" | jq -r .client_email
```

**Option B: Check in Google Cloud Console**
1. Go to [IAM & Admin > Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts?project=amazon-ppc-474902)
2. Look for the service account name you're using (e.g., `vercel-dashboard@amazon-ppc-474902.iam.gserviceaccount.com`)

### Step 2: Grant Required Permissions

You need to grant TWO roles to your service account:

#### Method 1: Using gcloud CLI (Recommended)

Open [Google Cloud Shell](https://shell.cloud.google.com/?project=amazon-ppc-474902) and run:

```bash
# Set your project ID
PROJECT_ID="amazon-ppc-474902"

# Set your service account email (replace with your actual service account)
SERVICE_ACCOUNT_EMAIL="your-service-account@amazon-ppc-474902.iam.gserviceaccount.com"

# Grant BigQuery Data Viewer role (allows reading data)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataViewer"

# Grant BigQuery Job User role (allows running queries)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.jobUser"
```

#### Method 2: Using Google Cloud Console (Alternative)

1. Go to [IAM & Admin](https://console.cloud.google.com/iam-admin/iam?project=amazon-ppc-474902)
2. Find your service account in the principals list
3. Click the **pencil icon** (Edit) next to your service account
4. Click **"+ ADD ANOTHER ROLE"**
5. Add these two roles:
   - **BigQuery Data Viewer** (`roles/bigquery.dataViewer`)
   - **BigQuery Job User** (`roles/bigquery.jobUser`)
6. Click **"SAVE"**

### Step 3: Verify Permissions

Check that the permissions were granted successfully:

```bash
# View all IAM roles for your service account
gcloud projects get-iam-policy amazon-ppc-474902 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL" \
  --format="table(bindings.role)"
```

You should see both:
- `roles/bigquery.dataViewer` (or `roles/bigquery.dataEditor`)
- `roles/bigquery.jobUser`

### Step 4: Test the Fix

1. Wait 1-2 minutes for IAM changes to propagate
2. Refresh your dashboard page
3. The error should be resolved and data should load

## Understanding the Roles

### BigQuery Data Viewer (`roles/bigquery.dataViewer`)
- **What it does**: Allows reading data from BigQuery datasets and tables
- **Permissions included**: 
  - `bigquery.datasets.get`
  - `bigquery.tables.get`
  - `bigquery.tables.getData`
  - `bigquery.tables.list`

### BigQuery Job User (`roles/bigquery.jobUser`)
- **What it does**: Allows creating and running query jobs
- **Permissions included**:
  - `bigquery.jobs.create` ⭐ (This is the missing permission!)
  - `bigquery.jobs.get`
  - `bigquery.jobs.list`

> **Note**: Without `roles/bigquery.jobUser`, the service account can see the data but cannot execute queries to retrieve it.

## Alternative: Using BigQuery Data Editor

If you also need to write data to BigQuery (for optimization results), use:

```bash
# Grant BigQuery Data Editor instead of Data Viewer
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataEditor"

# Still need Job User for queries
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.jobUser"
```

**BigQuery Data Editor** includes all permissions from Data Viewer PLUS:
- `bigquery.tables.create`
- `bigquery.tables.update`
- `bigquery.tables.delete`

## Troubleshooting

### Error: "Permission denied on resource project"

**Cause**: You don't have permission to grant IAM roles.

**Solution**: Ask a project owner/admin to grant the roles, or request these roles for yourself:
- `roles/resourcemanager.projectIamAdmin`
- `roles/owner`

### Error: "Service account does not exist"

**Cause**: The service account email is incorrect or the account was deleted.

**Solution**:
1. List all service accounts: `gcloud iam service-accounts list`
2. Verify the email address is correct
3. If the account doesn't exist, create a new service account and update your credentials

### Permissions granted but still getting error

**Cause**: IAM changes can take 1-2 minutes to propagate.

**Solution**:
1. Wait 2 minutes
2. Clear your browser cache
3. Hard refresh the page (Ctrl+F5 or Cmd+Shift+R)
4. Check the service account email in your environment variables matches the one you granted permissions to

## Quick Reference Commands

```bash
# Check if your service account has the required roles
gcloud projects get-iam-policy amazon-ppc-474902 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:YOUR_EMAIL" \
  --format="table(bindings.role)"

# List all service accounts in the project
gcloud iam service-accounts list --project=amazon-ppc-474902

# Test BigQuery access
bq query --project_id=amazon-ppc-474902 --use_legacy_sql=false \
  'SELECT COUNT(*) as test FROM `amazon-ppc-474902.amazon_ppc.optimization_results` LIMIT 1'
```

## Related Documentation

- [ACCESS_GUIDE.md](ACCESS_GUIDE.md) - Complete access configuration guide
- [BIGQUERY_DATASET_FIX.md](BIGQUERY_DATASET_FIX.md) - Dataset setup and schema
- [BIGQUERY_INTEGRATION.md](BIGQUERY_INTEGRATION.md) - Full BigQuery integration guide
- [Google Cloud IAM Documentation](https://cloud.google.com/iam/docs/overview)
- [BigQuery IAM Roles](https://cloud.google.com/bigquery/docs/access-control)

## Summary

✅ **Problem**: Service account lacks `bigquery.jobs.create` permission  
✅ **Solution**: Grant `roles/bigquery.dataViewer` + `roles/bigquery.jobUser`  
✅ **Time**: ~2 minutes for permissions to propagate  
✅ **Verification**: Refresh dashboard to confirm data loads  

This is a common issue when setting up a new service account for dashboard access. Once permissions are granted, the error will not recur.
