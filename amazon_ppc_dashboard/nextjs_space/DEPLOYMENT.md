# Deployment Guide

This guide explains how to deploy the Amazon PPC Dashboard to Vercel.

## Prerequisites

Before deploying, ensure you have:
- A Vercel account (https://vercel.com)
- Access to the `natureswaysoil/Amazom-PPC` repository
- The dashboard API key from the Cloud Function configuration

## Deployment Steps

### Step 1: Create New Project in Vercel

1. Go to [https://vercel.com/dashboard](https://vercel.com/dashboard)
2. Click **"Add New Project"**
3. Click **"Import Git Repository"**
4. Select or authorize access to `natureswaysoil/Amazom-PPC`

### Step 2: Configure Project Settings

When configuring the project:

**Important Settings:**
- **Framework Preset**: Next.js
- **Root Directory**: `amazon_ppc_dashboard/nextjs_space` ⚠️ **CRITICAL**
- **Build Command**: `npm run build` (should be auto-detected)
- **Output Directory**: `.next` (should be auto-detected)
- **Install Command**: `npm install` (should be auto-detected)

### Step 3: Configure Environment Variables

In the Vercel project settings, add the following environment variables:

**Required:**
```
DASHBOARD_API_KEY=your_dashboard_api_key_here
```

**Required for BigQuery Integration:**
```
GCP_PROJECT=amazon-ppc-474902
GOOGLE_CLOUD_PROJECT=amazon-ppc-474902
BQ_DATASET_ID=amazon_ppc
BQ_LOCATION=us-east4
```

**Optional (if needed for future features):**
```
NEXTAUTH_URL=https://your-dashboard.vercel.app
NEXTAUTH_SECRET=your_nextauth_secret_here
DATABASE_URL=your_database_url_here
```

**Notes:**
- The `DASHBOARD_API_KEY` must match the key configured in the Google Cloud Function's Secret Manager.
- The `GCP_PROJECT` and `GOOGLE_CLOUD_PROJECT` should be set to your Google Cloud project ID (e.g., `amazon-ppc-474902`).
- The `BQ_DATASET_ID` should match the BigQuery dataset created by `setup-bigquery.sh` (default: `amazon_ppc`).
- For Google Cloud authentication, you'll also need to configure `GOOGLE_APPLICATION_CREDENTIALS` (see Step 3a below).

### Step 3a: Configure Google Cloud Service Account (for BigQuery)

To enable BigQuery data queries, you need to create a service account and configure authentication:

1. **Create a service account for Vercel:**

```bash
# Set your project ID
PROJECT_ID="amazon-ppc-474902"

# Create service account
gcloud iam service-accounts create vercel-dashboard \
    --display-name="Vercel Dashboard Service Account" \
    --project=$PROJECT_ID

# Grant BigQuery permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:vercel-dashboard@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:vercel-dashboard@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"

# Create and download key
gcloud iam service-accounts keys create vercel-key.json \
    --iam-account=vercel-dashboard@${PROJECT_ID}.iam.gserviceaccount.com
```

2. **Add service account credentials to Vercel:**

**Recommended method - Use GCP_SERVICE_ACCOUNT_KEY:**

In Vercel project settings → Environment Variables, add a new variable:

- **Name:** `GCP_SERVICE_ACCOUNT_KEY`
- **Value:** Paste the **entire contents** of `vercel-key.json` file (the full JSON object)
- **Environment:** Production, Preview, and Development (select all)

Example of what to paste (your actual file will have real values):
```json
{
  "type": "service_account",
  "project_id": "amazon-ppc-474902",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "vercel-dashboard@amazon-ppc-474902.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://..."
}
```

**Alternative method - Use GOOGLE_APPLICATION_CREDENTIALS:**

If you prefer, you can use `GOOGLE_APPLICATION_CREDENTIALS` instead:
```
GOOGLE_APPLICATION_CREDENTIALS=<paste the entire contents of vercel-key.json here>
```

⚠️ **Important:** Do NOT use a file path (e.g., `/path/to/key.json`) on Vercel - it won't work. Always paste the JSON content directly.

### Step 4: Deploy

1. Click **"Deploy"**
2. Wait for the deployment to complete (usually 2-3 minutes)
3. Note your deployment URL (e.g., `https://your-project.vercel.app`)

### Step 5: Test Deployment

Test the health endpoint:
```bash
curl https://your-project.vercel.app/api/health
```

Expected response:
```json
{
  "status": "ok",
  "timestamp": "2025-...",
  "service": "Amazon PPC Dashboard"
}
```

### Step 6: Update Cloud Function Configuration

Update the Cloud Function's `DASHBOARD_URL` environment variable with your Vercel deployment URL:

```bash
gcloud secrets versions add DASHBOARD_URL --data-file=- <<EOF
https://your-project.vercel.app
EOF
```

Then redeploy the Cloud Function to pick up the new URL.

## Verifying Integration

### Test from Cloud Function

Run this command to verify the Cloud Function can connect to your dashboard:

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?health=true"
```

Expected response should include:
```json
{
  "dashboard_ok": true
}
```

### Test Full Integration

Run a dry-run optimization to verify end-to-end integration:

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app"
```

Then check your Vercel deployment logs to see the incoming data.

## Troubleshooting

### "Root Directory not found" Error

**Problem:** Vercel shows error about root directory not found.

**Solution:** Ensure the **Root Directory** is set to exactly `amazon_ppc_dashboard/nextjs_space` in the project settings.

To fix:
1. Go to Vercel project settings
2. Navigate to "General" → "Build & Development Settings"
3. Set "Root Directory" to `amazon_ppc_dashboard/nextjs_space`
4. Save and redeploy

### Build Fails

**Problem:** Build process fails with module errors.

**Solution:** 
1. Check that `package.json` is properly formatted
2. Ensure Node.js version is 18.x or later
3. Try clearing the build cache in Vercel

### API Endpoints Return 500 Errors

**Problem:** API endpoints return internal server errors.

**Solution:**
1. Check Vercel function logs for detailed error messages
2. Verify `DASHBOARD_API_KEY` is set in environment variables
3. Ensure TypeScript compilation is successful

### Dashboard Not Receiving Data

**Problem:** Cloud Function runs but dashboard doesn't receive updates.

**Solution:**
1. Verify API key matches in both places
2. Check that `DASHBOARD_URL` in Cloud Function points to your Vercel deployment
3. Review Vercel function logs for incoming requests
4. Test individual endpoints with curl

### BigQuery Error: "GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variable must be set"

**Problem:** Dashboard displays an error about missing GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variables, even after following the deployment steps.

**Root Cause:** This error occurs when the environment variables are not properly set in Vercel. Note that setting these in the optimizer's Cloud Function does NOT affect the dashboard - the dashboard needs its own environment variable configuration.

**Step-by-Step Solution:**

1. **Check Current Configuration:**
   ```bash
   # Use the new config-check endpoint to diagnose issues
   curl "https://your-dashboard.vercel.app/api/config-check"
   ```
   This will show you exactly what's configured and what's missing.

2. **Set Required Environment Variables in Vercel:**
   
   Go to your Vercel project → Settings → Environment Variables, and add:
   
   ```
   GCP_PROJECT=amazon-ppc-474902
   GOOGLE_CLOUD_PROJECT=amazon-ppc-474902
   BQ_DATASET_ID=amazon_ppc
   BQ_LOCATION=us-east4
   ```
   
   Make sure to select **Production**, **Preview**, and **Development** for each variable.

3. **Add Google Cloud Service Account Credentials:**
   
   You MUST add credentials for BigQuery authentication. Choose one method:
   
   **Method A (Recommended):** Use `GCP_SERVICE_ACCOUNT_KEY`:
   - In Vercel, add a new environment variable named `GCP_SERVICE_ACCOUNT_KEY`
   - Paste the entire JSON content from your `vercel-key.json` file
   - Example: `{"type":"service_account","project_id":"amazon-ppc-474902",...}`
   
   **Method B:** Use `GOOGLE_APPLICATION_CREDENTIALS`:
   - Add environment variable named `GOOGLE_APPLICATION_CREDENTIALS`
   - Paste the entire JSON content (NOT a file path!)
   - ⚠️ Do NOT use a file path like `/path/to/key.json` - it won't work on Vercel

4. **Verify Service Account Permissions:**
   ```bash
   # Check if service account has required roles
   gcloud projects get-iam-policy amazon-ppc-474902 \
     --flatten="bindings[].members" \
     --filter="bindings.members:vercel-dashboard@amazon-ppc-474902.iam.gserviceaccount.com"
   ```
   
   The service account needs:
   - `roles/bigquery.dataViewer`
   - `roles/bigquery.jobUser`

5. **Redeploy the Dashboard:**
   
   After adding/updating environment variables, you MUST redeploy:
   - Go to Vercel → Deployments
   - Click "..." menu on latest deployment
   - Select "Redeploy"
   - OR: Push a new commit to trigger automatic deployment

6. **Verify the Fix:**
   ```bash
   # Check configuration status
   curl "https://your-dashboard.vercel.app/api/config-check"
   
   # Test BigQuery connection
   curl "https://your-dashboard.vercel.app/api/bigquery-data?table=optimization_results&limit=1"
   ```

**Common Mistakes:**

- ❌ **Using a file path for credentials:** Vercel doesn't have access to local files. Always paste JSON content.
- ❌ **Not redeploying after adding variables:** New environment variables only take effect after redeployment.
- ❌ **Only setting variables in Cloud Function:** The optimizer and dashboard are separate deployments with separate environment variables.
- ❌ **Forgetting to select all environments:** Make sure to check Production, Preview, and Development when adding variables.
- ❌ **Invalid JSON format:** Ensure the service account JSON is valid (use a JSON validator if unsure).

**Still Having Issues?**

1. Check Vercel function logs for detailed error messages
2. Verify your service account JSON is valid: https://jsonlint.com/
3. Ensure the BigQuery dataset was created: `bq ls amazon-ppc-474902:amazon_ppc`
4. Contact support with the output from `/api/config-check`

## Viewing Logs

### Vercel Deployment Logs

1. Go to your Vercel project
2. Click on "Deployments"
3. Select the latest deployment
4. Click "Functions" to view logs for each API route

### Real-time Logs

You can also view real-time logs using the Vercel CLI:

```bash
vercel logs amazon-ppc-dashboard --follow
```

## Production Checklist

Before going to production, ensure:

- [ ] Root directory is correctly set to `amazon_ppc_dashboard/nextjs_space`
- [ ] Environment variables are configured (especially `DASHBOARD_API_KEY`)
- [ ] BigQuery environment variables are set (`GCP_PROJECT`, `GOOGLE_CLOUD_PROJECT`, `BQ_DATASET_ID`, `BQ_LOCATION`)
- [ ] Google Cloud service account credentials are configured (`GOOGLE_APPLICATION_CREDENTIALS`)
- [ ] Service account has BigQuery permissions (`roles/bigquery.dataViewer`, `roles/bigquery.jobUser`)
- [ ] BigQuery dataset and tables are created (run `../../setup-bigquery.sh` if needed)
- [ ] Health endpoint is accessible
- [ ] BigQuery API endpoint returns data (test with `/api/bigquery-data?table=optimization_results&limit=1`)
- [ ] API key authentication is working
- [ ] Cloud Function `DASHBOARD_URL` is updated
- [ ] Test optimization run completes successfully
- [ ] Vercel logs show incoming data
- [ ] Custom domain is configured (optional)
- [ ] HTTPS is enabled (should be automatic)

## Next Steps

After successful deployment:

1. **Implement Data Storage**: Currently, API endpoints only log data. Implement database storage for persistence.
2. **Build Dashboard UI**: Create a UI to visualize optimization results.
3. **Set Up Monitoring**: Configure alerts for errors or anomalies.
4. **Add Analytics**: Track optimization trends over time.

## Support

For additional help:
- Check the [README.md](./README.md) for general information
- Review [OPTIMIZER_INTEGRATION.md](./OPTIMIZER_INTEGRATION.md) for integration details
- Consult [Vercel Documentation](https://vercel.com/docs)
- Review [Next.js Documentation](https://nextjs.org/docs)
