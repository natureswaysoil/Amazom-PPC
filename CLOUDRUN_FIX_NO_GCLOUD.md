# Cloud Run Job Fix - Manual Instructions (No gcloud CLI Required)

## ⚠️ Important: Run These Commands in Google Cloud Shell

Since gcloud CLI is not available in your current environment, you'll need to run these commands in **Google Cloud Shell** or any environment with gcloud installed.

---

## 🚀 Quick Fix for Public Google Sheet

Since your Google Sheet is **already public**, you only need to:
1. Update the CSV_URL to use the correct export format
2. Optionally adjust the timeout

---

## 📋 Step-by-Step Instructions

### Step 1: Access Google Cloud Shell

1. Go to: https://console.cloud.google.com
2. Click the **Cloud Shell** icon (>_) in the top right
3. Wait for the terminal to initialize

### Step 2: Verify Your Google Sheet URL

Your Google Sheet URL should look like this:

**❌ WRONG** (regular sharing URL):
```
https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit#gid=0
```

**✅ CORRECT** (CSV export URL):
```
https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0
```

**To convert:**
1. Find your Sheet ID (between `/d/` and `/edit`)
2. Replace the URL format as shown above

### Step 3: Test Your CSV URL

Before updating the Cloud Run Job, test the URL:

```bash
# Replace YOUR_CSV_URL with your actual URL
curl -L "YOUR_CSV_URL" | head -n 5
```

**Expected**: You should see CSV data (comma-separated values)  
**If you see HTML**: The URL format is wrong or the sheet isn't accessible

---

## 🔧 Fix Commands (Run in Cloud Shell)

### Option A: Quick One-Command Fix

Replace `YOUR_SHEET_ID` and `GID` with your actual values:

```bash
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --set-env-vars CSV_URL="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0"
```

### Option B: Update Multiple Settings

If you also want to increase the timeout:

```bash
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --set-env-vars CSV_URL="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0" \
  --task-timeout=1800s
```

---

## 🧪 Test the Fix

After updating the configuration:

```bash
gcloud run jobs execute natureswaysoil-video-job \
  --region=us-east4 \
  --wait
```

This will run the job and wait for it to complete. You should see it finish successfully without timing out.

---

## 📊 Monitor the Results

### View Recent Logs

```bash
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=natureswaysoil-video-job" \
  --limit=50 \
  --format='table(timestamp,severity,textPayload)'
```

### Check for Errors

```bash
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=natureswaysoil-video-job AND severity>=ERROR" \
  --limit=20
```

### Watch Logs in Real-Time

```bash
gcloud logging tail \
  "resource.type=cloud_run_job AND resource.labels.job_name=natureswaysoil-video-job"
```

---

## 🌐 Alternative: Fix via Google Cloud Console (No Commands)

If you prefer using the web interface:

### Step 1: Navigate to Cloud Run Jobs
1. Go to: https://console.cloud.google.com/run/jobs
2. Select your project
3. Find and click **natureswaysoil-video-job**

### Step 2: Edit Configuration
1. Click the **"EDIT"** button at the top
2. Click on the **"Variables & Secrets"** tab
3. Find the `CSV_URL` environment variable
4. Click the **edit (pencil)** icon

### Step 3: Update CSV_URL
1. Replace the value with:
   ```
   https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0
   ```
2. Replace `YOUR_SHEET_ID` with your actual Sheet ID
3. Replace `gid=0` with your tab's GID if needed

### Step 4: (Optional) Increase Timeout
1. Click on the **"Container"** tab
2. Find **"Task timeout"**
3. Change from **600** to **1800** seconds (or appropriate value)

### Step 5: Deploy Changes
1. Click **"DEPLOY"** at the bottom
2. Wait for deployment to complete

### Step 6: Test the Job
1. Click the **"EXECUTE"** button at the top
2. Click **"Execute job"** in the dialog
3. Monitor the execution - it should complete without timeout

---

## 🔍 How to Find Your Sheet ID and GID

### Finding Sheet ID
From your Google Sheets URL:
```
https://docs.google.com/spreadsheets/d/[THIS_IS_YOUR_SHEET_ID]/edit#gid=0
                                       ^^^^^^^^^^^^^^^^^^^^^^^^
```

**Example:**
```
URL: https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7G8H9I0J/edit#gid=0
Sheet ID: 1A2B3C4D5E6F7G8H9I0J
```

### Finding GID (Tab ID)
1. Open your Google Sheet
2. Click on the tab/sheet you want to export
3. Look at the URL - the number after `#gid=` is your GID

**Example:**
```
URL: ...#gid=123456789
GID: 123456789
```

For the first (default) tab, GID is usually `0`.

---

## ✅ Verification Checklist

After making changes, verify:

- [ ] CSV_URL uses `/export?format=csv` format (not `/edit`)
- [ ] Sheet ID is correct
- [ ] GID matches your desired tab
- [ ] URL test with curl returns CSV data (not HTML)
- [ ] Cloud Run Job configuration is updated
- [ ] Job executes successfully without timeout
- [ ] Logs show successful data retrieval

---

## 🎯 Complete Example

Here's a complete example with a sample Sheet ID:

### Before (Wrong):
```
https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz123456789/edit#gid=0
```

### After (Correct):
```
https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz123456789/export?format=csv&gid=0
```

### Update Command:
```bash
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --set-env-vars CSV_URL="https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz123456789/export?format=csv&gid=0"
```

---

## 🆘 Troubleshooting

### Issue: "Job not found"
**Solution**: Verify the job name and region:
```bash
gcloud run jobs list --regions=us-east4
```

### Issue: "Permission denied"
**Solution**: Ensure you're authenticated:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Issue: Still getting HTML instead of CSV
**Possible causes:**
1. GID is wrong - try `gid=0` for the first tab
2. Sheet ID is incorrect - double-check the URL
3. Sheet isn't truly public - verify sharing settings

**To verify sheet is public:**
1. Open Google Sheet
2. Click "Share"
3. Should say "Anyone with the link" can view
4. Test in incognito/private browser window

### Issue: Job still times out
**If URL is correct but job still times out:**
1. The issue might be in your application code
2. Consider integrating the `google_sheet_fetcher.py` utility
3. Check application logs for specific errors:
   ```bash
   gcloud logging read \
     "resource.type=cloud_run_job AND resource.labels.job_name=natureswaysoil-video-job" \
     --limit=100
   ```

---

## 📞 Need More Help?

1. **Google Cloud Shell Tutorial**: https://cloud.google.com/shell/docs/using-cloud-shell
2. **Cloud Run Jobs Documentation**: https://cloud.google.com/run/docs/create-jobs
3. **Google Sheets CSV Export**: https://support.google.com/docs/answer/183965

---

## 🚀 Quick Start Summary

**For someone with access to Google Cloud Shell:**

1. Open Cloud Shell: https://console.cloud.google.com
2. Run this command (replace YOUR_SHEET_ID):
   ```bash
   gcloud run jobs update natureswaysoil-video-job \
     --region=us-east4 \
     --set-env-vars CSV_URL="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0"
   ```
3. Test: `gcloud run jobs execute natureswaysoil-video-job --region=us-east4 --wait`
4. Done! ✅

---

**Last Updated**: November 8, 2025  
**Contact**: james@natureswaysoil.com
