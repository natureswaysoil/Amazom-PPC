# Run Optimizer with Live Data - Quick Guide

Automated script to load credentials from Google Secret Manager, run the optimizer, and populate BigQuery with live Amazon PPC campaign data.

## Quick Start

### One-Command Execution

```bash
./run_optimizer_with_data.sh
```

This single command will:
1. ✅ Load all credentials from Google Secret Manager
2. ✅ Verify credentials are valid
3. ✅ Run the Amazon PPC optimizer
4. ✅ Populate BigQuery with live campaign data
5. ✅ Make data available for the dashboard

### With Dashboard Auto-Launch

```bash
./run_optimizer_with_data.sh --start-dashboard
```

This will run the optimizer and automatically start the dashboard when complete.

---

## Options

### Dry Run Mode (Recommended for First Run)

Test the complete flow without making any changes to your campaigns:

```bash
./run_optimizer_with_data.sh --dry-run
```

### Verify Credentials Only

Check that all required secrets are accessible before running:

```bash
./run_optimizer_with_data.sh --verify-only
```

### Custom Configuration

Use a specific configuration file:

```bash
./run_optimizer_with_data.sh --config my-config.json
```

### All Options Combined

```bash
./run_optimizer_with_data.sh --dry-run --config config.json --start-dashboard
```

---

## What It Does

### Step 1: Load Credentials
- Connects to Google Secret Manager
- Fetches all required credentials:
  - `amazon-client-id` - Amazon Advertising API client ID
  - `amazon-client-secret` - Amazon API client secret
  - `amazon-refresh-token` - Amazon API refresh token
  - `amazon-profile-id` - Amazon Advertising profile ID
  - `bigquery-service-account` - BigQuery credentials JSON
- Exports them as environment variables

### Step 2: Verify Setup
- Checks that all required credentials are present
- Validates Google Cloud authentication
- Confirms BigQuery access

### Step 3: Run Optimizer
- Executes `optimizer_core.py` with loaded credentials
- Fetches live campaign data from Amazon Advertising API
- Analyzes performance and identifies optimization opportunities
- (In normal mode) Makes recommended bid/budget adjustments
- Writes all results to BigQuery

### Step 4: Populate BigQuery
Data is written to these tables:
- **optimization_results** - Summary of each optimization run
- **campaign_details** - Performance metrics for each campaign
- **optimization_progress** - Real-time progress during execution
- **optimization_errors** - Any errors encountered
- **optimizer_run_events** - Detailed event log

### Step 5: Display in Dashboard
- Dashboard automatically reads from BigQuery
- Refreshes every 5 minutes
- Shows live campaign performance data

---

## Prerequisites

### 1. Google Cloud Authentication

Authenticate with Google Cloud:

```bash
gcloud auth application-default login
```

### 2. Required Secrets in Secret Manager

Ensure these secrets exist in Google Secret Manager:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `amazon-client-id` | Amazon Advertising API client ID | `amzn1.application-oa2-client.abc123...` |
| `amazon-client-secret` | Amazon API client secret | `amzn1.oa2-cs.v1.xyz789...` |
| `amazon-refresh-token` | Amazon API refresh token | `Atzr\|IwEBIABC123...` |
| `amazon-profile-id` | Amazon Advertising profile ID | `1234567890` |
| `bigquery-service-account` | BigQuery service account JSON | `{"type": "service_account", ...}` |

### 3. Permissions

Your Google Cloud account needs:
- `secretmanager.versions.access` permission for Secret Manager
- `bigquery.tables.create` and `bigquery.tables.updateData` for BigQuery

---

## Usage Examples

### First Time Setup (Dry Run)

```bash
# 1. Verify credentials are accessible
./run_optimizer_with_data.sh --verify-only

# 2. Test without making changes
./run_optimizer_with_data.sh --dry-run

# 3. Run for real
./run_optimizer_with_data.sh
```

### Daily Optimization Run

```bash
# Standard daily run
./run_optimizer_with_data.sh

# View results immediately
./run_optimizer_with_data.sh --start-dashboard
```

### Scheduled Automation

Add to crontab for daily execution at 6 AM:

```bash
0 6 * * * cd /path/to/Amazom-PPC && ./run_optimizer_with_data.sh >> /var/log/ppc-optimizer.log 2>&1
```

Or use Cloud Scheduler with this command:

```bash
gcloud scheduler jobs create http ppc-optimizer-daily \
  --schedule="0 6 * * *" \
  --uri="https://YOUR-CLOUD-RUN-URL/run" \
  --http-method=POST
```

---

## Output Example

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🚀 Amazon PPC Optimizer with Live Data
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ Checking for load_secrets.py script...
✓ Found load_secrets.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📦 Loading Credentials from Secret Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ Fetching credentials from Google Secret Manager...
✓ Credentials verified successfully
ℹ Loading credentials into environment...
✓ Credentials loaded successfully
  • Amazon Client ID: amzn1.application-o...
  • Profile ID: 1234567890
  • GCP Project: my-gcp-project

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚙️  Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ Checking configuration file...
✓ Found config file: config.json

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🔄 Running Amazon PPC Optimizer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ Starting optimizer...

[Optimizer output...]

✓ Optimizer completed successfully
ℹ Data has been written to BigQuery tables

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Live data is now available in BigQuery tables:
  • optimization_results
  • campaign_details
  • optimization_progress
  • optimization_errors
  • optimizer_run_events

ℹ To view the data in the dashboard, run:

    cd dashboard && python app.py

ℹ Or run this script with --start-dashboard to auto-launch

✓ Done! 🎉
```

---

## Troubleshooting

### Error: "Failed to verify credentials in Secret Manager"

**Solutions:**
1. Authenticate with Google Cloud:
   ```bash
   gcloud auth application-default login
   ```

2. Verify secrets exist:
   ```bash
   gcloud secrets list
   ```

3. Check you have access:
   ```bash
   gcloud secrets versions access latest --secret="amazon-client-id"
   ```

### Error: "Required Amazon API credentials not loaded"

**Solutions:**
1. Verify secret names match exactly:
   - `amazon-client-id` (not `AMAZON_CLIENT_ID`)
   - `amazon-client-secret`
   - `amazon-refresh-token`
   - `amazon-profile-id`

2. Check secret content is not empty:
   ```bash
   python load_secrets.py --verify
   ```

### Error: "Config file not found"

**Solutions:**
- Create `config.json` in the repository root
- Or specify a different config: `--config path/to/config.json`
- Or omit config file (will use environment variables only)

### Optimizer runs but no data in dashboard

**Solutions:**
1. Check BigQuery tables were created:
   ```bash
   bq ls --project_id=YOUR_PROJECT
   ```

2. Verify data was written:
   ```bash
   bq query --project_id=YOUR_PROJECT "SELECT COUNT(*) FROM optimization_results"
   ```

3. Check dashboard is using correct project:
   ```bash
   echo $GCP_PROJECT_ID
   ```

---

## Advanced Usage

### Run with Custom Environment

```bash
export GCP_PROJECT_ID="my-custom-project"
export DATASET_ID="custom_dataset"
./run_optimizer_with_data.sh
```

### Integration with CI/CD

```yaml
# .github/workflows/daily-optimization.yml
name: Daily PPC Optimization

on:
  schedule:
    - cron: '0 6 * * *'  # 6 AM daily
  workflow_dispatch:  # Manual trigger

jobs:
  optimize:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_CREDENTIALS }}
      
      - name: Run Optimizer
        run: ./run_optimizer_with_data.sh
      
      - name: Notify on completion
        if: success()
        run: echo "Optimization completed successfully"
```

---

## Next Steps

After running the optimizer:

1. **View Dashboard**
   ```bash
   cd dashboard && python app.py
   ```
   Open http://localhost:8080

2. **Check Results**
   ```bash
   python -c "from google.cloud import bigquery; 
              client = bigquery.Client(); 
              print(list(client.query('SELECT * FROM optimization_results LIMIT 1')))"
   ```

3. **Schedule Regular Runs**
   - Use cron for Linux/Mac
   - Use Task Scheduler for Windows
   - Use Cloud Scheduler for cloud deployment

4. **Monitor Performance**
   - Review dashboard metrics
   - Check optimization_errors table
   - Set up alerts for failures

---

## Related Documentation

- [Optimizer Setup Guide](dashboard/OPTIMIZER_SETUP_GUIDE.md) - Detailed credential setup
- [Amazon API Versions](AMAZON_API_VERSIONS.md) - API version requirements
- [Dashboard README](dashboard/README.md) - Dashboard features and API
- [Data Source Guide](dashboard/DATA_SOURCE_GUIDE.md) - How data flows from Amazon to BigQuery

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review [OPTIMIZER_SETUP_GUIDE.md](dashboard/OPTIMIZER_SETUP_GUIDE.md)
3. Verify credentials with `./run_optimizer_with_data.sh --verify-only`
4. Check optimizer logs for detailed error messages
