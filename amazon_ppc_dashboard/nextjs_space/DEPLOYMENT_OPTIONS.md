# Dashboard Deployment Options

Since you can't open Vercel's login page in this dev environment, here are your deployment options:

## Option 1: GitHub → Vercel Auto-Deploy (RECOMMENDED)

This is the easiest way - Vercel automatically deploys when you push to GitHub.

### Steps:

1. **Push this code to GitHub** (if not already):
   ```bash
   cd /workspaces/Amazom-PPC
   git add .
   git commit -m "Add Next.js dashboard for Amazon PPC"
   git push origin main
   ```

2. **Connect Vercel to GitHub** (from your local computer or any browser):
   - Go to https://vercel.com
   - Click "Add New Project"
   - Import your GitHub repository: `natureswaysoil/Amazom-PPC`
   - Set root directory to: `amazon_ppc_dashboard/nextjs_space`
   - Add environment variables (see below)
   - Click "Deploy"

3. **Environment Variables to Add in Vercel**:
   ```
   GOOGLE_CLOUD_PROJECT=amazon-ppc-474902
   BIGQUERY_DATASET=amazon_ppc
   GCP_CREDENTIALS=<your service account JSON>
   ```

**That's it!** Vercel will auto-deploy on every push.

---

## Option 2: Use Vercel Token (In Dev Environment)

If you have a Vercel token, you can deploy from here:

```bash
cd /workspaces/Amazom-PPC/amazon_ppc_dashboard/nextjs_space

# Set token as environment variable
export VERCEL_TOKEN="your_token_here"

# Deploy
vercel --token $VERCEL_TOKEN --prod
```

Get token from: https://vercel.com/account/tokens

---

## Option 3: Deploy to Google Cloud Run

Since you're already using Google Cloud, deploy as a container:

```bash
cd /workspaces/Amazom-PPC/amazon_ppc_dashboard/nextjs_space

# Build container
gcloud builds submit --tag gcr.io/amazon-ppc-474902/ppc-dashboard

# Deploy to Cloud Run
gcloud run deploy ppc-dashboard \
  --image gcr.io/amazon-ppc-474902/ppc-dashboard \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=amazon-ppc-474902,BIGQUERY_DATASET=amazon_ppc"
```

**Note:** Requires a Dockerfile (I can create one if needed)

---

## Option 4: Run Locally for Testing

Test the dashboard on your local machine:

```bash
cd /workspaces/Amazom-PPC/amazon_ppc_dashboard/nextjs_space

# Install dependencies (already done)
npm install

# Run development server
npm run dev

# Open in browser: http://localhost:3000
```

---

## Recommendation

**Use Option 1** (GitHub → Vercel) because:
- ✅ Easiest setup
- ✅ Automatic deployments on git push
- ✅ Free for personal projects
- ✅ Built-in SSL/CDN
- ✅ No server management

You can set it up from any computer with a browser, then all future deployments happen automatically when you push code.

---

## Quick Setup for Option 1

From your local computer (with browser access):

1. Visit https://vercel.com and sign in
2. Click "Add New" → "Project"
3. Import `natureswaysoil/Amazom-PPC`
4. Configure:
   - **Root Directory:** `amazon_ppc_dashboard/nextjs_space`
   - **Framework Preset:** Next.js (auto-detected)
   - **Build Command:** `npm run build` (default)
   - **Output Directory:** `.next` (default)
5. Add Environment Variables (from Settings):
   ```
   GOOGLE_CLOUD_PROJECT=amazon-ppc-474902
   BIGQUERY_DATASET=amazon_ppc
   ```
6. Deploy!

Your dashboard will be live at: `https://your-project.vercel.app`
