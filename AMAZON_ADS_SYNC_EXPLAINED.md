# Amazon Ads Sync Job Explained

## Overview

The Amazon Ads Sync job is a scheduled process that synchronizes advertising data from the Amazon Advertising API to BigQuery for analytics and reporting. This job runs periodically (typically hourly or daily) to keep your data warehouse up-to-date with the latest campaign performance.

## What This Job Does

Based on the logs from the recent run, the sync job performs the following operations in sequence:

### 1. **Campaign Synchronization** (06:01:46 - 06:01:54)
   - **Purpose**: Fetches all active advertising campaigns from Amazon Ads API
   - **Process**:
     - Discovers all available advertising profiles across different marketplaces (BR, CA, MX, US)
     - Queries multiple API endpoints (US, EU, FE regions) to retrieve campaigns
     - Handles API errors gracefully (403 Forbidden, 400 Bad Request errors are logged but don't stop the sync)
   - **Result**: Successfully synced **266 campaigns** to BigQuery
   - **Duration**: ~8 seconds

### 2. **Keyword Synchronization** (06:01:54 - 06:02:04)
   - **Purpose**: Fetches all advertising keywords across all campaigns
   - **Process**:
     - Similar multi-region approach as campaigns
     - Retrieves keyword data from all active ad groups
     - Filters out invalid or archived keywords
   - **Result**: Successfully synced **6,516 keywords** to BigQuery (skipped 0 duplicates)
   - **Duration**: ~10 seconds

### 3. **Performance Report Synchronization** (06:02:04 - 06:17:05)

The job attempts to sync three types of performance reports, all of which **timed out**:

#### a. **Keyword Performance Report** (06:02:04 - 06:07:04)
   - **Purpose**: Retrieve 14-day performance metrics for keywords (impressions, clicks, cost, conversions)
   - **Issue**: Report creation succeeded but polling for completion timed out
   - **Result**: ⚠️ **FAILED** - "Report did not complete in time"
   - **Duration**: 5 minutes (timeout limit reached)

#### b. **Campaign Performance Report** (06:07:04 - 06:12:04)
   - **Purpose**: Retrieve 14-day performance metrics for campaigns
   - **Issue**: Same timeout issue as keyword report
   - **Result**: ⚠️ **FAILED** - "Report did not complete in time"
   - **Duration**: 5 minutes (timeout limit reached)

#### c. **Placement Performance Report** (06:12:04 - 06:17:05)
   - **Purpose**: Retrieve Top-of-Search placement metrics
   - **Issue**: Same timeout issue
   - **Result**: ⚠️ **FAILED** - "Report did not complete in time"
   - **Duration**: 5 minutes (timeout limit reached)

### 4. **Job Completion** (06:17:05)
   - Despite the report failures, the job marked itself as "completed successfully"
   - **Total Duration**: ~15.5 minutes
   - **Status**: ✅ Partial success (campaigns and keywords synced, but performance reports failed)

## The Timeout Issue Explained

### Why Are Reports Timing Out?

Amazon Advertising API reports are **asynchronous**:

1. You submit a report request to Amazon
2. Amazon queues your request and begins processing
3. You must poll the status endpoint repeatedly until the report is ready
4. Once ready, you download the report data

**The Problem**: The current timeout is set to **300 seconds (5 minutes)**, but Amazon's report processing can take longer, especially for:
- Large accounts with thousands of keywords/campaigns
- High-traffic periods when Amazon's API is busy
- Complex reports with multiple metrics and date ranges
- Cross-region accounts (BR, CA, MX, US)

### Impact of Timeout Failures

When performance reports fail:
- ❌ No updated metrics for the last 14 days
- ❌ Optimization decisions may be based on stale data
- ❌ Dashboard shows outdated performance
- ✅ Historical campaign and keyword structure is still current

### Current Polling Strategy

From `optimizer_core.py` (lines 1808-1890):

```python
Default timeout: 300 seconds (5 minutes)
Initial poll interval: 2 seconds
Max poll interval: 10 seconds (exponential backoff)
Polling strategy: Exponential backoff (1.5x multiplier)
```

**Polling sequence**:
- Poll 1: wait 2s → check status
- Poll 2: wait 3s → check status  
- Poll 3: wait 4.5s → check status
- Poll 4: wait 6.75s → check status
- Polls 5+: wait 10s → check status (capped at max)

**Total polls in 5 minutes**: ~20-25 status checks

## Recommended Solutions

### Option 1: Increase Timeout (Immediate Fix)

Set environment variable to allow longer wait times:

```bash
export AMAZON_REPORT_TIMEOUT_SECONDS=900  # 15 minutes
```

**Pros**: 
- Simple configuration change
- No code modifications needed
- Should resolve most timeout issues

**Cons**:
- Longer-running cloud functions (may increase costs)
- Still may timeout for very large accounts

### Option 2: Implement Report Queuing (Robust Solution)

Change the sync job to:
1. Submit report requests to Amazon
2. Store report IDs in database
3. Schedule a separate job to poll and download completed reports
4. Update BigQuery when reports are ready

**Pros**:
- Decouples report creation from retrieval
- Can handle reports that take 30+ minutes
- More resilient to Amazon API delays

**Cons**:
- Requires architectural changes
- More complex to implement and monitor

### Option 3: Reduce Report Scope

Request smaller date ranges or fewer metrics:
- Change from 14-day to 7-day reports
- Request fewer metric columns
- Split reports by marketplace

**Pros**:
- Faster report generation
- Lower chance of timeout

**Cons**:
- Less data available for analysis
- May require multiple report requests

## Environment Variables for Timeout Control

The following environment variables can be configured:

| Variable | Default | Description |
|----------|---------|-------------|
| `AMAZON_REPORT_TIMEOUT_SECONDS` | 300 | Total time to wait for report completion |
| `AMAZON_REPORT_POLL_INITIAL_SECONDS` | 2 | Initial delay between status checks |
| `AMAZON_REPORT_POLL_MAX_SECONDS` | 10 | Maximum delay between status checks |
| `AMAZON_REPORT_MAX_STATUS_FAILURES` | 8 | Consecutive failures before aborting |

## Monitoring and Alerts

To prevent silent failures, consider:

1. **Email alerts** when reports timeout (using existing Resend integration)
2. **Dashboard indicators** showing last successful sync time
3. **GitHub Actions health checks** to verify report completion
4. **Metric staleness warnings** when data is >24 hours old

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Amazon Ads Sync Job                      │
│                  (Google Cloud Function/Run)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Fetches data from
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Amazon Advertising API (Multiple Regions)       │
│   • advertising-api.amazon.com (Americas)                    │
│   • advertising-api-eu.amazon.com (Europe)                   │
│   • advertising-api-fe.amazon.com (Far East)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Stores data in
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Google BigQuery                       │
│   • Campaigns table                                          │
│   • Keywords table                                           │
│   • Performance metrics tables                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Powers
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PPC Optimization Dashboard                │
│   • Performance analytics                                    │
│   • Bid recommendations                                      │
│   • Budget tracking                                          │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps

1. **Immediate**: Increase `AMAZON_REPORT_TIMEOUT_SECONDS` to 900 (15 minutes)
2. **Monitor**: Track if reports complete within the new timeout
3. **Long-term**: Consider implementing asynchronous report queuing for large accounts

## Related Documentation

- `optimizer_core.py` - Core Amazon Ads API integration (lines 1808-1890: report polling)
- `bigquery_client.py` - BigQuery data storage
- `AMAZON_API_VERSIONS.md` - Amazon Ads API version compatibility
- `BIGQUERY_INTEGRATION.md` - BigQuery schema and data flow
