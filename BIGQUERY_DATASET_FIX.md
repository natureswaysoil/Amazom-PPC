# BigQuery Dataset Not Found - Fix Guide

## Problem

```
Failed to load BigQuery data: Failed to fetch (proxy). 
Ensure the proxy URL is correct, uses https, and allows origin https://natureswaysoil.github.io. 
Details: Not found: Dataset amazon-ppc-474902:amazon_ppc was not found in location us-east4
```

## Root Cause

The BigQuery dataset `amazon-ppc-474902:amazon_ppc` does not exist in location `us-east4`. The setup script had an issue with REPEATED field definitions that prevented proper table creation.

## Solution

### Step 1: Create BigQuery Dataset and Tables

Run the setup script to create the dataset with all required tables:

```bash
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
```

This script will:
- ✅ Create the `amazon_ppc` dataset in `us-east4` location
- ✅ Create `optimization_results` table (with REPEATED fields for enabled_features, errors, warnings)
- ✅ Create `campaign_details` table
- ✅ Create `optimization_progress` table
- ✅ Create `optimization_errors` table
- ✅ Configure daily time partitioning for cost optimization

### Step 2: Grant Permissions

The Cloud Function service account needs BigQuery permissions:

```bash
# Get the service account email
PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format='value(projectNumber)')
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

### Step 3: Verify Setup

Check that the dataset and tables were created:

```bash
# List tables in the dataset
bq ls amazon-ppc-474902:amazon_ppc

# Show dataset details
bq show amazon-ppc-474902:amazon_ppc

# Verify table schema
bq show --schema amazon-ppc-474902:amazon_ppc.optimization_results
```

Expected output:
```
Tables in amazon-ppc-474902:amazon_ppc
  optimization_results
  campaign_details
  optimization_progress
  optimization_errors
```

### Step 4: Test the Integration

Trigger an optimization run and verify data is written:

```bash
# Query recent results
bq query --use_legacy_sql=false \
  "SELECT run_id, status, keywords_optimized, timestamp 
   FROM \`amazon-ppc-474902.amazon_ppc.optimization_results\` 
   ORDER BY timestamp DESC 
   LIMIT 5"
```

## What Changed

### Fixed Files

**setup-bigquery.sh:**
- Fixed REPEATED fields schema definition using JSON schema file
- Previously used inline field definitions which don't support REPEATED mode
- Now creates a temporary schema file for proper REPEATED field handling

**BIGQUERY_INTEGRATION.md:**
- Added specific troubleshooting for "Dataset not found" error
- Included verification steps and alternative solutions

**README.md:**
- Added BigQuery troubleshooting section
- Provided quick reference for dataset setup

## Configuration

Ensure your `config.json` has BigQuery enabled:

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

Or set environment variables:

```bash
export GCP_PROJECT=amazon-ppc-474902
export BQ_DATASET_ID=amazon_ppc
export BQ_LOCATION=us-east4
```

## Dashboard Integration

Once the dataset is created, the dashboard will automatically:
1. Query BigQuery for optimization results
2. Display summary metrics (last 7 days)
3. Show recent optimization runs in a table
4. Auto-refresh every 5 minutes

Access the dashboard at: `https://amazonppcdashboard.vercel.app`

## Troubleshooting

### Error: "bq: command not found"

Install Google Cloud SDK with BigQuery tools:
```bash
gcloud components install bq
```

### Error: "Permission denied"

Ensure you have the required IAM roles:
- `roles/bigquery.admin` or `roles/bigquery.dataEditor` on the dataset
- Authenticate with: `gcloud auth login`

### Error: "Dataset already exists in different location"

If the dataset exists in a different location:

**Option A (Recommended)**: Update configuration to match existing location
```bash
# Check current location
bq show amazon-ppc-474902:amazon_ppc

# Update config.json with the actual location
```

**Option B**: Delete and recreate in us-east4
```bash
bq rm -r -f -d amazon-ppc-474902:amazon_ppc
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
```

## Cost Estimate

BigQuery charges for storage and queries:
- **Storage**: ~$0.02/GB/month (first 10GB free)
- **Queries**: $5/TB processed (first 1TB/month free)
- **Expected**: <$1/month for typical usage

Tables use daily partitioning to minimize query costs.

## References

- [BIGQUERY_INTEGRATION.md](BIGQUERY_INTEGRATION.md) - Complete integration guide
- [BIGQUERY_FIX_SUMMARY.md](BIGQUERY_FIX_SUMMARY.md) - Original fix implementation
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)

## Summary

✅ **Fixed**: Setup script now properly handles REPEATED fields  
✅ **Resolution**: Run `./setup-bigquery.sh` to create dataset and tables  
✅ **Verification**: Use `bq ls` to confirm dataset exists  
✅ **Access**: Dashboard will display data automatically  

This fix ensures the BigQuery dataset is created with the correct schema, including proper REPEATED field support for arrays in the optimization results.
