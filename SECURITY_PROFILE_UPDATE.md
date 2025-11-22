# Amazon Advertising API Security Profile Update

**Date**: November 21, 2025  
**Status**: New Security Profile Created - Requires Reauthorization

## 🔴 LIVE STATUS (Last Check: Nov 21, 2025)

**Current Permission State**: ❌ **SPONSORED PRODUCTS ACCESS REVOKED**

### Profile Details (Verified)
- **Profile ID**: `1780498399290938`
- **Account Type**: Seller (Nature's Way Soil)
- **Country**: US (countryCode: `US`)
- **Region**: NA (North America)
- **Endpoint**: `https://advertising-api.amazon.com` ✅ Correct
- **Marketplace**: `ATVPDKIKX0DER` (Amazon.com)
- **Valid Payment Method**: ✅ Yes

### API Access Test Results

| API Product | Endpoint | Status | Details |
|-------------|----------|--------|---------|
| ✅ Profiles API | `/v2/profiles` | 200 OK | 7 profiles accessible (all regions) |
| ❌ Sponsored Products | `/sp/campaigns` | **403 Forbidden** | `Invalid key=value pair` - **SP scope not granted** |
| ❌ Sponsored Products (legacy) | `/v2/sp/campaigns` | **404 Not Found** | Endpoint deprecated/moved |
| ❌ Sponsored Brands | `/sb/v4/campaigns` | **403 Forbidden** | `Invalid key=value pair` - **SB scope not granted** |
| ✅ Sponsored Display | `/sd/campaigns` | 200 OK | 1 campaign retrieved - **SD scope granted** |

### Root Cause Analysis

**✅ What's Working:**
1. Token refresh: Working (`9bfcdcb417fdb310`)
2. Region endpoint: Correct (NA → `advertising-api.amazon.com`)
3. Profile ID: Valid and accessible
4. Headers: All required headers present (`Advertising-API-Scope`, `ClientId`, `Authorization`)
5. Account type: Valid seller with payment method

**❌ What's Blocked:**
1. **Sponsored Products scope**: NOT granted to current refresh token
2. **Sponsored Brands scope**: NOT granted to current refresh token
3. **Campaign Management permission**: Token lacks `advertising::campaign_management` for SP/SB

**✅ What's Partially Working:**
- **Sponsored Display**: Has permission (indicates token is valid but scopes are selective)

### Diagnosis: OAuth Scope Not Granted

The 403 error `Invalid key=value pair (missing equal-sign)` **does NOT mean wrong headers**.  
It means: **Your refresh token was never granted `advertising::campaign_management` scope for SP/SB products.**

**Why SD works but SP doesn't:**
- Your current token has `advertising::campaign_management` for **Sponsored Display only**
- SP and SB require explicit consent during OAuth for those product types
- Amazon treats each ad product (SP, SB, SD) as separate entitlements

**Action Required**: Complete OAuth reauthorization with the new Security Profile that explicitly requests SP/SB scopes.

## New Security Profile Details

| Field | Value |
|-------|-------|
| **Security Profile Name** | Amazon- PPC- Bid- Optimizer |
| **Security Profile ID** | `amzn1.application.e5e766db2a154722b5aee7a7df59b796` |
| **Description** | `cpc_advertising:campaign_management/ advertising::campaign_management / advertising::reporting` |
| **Consent Privacy Notice URL** | https://natureswaysoil.com |

## Requested Scopes

The security profile includes the following scopes:
- `cpc_advertising:campaign_management` (legacy format)
- `advertising::campaign_management` (current format for Sponsored Products, Sponsored Brands, Sponsored Display)
- `advertising::reporting` (reporting API access)

## Required Actions

### 1. Obtain Client Credentials
**→ Check Amazon Developer Console for the new Client ID and Client Secret associated with this Security Profile.**

Expected format:
- Client ID: `amzn1.application-oa2-client.{hash}`
- Client Secret: `amzn1.oa2-cs.v1.{hash}`

### 2. Generate Authorization URL

Use the new Client ID to construct an authorization URL:

```
https://www.amazon.com/ap/oa?client_id={NEW_CLIENT_ID}&scope=advertising::campaign_management%20advertising::reporting&response_type=code&redirect_uri={YOUR_REDIRECT_URI}
```

**Note**: Replace `{YOUR_REDIRECT_URI}` with the URL registered in Web Settings (e.g., `https://natureswaysoil.com/callback` or similar).

### 3. Complete Authorization Flow

1. Visit the authorization URL in a browser
2. Sign in with the Amazon Advertising account
3. Grant consent for the requested scopes
4. Copy the authorization code from the redirect URL

### 4. Exchange Authorization Code for Refresh Token

```bash
curl -X POST https://api.amazon.com/auth/o2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code={AUTHORIZATION_CODE}" \
  -d "client_id={NEW_CLIENT_ID}" \
  -d "client_secret={NEW_CLIENT_SECRET}" \
  -d "redirect_uri={YOUR_REDIRECT_URI}"
```

Response will include:
```json
{
  "access_token": "Atza|...",
  "refresh_token": "Atzr|...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**→ Save the `refresh_token` securely.**

### 5. Update Secret Manager

Update the following secrets in Google Cloud Secret Manager:

```bash
# Update Client ID
echo -n "{NEW_CLIENT_ID}" | gcloud secrets versions add AMAZON_CLIENT_ID --data-file=- --project=amazon-ppc-474902

# Update Client Secret
echo -n "{NEW_CLIENT_SECRET}" | gcloud secrets versions add AMAZON_CLIENT_SECRET --data-file=- --project=amazon-ppc-474902

# Update Refresh Token
echo -n "{NEW_REFRESH_TOKEN}" | gcloud secrets versions add AMAZON_REFRESH_TOKEN --data-file=- --project=amazon-ppc-474902

# Profile ID remains the same (1780498399290938) unless changed
```

### 6. Verify New Credentials

Run permission diagnostics:

```bash
./run_sp_permission_diagnostics.sh amazon-ppc-474902
```

Expected output:
```json
{
  "conclusion": "All endpoints accessible",
  "endpoints": {
    "sp_campaigns": {
      "status": 200,
      "interpretation": "SP_ACCESS_OK"
    }
  }
}
```

### 7. Redeploy Services (if needed)

If secrets are consumed at deployment time (not runtime), redeploy:

```bash
# Cloud Function
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --region=us-central1 \
  --project=amazon-ppc-474902

# Cloud Run Dashboard
cd optimizer && ./deploy_cloudrun.sh amazon-ppc-474902 us-central1
```

## Validation Checklist

- [ ] New Client ID and Client Secret obtained from Amazon Developer Console
- [ ] Authorization flow completed and consent granted
- [ ] Refresh token obtained via token exchange
- [ ] All three secrets updated in Google Secret Manager
- [ ] Diagnostics script confirms `sp_access_ok` and `sb_access_ok`
- [ ] Optimizer can retrieve campaigns (`?verify_connection=true`)
- [ ] Permission health endpoint shows `sp_permission: present`

## Expected Scope Grants

After completing reauthorization, the following API access should work:

| Ad Product | Endpoint | Expected Status |
|------------|----------|-----------------|
| Sponsored Products | `/sp/campaigns` | 200 |
| Sponsored Products (v3) | `/sp/v3/campaigns` | 200 |
| Sponsored Brands (v4) | `/sb/v4/campaigns` | 200 |
| Sponsored Display | `/sd/campaigns` | 200 |
| Reporting | `/v2/reports` | 200 |
| Profiles | `/v2/profiles` | 200 (already working) |

## Troubleshooting

### If 403 persists after update:
1. Confirm redirect URI in Web Settings matches the one used in authorization URL
2. Verify consent was granted for **all** requested scopes (campaign_management + reporting)
3. Check that the refresh token was not truncated (common with copy-paste errors)
4. Ensure no trailing spaces or newlines in Secret Manager values

### If authorization URL fails:
- Confirm Client ID format is correct (`amzn1.application-oa2-client.{hash}`)
- Verify the redirect URI is registered under Web Settings in the Security Profile
- Try encoding the redirect URI: use `%3A%2F%2F` for `://` and `%2F` for `/`

## Documentation References

- Reauthorization Checklist: `optimizer/AMAZON_SP_REAUTHORIZATION_CHECKLIST.md`
- API Version Matrix: `AMAZON_API_VERSION_MATRIX.md`
- Permission Diagnostics: `diagnose_sp_permissions.py`
- Security Profile: Amazon Developer Console > Login with Amazon > Manage

---
**Next Step**: Obtain Client ID and Client Secret from Amazon Developer Console, then execute steps 2-7.
