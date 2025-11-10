# BigQuery Integration Guide

This guide explains how to enable BigQuery integration for the Amazon PPC Optimizer to store and analyze optimization data.

## Overview

The BigQuery integration automatically stores:
- **Optimization Results**: Summary metrics from each optimization run
- **Campaign Details**: Campaign-level performance data
- **Progress Updates**: Real-time status updates during optimization
- **Errors**: Error logs and troubleshooting information

## Prerequisites

1. **Google Cloud Project**: You need a GCP project with BigQuery API enabled
2. **Permissions**: The Cloud Function service account needs BigQuery Data Editor role
3. **BigQuery API**: Must be enabled in your GCP project

## Quick Setup

### Step 1: Enable BigQuery in Configuration

Update your `config.json` or set environment variables:

```json
{
  "bigquery": {
    "enabled": true,
    "project_id": "amazon-ppc-474902",
    "dataset_id": "amazon_ppc",
    "location": "us-east4"
  }
}
```

Or use environment variables:
```bash
export GOOGLE_CLOUD_PROJECT=amazon-ppc-474902
export BQ_DATASET_ID=amazon_ppc
export BQ_LOCATION=us-east4
```

### Step 2: Run the Setup Script

The setup script creates the dataset and all required tables:

```bash
# Use default values (from config.json)
./setup-bigquery.sh

# Or specify custom values
./setup-bigquery.sh YOUR_PROJECT_ID YOUR_DATASET_ID YOUR_LOCATION
```

Example:
```bash
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
```

### Step 3: Fix BigQuery Data Transfer organization_id (if applicable)

If you are using the **BigQuery Data Transfer Service** to ingest
Amazon PPC data and see errors such as:

```
TransferRun only supports numeric values in organization id
```

update the transfer configuration so that the `organization_id` is a
numeric string.  This repository includes a helper script that performs
the validation and update for you.  It will even normalize values such as
`organizations/123456` down to the numeric portion automatically so that
you do not have to edit the value by hand:

```bash
python fix_bigquery_transfer.py \
  --project-id amazon-ppc-474902 \
  --location us \
  --config-id 69588e94-0000-2970-aebe-582429ad18d4 \
  --organization-id 1234567890
```

- Replace `1234567890` with your numeric organization ID provided by
  the data source.
- Use `--dry-run` to preview the change without updating the transfer.

The script will raise a validation error if no digits are present at all
in the supplied value, preventing misconfiguration before the transfer
run starts.

### Step 4: Grant Permissions

Grant the Cloud Function service account permission to write to BigQuery:

```bash
# Get the service account email
PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant BigQuery Data Editor role
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/bigquery.dataEditor"

# Grant BigQuery Job User role
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/bigquery.jobUser"
```

### Step 5: Test the Integration

Run the optimizer and check that data appears in BigQuery:

```bash
# Trigger an optimization run
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://YOUR-CLOUD-FUNCTION-URL"

# Query the results
bq query --use_legacy_sql=false \
  "SELECT run_id, status, keywords_optimized, average_acos 
   FROM \`amazon-ppc-474902.amazon_ppc.optimization_results\` 
   ORDER BY timestamp DESC 
   LIMIT 5"
```

## Data Schema

### Table: optimization_results

Main table with summary metrics from each optimization run.

| Field | Type | Description |
|-------|------|-------------|
| timestamp | TIMESTAMP | When the optimization ran |
| run_id | STRING | Unique identifier for this run |
| status | STRING | 'success', 'failed', etc. |
| profile_id | STRING | Amazon Ads profile ID |
| dry_run | BOOLEAN | Whether this was a test run |
| duration_seconds | FLOAT | How long the optimization took |
| campaigns_analyzed | INTEGER | Number of campaigns processed |
| keywords_optimized | INTEGER | Number of keyword bids adjusted |
| bids_increased | INTEGER | Number of bids increased |
| bids_decreased | INTEGER | Number of bids decreased |
| negative_keywords_added | INTEGER | Negative keywords added |
| budget_changes | INTEGER | Number of budget adjustments |
| total_spend | FLOAT | Total ad spend (14-day lookback) |
| total_sales | FLOAT | Total sales (14-day lookback) |
| average_acos | FLOAT | Average ACOS across campaigns |
| target_acos | FLOAT | Target ACOS from configuration |
| lookback_days | INTEGER | Days of data analyzed |
| enabled_features | STRING (REPEATED) | List of enabled features |
| errors | STRING (REPEATED) | Errors encountered |
| warnings | STRING (REPEATED) | Warnings generated |

**Partitioning**: Daily partitioning on `timestamp` field

### Table: campaign_details

Campaign-level performance metrics.

| Field | Type | Description |
|-------|------|-------------|
| timestamp | TIMESTAMP | When the optimization ran |
| run_id | STRING | Links to optimization_results |
| campaign_id | STRING | Amazon campaign ID |
| campaign_name | STRING | Campaign name |
| spend | FLOAT | Campaign spend |
| sales | FLOAT | Campaign sales |
| acos | FLOAT | Campaign ACOS |
| impressions | INTEGER | Ad impressions |
| clicks | INTEGER | Ad clicks |
| conversions | INTEGER | Conversions |
| budget | FLOAT | Daily budget |
| status | STRING | Campaign status |

**Partitioning**: Daily partitioning on `timestamp` field

### Table: optimization_progress

Real-time progress updates during optimization.

| Field | Type | Description |
|-------|------|-------------|
| timestamp | TIMESTAMP | Update time |
| run_id | STRING | Links to optimization_results |
| status | STRING | 'started', 'running', 'completed' |
| message | STRING | Progress message |
| percent_complete | FLOAT | Progress percentage (0-100) |
| profile_id | STRING | Amazon Ads profile ID |

**Partitioning**: Daily partitioning on `timestamp` field

### Table: optimization_errors

Error logs for troubleshooting.

| Field | Type | Description |
|-------|------|-------------|
| timestamp | TIMESTAMP | When error occurred |
| run_id | STRING | Links to optimization_results |
| status | STRING | 'failed' |
| profile_id | STRING | Amazon Ads profile ID |
| error_type | STRING | Exception class name |
| error_message | STRING | Error description |
| traceback | STRING | Full Python traceback |
| context | STRING | Additional context (JSON) |

**Partitioning**: Daily partitioning on `timestamp` field

## Example Queries

### Recent Optimization Results

```sql
SELECT 
  timestamp,
  run_id,
  keywords_optimized,
  bids_increased,
  bids_decreased,
  average_acos,
  duration_seconds
FROM `amazon-ppc-474902.amazon_ppc.optimization_results`
WHERE DATE(timestamp) >= CURRENT_DATE() - 7
ORDER BY timestamp DESC
```

### Campaign Performance Trends

```sql
SELECT 
  campaign_name,
  DATE(timestamp) as date,
  AVG(acos) as avg_acos,
  SUM(spend) as total_spend,
  SUM(sales) as total_sales
FROM `amazon-ppc-474902.amazon_ppc.campaign_details`
WHERE DATE(timestamp) >= CURRENT_DATE() - 30
GROUP BY campaign_name, DATE(timestamp)
ORDER BY date DESC, campaign_name
```

### Optimization Success Rate

```sql
SELECT 
  status,
  COUNT(*) as count,
  AVG(duration_seconds) as avg_duration,
  AVG(keywords_optimized) as avg_keywords_optimized
FROM `amazon-ppc-474902.amazon_ppc.optimization_results`
WHERE DATE(timestamp) >= CURRENT_DATE() - 30
GROUP BY status
```

### Error Analysis

```sql
SELECT 
  DATE(timestamp) as date,
  error_type,
  COUNT(*) as error_count,
  ARRAY_AGG(error_message LIMIT 5) as sample_messages
FROM `amazon-ppc-474902.amazon_ppc.optimization_errors`
WHERE DATE(timestamp) >= CURRENT_DATE() - 7
GROUP BY date, error_type
ORDER BY date DESC, error_count DESC
```

## Dashboard Integration

### Using BigQuery with Dashboards

The data stored in BigQuery can be visualized using:

1. **Looker Studio** (formerly Data Studio):
   - Connect to BigQuery
   - Create visualizations from your tables
   - Share dashboards with stakeholders

2. **Tableau**:
   - Use BigQuery connector
   - Build custom visualizations

3. **Custom Dashboards**:
   - Query BigQuery API from your web app
   - Use the provided proxy service

### BigQuery Proxy for Frontend

The optimizer includes a BigQuery proxy configuration that allows frontend applications to query the data:

```typescript
// In your Next.js/React app
const proxy = 'https://bq-proxy-1009540130231.us-east4.run.app';
const location = 'us-east4';

// Query example (through proxy)
fetch(`${proxy}/query`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'SELECT * FROM amazon_ppc.optimization_results LIMIT 10'
  })
})
```

## Cost Optimization

BigQuery charges for:
1. **Storage**: ~$0.02 per GB per month (first 10GB free)
2. **Queries**: $5 per TB processed (first 1TB free per month)

Estimated costs for typical usage:
- **Storage**: 1-5GB/month = ~$0.10/month
- **Queries**: <1TB/month = Free
- **Total**: <$1/month for most use cases

### Cost-Saving Tips

1. **Partition Tables**: Already configured (daily partitioning on timestamp)
2. **Use Date Filters**: Always include date filters in WHERE clauses
3. **Select Specific Columns**: Don't use `SELECT *` in production queries
4. **Set Query Limits**: Use LIMIT clause when exploring data

## Troubleshooting

### Error: "Failed to load BigQuery data" / "Dataset not found in location us-east4"

This error occurs when the BigQuery dataset and tables haven't been created yet, or were created in a different location than expected.

**Solution:**

1. Run the setup script to create the dataset and tables:
```bash
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
```

2. Verify the dataset was created in the correct location:
```bash
bq show amazon-ppc-474902:amazon_ppc
```

3. If the dataset exists in a different location, you have two options:
   - **Option A (Recommended)**: Update your configuration to use the existing location
   - **Option B**: Delete the old dataset and recreate it in us-east4:
     ```bash
     bq rm -r -f -d amazon-ppc-474902:amazon_ppc
     ./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
     ```

4. Ensure all environment variables are correctly configured:
   - `GCP_PROJECT=amazon-ppc-474902`
   - `BQ_DATASET_ID=amazon_ppc`
   - `BQ_LOCATION=us-east4`

### Error: "Dataset not found"

Run the setup script:
```bash
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
```

### Error: "Permission denied"

Grant permissions to the service account:
```bash
# Find your service account
gcloud projects get-iam-policy amazon-ppc-474902

# Grant required roles
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
    --member="serviceAccount:YOUR_SERVICE_ACCOUNT" \
    --role="roles/bigquery.dataEditor"
```

### Error: "BigQuery API not enabled"

Enable the BigQuery API:
```bash
gcloud services enable bigquery.googleapis.com --project=amazon-ppc-474902
```

### Data Not Appearing

1. Check optimizer logs for BigQuery errors
2. Verify configuration is correct in `config.json`
3. Ensure `bigquery.enabled` is set to `true`
4. Check service account permissions

### Query Performance Issues

1. Use date partitioning filters:
   ```sql
   WHERE DATE(timestamp) >= CURRENT_DATE() - 7
   ```

2. Create views for common queries:
   ```sql
   CREATE VIEW amazon_ppc.recent_optimizations AS
   SELECT * FROM amazon_ppc.optimization_results
   WHERE DATE(timestamp) >= CURRENT_DATE() - 30
   ```

## Manual Table Creation

If you prefer to create tables manually instead of using the setup script:

```bash
# Create dataset
bq mk --location=us-east4 \
    --description="Amazon PPC Optimization data" \
    --dataset amazon-ppc-474902:amazon_ppc

# Create optimization_results table
bq mk --table \
    --time_partitioning_field=timestamp \
    --time_partitioning_type=DAY \
    amazon-ppc-474902:amazon_ppc.optimization_results \
    timestamp:TIMESTAMP,run_id:STRING,status:STRING,...
```

(See setup-bigquery.sh for complete field definitions)

## Support

For issues or questions:
1. Check Cloud Function logs: `gcloud functions logs read amazon-ppc-optimizer`
2. Query BigQuery logs: `bq ls -j amazon-ppc-474902`
3. Review optimizer logs for BigQuery-related messages

## Summary

✅ **Setup**: Run `./setup-bigquery.sh` to create dataset and tables  
✅ **Configuration**: Enable in `config.json` with project ID and dataset  
✅ **Permissions**: Grant BigQuery roles to service account  
✅ **Testing**: Run optimizer and query results in BigQuery  
✅ **Dashboard**: Connect your visualization tool to BigQuery  

The BigQuery integration runs automatically - no code changes needed once configured!
