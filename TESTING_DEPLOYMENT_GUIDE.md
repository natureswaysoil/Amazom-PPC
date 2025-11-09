# Testing and Deployment Guide - HTTP Client Improvements

## Quick Deployment Commands

### Deploy to Google Cloud Functions

```bash
# Set your project
gcloud config set project amazon-ppc-474902

# Deploy the function with updated code
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
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest
```

---

## Testing the Improvements

### 1. Test Locally (with Debug Logging)

Create a test script:

```python
#!/usr/bin/env python3
import logging
import os

# Enable DEBUG logging to see all request/response details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set your credentials
os.environ['AMAZON_CLIENT_ID'] = 'your_client_id'
os.environ['AMAZON_CLIENT_SECRET'] = 'your_client_secret'
os.environ['AMAZON_REFRESH_TOKEN'] = 'your_refresh_token'
os.environ['AMAZON_PROFILE_ID'] = 'your_profile_id'

from optimizer_core import PPCAutomation

# Initialize and run a test
automation = PPCAutomation({
    'amazon_api': {
        'client_id': os.environ['AMAZON_CLIENT_ID'],
        'client_secret': os.environ['AMAZON_CLIENT_SECRET'],
        'refresh_token': os.environ['AMAZON_REFRESH_TOKEN'],
        'profile_id': os.environ['AMAZON_PROFILE_ID'],
        'region': 'NA'
    }
})

# Test connection - this will log detailed request/response info
result = automation.verify_connection(sample_size=3)
print(f"\nConnection test result: {result}")
```

Save as `test_http_logging.py` and run:

```bash
python test_http_logging.py
```

**Expected output:**
```
DEBUG - optimizer_core - Amazon API GET https://advertising-api.amazon.com/v2/sp/campaigns (attempt 1/3)
DEBUG - optimizer_core - Request headers: {'Authorization': 'REDACTED', 'Content-Type': 'application/json', ...}
DEBUG - optimizer_core - Response status: 200
DEBUG - optimizer_core - Response headers: {'content-type': 'application/json', ...}
INFO - optimizer_core - Retrieved 3 campaigns
```

### 2. Test in Cloud Functions (with Logs)

Execute the function and watch logs:

```bash
# Terminal 1: Tail logs
gcloud logging tail \
  'resource.type="cloud_function" AND resource.labels.function_name="amazon-ppc-optimizer"' \
  --project=amazon-ppc-474902

# Terminal 2: Invoke function
gcloud functions call amazon-ppc-optimizer \
  --gen2 \
  --region=us-central1 \
  --data '{"dry_run": true, "features": ["verify_connection"]}'
```

### 3. Trigger a 400 Error Intentionally (for testing)

To verify the enhanced logging captures 400 errors properly:

```python
# Create a test that sends invalid data
from optimizer_core import AmazonAdsAPI

api = AmazonAdsAPI(config)

# This will fail with 400 and log detailed error info
try:
    response = api._request('POST', '/v2/sp/campaigns', json={
        'invalidField': 'badValue'  # Invalid payload
    })
except Exception as e:
    print(f"Caught expected error: {e}")
```

Check logs for the detailed output showing:
- The exact invalid payload sent
- The 400 response status
- The error message from Amazon explaining what's wrong

---

## Monitoring HTTP Errors

### View All HTTP Errors (400, 500, etc.)

```bash
gcloud logging read \
  'resource.type="cloud_function" 
   AND resource.labels.function_name="amazon-ppc-optimizer" 
   AND (textPayload=~"error 400" OR textPayload=~"status: 400" OR textPayload=~"400 Client Error")' \
  --limit=50 \
  --project=amazon-ppc-474902 \
  --format='table(timestamp, severity, textPayload)'
```

### View Request/Response Details

```bash
gcloud logging read \
  'resource.type="cloud_function" 
   AND resource.labels.function_name="amazon-ppc-optimizer" 
   AND (textPayload=~"Request body preview" OR textPayload=~"Response body preview")' \
  --limit=50 \
  --project=amazon-ppc-474902
```

### View Dashboard Errors

```bash
gcloud logging read \
  'resource.type="cloud_function" 
   AND resource.labels.function_name="amazon-ppc-optimizer" 
   AND textPayload=~"Dashboard.*returned"' \
  --limit=50 \
  --project=amazon-ppc-474902
```

---

## Troubleshooting Common Issues

### Issue: Not Seeing Debug Logs

**Solution:** Cloud Functions defaults to INFO level. Set LOG_LEVEL environment variable:

```bash
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  ... (other flags) \
  --set-env-vars LOG_LEVEL=DEBUG
```

Or programmatically in `main.py`:

```python
import os
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(level=getattr(logging, log_level))
```

### Issue: Logs Are Too Verbose

**Solution:** Use INFO level and only ERROR/WARNING will show request/response details:

```bash
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  ... (other flags) \
  --set-env-vars LOG_LEVEL=INFO
```

### Issue: Still Seeing HTTP 400 Errors

**Solution:** With the enhanced logging, check:

1. **URL** - Is the endpoint correct?
   ```
   Look for: "Amazon API POST https://..."
   ```

2. **Request Body** - Is the payload valid?
   ```
   Look for: "Request body preview: {...}"
   ```

3. **Response Body** - What does Amazon say?
   ```
   Look for: "Amazon API error 400: {error details}"
   ```

4. **Common 400 Causes:**
   - Missing required field → Check API docs
   - Invalid enum value → Check allowed values
   - Wrong data type → Check field types
   - State transition not allowed → Check campaign/ad group state

---

## Performance Considerations

### Log Volume

With DEBUG logging enabled, expect approximately:
- **2-4 log entries per HTTP request** (request + response + optional error)
- **~500-1500 bytes per request** (with preview truncation)

For a typical optimization run with 100 API calls:
- **~200-400 log entries**
- **~50-150 KB of log data**

This is within Cloud Functions/Cloud Logging free tier limits.

### Cost Impact

- **Negligible** - Logging is built into GCP and included in Cloud Functions pricing
- Log storage beyond free tier: $0.50/GB/month
- Typical monthly logs: < 100 MB = negligible cost

### Disable Debug Logs in Production

For production, use INFO level:
```bash
--set-env-vars LOG_LEVEL=INFO
```

This still logs:
- ✅ Error response bodies (400+)
- ✅ Request failures
- ✅ Retry attempts
- ❌ Request/response details for successful calls (reduces noise)

---

## Verification Checklist

After deploying the improvements:

- [ ] Function deploys successfully
- [ ] Health check returns 200
- [ ] Logs show request URLs for API calls
- [ ] Errors include response body preview
- [ ] Sensitive headers (Authorization) are masked
- [ ] Retry logic works (see attempt numbers in logs)
- [ ] 400 errors show detailed error message from API
- [ ] Dashboard calls log request/response details
- [ ] Report downloads log status and size

---

## Example: Analyzing a Real 400 Error

### Before (Old Logging):
```
ERROR: Request failed after 3 attempts: 400 Client Error: Bad Request for url: https://...
```
❌ No details about what's wrong

### After (Enhanced Logging):
```
DEBUG: Amazon API POST https://advertising-api.amazon.com/v2/sp/campaigns/123/bids (attempt 1/3)
DEBUG: Request headers: {'Authorization': 'REDACTED', 'Content-Type': 'application/json', ...}
DEBUG: Request body preview: {"campaignId": "123", "bid": {"amount": -5.0}}
DEBUG: Response status: 400
ERROR: Amazon API error 400: {"code":"INVALID_ARGUMENT","details":"Bid amount must be positive"}
ERROR: Request failed after 3 attempts: 400 Client Error
ERROR: Final error response body: {"code":"INVALID_ARGUMENT","details":"Bid amount must be positive"}
```
✅ Clear: The bid amount is negative, which is invalid

**Fix:** Update code to validate bid amount is positive before sending to API.

---

## Rolling Back (If Needed)

If you need to revert the changes:

```bash
# Redeploy from a previous version
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --source=gs://your-backup-bucket/previous-version.zip \
  ... (other flags)
```

Or use git:
```bash
git revert HEAD
git push origin main
# Then redeploy
```

---

## Next Steps

1. **Deploy** the updated code
2. **Test** with a dry run to verify logging works
3. **Monitor** logs for any HTTP 400 errors
4. **Analyze** error details in logs
5. **Fix** any identified issues
6. **Redeploy** and verify

---

## Support

If you encounter issues:

1. Check logs first with the commands above
2. Look for "Request body preview" and "Response body preview" in logs
3. Compare request payload with Amazon Ads API documentation
4. File issues at: https://github.com/natureswaysoil/Amazom-PPC/issues

---

**Created**: November 9, 2025  
**Version**: 1.0  
**Status**: Production Ready ✅
