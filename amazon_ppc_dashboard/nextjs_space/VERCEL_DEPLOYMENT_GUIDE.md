# Vercel Deployment Guide for Amazon PPC Dashboard

This guide provides step-by-step instructions for deploying the Amazon PPC Dashboard to Vercel.

## 🚀 Quick Deploy (Recommended)

### Option 1: Deploy via Vercel Dashboard (Easiest - 5 minutes)

1. **Go to Vercel Dashboard**
   - Visit: https://vercel.com/new
   - Sign in or create a Vercel account

2. **Import Git Repository**
   - Click "Add New Project"
   - Select "Import Git Repository"
   - Choose: `natureswaysoil/Amazom-PPC`
   - Click "Import"

3. **Configure Project Settings**
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: `amazon_ppc_dashboard/nextjs_space` ⚠️ **IMPORTANT!**
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)
   - **Install Command**: `npm install` (auto-detected)

4. **Add Environment Variables**
   
   Click "Environment Variables" and add the following:

   **Required for Dashboard API:**
   ```
   DASHBOARD_API_KEY=<your_dashboard_api_key>
   ```

   **Required for BigQuery Integration:**
   ```
   GCP_SERVICE_ACCOUNT_KEY=<paste_your_service_account_json_here>
   GCP_PROJECT=amazon-ppc-474902
   BQ_DATASET_ID=amazon_ppc
   BQ_LOCATION=us-east4
   ```

   💡 **Tip**: For `GCP_SERVICE_ACCOUNT_KEY`, you can paste the entire JSON file content or use base64 encoding:
   ```bash
   cat service-account-key.json | base64 | tr -d '\n'
   ```

5. **Deploy**
   - Click "Deploy"
   - Wait for deployment to complete (~2-3 minutes)
   - Your dashboard will be live at: `https://your-project-name.vercel.app`

---

### Option 2: Deploy via Vercel CLI

1. **Install Vercel CLI**
   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel**
   ```bash
   vercel login
   ```

3. **Navigate to Dashboard Directory**
   ```bash
   cd amazon_ppc_dashboard/nextjs_space
   ```

4. **Deploy**
   ```bash
   vercel --prod
   ```

5. **Set Environment Variables**
   ```bash
   vercel env add DASHBOARD_API_KEY
   vercel env add GCP_SERVICE_ACCOUNT_KEY
   vercel env add GCP_PROJECT
   vercel env add BQ_DATASET_ID
   vercel env add BQ_LOCATION
   ```

6. **Redeploy with Environment Variables**
   ```bash
   vercel --prod
   ```

---

### Option 3: Automated GitHub Actions Deployment

A GitHub Actions workflow has been created at `.github/workflows/deploy-vercel-dashboard.yml` that automatically deploys to Vercel when changes are pushed.

**Setup Steps:**

1. **Get Vercel Credentials**
   - Go to: https://vercel.com/account/tokens
   - Create a new token: Name it "GitHub Actions"
   - Copy the token

2. **Create Vercel Project**
   - Deploy once manually via Vercel Dashboard (Option 1)
   - Get your Project ID from: https://vercel.com/[your-username]/[project-name]/settings
   - Get your Org ID from: https://vercel.com/account

3. **Add GitHub Secrets**
   - Go to: https://github.com/natureswaysoil/Amazom-PPC/settings/secrets/actions
   - Click "New repository secret"
   - Add the following secrets:
     - `VERCEL_TOKEN`: Your Vercel token from step 1
     - `VERCEL_ORG_ID`: Your organization ID
     - `VERCEL_PROJECT_ID`: Your project ID
     - `VERCEL_GCP_SERVICE_ACCOUNT_KEY`: Your GCP service account JSON
     - `VERCEL_DASHBOARD_API_KEY`: Your dashboard API key

4. **Trigger Deployment**
   - Push changes to `main` or your branch
   - Or manually trigger via: Actions → Deploy Dashboard to Vercel → Run workflow

---

## 📋 Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DASHBOARD_API_KEY` | Yes | API key for Cloud Function integration | `your-secret-key-here` |
| `GCP_SERVICE_ACCOUNT_KEY` | Yes | Google Cloud service account JSON | `{"type":"service_account",...}` |
| `GCP_PROJECT` | No* | Google Cloud project ID | `amazon-ppc-474902` |
| `BQ_DATASET_ID` | No* | BigQuery dataset name | `amazon_ppc` |
| `BQ_LOCATION` | No* | BigQuery dataset location | `us-east4` |
| `NEXTAUTH_URL` | No | Dashboard URL (for auth) | `https://your-app.vercel.app` |

*Auto-detected from service account if not provided.

---

## 🧪 Testing Your Deployment

After deployment, test these endpoints:

1. **Health Check**
   ```bash
   curl https://your-app.vercel.app/api/health
   ```
   Expected: `{"status":"ok","timestamp":"...","service":"Amazon PPC Dashboard"}`

2. **Configuration Check**
   ```bash
   curl https://your-app.vercel.app/api/config-check
   ```
   Expected: Configuration status and diagnostics

3. **Main Dashboard**
   ```
   Visit: https://your-app.vercel.app/
   ```
   Should display the dashboard (may show error state if no optimization data exists yet)

---

## 🔧 Troubleshooting

### Deployment Fails at Build Step

**Error**: `Cannot find module 'next'`
- **Solution**: Ensure `Root Directory` is set to `amazon_ppc_dashboard/nextjs_space`

**Error**: ESLint errors
- **Solution**: Run `npm run lint` locally and fix issues before deploying

### Dashboard Shows "Configuration Error"

**Error**: "Could not load Google Cloud credentials"
- **Solution**: Check that `GCP_SERVICE_ACCOUNT_KEY` is set correctly in Vercel environment variables
- Verify the JSON is valid (not truncated)
- Try base64 encoding if pasting raw JSON has issues

### BigQuery Errors

**Error**: "Not found: Dataset amazon-ppc-474902:amazon_ppc"
- **Solution**: Run the optimizer at least once to create the BigQuery dataset
- Or manually create the dataset using the setup script

**Error**: "Permission denied"
- **Solution**: Grant BigQuery roles to the service account:
  ```bash
  gcloud projects add-iam-policy-binding amazon-ppc-474902 \
    --member="serviceAccount:your-sa@amazon-ppc-474902.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataViewer"
  
  gcloud projects add-iam-policy-binding amazon-ppc-474902 \
    --member="serviceAccount:your-sa@amazon-ppc-474902.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"
  ```

---

## 🔄 Updating the Deployment

### Automatic Updates (with GitHub Actions)
- Push changes to your branch
- GitHub Actions will automatically rebuild and redeploy

### Manual Updates (Vercel Dashboard)
- Vercel automatically deploys on every push to the connected branch
- Or click "Redeploy" in the Vercel dashboard

### Manual Updates (Vercel CLI)
```bash
cd amazon_ppc_dashboard/nextjs_space
vercel --prod
```

---

## 📱 Custom Domain (Optional)

1. Go to: https://vercel.com/[your-username]/[project-name]/settings/domains
2. Click "Add Domain"
3. Enter your custom domain (e.g., `dashboard.example.com`)
4. Follow DNS configuration instructions
5. Wait for SSL certificate to provision (~5 minutes)

---

## 💡 Best Practices

1. **Use Environment Variables**: Never commit sensitive keys to the repository
2. **Test Locally First**: Run `npm run build` locally before deploying
3. **Monitor Deployments**: Check Vercel deployment logs if issues occur
4. **Set Up Alerts**: Configure Vercel to notify you of deployment failures
5. **Use Preview Deployments**: Test changes in preview deployments before merging to main

---

## 📚 Additional Resources

- [Vercel Documentation](https://vercel.com/docs)
- [Next.js Deployment](https://nextjs.org/docs/deployment)
- [Dashboard Setup Guide](./DASHBOARD_SETUP_QUICKSTART.md)
- [BigQuery Integration](./README_BIGQUERY.md)

---

## 🆘 Need Help?

- Check `/api/config-check` endpoint for diagnostics
- Check `/api/setup-guide` for step-by-step setup instructions
- Review Vercel deployment logs in the dashboard
- See [DEPLOYMENT.md](./DEPLOYMENT.md) for more details
