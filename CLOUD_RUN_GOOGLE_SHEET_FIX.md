# Cloud Run Job - Google Sheet Access Fix

## Problem Summary
Cloud Run Job `natureswaysoil-video-job` in region `us-east4` is timing out after 600 seconds due to HTTP 400 "Page Not Found" error when accessing a Google Sheet via the `CSV_URL` environment variable.

## Root Causes
1. **Incorrect URL format**: Google Sheets URL is not in CSV export format
2. **Permission issues**: Service account lacks access to the sheet
3. **Private/restricted sheet**: Sheet is not publicly accessible
4. **Deleted/moved sheet**: The sheet no longer exists at that URL

---

## Quick Fix Steps

### Step 1: Verify the Google Sheet URL Format

Google Sheets must be accessed in a specific format for CSV export:

**❌ WRONG** (typical sharing URL):
```
https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=0
```

**✅ CORRECT** (CSV export URL):
```
https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0
```

To fix:
1. Find your sheet ID in the URL (between `/d/` and `/edit`)
2. Replace the entire URL with the export format above
3. If using a specific tab, replace `gid=0` with your tab's GID

### Step 2: Check Sheet Permissions

#### Option A: Make Sheet Publicly Accessible (Simplest)
1. Open your Google Sheet
2. Click **Share** button (top right)
3. Click **Change to anyone with the link**
4. Set permission to **Viewer**
5. Click **Done**

#### Option B: Grant Service Account Access (Recommended for Production)
1. Get your Cloud Run Job's service account email:
   ```bash
   gcloud run jobs describe natureswaysoil-video-job \
     --region=us-east4 \
     --format='value(spec.template.spec.serviceAccountName)'
   ```

2. If no custom service account, it uses the default:
   ```
   {PROJECT_NUMBER}-compute@developer.gserviceaccount.com
   ```
   Get project number:
   ```bash
   gcloud projects describe $(gcloud config get-value project) \
     --format='value(projectNumber)'
   ```

3. Share the Google Sheet with the service account email:
   - Open Google Sheet → **Share**
   - Add the service account email
   - Set permission to **Viewer**
   - Uncheck "Notify people"
   - Click **Share**

### Step 3: Update the CSV_URL Environment Variable

```bash
# Update the Cloud Run Job with corrected URL
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --set-env-vars CSV_URL="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0"
```

### Step 4: Test the URL Manually

Before deploying, verify the URL works:

```bash
# Test with curl (should return CSV data, not HTML)
curl -L "YOUR_CSV_URL_HERE"

# If you get HTML with "Page Not Found", the URL is wrong or permissions are missing
```

### Step 5: Increase Timeout (Optional)

If the job legitimately needs more than 600 seconds:

```bash
gcloud run jobs update natureswaysoil-video-job \
  --region=us-east4 \
  --task-timeout=1800s
```

---

## Diagnostic Script

Run this to diagnose the current configuration:

```bash
#!/bin/bash

REGION="us-east4"
JOB_NAME="natureswaysoil-video-job"

echo "=== Cloud Run Job Diagnostics ==="
echo ""

# Get current configuration
echo "📋 Current Configuration:"
gcloud run jobs describe $JOB_NAME --region=$REGION \
  --format='table(
    spec.template.spec.serviceAccountName:label="Service Account",
    spec.template.spec.taskCount:label="Tasks",
    spec.template.spec.template.spec.containers[0].env[].name:label="Env Vars"
  )'

echo ""
echo "🔍 Environment Variables:"
gcloud run jobs describe $JOB_NAME --region=$REGION \
  --format='value(spec.template.spec.template.spec.containers[0].env)' | \
  grep -i csv || echo "No CSV_URL found"

echo ""
echo "⏱️ Timeout Settings:"
gcloud run jobs describe $JOB_NAME --region=$REGION \
  --format='value(spec.template.spec.template.spec.containers[0].resources.limits.cpu,
    spec.template.spec.template.spec.containers[0].resources.limits.memory,
    spec.template.spec.template.spec.timeoutSeconds)'

echo ""
echo "📜 Recent Execution Logs:"
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME" \
  --limit=10 \
  --format='table(timestamp,severity,textPayload)' \
  --region=$REGION

echo ""
echo "=== Next Steps ==="
echo "1. Check if CSV_URL is in the correct format (export?format=csv)"
echo "2. Verify Google Sheet permissions"
echo "3. Test URL manually with: curl -L 'YOUR_CSV_URL'"
```

---

## Application Code Improvements

Add better error handling for Google Sheet access in your application:

### Python Example

```python
import os
import requests
import sys
import time
from typing import Optional

def fetch_google_sheet_csv(max_retries: int = 3, timeout: int = 30) -> Optional[str]:
    """
    Fetch CSV data from Google Sheet with proper error handling and retries.
    
    Args:
        max_retries: Number of retry attempts
        timeout: Request timeout in seconds
        
    Returns:
        CSV content as string, or None if failed
    """
    csv_url = os.getenv('CSV_URL')
    
    if not csv_url:
        print("ERROR: CSV_URL environment variable not set", file=sys.stderr)
        return None
    
    # Validate URL format
    if '/export?format=csv' not in csv_url:
        print("WARNING: CSV_URL may not be in CSV export format", file=sys.stderr)
        print(f"Expected format: https://docs.google.com/spreadsheets/d/{{ID}}/export?format=csv&gid=0", file=sys.stderr)
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Attempting to fetch Google Sheet (attempt {attempt}/{max_retries})...")
            
            response = requests.get(
                csv_url,
                timeout=timeout,
                allow_redirects=True,
                headers={'User-Agent': 'Cloud-Run-Job/1.0'}
            )
            
            # Check for HTML error pages (like "Page Not Found")
            content_type = response.headers.get('content-type', '').lower()
            
            if 'text/html' in content_type:
                print(f"ERROR: Received HTML instead of CSV. Status: {response.status_code}", file=sys.stderr)
                print(f"URL: {csv_url}", file=sys.stderr)
                print(f"Response preview: {response.text[:500]}", file=sys.stderr)
                
                if attempt == max_retries:
                    print("FATAL: All retry attempts exhausted", file=sys.stderr)
                    return None
                    
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            
            if response.status_code == 200:
                print(f"✓ Successfully fetched CSV data ({len(response.text)} bytes)")
                return response.text
            else:
                print(f"ERROR: HTTP {response.status_code}: {response.reason}", file=sys.stderr)
                
        except requests.Timeout:
            print(f"ERROR: Request timeout after {timeout}s", file=sys.stderr)
        except requests.RequestException as e:
            print(f"ERROR: Request failed: {e}", file=sys.stderr)
        
        if attempt < max_retries:
            wait_time = 2 ** attempt
            print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    return None


def main():
    """Main entry point with fast-fail on CSV access errors"""
    print("Starting Cloud Run Job...")
    
    # Fetch CSV with timeout to prevent hanging
    csv_data = fetch_google_sheet_csv(max_retries=3, timeout=30)
    
    if csv_data is None:
        print("FATAL: Failed to fetch Google Sheet CSV", file=sys.stderr)
        sys.exit(1)  # Exit immediately instead of waiting for timeout
    
    # Process CSV data
    print(f"Processing {len(csv_data.splitlines())} rows...")
    # ... your processing logic here ...
    
    print("Job completed successfully")


if __name__ == '__main__':
    main()
```

### Node.js Example

```javascript
const axios = require('axios');

async function fetchGoogleSheetCSV(maxRetries = 3, timeout = 30000) {
  const csvUrl = process.env.CSV_URL;
  
  if (!csvUrl) {
    console.error('ERROR: CSV_URL environment variable not set');
    return null;
  }
  
  // Validate URL format
  if (!csvUrl.includes('/export?format=csv')) {
    console.warn('WARNING: CSV_URL may not be in CSV export format');
  }
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`Attempting to fetch Google Sheet (attempt ${attempt}/${maxRetries})...`);
      
      const response = await axios.get(csvUrl, {
        timeout,
        maxRedirects: 5,
        validateStatus: status => status === 200,
        headers: { 'User-Agent': 'Cloud-Run-Job/1.0' }
      });
      
      // Check for HTML error pages
      const contentType = response.headers['content-type'] || '';
      
      if (contentType.includes('text/html')) {
        console.error(`ERROR: Received HTML instead of CSV`);
        console.error(`URL: ${csvUrl}`);
        console.error(`Response preview: ${response.data.substring(0, 500)}`);
        
        if (attempt === maxRetries) {
          console.error('FATAL: All retry attempts exhausted');
          return null;
        }
        
        await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
        continue;
      }
      
      console.log(`✓ Successfully fetched CSV data (${response.data.length} bytes)`);
      return response.data;
      
    } catch (error) {
      if (error.code === 'ECONNABORTED') {
        console.error(`ERROR: Request timeout after ${timeout}ms`);
      } else {
        console.error(`ERROR: Request failed: ${error.message}`);
      }
      
      if (attempt < maxRetries) {
        const waitTime = Math.pow(2, attempt);
        console.log(`Retrying in ${waitTime} seconds...`);
        await new Promise(resolve => setTimeout(resolve, waitTime * 1000));
      }
    }
  }
  
  return null;
}

async function main() {
  console.log('Starting Cloud Run Job...');
  
  // Fetch CSV with fast-fail on errors
  const csvData = await fetchGoogleSheetCSV(3, 30000);
  
  if (!csvData) {
    console.error('FATAL: Failed to fetch Google Sheet CSV');
    process.exit(1);  // Exit immediately instead of waiting for timeout
  }
  
  // Process CSV data
  const rows = csvData.split('\n');
  console.log(`Processing ${rows.length} rows...`);
  // ... your processing logic here ...
  
  console.log('Job completed successfully');
}

main().catch(error => {
  console.error('Unhandled error:', error);
  process.exit(1);
});
```

---

## Deployment Checklist

Before deploying the fixed configuration:

- [ ] Google Sheet URL is in CSV export format (`/export?format=csv`)
- [ ] Sheet permissions allow service account or public access
- [ ] Test URL with `curl` returns CSV data (not HTML)
- [ ] Application code includes fast-fail error handling
- [ ] Timeout is appropriate for job duration (not just waiting for errors)
- [ ] Logging captures CSV_URL for debugging
- [ ] Service account has necessary Google Sheets API permissions (if using API)

---

## Monitoring and Alerts

Set up alerts to catch this issue early:

```bash
# Create log-based alert for "Page Not Found" errors
gcloud alpha monitoring policies create \
  --notification-channels=YOUR_CHANNEL_ID \
  --display-name="Cloud Run Job - Google Sheet Access Error" \
  --condition-display-name="Page Not Found in Logs" \
  --condition-threshold-value=1 \
  --condition-threshold-duration=60s \
  --condition-filter='
    resource.type="cloud_run_job"
    AND resource.labels.job_name="natureswaysoil-video-job"
    AND (textPayload=~"Page Not Found" OR textPayload=~"HTTP 400")
  '
```

---

## Additional Resources

- [Google Sheets CSV Export Format](https://support.google.com/docs/answer/183965)
- [Cloud Run Job Timeouts](https://cloud.google.com/run/docs/configuring/task-timeout)
- [Service Account Permissions](https://cloud.google.com/iam/docs/service-accounts)
- [Cloud Run Job Troubleshooting](https://cloud.google.com/run/docs/troubleshooting)

---

## Contact
If issues persist after following this guide, check:
1. Cloud Run Job execution logs in Cloud Logging
2. Google Sheet sharing settings
3. Network/firewall rules that might block Google Sheets API
