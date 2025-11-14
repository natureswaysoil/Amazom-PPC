# Dashboard API Key Sync Guide

## Problem
The dashboard returns `401 Unauthorized` because the API key in Google Cloud Secret Manager doesn't match the key configured in Vercel.

## Solution

### Option 1: Update Vercel to Match Secret Manager (Recommended)

1. **Get the current API key from Secret Manager:**
   ```bash
   gcloud secrets versions access latest \
     --secret=dashboard-api-key \
     --project=amazon-ppc-474902
   ```

2. **Update Vercel environment variable:**
   - Go to: https://vercel.com/natureswaysoil/nextjsspace-six/settings/environment-variables
   - Find `DASHBOARD_API_KEY`
   - Update it to match the value from step 1
   - Click "Save"
   - Redeploy: `vercel --prod` or trigger via Git push

3. **Verify the update:**
   ```bash
   curl -X POST https://nextjsspace-six.vercel.app/api/optimization-results \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_NEW_API_KEY" \
     -d '{"test": "data", "timestamp": "2025-11-14T00:00:00Z"}'
   ```

### Option 2: Update Secret Manager to Match Vercel

1. **Get the current API key from Vercel:**
   - Go to: https://vercel.com/natureswaysoil/nextjsspace-six/settings/environment-variables
   - Find `DASHBOARD_API_KEY` and copy its value

2. **Update Secret Manager:**
   ```bash
   echo -n "YOUR_VERCEL_API_KEY" | gcloud secrets versions add dashboard-api-key \
     --project=amazon-ppc-474902 \
     --data-file=-
   ```

3. **Redeploy Cloud Function to use new secret:**
   ```bash
   cd ~/Amazom-PPC
   ./deploy-quick.sh
   ```

### Option 3: Generate New API Key for Both

1. **Generate a secure random API key:**
   ```bash
   # Generate 32-byte hex string
   openssl rand -hex 32
   ```

2. **Update Secret Manager:**
   ```bash
   echo -n "YOUR_NEW_API_KEY" | gcloud secrets versions add dashboard-api-key \
     --project=amazon-ppc-474902 \
     --data-file=-
   ```

3. **Update Vercel:**
   - Go to: https://vercel.com/natureswaysoil/nextjsspace-six/settings/environment-variables
   - Update `DASHBOARD_API_KEY` with the new key
   - Redeploy

4. **Redeploy Cloud Function:**
   ```bash
   cd ~/Amazom-PPC
   ./deploy-quick.sh
   ```

## Verification

Test the API key is working:

```bash
# Get the API key
API_KEY=$(gcloud secrets versions access latest --secret=dashboard-api-key --project=amazon-ppc-474902)

# Test dashboard endpoint
curl -X POST https://nextjsspace-six.vercel.app/api/optimization-results \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"test": "data", "timestamp": "2025-11-14T00:00:00Z"}' | python3 -m json.tool
```

Expected response:
```json
{
  "success": true,
  "received": true,
  "run_id": null
}
```

## Current Status

Based on test results:
- ✅ Dashboard expects: `Authorization: Bearer {api_key}` header
- ❌ Current API key (`06295684993c7c5bc52b03c50a0ea05f5b8b01f0`) is rejected by Vercel
- ⚠️ Keys are out of sync between Secret Manager and Vercel

## Next Steps

1. Choose one of the three options above
2. Run verification test
3. Deploy Cloud Function if you updated Secret Manager
4. Run a full optimization to ensure data flows to dashboard

## BigQuery Tables Available

The dashboard queries these BigQuery tables:

### 1. `optimization_results`
- **Purpose:** Stores summary of each optimization run
- **Schema:**
  - `timestamp` (TIMESTAMP) - When the run completed
  - `run_id` (STRING) - Unique identifier
  - `status` (STRING) - success/error
  - `profile_id` (STRING) - Amazon profile ID
  - `dry_run` (BOOLEAN) - Was this a dry run?
  - `duration_seconds` (FLOAT) - How long it took
  - `campaigns_analyzed` (INTEGER)
  - `keywords_optimized` (INTEGER)
  - `bids_increased` (INTEGER)
  - `bids_decreased` (INTEGER)
  - `negative_keywords_added` (INTEGER)
  - `budget_changes` (INTEGER)
  - `total_spend` (FLOAT)
  - `total_sales` (FLOAT)
  - `average_acos` (FLOAT)
  - `enabled_features` (REPEATED STRING)
  - `errors` (REPEATED STRING)
  - `warnings` (REPEATED STRING)

### 2. `campaign_details`
- **Purpose:** Stores campaign-level performance data
- **Schema:**
  - `timestamp` (TIMESTAMP)
  - `run_id` (STRING)
  - `campaign_id` (STRING)
  - `campaign_name` (STRING)
  - `spend` (FLOAT)
  - `sales` (FLOAT)
  - `acos` (FLOAT)
  - `impressions` (INTEGER)
  - `clicks` (INTEGER)
  - `conversions` (INTEGER)
  - `budget` (FLOAT)
  - `status` (STRING)

### 3. `optimization_progress`
- **Purpose:** Real-time progress updates during optimization
- **Schema:**
  - `timestamp` (TIMESTAMP)
  - `run_id` (STRING)
  - `status` (STRING)
  - `message` (STRING)
  - `percent_complete` (FLOAT)
  - `profile_id` (STRING)

### 4. `optimizer_run_events`
- **Purpose:** Event log for optimizer runs
- **Schema:**
  - `timestamp` (TIMESTAMP)
  - `run_id` (STRING)
  - `status` (STRING)
  - `details` (STRING)

## Dashboard Data Flow

1. **Optimizer runs** → Writes to BigQuery tables
2. **Dashboard API** (`/api/bigquery-data`) → Queries BigQuery
3. **Dashboard UI** (`page.tsx`) → Displays data

### Dashboard Queries

The dashboard currently queries:
- ✅ `optimization_results` - Last 5 runs, 7 days
- ✅ `summary` - Aggregated stats by day, 7 days
- ❌ `campaign_details` - Available but not displayed in UI

### Missing from Dashboard

To show all data, the dashboard should also display:
- Campaign-level breakdown (from `campaign_details`)
- Real-time progress (from `optimization_progress`)
- Event logs (from `optimizer_run_events`)

## Recommendations

1. **Fix API key mismatch** (use Option 1 above)
2. **Add campaign details view** to dashboard
3. **Add progress indicator** for live optimization runs
4. **Add event log viewer** for debugging
