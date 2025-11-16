# Dashboard Demo Data Guide

## Quick Start: See the Dashboard with Sample Data

If you want to see the dashboard working with data **without running the actual optimizer**, use the sample data generator.

### Step 1: Configure BigQuery Credentials

Set your BigQuery credentials (same as for the dashboard):

```bash
# Option 1: Service account file
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Option 2: JSON string
export GCP_CREDENTIALS_JSON='{"type": "service_account", ...}'

# Option 3: Base64 encoded
export GCP_CREDENTIALS_BASE64='base64-encoded-credentials'

# Set project ID
export GCP_PROJECT_ID="your-project-id"
```

### Step 2: Generate Sample Data

Run the sample data generator:

```bash
cd dashboard
python generate_sample_data.py
```

This will:
1. Create BigQuery tables if they don't exist
2. Generate realistic sample PPC optimization data
3. Populate all 5 tables with sample data:
   - `optimization_results` (10 runs)
   - `campaign_details` (~60 campaigns)
   - `optimization_progress` (~60 progress updates)
   - `optimization_errors` (5 sample errors)
   - `optimizer_run_events` (20 events)

### Step 3: View the Dashboard

Start the dashboard:

```bash
python app.py
```

Open http://localhost:8080 and you'll see:
- ✅ Summary cards with metrics
- ✅ Charts showing trends
- ✅ All 5 tables with data
- ✅ Fully functional dashboard

## What Data is Generated?

### Optimization Results
- 10 optimization runs spread over 30 days
- Realistic metrics (spend, sales, ACOS, keywords optimized)
- Mix of successful and completed-with-warnings statuses
- Varying campaign counts and keyword adjustments

### Campaign Details
- 4-7 campaigns per optimization run
- Real campaign names (Organic Fertilizer, Garden Soil, etc.)
- Performance metrics (spend, sales, impressions, clicks, conversions)
- Different ACOS values showing various performance levels

### Optimization Progress
- 6 progress stages per run (initializing → completing)
- Progress percentages from 0% to 100%
- Realistic timing between stages

### Optimization Errors
- Sample API timeouts, rate limits, and validation errors
- All marked as resolved
- Includes context for troubleshooting

### Run Events
- Start and complete events for each run
- Timestamps showing run duration
- Mix of completed and completed-with-warnings

## Sample Data Characteristics

The generated data is designed to be realistic:

- **ACOS values**: 12.5% - 40% (typical range for PPC campaigns)
- **ROAS**: 3x - 8x (healthy return on ad spend)
- **Spend per campaign**: $50 - $400
- **Keywords per run**: 50 - 200
- **Campaigns per run**: 5 - 15

This gives you a good representation of what the dashboard looks like with real optimization data.

## Regenerating Data

To clear and regenerate sample data:

```bash
# Delete existing data (be careful!)
bq query --nouse_legacy_sql \
  "DELETE FROM \`your-project.amazon_ppc.optimization_results\` WHERE TRUE"

# Repeat for other tables...

# Generate fresh data
python generate_sample_data.py
```

## Moving to Real Data

Once you're ready to use real data:

1. **Configure Amazon Advertising API credentials**:
   ```bash
   export AMAZON_CLIENT_ID="your-client-id"
   export AMAZON_CLIENT_SECRET="your-client-secret"
   export AMAZON_REFRESH_TOKEN="your-refresh-token"
   export AMAZON_PROFILE_ID="your-profile-id"
   ```

2. **Run the actual optimizer**:
   ```bash
   cd ..  # Back to repository root
   python optimizer_core.py --config config.json
   ```

3. **Dashboard automatically shows real data**: The sample data will be replaced as the optimizer runs

## Troubleshooting

### "Failed to initialize BigQuery client"
- Check that credentials environment variable is set
- Verify service account has BigQuery Data Editor role

### "Permission denied"
- Service account needs `BigQuery Data Editor` role (not just Viewer)
- Check project ID matches your BigQuery project

### Script runs but dashboard still shows errors
- Wait a moment for BigQuery to process inserts
- Refresh the dashboard browser page
- Check BigQuery console to verify data was written

### Tables not created
- Script automatically creates tables
- If issues, manually create dataset:
  ```bash
  bq mk --dataset your-project:amazon_ppc
  ```

## Customization

Edit `generate_sample_data.py` to customize:

- **Number of runs**: Change `num_runs = 10` to generate more/less data
- **Campaign names**: Edit `CAMPAIGN_NAMES` list
- **Metric ranges**: Adjust `random.uniform()` calls for spend, sales, etc.
- **Time range**: Modify `timedelta(days=i * 3)` for different date distribution

## Cleanup

To remove all sample data:

```bash
# Delete all data from tables
bq query --nouse_legacy_sql \
  "DELETE FROM \`your-project.amazon_ppc.optimization_results\` WHERE TRUE;
   DELETE FROM \`your-project.amazon_ppc.campaign_details\` WHERE TRUE;
   DELETE FROM \`your-project.amazon_ppc.optimization_progress\` WHERE TRUE;
   DELETE FROM \`your-project.amazon_ppc.optimization_errors\` WHERE TRUE;
   DELETE FROM \`your-project.amazon_ppc.optimizer_run_events\` WHERE TRUE;"
```

Or delete the entire dataset:

```bash
bq rm -r -f -d your-project:amazon_ppc
```

## Summary

The sample data generator lets you:
- ✅ See the dashboard working immediately
- ✅ Understand what data the optimizer generates
- ✅ Test dashboard features without API credentials
- ✅ Demo the system to stakeholders
- ✅ Develop/debug dashboard without running optimizer

Perfect for:
- Initial setup and configuration
- Testing deployment
- Training and demos
- Development and debugging
