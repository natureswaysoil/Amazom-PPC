# Quick Reference: Fixing natureswaysoil-video-job Timeout

## The Problem
Cloud Run Job `natureswaysoil-video-job` times out after 600s due to HTTP 400 "Page Not Found" when accessing Google Sheet via `CSV_URL`.

## Quick Fix (3 steps)

### 1. Run Diagnostics
```bash
./diagnose-cloudrun-job.sh
```
This will identify the exact issue with your CSV_URL.

### 2. Apply Fix
```bash
./fix-cloudrun-sheet.sh
```
This will:
- Convert your Google Sheets URL to proper CSV export format
- Test accessibility
- Update the Cloud Run Job configuration

### 3. Test
```bash
gcloud run jobs execute natureswaysoil-video-job --region=us-east4 --wait
```

---

## Manual Fix Commands

If you prefer to fix manually:

### Check Current Config
```bash
gcloud run jobs describe natureswaysoil-video-job \
  --region=us-east4 \
  --format='json' | jq '.spec.template.spec.template.spec.containers[0].env'
```

### Update CSV_URL (use your actual sheet ID)
```bash
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --set-env-vars CSV_URL="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0"
```

### Increase Timeout (if needed)
```bash
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --task-timeout=1800s
```

### Test URL Manually
```bash
curl -L "YOUR_CSV_URL" | head -n 5
```
Should return CSV data, not HTML.

---

## Common Issues & Solutions

### Issue: "Page Not Found" (HTML instead of CSV)
**Cause**: Wrong URL format  
**Fix**: URL must be `/export?format=csv`, not `/edit`

**Wrong**: `https://docs.google.com/spreadsheets/d/ABC123/edit#gid=0`  
**Right**: `https://docs.google.com/spreadsheets/d/ABC123/export?format=csv&gid=0`

### Issue: HTTP 403 Forbidden
**Cause**: Service account lacks permissions  
**Fix**: Share sheet with service account or make public

Get service account:
```bash
gcloud run jobs describe natureswaysoil-video-job \
  --region=us-east4 \
  --format='value(spec.template.spec.serviceAccountName)'
```

Then share Google Sheet with that email address (Viewer permission).

### Issue: HTTP 404 Not Found
**Cause**: Sheet doesn't exist or wrong ID  
**Fix**: Verify sheet URL in browser, check sheet ID

### Issue: Still timing out after fix
**Cause**: Application issue, not URL  
**Fix**: Check application logs for actual errors

```bash
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=natureswaysoil-video-job" \
  --limit=50 \
  --format='table(timestamp,severity,textPayload)'
```

---

## Google Sheets URL Format Guide

### Finding Sheet ID
URL: `https://docs.google.com/spreadsheets/d/`**`1A2B3C4D5E6F7G8H`**`/edit#gid=0`  
Sheet ID: **`1A2B3C4D5E6F7G8H`** (between `/d/` and `/edit`)

### Finding Tab GID
Click on the tab you want → Look at URL: `...#gid=`**`123456`**  
Tab GID: **`123456`** (after `#gid=`)

### Building Export URL
Format: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}`

Example: `https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7G8H/export?format=csv&gid=0`

---

## Monitoring

### Watch logs in real-time
```bash
gcloud logging tail \
  "resource.type=cloud_run_job AND resource.labels.job_name=natureswaysoil-video-job"
```

### Check for errors
```bash
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=natureswaysoil-video-job AND severity>=ERROR" \
  --limit=20
```

---

## Additional Help

See detailed documentation: `CLOUD_RUN_GOOGLE_SHEET_FIX.md`

## Contact
- GitHub Issues: https://github.com/natureswaysoil/Amazom-PPC/issues
- Email: james@natureswaysoil.com
