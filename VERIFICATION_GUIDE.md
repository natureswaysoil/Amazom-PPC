# Amazon PPC Optimizer - Complete Verification Guide

This comprehensive guide explains how to verify that your Amazon PPC Optimizer deployment and dashboard data integration are working correctly.

## Table of Contents

1. [Overview](#overview)
2. [Data Pipeline Architecture](#data-pipeline-architecture)
3. [Verification Steps](#verification-steps)
4. [Dashboard Endpoints](#dashboard-endpoints)
5. [Testing Procedures](#testing-procedures)
6. [Troubleshooting](#troubleshooting)
7. [Logging and Monitoring](#logging-and-monitoring)

---

## Overview

The Amazon PPC Optimizer communicates with your dashboard via HTTP POST requests to send optimization status, results, and errors. This guide provides step-by-step instructions to verify that all components are working correctly.

### Key Components

- **Cloud Function**: `amazon-ppc-optimizer` (deployed on Google Cloud Functions Gen2)
- **Dashboard**: Web UI for monitoring optimization runs
- **Dashboard API**: Backend endpoints receiving optimizer data
- **Cloud Logging**: Google Cloud Logs Explorer for troubleshooting

---

## Data Pipeline Architecture

### How It Works

```
Optimizer (Cloud Function)
    │
    ├─→ POST /api/optimization-status    (start, progress updates)
    ├─→ POST /api/optimization-results   (final results with metrics)
    └─→ POST /api/optimization-error     (error reporting)
         │
         ↓
    Dashboard Backend
         │
         ↓
    Dashboard Web UI
    (displays data to user)
```

### Communication Flow

1. **Optimization Start**: Function POSTs to `/api/optimization-status` with status="started"
2. **Progress Updates**: Real-time progress POSTs to `/api/optimization-status` with percentage
3. **Results**: Enhanced payload POSTs to `/api/optimization-results` with full metrics
4. **Errors**: Any failures POST to `/api/optimization-error` with context

### Key Features

- ✅ **Non-blocking**: Dashboard failures don't stop optimization
- ✅ **Retry Logic**: Exponential backoff with 3 retry attempts
- ✅ **Comprehensive Logging**: All requests/responses logged to Cloud Logging
- ✅ **Authentication**: Secure API key authentication via Bearer token
- ✅ **Enhanced Payload**: Detailed metrics, campaigns, and performance data

---

## Verification Steps

### A. Health Check (Lightweight Test)

**Purpose**: Verify the function is deployed and responsive without running optimization.

**Command**:
```bash
FUNCTION_URL="https://amazon-ppc-optimizer-YOURHASH-uc.a.run.app"

curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?health=true"
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-03T15:17:07.654Z",
  "dashboard_ok": true,
  "email_ok": false,
  "environment": "cloud_function"
}
```

**What This Verifies**:
- ✅ Function is deployed and accessible
- ✅ Configuration loads successfully
- ✅ Dashboard endpoint is reachable (`dashboard_ok: true`)
- ✅ Function has proper authentication

---

### B. Verify Amazon Ads Connection

**Purpose**: Test Amazon Advertising API credentials without running full optimization.

**Command**:
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=3"
```

**Expected Response**:
```json
{
  "status": "success",
  "message": "Amazon Ads API connection verified",
  "profile_id": "1780498399290938",
  "timestamp": "2025-11-03T15:17:07.654Z",
  "sample_size": 3,
  "note": "Connection successful - credentials are valid and API is reachable"
}
```

**What This Verifies**:
- ✅ Amazon API credentials are valid
- ✅ Access token can be refreshed
- ✅ Amazon Ads API is reachable
- ✅ Profile ID is correct

---

### C. Dry Run Test (Full Optimization Without Changes)

**Purpose**: Run complete optimization logic without making actual bid/budget changes.

**Command**:
```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "${FUNCTION_URL}"
```

**Expected Response**:
```json
{
  "status": "success",
  "message": "Optimization completed successfully",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "results": {
    "bid_optimization": {
      "keywords_analyzed": 1000,
      "bids_increased": 611,
      "bids_decreased": 389,
      "no_change": 0
    },
    "summary": {
      "campaigns_analyzed": 253,
      "keywords_optimized": 1000,
      "total_spend": 1234.56,
      "total_sales": 2345.67
    }
  },
  "duration_seconds": 45.23,
  "dry_run": true,
  "timestamp": "2025-11-03T15:17:07.654Z"
}
```

**What This Verifies**:
- ✅ Full optimization logic executes successfully
- ✅ Amazon Ads API data is retrieved and processed
- ✅ Dashboard receives status and result POSTs
- ✅ No actual changes made (dry_run mode)

---

### D. Cloud Logging Verification

**Purpose**: Confirm dashboard communication in Cloud Logs.

**Steps**:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **Logging** → **Logs Explorer**
3. Set the following filters:
   - **Resource**: Cloud Function → `amazon-ppc-optimizer`
   - **Time range**: Last 1 hour

**Search for these log entries**:

✅ **Successful Dashboard POST**:
```
Dashboard POST /api/optimization-results: HTTP 200
Dashboard updated successfully with optimization results
```

✅ **Progress Updates**:
```
Dashboard POST /api/optimization-status: HTTP 200
```

✅ **Error Logs** (if dashboard fails):
```
Dashboard update failed
Error sending results to dashboard: [error details]
```

**What This Verifies**:
- ✅ Dashboard API endpoints respond with HTTP 200
- ✅ Retry logic works (if applicable)
- ✅ Authentication succeeds
- ✅ Full request/response cycle completes

---

### E. Dashboard Web UI Verification

**Purpose**: Confirm data appears in the dashboard UI.

**Steps**:

1. Open your dashboard URL (e.g., `https://ppc-dashboard.abacusai.app`)
2. Look for:
   - ✅ **Recent Activity**: Shows latest optimization run
   - ✅ **Updated Counters**: Campaigns analyzed, bids changed, etc.
   - ✅ **Last Updated Timestamp**: Matches your test run time
   - ✅ **Run Details**: Summary metrics, duration, status

**Example Dashboard Display**:
```
Last Run: November 3, 2025 at 3:17 PM
Status: Success (DRY RUN)
Duration: 45.23 seconds

Summary:
- Campaigns Analyzed: 253
- Keywords Optimized: 1,000
- Bids Increased: 611
- Total Spend: $1,234.56
- Total Sales: $2,345.67
- ACOS: 52.6%
```

**What This Verifies**:
- ✅ Dashboard receives and stores optimization data
- ✅ UI displays correct metrics
- ✅ Timestamp synchronization works
- ✅ Real-time updates function properly

---

## Dashboard Endpoints

### 1. POST /api/optimization-status

**Purpose**: Send real-time status updates (start, progress, completion).

**Request Headers**:
```
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY
X-Profile-ID: 1780498399290938
```

**Payload - Start**:
```json
{
  "timestamp": "2025-11-03T15:17:07.654Z",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "profile_id": "1780498399290938",
  "dry_run": false
}
```

**Payload - Progress**:
```json
{
  "timestamp": "2025-11-03T15:17:07.654Z",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "message": "Analyzing keywords...",
  "percent_complete": 50.0,
  "profile_id": "1780498399290938"
}
```

**Expected Response**:
```json
{
  "status": "ok",
  "message": "Status update received"
}
```

---

### 2. POST /api/optimization-results

**Purpose**: Send completed optimization results with full metrics.

**Request Headers**:
```
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY
X-Profile-ID: 1780498399290938
```

**Payload Structure**:
```json
{
  "timestamp": "2025-11-03T15:17:07.654Z",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "success",
  "profile_id": "1780498399290938",
  "dry_run": false,
  "duration_seconds": 45.23,
  
  "summary": {
    "campaigns_analyzed": 253,
    "keywords_optimized": 1000,
    "bids_increased": 611,
    "bids_decreased": 389,
    "negative_keywords_added": 25,
    "budget_changes": 5,
    "total_spend": 1234.56,
    "total_sales": 2345.67,
    "average_acos": 0.526
  },
  
  "features": {
    "bid_optimization": {
      "keywords_analyzed": 1000,
      "bids_increased": 611,
      "bids_decreased": 389
    },
    "dayparting": {
      "current_day": "MONDAY",
      "current_hour": 15,
      "multiplier": 1.2
    },
    "campaign_management": {
      "campaigns_paused": 2,
      "campaigns_activated": 3
    }
  },
  
  "campaigns": [
    {
      "campaign_id": "123456",
      "campaign_name": "Product Campaign",
      "spend": 123.45,
      "sales": 234.56,
      "acos": 0.526,
      "keywords_count": 50,
      "changes_made": 12
    }
  ],
  
  "top_performers": [
    {
      "keyword_text": "organic soil",
      "clicks": 120,
      "sales": 345.67,
      "acos": 0.35,
      "bid_change": 0.15
    }
  ],
  
  "errors": [],
  "warnings": [],
  
  "config_snapshot": {
    "target_acos": 0.45,
    "lookback_days": 14,
    "enabled_features": ["bid_optimization", "dayparting"]
  }
}
```

**Expected Response**:
```json
{
  "status": "ok",
  "message": "Results received and stored",
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### 3. POST /api/optimization-error

**Purpose**: Report errors that occur during optimization.

**Request Headers**:
```
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY
X-Profile-ID: 1780498399290938
```

**Payload**:
```json
{
  "timestamp": "2025-11-03T15:17:07.654Z",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "profile_id": "1780498399290938",
  "error": {
    "type": "ValueError",
    "message": "Invalid configuration parameter",
    "traceback": "Traceback (most recent call last):\n  File...",
    "context": {
      "function": "run_optimizer",
      "timestamp": "2025-11-03T15:17:07.654Z",
      "dry_run": false
    }
  }
}
```

**Expected Response**:
```json
{
  "status": "ok",
  "message": "Error report received"
}
```

---

## Testing Procedures

### Manual Testing Protocol

#### 1. Initial Deployment Verification

```bash
# Step 1: Health check
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?health=true"

# Step 2: Verify connection
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=3"

# Step 3: Dry run test
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "${FUNCTION_URL}"
```

#### 2. Check Logs After Each Test

```bash
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --limit=50 \
  --project=YOUR_PROJECT_ID
```

**Look for**:
- ✅ `Dashboard POST /api/optimization-results: HTTP 200`
- ✅ `Dashboard updated successfully with optimization results`
- ❌ `Dashboard update failed`
- ❌ `Error sending results to dashboard`

#### 3. Verify Dashboard Displays Data

1. Open dashboard in browser
2. Check for new entry with matching timestamp
3. Verify metrics match optimization results
4. Confirm run_id appears in dashboard

---

## Troubleshooting

### Dashboard Doesn't Show Data

**Symptoms**:
- Optimizer runs successfully
- Logs show HTTP 200 responses
- Dashboard UI doesn't update

**Solutions**:

1. **Check Dashboard API Key**:
   ```bash
   gcloud secrets versions access latest --secret=dashboard-api-key
   ```
   - Verify key matches dashboard configuration

2. **Verify Dashboard URL**:
   ```bash
   gcloud secrets versions access latest --secret=dashboard-url
   ```
   - Ensure URL is correct and accessible

3. **Test Dashboard Endpoint Manually**:
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -d '{"test": "data"}' \
     "https://your-dashboard.com/api/optimization-results"
   ```

4. **Check Dashboard Server Logs**:
   - Look for incoming POST requests
   - Verify requests aren't being rejected

---

### Dashboard Update Failed Errors

**Symptoms**:
- Logs show `Dashboard update failed`
- HTTP status codes: 401, 403, 429, 500

**Solutions**:

**HTTP 401/403 (Authentication Error)**:
```bash
# Verify API key is configured
gcloud secrets describe dashboard-api-key

# Update if needed
echo -n "NEW_API_KEY" | gcloud secrets versions add dashboard-api-key --data-file=-

# Redeploy function
./deploy.sh
```

**HTTP 429 (Rate Limit)**:
- Dashboard is rate limiting requests
- Check `Retry-After` header in logs
- Reduce optimization frequency
- Contact dashboard administrator

**HTTP 500 (Server Error)**:
- Dashboard backend is experiencing issues
- Check dashboard server logs
- Verify dashboard is deployed and running
- Test dashboard health endpoint

---

### Connection Timeout Errors

**Symptoms**:
- `Dashboard request timeout after 30s`
- Requests hanging without response

**Solutions**:

1. **Increase Timeout** (in `config.json` or environment):
   ```json
   {
     "dashboard": {
       "timeout": 60
     }
   }
   ```

2. **Check Network Connectivity**:
   ```bash
   # From Cloud Shell, test dashboard reachability
   curl -I https://your-dashboard.com
   ```

3. **Verify Dashboard Performance**:
   - Check dashboard server response times
   - Investigate slow database queries
   - Scale dashboard infrastructure if needed

---

### No Logs Appear

**Symptoms**:
- Function runs but no dashboard logs appear
- Can't find `Dashboard POST` messages

**Solutions**:

1. **Check Log Level**:
   - Ensure logging level is INFO or DEBUG
   - Verify logs aren't filtered

2. **Search Correct Time Range**:
   - Expand time range in Logs Explorer
   - Check timezone differences

3. **Filter by Resource**:
   ```
   resource.type="cloud_function"
   resource.labels.function_name="amazon-ppc-optimizer"
   "dashboard"
   ```

---

## Logging and Monitoring

### Key Log Messages

**Success Indicators**:
```
✅ "Dashboard POST /api/optimization-results: HTTP 200"
✅ "Dashboard updated successfully with optimization results"
✅ "Dashboard POST /api/optimization-status: HTTP 200"
```

**Warning Indicators**:
```
⚠️  "Dashboard rate limit exceeded"
⚠️  "Dashboard returned 429"
⚠️  "Retrying in X seconds..."
```

**Error Indicators**:
```
❌ "Dashboard update failed"
❌ "Dashboard connection error"
❌ "Dashboard request timeout"
❌ "Error sending results to dashboard"
```

---

### Cloud Logging Queries

**Find All Dashboard Interactions**:
```
resource.type="cloud_function"
resource.labels.function_name="amazon-ppc-optimizer"
"dashboard"
```

**Find Failed Dashboard Updates**:
```
resource.type="cloud_function"
resource.labels.function_name="amazon-ppc-optimizer"
("Dashboard update failed" OR "Dashboard connection error")
```

**Find Specific Run by ID**:
```
resource.type="cloud_function"
resource.labels.function_name="amazon-ppc-optimizer"
"run_id=550e8400-e29b-41d4-a716-446655440000"
```

---

### Monitoring Metrics

**Key Performance Indicators**:

1. **Dashboard Success Rate**:
   - Target: > 99%
   - Metric: Successful POSTs / Total attempts

2. **Dashboard Response Time**:
   - Target: < 5 seconds
   - Metric: Time to HTTP 200 response

3. **Retry Rate**:
   - Target: < 1%
   - Metric: Requests requiring retry

4. **Error Rate**:
   - Target: < 0.1%
   - Metric: Failed dashboard updates

---

## Configuration Best Practices

### 1. Dashboard Configuration

**Recommended `config.json` settings**:
```json
{
  "dashboard": {
    "url": "https://ppc-dashboard.abacusai.app",
    "api_key": "stored-in-secret-manager",
    "enabled": true,
    "send_real_time_updates": true,
    "timeout": 30
  }
}
```

### 2. Environment Variables (Production)

**Use Secret Manager for sensitive values**:
```bash
# Store dashboard URL
echo -n "https://ppc-dashboard.abacusai.app" | \
  gcloud secrets create dashboard-url --data-file=-

# Store dashboard API key
echo -n "your-api-key" | \
  gcloud secrets create dashboard-api-key --data-file=-

# Deploy with secrets
gcloud functions deploy amazon-ppc-optimizer \
  --set-secrets=DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest
```

### 3. Retry Configuration

**Adjust retry behavior** in `dashboard_client.py`:
```python
@retry_with_backoff(
    max_attempts=3,      # Number of retry attempts
    initial_delay=2,     # Initial delay (seconds)
    max_delay=10         # Maximum delay (seconds)
)
```

---

## Support and Resources

### Documentation References

- **README.md**: General project overview and setup
- **DASHBOARD_INTEGRATION.md**: Detailed dashboard integration guide
- **DEPLOYMENT_GUIDE.md**: Deployment instructions
- **DEPLOYMENT_COMPLETE.md**: Post-deployment verification
- **DEPLOY_NOW.md**: Quick deployment commands

### Getting Help

**If verification fails**:

1. **Check Logs**: Review Cloud Logging for error details
2. **Test Health**: Use `?health=true` endpoint
3. **Verify Connection**: Use `?verify_connection=true`
4. **Run Dry Run**: Test with `dry_run: true`
5. **Contact Support**: james@natureswaysoil.com

---

## Conclusion

This verification guide provides comprehensive steps to ensure your Amazon PPC Optimizer and dashboard integration are working correctly. 

**Summary Checklist**:

- ✅ Health check returns `{"status": "healthy"}`
- ✅ Connection verification succeeds
- ✅ Dry run completes successfully
- ✅ Cloud Logs show `HTTP 200` responses
- ✅ Dashboard UI displays optimization data
- ✅ Timestamps match between optimizer and dashboard
- ✅ All endpoints respond within timeout
- ✅ No authentication or rate limit errors

**If all checks pass**: Your system is fully operational and ready for production use!

---

**Last Updated**: November 3, 2025  
**Version**: 2.0.0  
**Maintained By**: Nature's Way Soil
