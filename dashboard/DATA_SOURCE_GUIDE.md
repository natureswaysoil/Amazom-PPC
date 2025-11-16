# Dashboard Data Source Guide

## Overview

This guide explains where the dashboard gets its data and how to populate the BigQuery tables.

## Data Flow

```
Amazon Advertising API
        ↓
   Optimizer (optimizer_core.py)
        ↓
   BigQuery Tables
        ↓
   Dashboard (Flask App)
        ↓
   Your Browser
```

## Step-by-Step Setup

### 1. Configure Amazon Advertising API

The optimizer needs Amazon API credentials to fetch campaign data:

```bash
export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
export AMAZON_CLIENT_SECRET="amzn1.oa2-cs.v1.xxxxx"
export AMAZON_REFRESH_TOKEN="Atzr|IwEBIxxxxx"
export AMAZON_PROFILE_ID="1780498399290938"
```

Or use the `config.json` file in the repository root.

### 2. Configure BigQuery

The optimizer writes results to BigQuery, and the dashboard reads from it:

```bash
export GCP_PROJECT_ID="your-project-id"
export BIGQUERY_DATASET="amazon_ppc"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

**Service Account Permissions Needed:**
- `BigQuery Data Editor` (for optimizer to write)
- `BigQuery Data Viewer` (for dashboard to read)

### 3. Run the Optimizer

From the repository root:

```bash
# One-time run
python optimizer_core.py --config config.json

# With specific features
python optimizer_core.py --features bid_optimization,dayparting

# Dry run (no changes, still writes to BigQuery)
python optimizer_core.py --dry-run
```

This will:
1. Fetch campaign data from Amazon Advertising API
2. Perform optimizations (bid adjustments, keyword management, etc.)
3. Write results to BigQuery tables
4. Send updates to dashboard (if configured)

### 4. Verify Data in BigQuery

Check that tables were created and populated:

```bash
# List tables
bq ls --project_id=YOUR_PROJECT amazon_ppc

# Check row counts
bq query --nouse_legacy_sql \
  "SELECT 
    (SELECT COUNT(*) FROM \`YOUR_PROJECT.amazon_ppc.optimization_results\`) as results,
    (SELECT COUNT(*) FROM \`YOUR_PROJECT.amazon_ppc.campaign_details\`) as campaigns,
    (SELECT COUNT(*) FROM \`YOUR_PROJECT.amazon_ppc.optimization_progress\`) as progress,
    (SELECT COUNT(*) FROM \`YOUR_PROJECT.amazon_ppc.optimization_errors\`) as errors,
    (SELECT COUNT(*) FROM \`YOUR_PROJECT.amazon_ppc.optimizer_run_events\`) as events"
```

### 5. Start the Dashboard

The dashboard reads data from BigQuery:

```bash
cd dashboard

# Set BigQuery credentials (same as optimizer)
export GCP_PROJECT_ID="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Start dashboard
python app.py
```

Open http://localhost:8080 and you should see your data!

## BigQuery Tables Schema

### optimization_results
Main table with optimization run summaries:
- `timestamp` - When the run occurred
- `run_id` - Unique identifier
- `keywords_optimized` - Number of keywords adjusted
- `bids_increased` / `bids_decreased` - Bid changes
- `total_spend` / `total_sales` - Financial metrics
- `average_acos` - Average ACOS across campaigns

### campaign_details
Campaign-level metrics for each run:
- `campaign_id` / `campaign_name` - Campaign identifiers
- `spend` / `sales` / `acos` - Campaign performance
- `impressions` / `clicks` / `conversions` - Traffic metrics
- `budget` / `status` - Campaign settings

### optimization_progress
Real-time progress updates during runs:
- `timestamp` - Progress checkpoint time
- `stage` - Current optimization stage
- `progress_percent` - Completion percentage
- `message` - Progress description

### optimization_errors
Error logs for debugging:
- `timestamp` - When error occurred
- `error_type` - Category of error
- `error_message` - Detailed error description
- `context` - Additional debugging info

### optimizer_run_events
Audit trail of all events:
- `timestamp` - Event time
- `run_id` - Associated run
- `status` - Event status (started, completed, failed)
- `details` - Event specifics

## Automation

### Scheduled Runs

Set up Cloud Scheduler to run the optimizer regularly:

```bash
gcloud scheduler jobs create http ppc-optimizer-daily \
  --schedule="0 2 * * *" \
  --time-zone="America/New_York" \
  --uri="https://your-optimizer-cloud-run-url.run.app" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"features": ["bid_optimization", "dayparting"]}'
```

This runs the optimizer daily at 2 AM, automatically populating BigQuery with fresh data.

### Dashboard Auto-Refresh

The dashboard automatically refreshes data every 5 minutes, so new optimization runs appear automatically.

## Troubleshooting

### No tables in BigQuery
**Problem**: `bq ls` shows no tables

**Solution**: Run the optimizer at least once to create tables

### Tables are empty
**Problem**: Tables exist but have 0 rows

**Solution**: 
1. Check optimizer logs for errors
2. Verify Amazon API credentials are valid
3. Ensure BigQuery permissions allow writing

### Dashboard shows "Failed to initialize BigQuery client"
**Problem**: Dashboard can't connect to BigQuery

**Solution**:
1. Set `GOOGLE_APPLICATION_CREDENTIALS` or `GCP_CREDENTIALS_JSON`
2. Verify service account has `BigQuery Data Viewer` role
3. Check `GCP_PROJECT_ID` matches your BigQuery project

### Old data showing
**Problem**: Dashboard shows stale data

**Solution**:
1. Run optimizer to generate new data
2. Wait for dashboard auto-refresh (5 minutes)
3. Or manually refresh browser

## Data Retention

BigQuery tables use time partitioning by `timestamp` field. To manage storage:

```sql
-- Delete data older than 90 days
DELETE FROM `YOUR_PROJECT.amazon_ppc.optimization_results`
WHERE timestamp < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY);

-- Same for other tables
DELETE FROM `YOUR_PROJECT.amazon_ppc.campaign_details`
WHERE timestamp < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY);
```

Or set up automatic expiration:

```bash
bq update --time_partitioning_expiration=7776000 \
  YOUR_PROJECT:amazon_ppc.optimization_results
```

(7776000 seconds = 90 days)

## Summary

1. **Optimizer writes data** → BigQuery tables
2. **Dashboard reads data** → BigQuery tables
3. **Run optimizer regularly** → Fresh data
4. **Dashboard auto-refreshes** → Always current

The dashboard is just a viewer - all data comes from the optimizer's interaction with Amazon Advertising API.
