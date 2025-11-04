# CrewAI Integration Guide

This guide explains how the Amazon PPC Optimizer uses CrewAI to orchestrate data synchronization from BigQuery to the dashboard.

## Overview

The CrewAI integration creates specialized AI agents that work together to:
1. **Query** optimization data from BigQuery
2. **Transform** and prepare data for dashboard consumption
3. **Deliver** data reliably to the dashboard
4. **Verify** successful data delivery

## Architecture

### AI Agents

The system uses three specialized CrewAI agents:

#### 1. Data Analyst Agent
- **Role**: Query and analyze optimization data from BigQuery
- **Responsibilities**:
  - Query optimization results from BigQuery tables
  - Retrieve campaign-level performance data
  - Filter and aggregate data for the last 7 days
- **Tools**:
  - `query_bigquery_data`: Queries optimization_results table
  - `query_campaign_details`: Queries campaign_details table

#### 2. Data Engineer Agent
- **Role**: Transform and prepare data for dashboard consumption
- **Responsibilities**:
  - Format data according to dashboard API requirements
  - Validate data types and handle null values
  - Combine multiple data sources into cohesive payload
- **Tools**: Data transformation utilities

#### 3. Integration Specialist Agent
- **Role**: Reliably send data to dashboard and verify delivery
- **Responsibilities**:
  - Verify dashboard connectivity before sending data
  - Send data with proper authentication
  - Handle errors and retry logic
  - Confirm successful delivery
- **Tools**:
  - `send_to_dashboard`: Posts data to dashboard API
  - `verify_dashboard_connection`: Checks dashboard availability

### Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    Optimization Run                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
           ┌─────────────────────┐
           │  Write to BigQuery   │
           └──────────┬───────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │  CrewAI Sync Starts  │
           └──────────┬───────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌──────────────┐           ┌──────────────┐
│ Data Analyst │           │ Data Analyst │
│ Query Results│           │Query Campaigns│
└──────┬───────┘           └──────┬───────┘
       │                          │
       └──────────┬───────────────┘
                  │
                  ▼
          ┌───────────────┐
          │ Data Engineer │
          │Transform Data │
          └───────┬───────┘
                  │
                  ▼
       ┌──────────────────────┐
       │Integration Specialist│
       │  Verify Dashboard    │
       └──────────┬───────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │Integration Specialist│
       │   Send to Dashboard  │
       └──────────┬───────────┘
                  │
                  ▼
            ┌──────────┐
            │ Complete │
            └──────────┘
```

## Configuration

### Enable CrewAI Sync

Update your `config.json`:

```json
{
  "dashboard": {
    "url": "https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app",
    "api_key": "YOUR_DASHBOARD_API_KEY",
    "enabled": true,
    "send_real_time_updates": true,
    "timeout": 30,
    "sync_bigquery_data": true,
    "sync_interval_minutes": 15
  },
  "bigquery": {
    "enabled": true,
    "project_id": "amazon-ppc-474902",
    "dataset_id": "amazon_ppc",
    "location": "us-east4"
  }
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `sync_bigquery_data` | boolean | false | Enable automatic BigQuery to dashboard sync |
| `sync_interval_minutes` | integer | 15 | How often to sync data (for scheduled runs) |

### Environment Variables

For production deployments:

```bash
# Dashboard configuration
export DASHBOARD_URL="https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app"
export DASHBOARD_API_KEY="your_api_key"

# BigQuery configuration
export GCP_PROJECT="amazon-ppc-474902"
export GOOGLE_CLOUD_PROJECT="amazon-ppc-474902"
export BQ_DATASET_ID="amazon_ppc"
```

## Usage

### Automatic Sync

When `sync_bigquery_data` is enabled in config, the system automatically syncs data after each optimization run:

```python
# In main.py, after optimization completes
if CREWAI_SYNC_AVAILABLE and config.get('dashboard', {}).get('sync_bigquery_data', False):
    crewai_sync = BigQueryDashboardSync(config)
    sync_result = crewai_sync.sync_latest_run(run_id)
```

### Manual Sync via API

Trigger a manual sync using the Cloud Function endpoint:

```bash
# Sync last 7 days of data
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://YOUR-FUNCTION-URL?sync_bigquery=true"

# Sync specific optimization run
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://YOUR-FUNCTION-URL?sync_bigquery=true&run_id=YOUR_RUN_ID"
```

### Programmatic Usage

```python
from crewai_bigquery_sync import BigQueryDashboardSync

# Initialize
config = {
    'bigquery': {
        'project_id': 'amazon-ppc-474902',
        'dataset_id': 'amazon_ppc'
    },
    'dashboard': {
        'url': 'https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app',
        'api_key': 'your_api_key'
    }
}

sync = BigQueryDashboardSync(config)

# Sync last 7 days
result = sync.sync_data()

# Sync specific run
result = sync.sync_latest_run('run-uuid-here')
```

## API Endpoints

### Dashboard API

The CrewAI sync sends data to the following dashboard endpoints:

#### POST /api/optimization-data

Receives optimization data from BigQuery.

**Request Headers**:
```
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY
User-Agent: NWS-PPC-Optimizer-CrewAI/1.0
```

**Request Body**:
```json
{
  "data": [
    {
      "timestamp": "2025-11-04T10:00:00Z",
      "run_id": "uuid",
      "status": "success",
      "profile_id": "1780498399290938",
      "campaigns_analyzed": 10,
      "keywords_optimized": 150,
      "bids_increased": 75,
      "bids_decreased": 60,
      "total_spend": 1250.50,
      "total_sales": 3500.00,
      "average_acos": 0.357,
      "dry_run": false,
      "duration_seconds": 125.5
    }
  ],
  "run_id": "uuid"
}
```

**Success Response**:
```json
{
  "success": true,
  "message": "Data received successfully"
}
```

## Data Flow

### From BigQuery to Dashboard

1. **Query Phase**:
   - Data Analyst queries `optimization_results` table
   - Data Analyst queries `campaign_details` table
   - Retrieves last 7 days of data (configurable)

2. **Transform Phase**:
   - Data Engineer validates data types
   - Converts timestamps to ISO format
   - Handles null/missing values
   - Combines data sources

3. **Delivery Phase**:
   - Integration Specialist checks dashboard connectivity
   - Sends data with authentication
   - Handles retries on failure
   - Verifies successful delivery

### Data Schema

The sync sends the following data structure:

```typescript
interface OptimizationData {
  timestamp: string;          // ISO 8601 timestamp
  run_id: string;            // Unique run identifier
  status: string;            // 'success' | 'failed'
  profile_id: string;        // Amazon Ads profile ID
  campaigns_analyzed: number;
  keywords_optimized: number;
  bids_increased: number;
  bids_decreased: number;
  negative_keywords_added: number;
  budget_changes: number;
  total_spend: number;       // Total ad spend
  total_sales: number;       // Total sales
  average_acos: number;      // Average ACOS
  target_acos: number;       // Target ACOS from config
  dry_run: boolean;          // Was this a test run?
  duration_seconds: number;  // Optimization duration
}
```

## Error Handling

The CrewAI sync implements robust error handling:

### Non-Blocking Execution

```python
# Sync failures don't stop the optimization process
try:
    sync_result = crewai_sync.sync_latest_run(run_id)
    if sync_result.get('success'):
        logger.info("crewAI sync completed successfully")
    else:
        logger.warning(f"crewAI sync completed with issues")
except Exception as crew_err:
    logger.warning(f"crewAI sync failed (non-blocking): {crew_err}")
```

### Graceful Degradation

- If crewAI is not installed, the system continues without sync
- If BigQuery is unavailable, sync is skipped with a warning
- If dashboard is unreachable, errors are logged but optimization completes

### Retry Logic

The Integration Specialist agent handles retries automatically:
- Checks dashboard connectivity before sending
- Uses exponential backoff for retries
- Maximum 3 retry attempts
- Timeout: 30 seconds per request

## Monitoring

### Cloud Function Logs

Monitor the sync process in Cloud Logging:

```bash
# View recent sync logs
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=50 | grep -i crewai

# Filter for sync errors
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=50 | grep -i "crewai sync failed"
```

### Log Messages

Key log messages to monitor:

```
INFO: Syncing BigQuery data to dashboard with crewAI...
INFO: CrewAI sync completed successfully
WARNING: crewAI sync completed with issues: <error details>
WARNING: crewAI sync failed (non-blocking): <error details>
```

### Dashboard Verification

Verify data is appearing on the dashboard:

1. Open: https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app
2. Check for recent optimization runs
3. Verify timestamps match BigQuery data
4. Confirm metrics are accurate

## Troubleshooting

### Sync Not Running

**Problem**: CrewAI sync doesn't execute

**Solutions**:
1. Check if `sync_bigquery_data` is enabled in config
2. Verify crewAI is installed: `pip list | grep crewai`
3. Check Cloud Function logs for import errors
4. Ensure CREWAI_SYNC_AVAILABLE is True

```bash
# Check if crewAI is available
python3 -c "from crewai_bigquery_sync import CREWAI_AVAILABLE; print(CREWAI_AVAILABLE)"
```

### BigQuery Connection Errors

**Problem**: Cannot query BigQuery data

**Solutions**:
1. Verify BigQuery credentials are configured
2. Check service account has BigQuery permissions
3. Ensure project_id is correct in config
4. Verify BigQuery API is enabled

```bash
# Test BigQuery connection
python3 -c "from google.cloud import bigquery; client = bigquery.Client(); print('Connected')"
```

### Dashboard Unreachable

**Problem**: Cannot connect to dashboard

**Solutions**:
1. Verify dashboard URL is correct
2. Check dashboard is online (visit URL in browser)
3. Verify API key if authentication is required
4. Check network connectivity from Cloud Function

```bash
# Test dashboard connectivity
curl -I https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app
```

### Data Not Appearing on Dashboard

**Problem**: Sync succeeds but data doesn't appear

**Solutions**:
1. Check dashboard API endpoint is correct
2. Verify data format matches dashboard expectations
3. Check dashboard logs for processing errors
4. Confirm dashboard is configured to display the data

### Performance Issues

**Problem**: Sync takes too long

**Solutions**:
1. Reduce `limit` parameter in queries (default: 100)
2. Adjust timeout settings
3. Filter date range more aggressively
4. Check BigQuery query performance

## Testing

### Unit Tests

Run the test script to verify setup:

```bash
python3 test_crewai_sync.py
```

Tests include:
- Module import verification
- Configuration loading
- Tool availability
- Dashboard connectivity
- Class initialization

### Integration Tests

Test the full sync workflow:

```bash
# Trigger a test sync
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://YOUR-FUNCTION-URL?sync_bigquery=true"

# Check logs
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=20
```

### Manual Verification

1. Run an optimization (dry run is fine)
2. Check BigQuery for new data:
   ```sql
   SELECT * FROM `amazon-ppc-474902.amazon_ppc.optimization_results`
   ORDER BY timestamp DESC LIMIT 5
   ```
3. Trigger manual sync
4. Verify data on dashboard
5. Compare dashboard data with BigQuery

## Best Practices

### Configuration

1. **Use Environment Variables**: Keep sensitive data in environment variables, not config files
2. **Enable Monitoring**: Set up Cloud Logging alerts for sync failures
3. **Test in Dry Run**: Always test with `dry_run: true` first
4. **Set Reasonable Limits**: Don't query more data than needed

### Development

1. **Test Locally**: Use `test_crewai_sync.py` to verify setup
2. **Check Dependencies**: Ensure all required packages are installed
3. **Handle Errors**: Always implement graceful error handling
4. **Log Extensively**: Use appropriate log levels for debugging

### Production

1. **Monitor Logs**: Regularly check for sync errors
2. **Verify Data**: Periodically compare BigQuery and dashboard data
3. **Set Alerts**: Configure alerts for repeated failures
4. **Document Changes**: Keep track of configuration changes

## Dependencies

Required Python packages:

```
crewai==0.86.0
crewai-tools==0.17.0
google-cloud-bigquery==3.25.0
requests==2.31.0
```

Install all dependencies:

```bash
pip install -r requirements.txt
```

## Support

For issues or questions:

1. **Check Logs**: Review Cloud Function logs first
2. **Run Tests**: Execute `test_crewai_sync.py`
3. **Verify Config**: Ensure all configuration is correct
4. **Check Status**: Verify all services are online

## Summary

✅ **CrewAI Integration**: AI agents orchestrate data sync  
✅ **Automatic Sync**: Runs after each optimization  
✅ **Manual Trigger**: Available via API endpoint  
✅ **Non-Blocking**: Failures don't stop optimization  
✅ **Error Handling**: Robust retry and fallback logic  
✅ **Monitoring**: Comprehensive logging and alerts  

The CrewAI integration provides intelligent, reliable data synchronization from BigQuery to your dashboard!
