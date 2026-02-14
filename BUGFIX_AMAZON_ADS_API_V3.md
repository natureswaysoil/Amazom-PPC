# Bug Fix: Amazon Ads API v3 Campaigns List Endpoint

## Issue

The budget monitoring job was failing with the following error:

```
Error fetching budgets: 400 Name campaignId not found inside m at [9:32]
Location: US Job ID: 626c8d2d-4f28-45c4-a1b7-94e2b6c1b5fb
⚠️ No active campaigns found or client failed to retrieve data.
```

## Root Cause

Amazon migrated the Sponsored Products API to v3 in **March 2023**. The v3 API introduced breaking changes to the request body format for the `/sp/campaigns/list` endpoint.

### v2 Format (Legacy - Deprecated March 2023)
```json
{
  "startIndex": 0,
  "count": 50
}
```

### v3 Format (Current - Required as of March 2023)
```json
{
  "pagination": {
    "startIndex": 0,
    "count": 50
  }
}
```

The code was only sending the v2 format, which caused a **400 Bad Request** error when sent to the v3 endpoint.

## Solution

Updated the `list_campaigns_v3` method in `optimizer_core.py` to:

1. **Try v3 format first** (with pagination wrapper)
2. **Fallback to v2 format** (for legacy compatibility)
3. **Try v3 endpoint first** (`/v3/sp/campaigns/list`)
4. **Add detailed logging** for 400 errors

### Request Body Priority Order

The method now tries request bodies in this order:

1. **v3 format** (preferred):
   ```python
   {
       'pagination': {
           'startIndex': start_index,
           'count': count
       }
   }
   ```

2. **v2 format** (legacy):
   ```python
   {'startIndex': start_index, 'count': count}
   ```

3. **Empty body** (fallback):
   ```python
   {}
   ```

### Endpoint Priority Order

The method tries endpoints in this order:

1. `/v3/sp/campaigns/list` (v3, preferred)
2. `/v2/sp/campaigns/list` (v2, legacy)
3. `/sp/campaigns/list` (unversioned, last resort)

## Code Changes

### Before
```python
body_candidates = [
    {'startIndex': start_index, 'count': count},
    {},
]

endpoint_candidates = [
    '/v2/sp/campaigns/list',
    '/sp/campaigns/list',
]
```

### After
```python
body_candidates = [
    # v3 format (preferred)
    {
        'pagination': {
            'startIndex': start_index,
            'count': count
        }
    },
    # v2 format (legacy)
    {'startIndex': start_index, 'count': count},
    # Empty body (fallback)
    {},
]

endpoint_candidates = [
    # v3 endpoint (preferred for Sponsored Products as of March 2023)
    '/v3/sp/campaigns/list',
    # v2 endpoint (legacy, deprecated March 2023)
    '/v2/sp/campaigns/list',
    # Unversioned (last resort)
    '/sp/campaigns/list',
]
```

## Benefits

1. **Fixes the 400 error** - Uses correct v3 format
2. **Backward compatible** - Still works with v2 for legacy accounts
3. **Better diagnostics** - Logs detailed 400 error information
4. **Future-proof** - Prioritizes v3 endpoint as recommended by Amazon

## Testing

The fix has been validated with:
- ✅ Unit tests for request format structure
- ✅ Code review (no issues)
- ✅ Security scan (no vulnerabilities)

## Impact

This fix resolves:
- Budget monitoring job failures
- Campaign data retrieval issues
- `fetch_campaign_budgets()` errors
- Any code path using `list_campaigns_v3()` or the fallback in `get_campaigns()`

## References

- [Amazon Ads API v3 Documentation](https://advertising.amazon.com/API/docs/en-us/guides/sponsored-products/overview)
- [Python Amazon Ads API - Campaigns v3](https://python-amazon-ad-api.readthedocs.io/en/latest/sp/campaigns_v3.html)
- [Amazon Ads API Migration Guide](https://advertising.amazon.com/API/docs/en-us/guides/migration/sponsored-products)

## Related Files

- `optimizer_core.py` - Main fix implementation
- `AMAZON_API_VERSIONS.md` - API version documentation
- This document - Bug fix summary

## Date

Fixed: February 14, 2026
Issue occurred: February 1, 2026
