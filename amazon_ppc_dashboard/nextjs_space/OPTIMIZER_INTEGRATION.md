# Optimizer Integration Guide

This document describes how the Amazon PPC Optimizer Cloud Function integrates with this dashboard.

## Overview

The Cloud Function optimizer automatically sends data to this dashboard on every optimization run through secure API endpoints.

## Authentication

All POST requests from the optimizer include an API key in the Authorization header:

```
Authorization: Bearer YOUR_DASHBOARD_API_KEY
```

The API key must be configured in both:
1. **Cloud Function**: As a secret in Google Secret Manager (`DASHBOARD_API_KEY`)
2. **Dashboard**: As an environment variable in Vercel

## Data Flow

### 1. Optimization Start
When an optimization run begins, the optimizer sends:

**Endpoint**: `POST /api/optimization-status`

```json
{
  "run_id": "uuid-here",
  "status": "started",
  "profile_id": "your-profile-id",
  "timestamp": "2025-10-18T...",
  "dry_run": false,
  "features": ["bid_optimization", "dayparting"]
}
```

### 2. Progress Updates
During the optimization, periodic updates are sent:

**Endpoint**: `POST /api/optimization-status`

```json
{
  "run_id": "uuid-here",
  "status": "running",
  "profile_id": "your-profile-id",
  "timestamp": "2025-10-18T...",
  "message": "Analyzing keywords",
  "percent_complete": 50
}
```

### 3. Completion
When optimization completes successfully:

**Endpoint**: `POST /api/optimization-results`

```json
{
  "run_id": "uuid-here",
  "status": "success",
  "profile_id": "your-profile-id",
  "timestamp": "2025-10-18T...",
  "duration_seconds": 50.24,
  "dry_run": false,
  "summary": {
    "campaigns_analyzed": 253,
    "keywords_optimized": 1000,
    "bids_increased": 611,
    "bids_decreased": 0,
    "negative_keywords_added": 0
  },
  "features": {
    "bid_optimization": {
      "bids_increased": 611,
      "keywords_analyzed": 1000,
      "no_change": 389
    },
    "dayparting": {
      "schedules_updated": 10,
      "ad_groups_affected": 50
    }
  },
  "campaigns": [...],
  "top_performers": [...],
  "config_snapshot": {...}
}
```

### 4. Errors
If optimization fails:

**Endpoint**: `POST /api/optimization-error`

```json
{
  "run_id": "uuid-here",
  "status": "error",
  "profile_id": "your-profile-id",
  "timestamp": "2025-10-18T...",
  "error": "Rate limit exceeded",
  "error_type": "rate_limit",
  "traceback": "..."
}
```

## API Endpoint Details

### Health Check
**GET** `/api/health`

Used by the optimizer to verify dashboard connectivity.

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2025-10-18T...",
  "service": "Amazon PPC Dashboard"
}
```

### Status Updates
**POST** `/api/optimization-status`

Receives real-time status updates.

**Authentication**: Bearer token required

**Response**:
```json
{
  "success": true,
  "received": true
}
```

### Results
**POST** `/api/optimization-results`

Receives final optimization results.

**Authentication**: Bearer token required

**Response**:
```json
{
  "success": true,
  "received": true,
  "run_id": "uuid-here"
}
```

### Errors
**POST** `/api/optimization-error`

Receives error reports.

**Authentication**: Bearer token required

**Response**:
```json
{
  "success": true,
  "received": true
}
```

## Configuration

### Cloud Function Environment
The optimizer needs these environment variables:

```
DASHBOARD_URL=https://amazonppcdashboard.vercel.app
DASHBOARD_API_KEY=your_dashboard_api_key_here
```

These are stored in Google Secret Manager and bound to the Cloud Function.

### Dashboard Environment
The dashboard needs this environment variable in Vercel:

```
DASHBOARD_API_KEY=your_dashboard_api_key_here
```

**Important**: The API key must match in both places!

## Testing Integration

### 1. Test Health Check
From anywhere:
```bash
curl https://amazonppcdashboard.vercel.app/api/health
```

Expected: `{"status":"ok",...}`

### 2. Test from Cloud Function
```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?health=true"
```

Expected: `"dashboard_ok": true`

### 3. Test Optimization Run
```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app"
```

Then check Vercel deployment logs to see incoming data.

## Error Handling

The optimizer implements graceful degradation:

- If dashboard is unreachable, optimization continues
- Retries are attempted with exponential backoff
- Errors are logged but don't fail the optimization
- Dashboard connectivity is non-blocking

This ensures the optimizer can run even if the dashboard is temporarily unavailable.

## Security

- All endpoints except `/api/health` require API key authentication
- API key is transmitted via Authorization header
- HTTPS is enforced on all endpoints
- API key should be kept secret and rotated periodically

## Data Storage

The API endpoints currently log data to console. You should implement data storage:

1. **Database Storage**: Store results in a database (PostgreSQL, MongoDB, etc.)
2. **Time Series**: Use a time-series database for performance metrics
3. **Alerts**: Set up alerts for errors or anomalies
4. **Analytics**: Build dashboards to visualize optimization trends

Example implementation locations in the code:
- `app/api/optimization-status/route.ts`: Line 19 (TODO comment)
- `app/api/optimization-results/route.ts`: Line 22 (TODO comment)
- `app/api/optimization-error/route.ts`: Line 18 (TODO comment)

## Monitoring

### View Dashboard Logs
In Vercel:
1. Go to your project
2. Click "Deployments"
3. Click on the latest deployment
4. Click "Functions"
5. View logs for each API route

### View Optimizer Logs
```bash
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --limit=50
```

## Troubleshooting

### Dashboard Not Receiving Data
1. Check API key matches in both places
2. Verify DASHBOARD_URL is correct in Cloud Function
3. Check Vercel deployment logs for errors
4. Test health endpoint directly

### Authentication Errors
1. Verify API key is set in Vercel environment variables
2. Check API key format (no extra spaces or quotes)
3. Ensure Authorization header format is correct

### Connection Timeouts
1. Check Vercel deployment status
2. Verify network connectivity
3. Check for rate limiting

## Support

For issues or questions:
1. Check deployment logs (Vercel and Cloud Functions)
2. Review this documentation
3. Test endpoints individually
4. Verify environment variables
