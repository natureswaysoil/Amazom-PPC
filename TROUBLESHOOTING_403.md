# Amazon API 403 Error Troubleshooting Guide

## Problem
The optimizer returns 403 Forbidden with error: **"Invalid key=value pair (missing equal-sign) in Authorization header"**

This error typically indicates **whitespace corruption** in the access token or refresh token.

---

## Root Cause Analysis

The error message "Invalid key=value pair (missing equal-sign)" occurs when Amazon's API parser encounters a space character in the Authorization header value. When it sees:

```
Authorization: Bearer Atza|first_part second_part|last_part
```

Amazon interprets this as having TWO key=value pairs (`Bearer` and `Atza|first_part`), but neither has an equal sign, hence the error.

### Common Causes:
1. **Secret Manager whitespace corruption** - Copying/pasting secrets with trailing newlines or spaces
2. **Wrong API credentials** - Using Product Advertising API (PA-API) credentials instead of Amazon Advertising API
3. **Expired refresh token** - Token no longer valid, needs regeneration

---

## Diagnostic Tools

Run these in **Cloud Shell** (where gcloud is available):

### 1. Validate Credentials
```bash
cd ~/Amazom-PPC
python3 validate-amazon-credentials.py
```

This script:
- Tests token refresh with your credentials
- Checks access token for spaces/newlines
- Verifies Amazon Advertising API access
- Confirms profile_id is accessible

### 2. Check Secret Manager Corruption
```bash
cd ~/Amazom-PPC
./check-secret-corruption.sh
```

This script:
- Inspects all Amazon API secrets in Secret Manager
- Detects spaces, newlines, tabs, carriage returns
- Shows hex dump to reveal hidden characters
- Provides fix commands

---

## Solutions

### Solution 1: Fix Whitespace-Corrupted Secrets

If `check-secret-corruption.sh` finds whitespace issues:

```bash
# For AMAZON_REFRESH_TOKEN (most common culprit)
echo -n 'YOUR_ACTUAL_REFRESH_TOKEN' > /tmp/refresh_token.txt
gcloud secrets versions add AMAZON_REFRESH_TOKEN \
  --data-file=/tmp/refresh_token.txt \
  --project=amazon-ppc-474902
rm /tmp/refresh_token.txt

# For AMAZON_CLIENT_SECRET
echo -n 'YOUR_ACTUAL_CLIENT_SECRET' > /tmp/client_secret.txt
gcloud secrets versions add AMAZON_CLIENT_SECRET \
  --data-file=/tmp/client_secret.txt \
  --project=amazon-ppc-474902
rm /tmp/client_secret.txt

# Verify the fix
./check-secret-corruption.sh

# Redeploy
./deploy-with-service-account.sh

# Test
curl "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?verify_connection=true&verify_sample_size=5"
```

**CRITICAL**: Use `echo -n` (no newline) or create file without trailing newline.

---

### Solution 2: Verify API Registration

**Important distinction:**
- ❌ **Product Advertising API (PA-API)** - For affiliate product data at `webservices.amazon.com/paapi5`
- ✅ **Amazon Advertising API** - For PPC campaigns at `advertising-api.amazon.com`

**You need Amazon Advertising API credentials**, not PA-API.

#### Check Your Registration:
1. Visit: https://advertising.amazon.com/
2. Go to "Developer Center" or "API"
3. Confirm you have "Amazon Advertising API" access (NOT "Product Advertising API")
4. Your client_id should start with `amzn1.application-oa2-client.`

#### If You Have Wrong API:
1. Register for Amazon Advertising API: https://advertising.amazon.com/API
2. Create new LWA (Login with Amazon) credentials
3. Generate new refresh token through OAuth flow
4. Update all secrets in Secret Manager

---

### Solution 3: Regenerate Refresh Token

If your refresh token is expired or invalid:

1. **Via Amazon Advertising Console:**
   - Log into https://advertising.amazon.com
   - Go to Account Settings → API
   - Revoke existing token
   - Generate new refresh token

2. **Via OAuth Flow:**
   ```bash
   # Generate authorization URL
   CLIENT_ID="your_client_id"
   REDIRECT_URI="https://localhost"  # Or your registered redirect URI
   
   echo "Visit this URL in browser:"
   echo "https://www.amazon.com/ap/oa?client_id=${CLIENT_ID}&scope=advertising::campaign_management&response_type=code&redirect_uri=${REDIRECT_URI}"
   
   # After authorization, exchange code for refresh token
   # (Use the code from redirect URL query parameter)
   curl -X POST https://api.amazon.com/auth/o2/token \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=authorization_code" \
     -d "code=YOUR_AUTH_CODE" \
     -d "client_id=${CLIENT_ID}" \
     -d "client_secret=YOUR_CLIENT_SECRET" \
     -d "redirect_uri=${REDIRECT_URI}"
   ```

3. **Update Secret Manager:**
   ```bash
   echo -n 'YOUR_NEW_REFRESH_TOKEN' | gcloud secrets versions add AMAZON_REFRESH_TOKEN \
     --data-file=- \
     --project=amazon-ppc-474902
   ```

---

## Verification Checklist

After applying fixes:

- [ ] `validate-amazon-credentials.py` shows all green checkmarks
- [ ] `check-secret-corruption.sh` shows no whitespace warnings
- [ ] Token refresh succeeds (Step 2 in validator)
- [ ] Profiles endpoint returns your profile_id (Step 3 in validator)
- [ ] Verify endpoint returns `campaign_count > 0`:
  ```bash
  curl "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?verify_connection=true&verify_sample_size=5"
  ```
- [ ] Health check shows `campaigns_analyzed > 0`:
  ```bash
  curl "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?health=true"
  ```

---

## Still Having Issues?

If you've completed all steps and still see 403 errors:

1. **Check Cloud Logs for AUTH DIAGNOSTIC entries:**
   ```bash
   gcloud logging read \
     'resource.type="cloud_run_revision" 
      resource.labels.service_name="amazon-ppc-optimizer" 
      severity="ERROR" 
      textPayload=~"AUTH DIAGNOSTIC"' \
     --limit=20 \
     --format='table(timestamp,textPayload)' \
     --project amazon-ppc-474902
   ```

2. **Verify profile permissions:**
   - Log into Amazon Advertising Console
   - Confirm profile_id `1780498399290938` exists
   - Check that your API user has "Campaign Manager" or "Account Administrator" role

3. **Test with minimal request:**
   ```bash
   # Get fresh access token
   ACCESS_TOKEN=$(python3 -c "
   import requests
   import os
   r = requests.post('https://api.amazon.com/auth/o2/token', data={
       'grant_type': 'refresh_token',
       'refresh_token': os.getenv('AMAZON_REFRESH_TOKEN'),
       'client_id': os.getenv('AMAZON_CLIENT_ID'),
       'client_secret': os.getenv('AMAZON_CLIENT_SECRET')
   })
   print(r.json()['access_token'])
   ")
   
   # Test profiles endpoint
   curl -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "Amazon-Advertising-API-ClientId: ${AMAZON_CLIENT_ID}" \
        https://advertising-api.amazon.com/v2/profiles
   ```

4. **Contact Amazon Advertising API support:**
   - Forum: https://advertising.amazon.com/API/docs/en-us/support
   - Email: advertising-api@amazon.com

---

## Quick Reference

| Tool | Purpose | Location |
|------|---------|----------|
| `validate-amazon-credentials.py` | End-to-end credential test | Cloud Shell: `cd ~/Amazom-PPC && python3 validate-amazon-credentials.py` |
| `check-secret-corruption.sh` | Inspect secrets for whitespace | Cloud Shell: `cd ~/Amazom-PPC && ./check-secret-corruption.sh` |
| `deploy-with-service-account.sh` | Redeploy after secret changes | Cloud Shell: `cd ~/Amazom-PPC && ./deploy-with-service-account.sh` |
| Verify endpoint | Test optimizer connectivity | `curl "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?verify_connection=true&verify_sample_size=5"` |
| Cloud Logs | View AUTH DIAGNOSTIC logs | See gcloud logging command above |

---

## Additional Resources

- **Amazon Advertising API Documentation**: https://advertising.amazon.com/API/docs
- **OAuth/LWA Setup Guide**: https://developer.amazon.com/docs/login-with-amazon/
- **Sponsored Products API Reference**: https://advertising.amazon.com/API/docs/en-us/sponsored-products
- **Project README**: [README.md](./README.md)
- **Deployment Guide**: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
