# Dashboard Quick Start - Connect to Live Data

## 🎯 Goal

Connect your Amazon PPC Dashboard to BigQuery to display live optimization data.

## ⚡ Quick Setup (5 Minutes)

### Step 1: Get Service Account Credentials

```bash
# 1. Create service account
gcloud iam service-accounts create ppc-dashboard \
  --display-name="PPC Dashboard BigQuery Access"

# 2. Grant permissions
PROJECT_ID=$(gcloud config get-value project)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ppc-dashboard@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ppc-dashboard@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

# 3. Create and download key
gcloud iam service-accounts keys create ~/ppc-dashboard-key.json \
  --iam-account=ppc-dashboard@${PROJECT_ID}.iam.gserviceaccount.com

# 4. View the key (you'll copy this)
cat ~/ppc-dashboard-key.json
```

### Step 2: Configure Dashboard (Vercel)

1. Go to [Vercel Dashboard](https://vercel.com/dashboard) → Your Project
2. Navigate to **Settings** → **Environment Variables**
3. Add these variables:

| Name | Value | Environments |
|------|-------|--------------|
| `GCP_SERVICE_ACCOUNT_KEY` | Paste entire JSON from Step 1 | Production, Preview, Development |
| `GCP_PROJECT` | Your GCP project ID | Production, Preview, Development |
| `BQ_DATASET_ID` | `amazon_ppc` | Production, Preview, Development |
| `DASHBOARD_API_KEY` | Your secret API key | Production, Preview, Development |

4. Click **Save** for each variable
5. Redeploy your dashboard

### Step 3: Verify

```bash
# Test credentials
curl https://your-dashboard.vercel.app/api/credentials-debug

# Expected output:
# {"status":"ok","message":"Valid GCP credentials detected",...}

# Test BigQuery connection
curl https://your-dashboard.vercel.app/api/bigquery-data?table=optimization_results&limit=1

# Expected output:
# {"success":true,"data":[...],"metadata":{...}}
```

## ✅ Done!

Your dashboard should now display live data from BigQuery.

## 🔍 Troubleshooting

### Problem: "No Google Cloud credentials found"

**Quick Fix:**
```bash
# Check if variable is set
curl https://your-dashboard.vercel.app/api/credentials-debug

# If not, ensure you saved and deployed in Vercel
```

### Problem: "Base64 decoded but not valid JSON"

**Quick Fix:**
Use raw JSON instead of base64:
1. Copy the ENTIRE JSON from `cat ~/ppc-dashboard-key.json`
2. Paste directly into `GCP_SERVICE_ACCOUNT_KEY`
3. No modifications, no encoding!
4. Redeploy

### Problem: "Access Denied" or permission errors

**Quick Fix:**
```bash
# Grant required permissions
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="ppc-dashboard@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.jobUser"
```

### Problem: "Dataset not found"

**Quick Fix:**
```bash
# Ensure optimizer has run at least once to create tables
# Or run setup script:
./setup-bigquery.sh $PROJECT_ID amazon_ppc us-east4
```

## 📚 Complete Documentation

For detailed instructions, see:
- **[DASHBOARD_BIGQUERY_SETUP.md](amazon_ppc_dashboard/nextjs_space/DASHBOARD_BIGQUERY_SETUP.md)** - Complete setup guide (400+ lines)
- **[BIGQUERY_VERIFICATION_CHECKLIST.md](BIGQUERY_VERIFICATION_CHECKLIST.md)** - Step-by-step verification (350+ lines)
- **[test_bigquery_integration.py](test_bigquery_integration.py)** - Automated testing script (450+ lines)
- **[README_DASHBOARD_SETUP.md](amazon_ppc_dashboard/nextjs_space/README_DASHBOARD_SETUP.md)** - Dashboard docs
- **[DATA_FLOW_SUMMARY.md](DATA_FLOW_SUMMARY.md)** - Complete data flow architecture
- **[README.md](README.md)** - Main documentation

## 🆘 Still Having Issues?

1. **Check diagnostics:**
   ```bash
   curl https://your-dashboard.vercel.app/api/credentials-debug
   curl https://your-dashboard.vercel.app/api/config-check
   ```

2. **Verify BigQuery has data:**
   ```bash
   bq query --use_legacy_sql=false \
     'SELECT COUNT(*) FROM `your-project.amazon_ppc.optimization_results`'
   ```

3. **Test optimizer writes to BigQuery:**
   ```bash
   # Trigger optimizer
   curl -X POST $FUNCTION_URL \
     -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
     -d '{"dry_run":true}'
   ```

4. **Check logs:**
   - Vercel: Vercel Dashboard → Deployments → Logs
   - Cloud Function: `gcloud functions logs read amazon-ppc-optimizer`

## 💡 Pro Tips

- **Use raw JSON**: It's the most reliable method for credentials
- **Don't modify the JSON**: Copy/paste exactly as is
- **Verify locally first**: Test credentials with diagnostic endpoints
- **Check permissions**: Service account needs both Data Viewer AND Job User roles
- **Redeploy after changes**: Environment variable changes require redeployment
