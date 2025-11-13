
# 🚀 Deploy Updated Optimizer - Complete Guide

## ✅ What's Ready

The optimizer code has been updated with the correct Amazon Profile ID (`1780498399290938`) and committed locally:

```
Commit: 5292144
Message: Update profile ID to 1780498399290938 (US Seller)
Branch: main
Status: Ready to push
```

**Files Updated:**
- ✅ `config.json` - Profile ID updated
- ✅ `.env.template` - Environment variable template updated
- ✅ `main.py` - Profile ID support added
- ✅ `optimizer_profile_id_helper.py` - Helper module created
- ✅ `PROFILE_ID_UPDATE.md` - Documentation added

---

## 📤 STEP 1: Push Changes to GitHub

### Option A: Using GitHub Personal Access Token (Recommended)

1. **Create a GitHub Personal Access Token** (if you don't have one):
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Name it: "Amazon PPC Optimizer"
   - Select scope: **`repo`** (full control)
   - Click "Generate token"
   - **Copy the token** (you won't see it again!)

2. **Push the changes**:
   ```bash
   cd /path/to/amazon-ppc-optimizer
   
   # Replace YOUR_TOKEN with your actual token
   git push https://YOUR_TOKEN@github.com/natureswaysoil/Amazom-PPC.git main
   ```

### Option B: Using SSH (If SSH Keys Configured)

```bash
cd /path/to/amazon-ppc-optimizer

# Update remote to SSH
git remote set-url origin git@github.com:natureswaysoil/Amazom-PPC.git

# Push
git push origin main
```

### Option C: Using GitHub Web Interface

If you can't push from command line:

1. Download the changed files from `/home/ubuntu/amazon-ppc-optimizer/`:
   - `config.json`
   - `.env.template`
   - `main.py`
   - `optimizer_profile_id_helper.py`
   - `PROFILE_ID_UPDATE.md`

2. Go to: https://github.com/natureswaysoil/Amazom-PPC
3. Navigate to each file and click "Edit"
4. Replace the content with the updated version
5. Commit each change

---

## 🔄 STEP 2: Redeploy to Google Cloud Functions

### Prerequisites Check

Make sure you have:
- ✅ Google Cloud CLI (`gcloud`) installed
- ✅ Authenticated to Google Cloud: `gcloud auth login`
- ✅ Project set: `gcloud config set project amazon-ppc-474902`

### Quick Redeploy

1. **Pull the latest changes**:
   ```bash
   cd /path/to/amazon-ppc-optimizer
   git pull origin main
   ```

2. **Run the redeploy script**:
   ```bash
   ./redeploy.sh
   ```

   This will:
   - Pull latest code from GitHub
   - Deploy to Google Cloud Function with updated profile ID
   - Configure all secrets from Secret Manager
   - Set up the function with proper timeout and memory

3. **Wait for deployment** (usually 2-3 minutes)

---

## 🧪 STEP 3: Verify the Deployment

### Test the Optimizer Function

```bash
# Get the function URL
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)' \
  --project=amazon-ppc-474902)

# Test health endpoint
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?health=true"
```

Expected response:
```json
{
  "status": "healthy",
  "profile_id": "1780498399290938",
  "timestamp": "2024-11-12T..."
}
```

### Trigger a Test Run

```bash
# Trigger optimizer (dry run mode)
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -X POST "${FUNCTION_URL}" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

### Check Cloud Function Logs

```bash
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=50 \
  --project=amazon-ppc-474902
```

Look for:
- ✅ "Using profile ID: 1780498399290938"
- ✅ "Retrieved campaigns: X"
- ✅ "Optimization complete"
- ❌ No "Using placeholder profile_id" errors

---

## 📊 STEP 4: Verify Data in BigQuery

After the optimizer runs (wait ~10 minutes for Cloud Scheduler or trigger manually):

```bash
# Check recent optimization results
bq query --use_legacy_sql=false \
  --project_id=amazon-ppc-474902 \
  "SELECT 
    run_date,
    profile_id,
    status,
    bids_increased,
    campaigns_analyzed
   FROM \`amazon-ppc-474902.amazon_ppc.optimization_results\`
   WHERE profile_id = '1780498399290938'
   ORDER BY run_date DESC
   LIMIT 5"
```

### Check Campaign Performance Data

```bash
bq query --use_legacy_sql=false \
  --project_id=amazon-ppc-474902 \
  "SELECT 
    campaign_id,
    campaign_name,
    date,
    impressions,
    clicks,
    cost,
    sales,
    acos
   FROM \`amazon-ppc-474902.amazon_ppc.campaign_performance\`
   WHERE profile_id = '1780498399290938'
   ORDER BY date DESC
   LIMIT 10"
```

---

## 🎯 STEP 5: Check Dashboard

1. **Open your dashboard**: https://amazon-ppc-dashboard-qb63yk.abacusai.app

2. **Navigate to**:
   - **Overview** - Should show real metrics (not zero)
   - **Campaigns** - Should list actual campaigns
   - **Analytics** - Should show spend/sales trends
   - **Performance** - Should show optimization actions

3. **Verify financial metrics**:
   - Total Spend: Should show actual dollar amounts
   - Total Sales: Should show revenue data
   - ACOS: Should show percentage (not "--")
   - ROAS: Should show return metrics

---

## ⏰ STEP 6: Monitor Scheduled Runs

The optimizer runs automatically via Cloud Scheduler:

```bash
# Check scheduler status
gcloud scheduler jobs describe amazon-ppc-optimizer-daily \
  --location=us-central1 \
  --project=amazon-ppc-474902
```

**Default Schedule**: Daily at 6:00 AM UTC (adjust as needed)

To trigger manually:
```bash
gcloud scheduler jobs run amazon-ppc-optimizer-daily \
  --location=us-central1 \
  --project=amazon-ppc-474902
```

---

## 🔍 Troubleshooting

### Issue: "Profile ID still showing as placeholder"

**Solution**: Check Secret Manager
```bash
gcloud secrets versions access latest \
  --secret=ppc-profile-id \
  --project=amazon-ppc-474902
```

Should show: `1780498399290938`

If not, update it:
```bash
echo -n "1780498399290938" | \
  gcloud secrets versions add ppc-profile-id \
    --data-file=- \
    --project=amazon-ppc-474902
```

### Issue: "No data in BigQuery"

**Check**: 
1. Function logs for errors: `gcloud functions logs read amazon-ppc-optimizer`
2. Amazon API credentials are valid
3. Refresh token hasn't expired

### Issue: "Function deployment fails"

**Check**:
1. You have proper IAM permissions
2. All secrets exist in Secret Manager
3. Billing is enabled for the project

---

## 📋 Deployment Checklist

Use this checklist to track your progress:

- [ ] **Step 1**: Pushed changes to GitHub
- [ ] **Step 2**: Ran `./redeploy.sh` successfully
- [ ] **Step 3**: Verified health endpoint returns profile_id
- [ ] **Step 4**: Checked BigQuery has new data with correct profile_id
- [ ] **Step 5**: Dashboard shows real financial metrics
- [ ] **Step 6**: Cloud Scheduler is running on schedule

---

## 🎉 Success Indicators

You'll know it worked when:

✅ **GitHub**: Commit `5292144` visible on main branch  
✅ **Cloud Function**: Health check returns profile_id `1780498399290938`  
✅ **BigQuery**: New rows with `profile_id = '1780498399290938'`  
✅ **Dashboard**: Real spend, sales, and ACOS data (not zeros)  
✅ **Logs**: No "placeholder profile_id" warnings  

---

## 📞 Need Help?

**Repository**: https://github.com/natureswaysoil/Amazom-PPC  
**BigQuery Console**: https://console.cloud.google.com/bigquery?project=amazon-ppc-474902  
**Cloud Functions**: https://console.cloud.google.com/functions/list?project=amazon-ppc-474902  
**Dashboard**: https://amazon-ppc-dashboard-qb63yk.abacusai.app  

---

**Created**: November 12, 2024  
**Profile ID**: 1780498399290938 (US Seller)  
**Status**: Ready for deployment ✅
