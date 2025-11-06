# Verification and Audit Trail System

## Overview

The Amazon PPC Optimizer now includes a comprehensive verification and audit trail system that ensures data integrity, validates critical operations, and maintains detailed logs of all actions taken.

## Features

### 1. Verification System

The verification system performs automatic checks before and during optimization to ensure:

- **API Connection Verification**: Validates Amazon Ads API connectivity
- **Data Integrity Checks**: Ensures all required fields are present and valid
- **Bid Calculation Verification**: Validates bid changes are within acceptable ranges
- **Integration Health Checks**: Tests BigQuery and dashboard connectivity
- **Configuration Validation**: Verifies all required settings are present

### 2. Enhanced Audit Trail

The audit trail system captures:

- **All Optimization Actions**: Bid changes, campaign updates, keyword additions
- **Verification Results**: Pass/fail status of all checks
- **Data Transformations**: Changes to bids, budgets, and campaign states
- **System Events**: API calls, database writes, dashboard updates
- **Error Tracking**: Complete error context and stack traces

### 3. Multi-Destination Data Flow

Optimization data is automatically sent to multiple destinations:

1. **BigQuery**: For historical analysis and reporting
2. **Vercel Dashboard**: Real-time optimization monitoring
3. **GitHub Pages Dashboard**: Public-facing metrics at https://natureswaysoil.github.io/best/
4. **Audit Trail CSV**: Local audit logs for compliance

## Configuration

### Enable Verification System

The verification system runs automatically before each optimization. To customize:

```json
{
  "verification": {
    "enabled": true,
    "run_pre_optimization": true,
    "fail_on_critical_errors": false,
    "checks": [
      "api_connection",
      "data_integrity",
      "bid_calculation",
      "bigquery_connection",
      "dashboard_connection"
    ]
  }
}
```

### Configure GitHub Pages Dashboard

Add to your `config.json`:

```json
{
  "github_pages_dashboard": {
    "enabled": true,
    "repo_owner": "natureswaysoil",
    "repo_name": "best",
    "branch": "main",
    "data_path": "data/ppc-data.json",
    "github_token": "ghp_xxxxxxxxxxxx",
    "dashboard_url": "https://natureswaysoil.github.io/best/"
  }
}
```

**GitHub Token Requirements:**
- Scope: `repo` (full control of private repositories)
- Permissions: Read and write access to repository contents
- Generate at: https://github.com/settings/tokens/new

### Configure BigQuery

```json
{
  "bigquery": {
    "enabled": true,
    "project_id": "your-gcp-project-id",
    "dataset_id": "amazon_ppc",
    "location": "us-east4"
  }
}
```

## Verification Checks

### 1. API Connection Check

Validates Amazon Ads API connectivity by:
- Fetching a sample of campaigns (default: 3)
- Measuring response time
- Verifying authentication

**Pass Criteria:**
- HTTP 200 response
- Valid campaign data returned
- Response time < 10 seconds

**Failure Actions:**
- Log detailed error
- Record in audit trail
- Continue with caution flag

### 2. Data Integrity Check

Ensures all critical data fields are present and valid:

```python
required_fields = [
    'campaign_id',
    'keyword_id',
    'bid',
    'impressions',
    'clicks',
    'cost',
    'sales'
]
```

**Pass Criteria:**
- All required fields present
- No null/undefined values
- Data types match expected format

### 3. Bid Calculation Verification

Validates bid changes before applying:

```python
# Checks performed:
- new_bid >= min_bid (default: $0.25)
- new_bid <= max_bid (default: $5.00)
- abs(change_pct) <= max_change_pct (default: 50%)
- new_bid > 0
```

**Pass Criteria:**
- Bid within min/max bounds
- Change percentage reasonable
- No extreme values

### 4. Integration Health Checks

Tests connectivity to all external services:

#### BigQuery
- Dataset accessibility
- Write permissions
- Schema compatibility

#### Dashboard (Vercel)
- Endpoint reachability
- Authentication valid
- API response < 30s

#### GitHub Pages Dashboard
- Repository access
- Write permissions
- GitHub API availability

## Audit Trail Format

### CSV Audit Trail

Generated in `./logs/` directory with format:

```csv
timestamp,action_type,entity_type,entity_id,old_value,new_value,reason,dry_run
2024-01-15T10:30:00Z,BID_UPDATE,KEYWORD,123456,$0.75,$0.85,"Low ACOS (35%) - increasing bid",false
2024-01-15T10:30:01Z,VERIFICATION_CHECK,API_CONNECTION,amazon_ads_api,,passed,"Successfully connected",false
2024-01-15T10:30:05Z,CAMPAIGN_PAUSE,CAMPAIGN,789012,enabled,paused,"ACOS 65% above threshold 45%",false
```

### BigQuery Schema

#### optimization_results table
```sql
CREATE TABLE amazon_ppc.optimization_results (
  timestamp TIMESTAMP,
  run_id STRING,
  status STRING,
  profile_id STRING,
  dry_run BOOLEAN,
  duration_seconds FLOAT64,
  campaigns_analyzed INT64,
  keywords_optimized INT64,
  bids_increased INT64,
  bids_decreased INT64,
  negative_keywords_added INT64,
  budget_changes INT64,
  total_spend FLOAT64,
  total_sales FLOAT64,
  average_acos FLOAT64,
  enabled_features ARRAY<STRING>,
  errors ARRAY<STRING>,
  warnings ARRAY<STRING>
)
PARTITION BY DATE(timestamp);
```

#### optimization_progress table
```sql
CREATE TABLE amazon_ppc.optimization_progress (
  timestamp TIMESTAMP,
  run_id STRING,
  status STRING,
  message STRING,
  percent_complete FLOAT64,
  profile_id STRING
)
PARTITION BY DATE(timestamp);
```

#### optimization_errors table
```sql
CREATE TABLE amazon_ppc.optimization_errors (
  timestamp TIMESTAMP,
  run_id STRING,
  status STRING,
  profile_id STRING,
  error_type STRING,
  error_message STRING,
  traceback STRING,
  context STRING
)
PARTITION BY DATE(timestamp);
```

## GitHub Pages Dashboard Data Format

The dashboard receives data in JSON format:

```json
{
  "updated_at": "2024-01-15T10:30:00Z",
  "latest": {
    "timestamp": "2024-01-15T10:30:00Z",
    "run_id": "uuid-here",
    "status": "success",
    "dry_run": false,
    "duration_seconds": 45.3,
    "metrics": {
      "campaigns_analyzed": 15,
      "keywords_optimized": 87,
      "bids_increased": 42,
      "bids_decreased": 45,
      "negative_keywords_added": 8,
      "budget_changes": 3,
      "total_spend": 1250.50,
      "total_sales": 3500.00,
      "average_acos": 0.357
    }
  },
  "runs": [ /* last 30 runs */ ],
  "statistics": {
    "total_runs": 30,
    "successful_runs": 28,
    "total_campaigns_analyzed": 450,
    "total_keywords_optimized": 2610,
    "total_spend": 37515.00,
    "total_sales": 105000.00,
    "average_acos": 0.357,
    "last_30_days": {
      "runs": 30,
      "avg_campaigns_per_run": 15,
      "avg_keywords_per_run": 87
    }
  },
  "last_verification": {
    "timestamp": "2024-01-15T10:30:00Z",
    "results": { /* verification results */ },
    "summary": {
      "total": 4,
      "passed": 4,
      "failed": 0,
      "warnings": 0
    }
  }
}
```

## Usage Examples

### Running with Verification

Verification runs automatically with each optimization:

```bash
# Local dry run with verification
python main.py

# Cloud Function with verification
curl -X POST "https://your-function-url" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d '{"dry_run": true}'
```

### Viewing Verification Results

Check logs for verification output:

```bash
# Local logs
tail -f ppc_main_*.log | grep "VERIFICATION"

# Cloud Function logs
gcloud functions logs read amazon-ppc-optimizer --limit=50 | grep "verification"
```

### Accessing Audit Trail

```bash
# Local audit CSV
ls -lh logs/ppc_audit_*.csv
cat logs/ppc_audit_*.csv | grep "BID_UPDATE"

# BigQuery audit data
bq query --use_legacy_sql=false '
  SELECT * FROM amazon_ppc.optimization_results 
  WHERE DATE(timestamp) = CURRENT_DATE()
  ORDER BY timestamp DESC
  LIMIT 10
'
```

### Viewing Dashboard Data

#### GitHub Pages Dashboard
Visit: https://natureswaysoil.github.io/best/

#### BigQuery Dashboard
```sql
-- Recent optimization runs
SELECT 
  timestamp,
  run_id,
  campaigns_analyzed,
  keywords_optimized,
  total_spend,
  total_sales,
  average_acos
FROM amazon_ppc.optimization_results
WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
ORDER BY timestamp DESC;

-- Performance trends
SELECT 
  DATE(timestamp) as date,
  COUNT(*) as runs,
  AVG(campaigns_analyzed) as avg_campaigns,
  AVG(keywords_optimized) as avg_keywords,
  SUM(total_spend) as total_spend,
  SUM(total_sales) as total_sales,
  AVG(average_acos) as avg_acos
FROM amazon_ppc.optimization_results
WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

## Troubleshooting

### Verification Failures

**API Connection Failed**
```
✗ API connection failed: HTTPError 401
```
Solution: Check Amazon Ads API credentials, refresh token may be expired

**BigQuery Connection Failed**
```
✗ BigQuery connection failed: Dataset not found
```
Solution: Run `./setup-bigquery.sh` to create dataset and grant permissions

**Dashboard Connection Failed**
```
✗ Dashboard health check failed: Connection timeout
```
Solution: Check dashboard URL, firewall rules, API key validity

### Audit Trail Issues

**No Audit File Generated**
```
No audit entries to save
```
Solution: This is normal if no changes were made (dry_run or no actions needed)

**BigQuery Write Failed**
```
BigQuery write failed (non-blocking): Permission denied
```
Solution: Grant BigQuery Data Editor role to service account

**GitHub Pages Update Failed**
```
GitHub API error: HTTP 403 - Resource not accessible
```
Solution: Check GitHub token has `repo` scope and valid permissions

## Best Practices

### 1. Review Verification Results

Always check verification results before production runs:

```python
if verification_results['summary']['failed'] > 0:
    # Review failures, consider dry_run
    logger.warning(f"{verification_results['summary']['failed']} checks failed")
```

### 2. Monitor Audit Trail

Set up alerts for critical actions:
- Large bid changes (>50%)
- Campaign pauses/activations
- API errors
- Verification failures

### 3. Regular Data Review

Schedule regular reviews of:
- BigQuery optimization data
- GitHub Pages dashboard metrics
- Audit trail CSV files
- Error logs

### 4. Backup Strategies

- Export audit trails regularly
- Backup BigQuery tables monthly
- Archive GitHub Pages data history
- Keep local logs for compliance

## Security Considerations

### Credentials Management

- Store GitHub token in Secret Manager
- Use environment variables for sensitive data
- Rotate tokens regularly (every 90 days)
- Limit token scope to minimum required

### Access Control

- Restrict BigQuery dataset access
- Use GitHub repository deploy keys
- Enable Cloud Function authentication
- Audit access logs regularly

### Data Privacy

- Audit trails may contain sensitive data
- Encrypt data at rest (BigQuery automatic)
- Control public dashboard visibility
- Comply with data retention policies

## Support

For issues or questions:
- Check logs: `gcloud functions logs read amazon-ppc-optimizer`
- Review audit trail: `cat logs/ppc_audit_*.csv`
- Query BigQuery: See examples above
- Contact: james@natureswaysoil.com
