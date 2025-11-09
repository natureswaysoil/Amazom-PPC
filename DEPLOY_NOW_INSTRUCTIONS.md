# 🚀 Deploy the HTTP Client Improvements

## Option 1: Google Cloud Shell (Recommended - 2 minutes)

### Step 1: Open Cloud Shell
1. Go to: https://console.cloud.google.com
2. Click the **Cloud Shell** icon **(>_)** in the top-right corner
3. Wait for the terminal to load

### Step 2: Clone/Update Repository
```bash
# If you haven't cloned the repo yet
git clone https://github.com/natureswaysoil/Amazom-PPC.git
cd Amazom-PPC

# Or if you already have it, update it
cd Amazom-PPC
git pull origin main
```

### Step 3: Run the Deploy Script
```bash
./deploy-with-improvements.sh
```

That's it! The script will:
- ✅ Set the correct project
- ✅ Deploy with all secrets
- ✅ Configure enhanced logging
- ✅ Show you the function URL
- ✅ Give you test commands

---

## Option 2: Manual Commands (if script doesn't work)

```bash
# Set project
gcloud config set project amazon-ppc-474902

# Deploy
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --set-env-vars=LOG_LEVEL=INFO \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest
```

---

## After Deployment: Test the Improvements

### Test 1: Verify Connection (Quick Test)
```bash
gcloud functions call amazon-ppc-optimizer \
  --gen2 \
  --region=us-central1 \
  --data '{"dry_run":true,"features":["verify_connection"]}'
```

### Test 2: Watch Logs in Real-Time
```bash
gcloud logging tail \
  'resource.type="cloud_function" AND resource.labels.function_name="amazon-ppc-optimizer"' \
  --project=amazon-ppc-474902
```

### Test 3: Check for Errors
```bash
gcloud logging read \
  'resource.type="cloud_function" AND resource.labels.function_name="amazon-ppc-optimizer" AND severity>=ERROR' \
  --limit=20 \
  --project=amazon-ppc-474902
```

---

## What to Look For in Logs

With the improvements, you should now see:

✅ **Request Details:**
```
DEBUG: Amazon API GET https://advertising-api.amazon.com/v2/sp/campaigns (attempt 1/3)
DEBUG: Request headers: {'Authorization': 'REDACTED', ...}
```

✅ **Response Details:**
```
DEBUG: Response status: 200
DEBUG: Response headers: {...}
```

✅ **Error Details (if HTTP 400):**
```
ERROR: Amazon API error 400: {"code":"INVALID_ARGUMENT","details":"Campaign state transition not allowed"}
ERROR: Final error response body: {"code":"INVALID_ARGUMENT",...}
```

---

## Enable Debug Logging (Optional)

For maximum detail during troubleshooting:

```bash
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

# If this prints "(unset)", set your active project first:
# gcloud config set project YOUR_PROJECT_ID

gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --project="$PROJECT_ID" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --set-env-vars=LOG_LEVEL=DEBUG \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest
```

---

## Troubleshooting

### Issue: "gcloud: command not found"
**Solution:** You're in your dev container. Use Google Cloud Shell instead (it has gcloud pre-installed).

### Issue: "Permission denied"
**Solution:** Make script executable:
```bash
chmod +x deploy-with-improvements.sh
```

### Issue: "Secret not found"
**Solution:** Verify secrets exist:
```bash
gcloud secrets list --project=amazon-ppc-474902
```

### Issue: Deployment takes too long
**Normal:** First deployment can take 2-3 minutes. Subsequent deployments are faster (~1 minute).

---

## Quick Summary

**What changed:** Enhanced HTTP error logging throughout the codebase  
**Impact:** You'll now see detailed request/response info for all HTTP 400 errors  
**Risk:** Zero - all changes are backward compatible  
**Time to deploy:** 2-3 minutes  

**Next step:** Open Google Cloud Shell and run `./deploy-with-improvements.sh`

---

Last Updated: November 9, 2025
