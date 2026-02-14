# Deploying Dashboard to Vercel - Step-by-Step Guide

## Important Note About URLs

The URL `https://amazon-ppc-dashboard-qb63yk.abacusai.app` is an **Abacus AI domain**, not a Vercel domain.

When you deploy to Vercel, you'll get a URL like:
- `https://amazon-ppc-dashboard-[random-id].vercel.app`
- `https://your-project-name.vercel.app`

**To get the Abacus AI URL**, you would need to:
1. Deploy the dashboard somewhere (Vercel, Cloud Run, or Abacus AI platform)
2. If using Abacus AI, follow their deployment process
3. If using Vercel, you can optionally set up a custom domain

---

## Option 1: Deploy to Vercel (Recommended)

### Prerequisites
- GitHub account with access to this repository
- Vercel account (free tier is sufficient)
- Google Cloud service account with BigQuery access

### Step 1: Prepare the Repository

The dashboard code is already in your repository at:
```
amazon_ppc_dashboard/nextjs_space/
```

Make sure your latest changes are pushed to GitHub:
```bash
git push origin main
```

### Step 2: Create Vercel Account

1. Go to [vercel.com](https://vercel.com)
2. Sign up with GitHub (recommended)
3. Authorize Vercel to access your repositories

### Step 3: Import Project to Vercel

1. Click **"Add New"** → **"Project"**
2. Select your GitHub repository: `natureswaysoil/Amazom-PPC`
3. Configure project settings:
   - **Framework Preset**: Next.js (should auto-detect)
   - **Root Directory**: `amazon_ppc_dashboard/nextjs_space`
   - **Build Command**: `npm run build` (auto-filled)
   - **Output Directory**: `.next` (auto-filled)

   **Important**: Set the Root Directory to `amazon_ppc_dashboard/nextjs_space` in the Vercel project settings. This prevents Vercel from parsing the wrong package.json and ensures the dashboard package is used as the build root.

### Step 4: Configure Environment Variables

In the Vercel deployment configuration, add these environment variables:

**Required**:
```
BQ_DATASET_ID=amazon_ppc_data
BQ_LOCATION=us-east4
```

**Optional** (if not using service account auto-detection):
```
GCP_PROJECT=amazon-ppc-474902
GOOGLE_CLOUD_PROJECT=amazon-ppc-474902
```

**For API authentication**:
```
DASHBOARD_API_KEY=your_secure_api_key_here
```

### Step 5: Add Google Cloud Service Account

Vercel needs access to BigQuery. Add your service account credentials:

**Method 1: Using GOOGLE_APPLICATION_CREDENTIALS_JSON**

1. Get your service account JSON key:
   ```bash
   gcloud iam service-accounts keys create key.json \
     --iam-account=YOUR_SERVICE_ACCOUNT@PROJECT_ID.iam.gserviceaccount.com
   ```

2. Copy the entire JSON content

3. In Vercel environment variables, add:
   - **Name**: `GOOGLE_APPLICATION_CREDENTIALS_JSON`
   - **Value**: Paste the entire JSON content
   - **Environment**: Production, Preview, Development

**Method 2: Using Individual Fields**

Alternatively, you can add individual fields:
```
GCP_PROJECT_ID=amazon-ppc-474902
GCP_CLIENT_EMAIL=service-account@amazon-ppc-474902.iam.gserviceaccount.com
GCP_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n
```

### Step 6: Deploy

1. Click **"Deploy"**
2. Wait for deployment to complete (2-5 minutes)
3. You'll get a URL like: `https://amazon-ppc-dashboard-xyz123.vercel.app`

### Step 7: Test the Deployment

1. Open the Vercel URL in your browser
2. Verify the dashboard loads
3. Check that data from BigQuery is displayed
4. Test API endpoints:
   ```bash
   curl https://your-dashboard.vercel.app/api/health
   curl https://your-dashboard.vercel.app/api/optimization-results
   ```

### Step 8: Update Optimizer Configuration

Once deployed, update your optimizer to use the new URL:

```bash
# From repository root
python update_dashboard_url.py https://your-dashboard.vercel.app

# Or manually edit config.json:
# "dashboard": {
#   "url": "https://your-dashboard.vercel.app",
#   "api_key": "your_api_key",
#   "enabled": true
# }
```

Then update the Cloud Function:
```bash
gcloud functions deploy amazon-ppc-optimizer \
  --update-env-vars DASHBOARD_URL=https://your-dashboard.vercel.app
```

### Step 9: Verify End-to-End

Run the diagnostic tools:
```bash
python test_dashboard_connection.py
python verify_complete_setup.py
```

---

## Option 2: Deploy to Abacus AI Platform

If you specifically need the Abacus AI domain (`*.abacusai.app`):

### Using Abacus AI's Platform

1. Go to [abacusai.com](https://abacusai.com)
2. Create/login to your account
3. Follow their deployment process for Next.js applications
4. Configure the same environment variables as above
5. The platform should assign you a `*.abacusai.app` URL

**Note**: I don't have direct access to deploy to Abacus AI, but the dashboard code is compatible with any platform that supports Next.js.

---

## Option 3: Custom Domain on Vercel

If you want a specific domain name:

### After Deploying to Vercel

1. Go to your project in Vercel dashboard
2. Navigate to **Settings** → **Domains**
3. Click **"Add Domain"**
4. Options:
   - Use a custom domain you own (requires DNS configuration)
   - Vercel can provide `*.vercel.app` subdomains
   - You cannot directly get `*.abacusai.app` through Vercel

---

## Troubleshooting

### Build Fails

**Error**: `Module not found: Can't resolve '@google-cloud/bigquery'`

**Fix**: Ensure dependencies are installed. The `package.json` should include:
```json
"dependencies": {
  "@google-cloud/bigquery": "^7.0.0",
  "next": "^14.2.30",
  "react": "^18",
  "react-dom": "^18"
}
```

### BigQuery Connection Fails

**Error**: `Error: Could not load the default credentials`

**Fix**: Verify environment variables:
1. Check that `GOOGLE_APPLICATION_CREDENTIALS_JSON` is set
2. Ensure the service account has BigQuery permissions:
   ```bash
   gcloud projects add-iam-policy-binding amazon-ppc-474902 \
     --member="serviceAccount:YOUR_SA@amazon-ppc-474902.iam.gserviceaccount.com" \
     --role="roles/bigquery.dataViewer"
   ```

### Dashboard Loads but No Data

**Check**:
1. Verify BigQuery dataset exists: `amazon_ppc`
2. Check that tables have data:
   ```bash
   bq query --use_legacy_sql=false \
     'SELECT COUNT(*) FROM `amazon-ppc-474902.amazon_ppc.optimization_results`'
   ```
3. Check dashboard logs in Vercel dashboard

---

## Next Steps After Deployment

1. **Update optimizer config** with new dashboard URL
2. **Test connectivity** with diagnostic tools
3. **Monitor logs** in Vercel dashboard
4. **Set up auto-deployments** (Vercel does this automatically from GitHub)

---

## Quick Deployment Commands

If you have Vercel CLI installed:

```bash
# Install Vercel CLI
npm install -g vercel

# Navigate to dashboard directory
cd amazon_ppc_dashboard/nextjs_space

# Login to Vercel
vercel login

# Deploy to production
vercel --prod

# Follow prompts to configure project
```

---

## Summary

**For Vercel deployment**:
- You'll get a `*.vercel.app` URL
- Easy setup, free tier available
- Automatic deployments from GitHub
- Good for testing and production

**For Abacus AI domain**:
- You need to deploy through Abacus AI platform
- Or use Vercel with custom domain configuration
- The dashboard code is compatible with both

**Recommended approach**:
1. Deploy to Vercel first (easiest)
2. Test that everything works
3. If you need the Abacus AI domain specifically, configure custom domain or redeploy to Abacus AI platform

---

## Questions?

Run the verification tool to check current setup:
```bash
python verify_complete_setup.py
```

After deployment, test connectivity:
```bash
python test_dashboard_connection.py
```

Update configuration:
```bash
python update_dashboard_url.py <your-new-url>
```
