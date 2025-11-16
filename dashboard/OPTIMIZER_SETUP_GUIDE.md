# Optimizer Setup Guide - Generate Real Dashboard Data

This guide walks you through setting up the optimizer to populate BigQuery with real Amazon PPC campaign data.

## Prerequisites

Before running the optimizer, you need:

1. **Amazon Advertising API Credentials**
   - Client ID
   - Client Secret
   - Refresh Token
   - Profile ID

2. **Google Cloud BigQuery Setup**
   - GCP Project with BigQuery enabled
   - Service account with BigQuery Data Editor role
   - Credentials file or JSON

## Step 1: Configure Amazon Advertising API Credentials

### Get Your Amazon Credentials

If you don't have them yet:

1. Go to [Amazon Advertising Console](https://advertising.amazon.com/)
2. Navigate to Settings → API
3. Create an API application
4. Note your Client ID and Client Secret
5. Generate a refresh token using the authorization flow

### Set Environment Variables

```bash
export AMAZON_CLIENT_ID="amzn1.application-oa2-client.YOUR_CLIENT_ID"
export AMAZON_CLIENT_SECRET="amzn1.oa2-cs.v1.YOUR_SECRET"
export AMAZON_REFRESH_TOKEN="Atzr|IwEBIYOUR_REFRESH_TOKEN"
export AMAZON_PROFILE_ID="YOUR_PROFILE_ID"
```

Or create a `config.json` file in the repository root:

```json
{
  "amazon_api": {
    "client_id": "amzn1.application-oa2-client.YOUR_CLIENT_ID",
    "client_secret": "amzn1.oa2-cs.v1.YOUR_SECRET",
    "refresh_token": "Atzr|IwEBIYOUR_REFRESH_TOKEN",
    "profile_id": "YOUR_PROFILE_ID",
    "region": "NA"
  },
  "bid_optimization": {
    "enabled": true,
    "target_acos": 0.25,
    "min_bid": 0.25,
    "max_bid": 5.00
  },
  "dashboard": {
    "url": "https://your-dashboard-url.com"
  }
}
```

## Step 2: Configure Google Cloud BigQuery

### Set BigQuery Credentials

```bash
# Option 1: Path to service account JSON file
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Option 2: JSON string
export GCP_CREDENTIALS_JSON='{"type": "service_account", "project_id": "your-project", ...}'

# Option 3: Base64 encoded
export GCP_CREDENTIALS_BASE64='base64-encoded-json'

# Set project and dataset
export GCP_PROJECT_ID="your-project-id"
export BIGQUERY_DATASET="amazon_ppc"
```

### Verify BigQuery Access

Test your credentials:

```bash
# Using bq command-line tool
bq ls --project_id=your-project-id amazon_ppc

# Or using Python
python -c "
from google.cloud import bigquery
client = bigquery.Client(project='your-project-id')
print('BigQuery connection successful!')
print('Dataset:', client.get_dataset('amazon_ppc'))
"
```

## Step 3: Run the Optimizer

### Basic Run

From the repository root:

```bash
python optimizer_core.py --config config.json
```

### Run with Specific Features

```bash
# Only run bid optimization
python optimizer_core.py --features bid_optimization

# Run multiple features
python optimizer_core.py --features bid_optimization,dayparting,negative_keywords
```

### Dry Run (No Changes)

Test without making actual changes:

```bash
python optimizer_core.py --dry-run --config config.json
```

This will:
- Fetch campaign data from Amazon API
- Analyze performance
- Calculate optimizations
- Write results to BigQuery
- **NOT** apply changes to campaigns

### Verify Connection First

```bash
python optimizer_core.py --verify-connection --config config.json
```

## Step 4: Monitor the Optimizer

### Watch Progress

The optimizer will output progress information:

```
Initializing optimizer...
Fetching campaign data from Amazon Advertising API...
Analyzing 15 campaigns...
Optimizing 186 keywords...
Writing results to BigQuery...
✓ Optimization complete!
```

### Check BigQuery Tables

After the optimizer runs, verify data was written:

```bash
# Check row counts
bq query --nouse_legacy_sql "
SELECT 
  'optimization_results' as table_name,
  COUNT(*) as row_count 
FROM \`your-project.amazon_ppc.optimization_results\`
UNION ALL
SELECT 
  'campaign_details' as table_name,
  COUNT(*) as row_count 
FROM \`your-project.amazon_ppc.campaign_details\`
"
```

## Step 5: View Data in Dashboard

Once the optimizer completes:

1. Start the dashboard:
   ```bash
   cd dashboard
   python app.py
   ```

2. Open http://localhost:8080

3. You should now see:
   - Real metrics in summary cards
   - Actual campaign performance in charts
   - Your campaigns in the tables
   - Recent optimization history

## Automated Runs

### Cloud Scheduler (Google Cloud)

Set up automated runs:

```bash
gcloud scheduler jobs create http ppc-optimizer-daily \
  --schedule="0 2 * * *" \
  --time-zone="America/New_York" \
  --uri="https://your-optimizer-url.run.app" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"features": ["bid_optimization", "dayparting"]}'
```

### Cron Job (Linux/Mac)

Add to crontab:

```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/Amazom-PPC && /usr/bin/python optimizer_core.py --config config.json >> /var/log/ppc-optimizer.log 2>&1
```

## Troubleshooting

### "Failed to initialize BigQuery client"

**Cause**: BigQuery credentials not configured

**Fix**:
```bash
# Check if credentials are set
echo $GOOGLE_APPLICATION_CREDENTIALS
# or
echo $GCP_CREDENTIALS_JSON | jq .project_id

# If not set, export them
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
```

### "Amazon API authentication failed"

**Cause**: Invalid or expired Amazon API credentials

**Fix**:
1. Verify credentials in config.json
2. Check if refresh token is still valid
3. Regenerate refresh token if needed
4. Ensure profile_id is correct

### "No campaigns found"

**Cause**: Profile ID incorrect or no active campaigns

**Fix**:
1. Verify profile_id matches your Amazon Advertising account
2. Check that you have active campaigns in that profile
3. Ensure API has access to the profile

### Optimizer runs but dashboard shows no data

**Possible causes**:
1. Different BigQuery project/dataset in dashboard vs optimizer
2. Dashboard looking at wrong time range
3. Data written to different dataset

**Fix**:
```bash
# Verify both use same settings
echo "Optimizer project: $GCP_PROJECT_ID"
cd dashboard && python -c "import os; print(f'Dashboard project: {os.getenv(\"GCP_PROJECT_ID\", \"nature-way-soils\")}')"

# Check if data exists in BigQuery
bq query --nouse_legacy_sql "
SELECT COUNT(*), MAX(timestamp) as latest
FROM \`your-project.amazon_ppc.optimization_results\`
"
```

## Configuration Options

### Full config.json Example

```json
{
  "amazon_api": {
    "client_id": "amzn1.application-oa2-client.xxxxx",
    "client_secret": "amzn1.oa2-cs.v1.xxxxx",
    "refresh_token": "Atzr|IwEBIxxxxx",
    "profile_id": "1780498399290938",
    "region": "NA"
  },
  "bid_optimization": {
    "enabled": true,
    "target_acos": 0.25,
    "min_bid": 0.25,
    "max_bid": 5.00,
    "bid_adjustment_percentage": 0.15,
    "lookback_days": 30
  },
  "dayparting": {
    "enabled": true,
    "boost_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    "boost_multiplier": 1.2,
    "reduce_multiplier": 0.8
  },
  "negative_keywords": {
    "enabled": true,
    "min_clicks": 10,
    "min_acos": 0.50
  },
  "budget_optimization": {
    "enabled": true,
    "max_budget_increase": 0.20,
    "max_budget_decrease": 0.15
  },
  "dashboard": {
    "url": "http://localhost:8080"
  }
}
```

### Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `AMAZON_CLIENT_ID` | Amazon API Client ID | `amzn1.application-oa2-client.xxxxx` |
| `AMAZON_CLIENT_SECRET` | Amazon API Secret | `amzn1.oa2-cs.v1.xxxxx` |
| `AMAZON_REFRESH_TOKEN` | Amazon Refresh Token | `Atzr\|IwEBIxxxxx` |
| `AMAZON_PROFILE_ID` | Amazon Profile ID | `1780498399290938` |
| `GCP_PROJECT_ID` | Google Cloud Project | `your-project-id` |
| `BIGQUERY_DATASET` | BigQuery Dataset | `amazon_ppc` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to credentials | `/path/to/creds.json` |
| `PPC_DRY_RUN` | Dry run mode | `true` or `false` |
| `PPC_FEATURES` | Features to run | `bid_optimization,dayparting` |

## Next Steps

1. **Monitor Performance**: Watch dashboard charts after each run
2. **Adjust Settings**: Fine-tune target ACOS and bid ranges in config
3. **Schedule Regular Runs**: Set up daily automated optimizations
4. **Review Results**: Check optimization_results table for insights
5. **Iterate**: Adjust strategy based on performance data

## Support

If you encounter issues:

1. Check optimizer logs for errors
2. Verify all credentials are correct
3. Test with `--verify-connection` flag
4. Run with `--dry-run` first
5. Review BigQuery permissions
6. Check dashboard/DATA_SOURCE_GUIDE.md for data flow details

## Summary

**To generate real dashboard data:**

```bash
# 1. Set credentials
export AMAZON_CLIENT_ID="..."
export AMAZON_CLIENT_SECRET="..."
export AMAZON_REFRESH_TOKEN="..."
export AMAZON_PROFILE_ID="..."
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/creds.json"

# 2. Run optimizer
python optimizer_core.py --config config.json

# 3. Start dashboard
cd dashboard && python app.py

# 4. View at http://localhost:8080
```

Your dashboard will now display real campaign data and optimization results!
