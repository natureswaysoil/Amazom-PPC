# Testing the Fix with Google Secret Manager

This guide explains how to test the Amazon Ads API v3 fix using credentials stored in Google Secret Manager.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated
- Access to the `nature-way-soils` GCP project
- Secrets configured in Google Secret Manager:
  - `amazon-client-id`
  - `amazon-client-secret`
  - `amazon-refresh-token`
  - `amazon-profile-id`

## Quick Test (Recommended)

### 1. Load Credentials from Secret Manager

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Set project
export GCP_PROJECT_ID=nature-way-soils

# Load secrets into environment
eval $(python load_secrets.py --project nature-way-soils)
```

### 2. Verify API Connectivity

This tests the fixed API request format without making any changes:

```bash
# Test connection with the fix
python optimizer_core.py \
  --config sample_config.yaml \
  --verify-connection \
  --verify-sample-size 5
```

**Expected Output (Success):**
```
✓ Amazon Ads API connectivity verified (v3 list)
✓ Retrieved 5 campaigns
✓ Sample campaigns: [...]
```

**Previous Error (Before Fix):**
```
✗ Error fetching budgets: 400 Name campaignId not found inside m at [9:32]
```

### 3. Test Budget Fetching (Dry Run)

```bash
# Run budget fetch in dry-run mode
python optimizer_core.py \
  --config sample_config.yaml \
  --dry-run
```

## Detailed Testing

### Test 1: Verify Secret Loading

```bash
python load_secrets.py --project nature-way-soils --verify
```

**Expected Output:**
```
✓ Loaded AMAZON_CLIENT_ID
✓ Loaded AMAZON_CLIENT_SECRET
✓ Loaded AMAZON_REFRESH_TOKEN
✓ Loaded AMAZON_PROFILE_ID
✓ All required secrets loaded successfully!
```

### Test 2: Test Each Endpoint Format

The fix tries multiple endpoints in priority order. You can see which one succeeds by checking the logs:

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run verification
python optimizer_core.py \
  --config sample_config.yaml \
  --verify-connection 2>&1 | grep "Amazon API POST"
```

**Expected Log Output:**
```
INFO - Amazon API POST https://advertising-api.amazon.com/v3/sp/campaigns/list (attempt 1/3)
INFO - Retrieved 10 campaigns
```

The first attempt should succeed with `/v3/sp/campaigns/list` endpoint.

### Test 3: Full Integration Test

Test the complete budget monitoring flow:

```bash
# Set environment
export GCP_PROJECT_ID=nature-way-soils
eval $(python load_secrets.py)

# Run optimizer in dry-run mode
python optimizer_core.py \
  --config sample_config.yaml \
  --dry-run \
  --features bid_optimization

# Check logs for budget fetching
tail -f ppc_*.log | grep -i "budget\|campaign"
```

## Testing in Cloud Functions

### Deploy with Secrets

```bash
# Deploy Cloud Function with Secret Manager integration
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
  --set-secrets='AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=amazon-profile-id:latest'
```

### Test Deployed Function

```bash
# Get function URL
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)')

# Test with verify_connection parameter
curl -X POST "$FUNCTION_URL?verify_connection=true&verify_sample_size=5" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "success": true,
  "campaign_count": 10,
  "sample": [...],
  "method": "POST /sp/campaigns/list"
}
```

## Troubleshooting

### Error: "Missing API credentials"

**Cause:** Secrets not loaded from Google Secret Manager

**Solution:**
```bash
# Verify secrets exist in Secret Manager
gcloud secrets list --project=nature-way-soils | grep amazon

# Test secret access
gcloud secrets versions access latest --secret=amazon-client-id

# Re-authenticate if needed
gcloud auth application-default login
```

### Error: "400 Bad Request"

**Cause:** Using old version of the code without the fix

**Solution:**
```bash
# Pull latest changes
git pull origin main

# Verify the fix is present
grep -A 5 "v3 format (preferred)" optimizer_core.py
```

### Error: "401 Unauthorized"

**Cause:** Expired or invalid refresh token

**Solution:**
```bash
# Refresh token needs to be regenerated in Amazon Advertising Console
# See: FIND_ADS_API_CREDENTIALS.md for instructions
```

## Success Indicators

### ✅ Fix is Working When You See:

1. **In Logs:**
   ```
   INFO - Amazon API POST https://advertising-api.amazon.com/v3/sp/campaigns/list
   INFO - Retrieved X campaigns
   INFO - Fetched budget data for X campaigns
   ```

2. **No 400 Errors:**
   - No "Name campaignId not found" errors
   - No "Invalid key=value pair" errors

3. **Campaign Data Retrieved:**
   ```
   INFO - ✓ Retrieved X campaigns
   INFO - Fetched budget data for X campaigns
   ```

### ❌ Fix NOT Working When You See:

1. **400 Errors Still Occurring:**
   ```
   ERROR - 400 Bad Request: Name campaignId not found
   ```
   → Check you're using the latest code with the fix

2. **Using v2 Endpoint:**
   ```
   INFO - Amazon API POST .../v2/sp/campaigns/list
   ```
   → v3 should be tried first; check if v3 endpoint exists for your region

## Additional Resources

- `BUGFIX_AMAZON_ADS_API_V3.md` - Complete fix documentation
- `load_secrets.py` - Secret Manager integration
- `AMAZON_API_VERSIONS.md` - API version information
- Amazon Ads API docs: https://advertising.amazon.com/API/docs

## Support

If the fix doesn't resolve your issue:

1. Check logs for specific error messages
2. Verify credentials are correct in Secret Manager
3. Confirm Amazon Ads API access is enabled for your account
4. Check API version compatibility for your region
