# Cloud Run Job Timeout Fix - Complete Solution

This directory contains tools to diagnose and fix the **natureswaysoil-video-job** Cloud Run Job timeout issue caused by Google Sheet access errors.

## 📋 Problem Overview

**Job**: `natureswaysoil-video-job` (region: us-east4)  
**Issue**: Consistent timeouts after 600 seconds  
**Root Cause**: HTTP 400 "Page Not Found" error when accessing Google Sheet via `CSV_URL` environment variable

## 🚀 Quick Start

### Option 1: Automated Fix (Recommended)

```bash
# 1. Diagnose the issue
./diagnose-cloudrun-job.sh

# 2. Apply automatic fix
./fix-cloudrun-sheet.sh

# 3. Test the job
gcloud run jobs execute natureswaysoil-video-job --region=us-east4 --wait
```

### Option 2: Manual Fix

See [CLOUDRUN_QUICK_FIX.md](CLOUDRUN_QUICK_FIX.md) for step-by-step manual instructions.

### Option 3: Python Integration

Integrate the robust Google Sheet fetcher into your application code:

```python
from google_sheet_fetcher import fetch_google_sheet_csv
import sys

csv_data = fetch_google_sheet_csv(max_retries=3, timeout=30)
if csv_data is None:
    print("Failed to fetch Google Sheet")
    sys.exit(1)  # Fast fail instead of waiting for timeout

# Process CSV data
import csv
for row in csv.DictReader(csv_data.splitlines()):
    print(row)
```

## 📁 Files in This Solution

| File | Purpose |
|------|---------|
| `CLOUDRUN_QUICK_FIX.md` | Quick reference guide with common commands |
| `CLOUD_RUN_GOOGLE_SHEET_FIX.md` | Comprehensive documentation with detailed explanations |
| `diagnose-cloudrun-job.sh` | Diagnostic script to identify issues |
| `fix-cloudrun-sheet.sh` | Interactive fix script |
| `google_sheet_fetcher.py` | Python utility with robust error handling |
| `README_CLOUDRUN_FIX.md` | This file |

## 🔍 Common Issues & Solutions

### Issue 1: Wrong URL Format

**Symptom**: "Page Not Found" error, receives HTML instead of CSV

**Cause**: Using regular Google Sheets URL instead of CSV export URL

**Solution**:
```bash
# ❌ Wrong format
https://docs.google.com/spreadsheets/d/ABC123/edit#gid=0

# ✅ Correct format
https://docs.google.com/spreadsheets/d/ABC123/export?format=csv&gid=0
```

### Issue 2: Permission Denied

**Symptom**: HTTP 403 Forbidden error

**Cause**: Service account doesn't have access to the sheet

**Solution**:
1. Get service account email:
   ```bash
   gcloud run jobs describe natureswaysoil-video-job \
     --region=us-east4 \
     --format='value(spec.template.spec.serviceAccountName)'
   ```
2. Share Google Sheet with that email (Viewer permission)

**OR** make the sheet publicly accessible:
1. Open Google Sheet
2. Click "Share" → "Change to anyone with the link"
3. Set to "Viewer"

### Issue 3: Sheet Not Found

**Symptom**: HTTP 404 error

**Cause**: Sheet ID is incorrect or sheet was deleted

**Solution**: Verify the sheet exists and extract the correct ID from the URL

### Issue 4: Job Still Timing Out

**Symptom**: Times out even after fixing URL

**Cause**: Application logic issues, not URL-related

**Solution**: 
1. Check application logs for actual errors
2. Implement fast-fail error handling (use `google_sheet_fetcher.py`)
3. Increase timeout if job legitimately needs more time

## 🛠️ Testing Tools

### Test URL Access from Command Line

```bash
# Test if URL returns CSV (should show data, not HTML)
curl -L "YOUR_CSV_URL" | head -n 5

# Check HTTP status
curl -I -L "YOUR_CSV_URL"
```

### Test with Python Utility

```bash
# Test with CSV_URL environment variable
export CSV_URL="https://docs.google.com/spreadsheets/d/YOUR_ID/export?format=csv&gid=0"
python google_sheet_fetcher.py

# Or test with URL argument
python google_sheet_fetcher.py --url "YOUR_URL" --preview 10
```

## 📊 Monitoring

### View Recent Logs

```bash
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=natureswaysoil-video-job" \
  --limit=50 \
  --format='table(timestamp,severity,textPayload)'
```

### Watch Logs in Real-Time

```bash
gcloud logging tail \
  "resource.type=cloud_run_job AND resource.labels.job_name=natureswaysoil-video-job"
```

### Filter for Errors

```bash
gcloud logging read \
  "resource.type=cloud_run_job 
   AND resource.labels.job_name=natureswaysoil-video-job 
   AND severity>=ERROR" \
  --limit=20
```

## 🔧 Configuration Updates

### Update CSV_URL

```bash
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --set-env-vars CSV_URL="https://docs.google.com/spreadsheets/d/YOUR_ID/export?format=csv&gid=0"
```

### Increase Timeout

```bash
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --task-timeout=1800s
```

### Update Multiple Settings

```bash
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --set-env-vars CSV_URL="YOUR_URL" \
  --task-timeout=1800s \
  --memory=512Mi \
  --cpu=1
```

## 📖 Detailed Documentation

- **Quick Reference**: [CLOUDRUN_QUICK_FIX.md](CLOUDRUN_QUICK_FIX.md)
- **Complete Guide**: [CLOUD_RUN_GOOGLE_SHEET_FIX.md](CLOUD_RUN_GOOGLE_SHEET_FIX.md)

## 🔐 Google Sheets URL Format Reference

### Extract Sheet ID

From URL: `https://docs.google.com/spreadsheets/d/`**`1A2B3C4D5E6F7G8H`**`/edit#gid=0`  
Sheet ID: **`1A2B3C4D5E6F7G8H`** (between `/d/` and `/edit`)

### Extract Tab GID

Click on the tab → URL shows: `...#gid=`**`123456`**  
Tab GID: **`123456`** (after `#gid=`)

### Build CSV Export URL

```
https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}
```

**Example**:
```
https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7G8H/export?format=csv&gid=0
```

## 💡 Best Practices

1. **Always use CSV export format** for programmatic access
2. **Implement fast-fail error handling** to avoid timeouts
3. **Add retry logic with exponential backoff** for transient errors
4. **Log detailed error information** for debugging
5. **Validate URLs before deploying** to production
6. **Monitor job execution** regularly
7. **Set appropriate timeouts** based on actual job duration

## 🆘 Troubleshooting Workflow

```
1. Run diagnostics
   └─> ./diagnose-cloudrun-job.sh

2. Identify issue
   ├─> URL format wrong? → Run fix-cloudrun-sheet.sh
   ├─> Permission denied? → Share sheet with service account
   ├─> Sheet not found? → Verify sheet ID
   └─> Other issues? → Check application logs

3. Test fix
   └─> gcloud run jobs execute natureswaysoil-video-job --region=us-east4 --wait

4. Monitor results
   └─> gcloud logging tail "resource.type=cloud_run_job..."
```

## 📞 Support

- **GitHub Issues**: https://github.com/natureswaysoil/Amazom-PPC/issues
- **Email**: james@natureswaysoil.com
- **Documentation**: See all `.md` files in this directory

## ✅ Success Checklist

After applying fixes, verify:

- [ ] CSV_URL is in correct export format
- [ ] URL is accessible (returns CSV, not HTML)
- [ ] Service account has permissions (or sheet is public)
- [ ] Timeout is appropriate for job duration
- [ ] Application includes error handling
- [ ] Job executes successfully without timeout
- [ ] Logs show successful data retrieval

---

**Last Updated**: November 2025  
**Maintained by**: natureswaysoil team
