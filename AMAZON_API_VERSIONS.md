# Amazon Advertising API Version Guide

## Overview

Amazon has multiple API versions for different campaign types and purposes. It's important to use the correct version for each operation to ensure compatibility and avoid using deprecated endpoints.

## Sponsored Brands

### Campaign Management (Use V4)

✅ **Use V4 for Sponsored Brands campaigns**

- As of August 2023, all campaigns created using the version 3 Sponsored Brands `POST /sb/campaigns` endpoint are automatically stored as multi-ad group (version 4) campaigns
- Legacy Sponsored Brands version 3 campaigns created before October 2022 were marked as ARCHIVED by August 15th, 2024
- **Amazon strongly recommends migrating all v3 campaigns to v4**

### Reporting/Data Retrieval (Use V3)

📊 **Use V3 (not V4) for Sponsored Brands reporting**

- V3 is the current standard for reporting APIs
- V4 is for campaign management, not reporting
- Sponsored Brands reporting largely remains on V2/V3

## Sponsored Products

### Current Status (Use V3)

- **V3 is current** - Sponsored Products migrated to V3 as of March 2023
- ❌ **V2 was deprecated** - V2 API for Sponsored Products was deprecated on March 30, 2023
- All new development should use V3 for both management and reporting

## Sponsored Display

### Current Status (V2 → V3 transition)

- **V2 scheduled for shutdown** - V2 API for Sponsored Display is scheduled to shut down on October 31, 2024
- **Migrate to V3** - All Sponsored Display operations should use V3
- Reporting largely remains on V2/V3 during transition

## Summary Table

| Campaign Type | Management API | Reporting API | Notes |
|---------------|----------------|---------------|-------|
| **Sponsored Brands** | V4 | V3 | V4 for campaigns, V3 for reports |
| **Sponsored Products** | V3 | V3 | Fully migrated to V3 |
| **Sponsored Display** | V3 | V2/V3 | V2 shutdown October 2024 |

## Implementation in This Repository

### Current Optimizer Implementation

The optimizer in this repository uses the Amazon Advertising API to:
1. Fetch campaign performance data
2. Analyze metrics and calculate optimizations
3. Update bids and campaign settings
4. Write results to BigQuery

### Recommended Updates

Based on the API version guidance:

1. **Sponsored Brands Campaigns**
   - Use V4 endpoints for creating/updating campaigns
   - Use V3 endpoints for retrieving performance reports
   - Migrate any legacy V3 campaigns to V4

2. **Sponsored Products Campaigns**
   - Use V3 for all operations (already current standard)
   - Ensure no V2 endpoints remain in code

3. **Sponsored Display Campaigns**
   - Use V3 for all operations
   - Remove any V2 dependencies before October 31, 2024

### API Endpoint Examples

#### Sponsored Brands (V4 Campaign Management)

```python
# Create/Update Campaign (V4)
POST https://advertising-api.amazon.com/sb/v4/campaigns
GET https://advertising-api.amazon.com/sb/v4/campaigns/{campaignId}
PUT https://advertising-api.amazon.com/sb/v4/campaigns/{campaignId}
```

#### Sponsored Brands (V3 Reporting)

```python
# Get Performance Reports (V3)
POST https://advertising-api.amazon.com/reporting/reports
GET https://advertising-api.amazon.com/reporting/reports/{reportId}
```

#### Sponsored Products (V3)

```python
# Campaign Management (V3)
POST https://advertising-api.amazon.com/sp/campaigns
GET https://advertising-api.amazon.com/sp/campaigns/{campaignId}
PUT https://advertising-api.amazon.com/sp/campaigns/{campaignId}

# Reporting (V3)
POST https://advertising-api.amazon.com/reporting/reports
```

## Migration Checklist

When updating the optimizer code:

- [ ] Verify Sponsored Brands uses V4 for campaign operations
- [ ] Verify Sponsored Brands uses V3 for reporting
- [ ] Confirm Sponsored Products uses V3 for all operations
- [ ] Remove any V2 Sponsored Display endpoints
- [ ] Update Sponsored Display to V3
- [ ] Test API calls with correct version headers
- [ ] Update error handling for new API responses
- [ ] Document API version in code comments

## API Version Headers

Always include the correct API version in request headers:

```python
headers = {
    'Amazon-Advertising-API-ClientId': CLIENT_ID,
    'Authorization': f'Bearer {access_token}',
    'Amazon-Advertising-API-Scope': PROFILE_ID,
    'Content-Type': 'application/json'
}

# For Sponsored Brands V4 campaign operations
# URL: /sb/v4/campaigns

# For reporting (all campaign types)
# URL: /reporting/reports (V3 standard)

# For Sponsored Products V3
# URL: /sp/campaigns (V3 implicit)
```

## Resources

### Official Documentation

- [Amazon Advertising API Documentation](https://advertising.amazon.com/API/docs)
- [Sponsored Brands API V4](https://advertising.amazon.com/API/docs/en-us/sponsored-brands/3-0/openapi/prod)
- [Reporting API](https://advertising.amazon.com/API/docs/en-us/guides/reporting/v3/overview)

### Migration Guides

- [Sponsored Brands V3 to V4 Migration](https://advertising.amazon.com/API/docs/en-us/guides/migration/sponsored-brands)
- [Sponsored Products V2 to V3 Migration](https://advertising.amazon.com/API/docs/en-us/guides/migration/sponsored-products)

## Version History

| Date | Change |
|------|--------|
| August 2023 | Sponsored Brands V4 becomes default for new campaigns |
| March 2023 | Sponsored Products V2 deprecated, V3 required |
| August 2024 | Legacy Sponsored Brands V3 campaigns archived |
| October 2024 | Sponsored Display V2 scheduled shutdown |

## Support

If you encounter issues with API versions:

1. Check Amazon Advertising API documentation for latest version
2. Verify API version in request URL path
3. Review response headers for version information
4. Test with Amazon's API sandbox environment
5. Contact Amazon Advertising API support for migration assistance

## Notes

- Always use the latest stable API version
- Monitor Amazon's deprecation notices
- Plan migrations well before sunset dates
- Test thoroughly in sandbox before production
- Keep this document updated as Amazon releases new versions
