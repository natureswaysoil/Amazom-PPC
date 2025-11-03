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

**Optional (if needed for future features):**
```
NEXTAUTH_URL=https://your-dashboard.vercel.app
NEXTAUTH_SECRET=your_nextauth_secret_here
DATABASE_URL=your_database_url_here
```

**Note:** The `DASHBOARD_API_KEY` must match the key configured in the Google Cloud Function's Secret Manager.

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
- [ ] Health endpoint is accessible
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
