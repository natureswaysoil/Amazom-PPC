# Vercel Deployment Setup for Amazon PPC Dashboard

## ✅ Prerequisites Complete

The package.json has been updated with explicit versions of required dependencies:
- `next`: ^14.2.30
- `react`: ^18.3.1
- `react-dom`: ^18.3.1

The package-lock.json has been synchronized and the build has been tested successfully.

## 🚀 Deploy to Vercel

### Step 1: Import Project

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub
2. Click **"Add New"** → **"Project"**
3. Select the repository: `natureswaysoil/Amazom-PPC`

### Step 2: Configure Root Directory

**⚠️ CRITICAL: Set the Root Directory correctly**

In the project configuration screen:

```
Root Directory: amazon_ppc_dashboard/nextjs_space
```

**This is the most important setting!** Vercel needs to look in this subdirectory to find the Next.js application and its package.json.

### Step 3: Configure Build Settings

These should auto-detect, but verify:

- **Framework Preset**: Next.js
- **Build Command**: `npm run build`
- **Output Directory**: `.next`
- **Install Command**: `npm install`

### Step 4: Environment Variables

Add these environment variables in the Vercel project settings:

#### Required for BigQuery:
```
BQ_DATASET_ID=amazon_ppc
BQ_LOCATION=us-east4
```

#### Google Cloud Credentials (choose one method):

**Method A: JSON String (Recommended)**
```
GOOGLE_APPLICATION_CREDENTIALS_JSON=<paste entire service account JSON>
```

**Method B: Individual Fields**
```
GCP_PROJECT_ID=amazon-ppc-474902
GCP_CLIENT_EMAIL=service-account@amazon-ppc-474902.iam.gserviceaccount.com
GCP_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n
```

#### API Authentication:
```
DASHBOARD_API_KEY=<your_secure_api_key>
```

### Step 5: Deploy

Click **"Deploy"** and wait for the build to complete (2-5 minutes).

## 🔍 Verification

After deployment:

1. **Test the URL**: Open `https://your-project.vercel.app`
2. **Check Health Endpoint**: `https://your-project.vercel.app/api/health`
3. **Verify Data**: Check that optimization results are displayed

## 🔧 Troubleshooting

### "package.json is missing 'next' as a dependency"

**Solution**: Ensure Root Directory is set to `amazon_ppc_dashboard/nextjs_space`

This error occurs when Vercel looks at the repository root instead of the Next.js subdirectory.

### Build Fails with Module Not Found

**Check**:
1. Root Directory setting
2. package.json and package-lock.json are in sync
3. All dependencies are listed in package.json

### BigQuery Connection Fails

**Verify**:
1. Environment variables are set correctly
2. Service account has BigQuery permissions
3. Dataset `amazon_ppc` exists in project `amazon-ppc-474902`

## 📝 After Deployment

Update your optimizer configuration with the new dashboard URL:

```bash
# Update Cloud Function environment variable
gcloud functions deploy amazon-ppc-optimizer \
  --update-env-vars DASHBOARD_URL=https://your-project.vercel.app

# Or update config.json:
{
  "dashboard": {
    "url": "https://your-project.vercel.app",
    "api_key": "your_api_key",
    "enabled": true
  }
}
```

## 🎯 Summary

**Key Points**:
- ✅ package.json has all required dependencies with explicit versions
- ✅ Root Directory MUST be set to `amazon_ppc_dashboard/nextjs_space`
- ✅ Build has been tested and works locally
- ✅ Environment variables are required for BigQuery access

**Common Issues**:
- Most deployment errors are due to incorrect Root Directory setting
- Ensure you're pointing to `amazon_ppc_dashboard/nextjs_space`, not the repository root

---

For more details, see [VERCEL_DEPLOYMENT_GUIDE.md](../../VERCEL_DEPLOYMENT_GUIDE.md) in the repository root.
