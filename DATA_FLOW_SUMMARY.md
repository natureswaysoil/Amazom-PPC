# Amazon PPC Optimizer - Data Flow Summary

## Overview

This document provides a complete summary of what data is sent from the optimizer to the dashboard and how to verify the integration is working.

---

## Complete Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Cloud Scheduler (Trigger)                                   │
│  - Sends authenticated POST request                          │
│  - Can include dry_run and features parameters               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Cloud Function: run_optimizer                               │
│                                                               │
│  1. Load Configuration                                        │
│  2. Initialize DashboardClient                                │
│  3. Generate unique run_id                                    │
│  4. POST /api/optimization-status (status="started")         │
│  5. Initialize PPCAutomation                                  │
│  6. POST /api/optimization-status (progress updates)         │
│  7. Run optimization features                                 │
│  8. POST /api/optimization-results (full metrics)            │
│  9. Return response                                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Dashboard API Endpoints                                      │
│                                                               │
│  POST /api/optimization-status                               │
│  - Receives: start, progress, completion status              │
│  - Updates: Real-time UI progress indicator                  │
│                                                               │
│  POST /api/optimization-results                              │
│  - Receives: Full optimization metrics and results           │
│  - Updates: Dashboard tables, charts, summaries              │
│                                                               │
│  POST /api/optimization-error                                │
│  - Receives: Error details and context                       │
│  - Updates: Error log, notifications                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  Dashboard Web UI                                             │
│                                                               │
│  Displays:                                                    │
│  - Last run timestamp                                         │
│  - Run status (success/failed/running)                        │
│  - Summary metrics (campaigns, keywords, bids)               │
│  - Performance data (spend, sales, ACOS)                     │
│  - Campaign-level breakdown                                   │
│  - Top performing keywords                                    │
│  - Errors and warnings                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Sent to Dashboard

### 1. Optimization Start (POST /api/optimization-status)

**When**: At the beginning of each optimization run

**Data Sent**:
```json
{
  "timestamp": "2025-11-03T15:17:07.654Z",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "profile_id": "1780498399290938",
  "dry_run": false
}
```

**Purpose**: Notify dashboard that a new optimization run has started

**Dashboard Action**: 
- Creates new run entry
- Shows "Running" status in UI
- Displays start timestamp

---

### 2. Progress Updates (POST /api/optimization-status)

**When**: During optimization execution (10%, 20%, 90%, 100%)

**Data Sent**:
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

**Progress Messages**:
- 10%: "Initializing optimizer..."
- 20%: "Starting optimization..."
- 90%: "Processing results..."
- 100%: "Optimization completed successfully"

**Purpose**: Provide real-time progress feedback

**Dashboard Action**: 
- Updates progress bar
- Displays current step message
- Shows completion percentage

---

### 3. Final Results (POST /api/optimization-results)

**When**: After optimization completes successfully

**Data Sent** (Full Enhanced Payload):
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
      "bids_decreased": 389,
      "no_change": 0
    },
    "dayparting": {
      "current_day": "MONDAY",
      "current_hour": 15,
      "keywords_updated": 0,
      "multiplier": 1.2
    },
    "campaign_management": {
      "campaigns_analyzed": 253,
      "campaigns_paused": 2,
      "campaigns_activated": 3,
      "no_change": 248
    },
    "keyword_discovery": {
      "keywords_discovered": 15,
      "keywords_added": 8
    },
    "negative_keywords": {
      "negative_keywords_added": 25
    }
  },
  
  "campaigns": [
    {
      "campaign_id": "123456",
      "campaign_name": "Product Campaign A",
      "spend": 123.45,
      "sales": 234.56,
      "acos": 0.526,
      "keywords_count": 50,
      "changes_made": 12
    },
    {
      "campaign_id": "123457",
      "campaign_name": "Product Campaign B",
      "spend": 98.76,
      "sales": 187.65,
      "acos": 0.526,
      "keywords_count": 35,
      "changes_made": 8
    }
  ],
  
  "top_performers": [
    {
      "keyword_text": "organic soil",
      "clicks": 120,
      "sales": 345.67,
      "acos": 0.35,
      "bid_change": 0.15
    },
    {
      "keyword_text": "potting mix",
      "clicks": 95,
      "sales": 278.90,
      "acos": 0.38,
      "bid_change": 0.12
    }
  ],
  
  "errors": [],
  "warnings": [
    "Campaign 123458 has low budget remaining"
  ],
  
  "config_snapshot": {
    "target_acos": 0.45,
    "lookback_days": 14,
    "enabled_features": [
      "bid_optimization",
      "dayparting",
      "campaign_management"
    ]
  }
}
```

**Purpose**: Provide complete optimization results for dashboard display

**Dashboard Action**: 
- Updates run status to "Completed"
- Displays all summary metrics
- Populates campaign tables
- Shows top performers
- Lists any warnings or errors
- Records configuration used

---

### 4. Error Reporting (POST /api/optimization-error)

**When**: If optimization fails with an exception

**Data Sent**:
```json
{
  "timestamp": "2025-11-03T15:17:07.654Z",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "profile_id": "1780498399290938",
  "error": {
    "type": "ValueError",
    "message": "Invalid configuration parameter: target_acos",
    "traceback": "Traceback (most recent call last):\n  File \"main.py\", line 450, in run_optimizer\n    optimizer.run()\n  File \"optimizer_core.py\", line 123, in run\n    self._validate_config()\nValueError: Invalid configuration parameter: target_acos",
    "context": {
      "function": "run_optimizer",
      "timestamp": "2025-11-03T15:17:07.654Z",
      "dry_run": false
    }
  }
}
```

**Purpose**: Alert dashboard about optimization failures

**Dashboard Action**: 
- Updates run status to "Failed"
- Displays error message
- Shows error context
- Triggers notifications (if configured)

---

## Dashboard Display Components

### Main Dashboard View

```
┌──────────────────────────────────────────────────────────────┐
│  Amazon PPC Optimizer Dashboard                               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Last Run: November 3, 2025 at 3:17 PM                       │
│  Status: ✅ Success  Duration: 45.23s  Mode: Live            │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Summary Metrics                                     │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │  Campaigns Analyzed       253                        │    │
│  │  Keywords Optimized       1,000                      │    │
│  │  Bids Increased          611                        │    │
│  │  Bids Decreased          389                        │    │
│  │  Negative Keywords Added  25                         │    │
│  │  Budget Changes          5                          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Performance Metrics                                 │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │  Total Spend             $1,234.56                   │    │
│  │  Total Sales             $2,345.67                   │    │
│  │  Average ACOS            52.6%                       │    │
│  │  ROI                     90%                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Campaign Breakdown                                  │    │
│  ├──────────────┬─────────┬─────────┬──────┬──────────┤    │
│  │ Campaign     │ Spend   │ Sales   │ ACOS │ Changes  │    │
│  ├──────────────┼─────────┼─────────┼──────┼──────────┤    │
│  │ Campaign A   │ $123.45 │ $234.56 │ 52.6%│    12    │    │
│  │ Campaign B   │  $98.76 │ $187.65 │ 52.6%│     8    │    │
│  └──────────────┴─────────┴─────────┴──────┴──────────┘    │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Top Performing Keywords                             │    │
│  ├──────────────┬────────┬─────────┬──────┬───────────┤    │
│  │ Keyword      │ Clicks │ Sales   │ ACOS │ Bid Change│    │
│  ├──────────────┼────────┼─────────┼──────┼───────────┤    │
│  │ organic soil │  120   │ $345.67 │ 35%  │  +$0.15   │    │
│  │ potting mix  │   95   │ $278.90 │ 38%  │  +$0.12   │    │
│  └──────────────┴────────┴─────────┴──────┴───────────┘    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## How to Verify Everything Works

### Step-by-Step Verification Process

#### 1. Test Health Endpoint
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://YOUR-FUNCTION-URL?health=true"
```

**What to Check**:
- ✅ Returns HTTP 200
- ✅ `"status": "healthy"`
- ✅ `"dashboard_ok": true`

#### 2. Test Verify Connection
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://YOUR-FUNCTION-URL?verify_connection=true&verify_sample_size=3"
```

**What to Check**:
- ✅ Returns HTTP 200
- ✅ `"status": "success"`
- ✅ `"message": "Amazon Ads API connection verified"`

#### 3. Run Dry Run Test
```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "https://YOUR-FUNCTION-URL"
```

**What to Check**:
- ✅ Returns HTTP 200
- ✅ `"status": "success"`
- ✅ Contains optimization results
- ✅ `"dry_run": true`

#### 4. Check Cloud Logs
```bash
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --limit=50
```

**What to Look For**:
```
✅ "Started optimization run: 550e8400-e29b-41d4-a716-446655440000"
✅ "Dashboard POST /api/optimization-status: HTTP 200"
✅ "Dashboard POST /api/optimization-results: HTTP 200"
✅ "Dashboard updated successfully with optimization results"
```

#### 5. Check Dashboard UI

**What to Verify**:
- ✅ New run appears with correct timestamp
- ✅ Status shows "Success" or "Completed"
- ✅ Summary metrics match optimizer response
- ✅ Duration matches function execution time
- ✅ Campaign data is displayed
- ✅ Top performers are shown

---

## Troubleshooting Quick Reference

### Dashboard Doesn't Update

**Check**:
1. Cloud Logs for `Dashboard POST` messages
2. HTTP status codes (should be 200)
3. Dashboard API key in Secret Manager
4. Dashboard URL is correct
5. Dashboard server is running

**Fix**:
```bash
# Verify secrets
gcloud secrets describe dashboard-api-key
gcloud secrets describe dashboard-url

# Check function environment
gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format=yaml
```

### HTTP 401/403 Errors

**Cause**: API key authentication failure

**Fix**:
```bash
# Update API key
echo -n "NEW_API_KEY" | gcloud secrets versions add dashboard-api-key --data-file=-

# Redeploy
./deploy.sh
```

### HTTP 429 Errors

**Cause**: Rate limiting

**Fix**:
- Reduce optimization frequency
- Contact dashboard administrator
- Check rate limit headers in logs

### Connection Timeout

**Cause**: Dashboard not responding

**Fix**:
- Increase timeout in config
- Check dashboard server health
- Verify network connectivity

---

## Success Criteria

Your integration is working correctly when:

✅ **Health check** returns healthy status  
✅ **Connection verification** succeeds  
✅ **Dry run** completes without errors  
✅ **Cloud Logs** show HTTP 200 for dashboard POSTs  
✅ **Dashboard UI** displays optimization data  
✅ **Timestamps** match between optimizer and dashboard  
✅ **Metrics** are accurate and up-to-date  
✅ **No authentication errors** in logs  
✅ **No rate limit errors** in logs  

---

## Additional Resources

- **VERIFICATION_GUIDE.md**: Complete verification procedures
- **DASHBOARD_INTEGRATION.md**: Detailed integration documentation
- **README.md**: General setup and configuration
- **DEPLOYMENT_GUIDE.md**: Deployment instructions

---

**Last Updated**: November 3, 2025  
**Version**: 2.0.0  
**Maintained By**: Nature's Way Soil
