# BigQuery Integration Verification Checklist

This checklist helps you verify that the complete data flow from optimizer → BigQuery → dashboard is working correctly.

## Quick Status Check

Run these commands to quickly check the status of your BigQuery integration:

```bash
# 1. Test BigQuery integration (read-only)
python test_bigquery_integration.py --project-id amazon-ppc-474902 --read-only

# 2. Check dashboard configuration
curl https://your-dashboard-url.vercel.app/api/config-check | jq .

# 3. Test BigQuery data retrieval via dashboard API
curl https://your-dashboard-url.vercel.app/api/bigquery-data?limit=1 | jq .
```

---

## Phase 1: Optimizer → BigQuery (Data Writing)

### ✅ Prerequisites
- [ ] Optimizer is deployed to Cloud Function
- [ ] Optimizer configuration has `bigquery.enabled: true`
- [ ] GCP_SERVICE_ACCOUNT_KEY is set in Cloud Function environment
- [ ] Service account has BigQuery Data Editor + Job User roles

### ✅ Verification Steps

#### 1.1 Check Optimizer Configuration
```bash
# View optimizer configuration in Cloud Function
gcloud functions describe amazon-ppc-optimizer --region=us-central1 --gen2 --format=yaml | grep -A 10 "serviceConfig"
```

**Expected:** Environment variables include GCP_SERVICE_ACCOUNT_KEY, GCP_PROJECT

#### 1.2 Trigger Optimizer Run
```bash
# Trigger a dry-run optimization
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}' \
  "https://YOUR-FUNCTION-URL"
```

**Expected:** HTTP 200 with status "success" in response

#### 1.3 Check Optimizer Logs
```bash
# Check logs for BigQuery writes
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --limit=100 | grep -i bigquery
```

**Expected to see:**
- ✅ "BigQuery client initialized for project amazon-ppc-474902"
- ✅ "Successfully wrote optimization results to BigQuery"
- ✅ "Successfully wrote X campaign details to BigQuery"
- ❌ NO errors like "Failed to write to BigQuery"

#### 1.4 Query BigQuery Directly
```bash
# Check if data exists in optimization_results table
bq query --use_legacy_sql=false \
  'SELECT timestamp, run_id, status, campaigns_analyzed, keywords_optimized 
   FROM `amazon-ppc-474902.amazon_ppc.optimization_results` 
   ORDER BY timestamp DESC LIMIT 5'
```

**Expected:** See recent optimization runs with data

#### 1.5 Verify Enhanced Fields
```bash
# Check for campaigns and top_performers data
bq query --use_legacy_sql=false \
  "SELECT 
     run_id,
     LENGTH(campaigns) as campaigns_length,
     LENGTH(top_performers) as top_performers_length,
     LENGTH(features) as features_length
   FROM \`amazon-ppc-474902.amazon_ppc.optimization_results\`
   ORDER BY timestamp DESC LIMIT 5"
```

**Expected:** campaigns_length > 2 (not empty JSON), same for top_performers and features

---

## Phase 2: BigQuery → Dashboard (Data Reading)

### ✅ Prerequisites
- [ ] Dashboard is deployed (Vercel, Cloud Run, etc.)
- [ ] GCP_SERVICE_ACCOUNT_KEY is set in dashboard environment
- [ ] Service account has BigQuery Data Viewer + Job User roles
- [ ] Dashboard can reach BigQuery API (no firewall issues)

### ✅ Verification Steps

#### 2.1 Check Dashboard Configuration
Visit: `https://your-dashboard-url.vercel.app/api/config-check`

**Expected to see:**
- ✅ "status": "ok" or "warning"
- ✅ "gcp_service_account_key": {"set": true, "valid_json": true}
- ✅ "gcp_credentials_ok": true in diagnosis
- ❌ NO "Missing Google Cloud credentials" errors

#### 2.2 Test BigQuery Connection from Dashboard
Visit: `https://your-dashboard-url.vercel.app/api/bigquery-data?table=optimization_results&limit=1`

**Expected Response:**
```json
{
  "success": true,
  "data": [
    {
      "timestamp": "2025-11-16T...",
      "run_id": "...",
      "campaigns_analyzed": 253,
      "campaigns": [...],
      "top_performers": [...]
    }
  ],
  "metadata": {
    "projectId": "amazon-ppc-474902",
    "datasetId": "amazon_ppc",
    "table": "optimization_results",
    "rowCount": 1,
    "credentialSource": "..."
  }
}
```

**If you see errors:**
- "Missing Google Cloud credentials" → Set GCP_SERVICE_ACCOUNT_KEY
- "Access Denied" → Grant BigQuery permissions to service account
- "Not found: Dataset" → Trigger optimizer run to create tables
- "Not found: Table" → Trigger optimizer run to create tables

#### 2.3 Verify Dashboard UI
Visit: `https://your-dashboard-url.vercel.app/`

**Expected to see:**
- ✅ Optimization run statistics displayed
- ✅ Recent results table with data
- ✅ Performance metrics (spend, sales, ACOS)
- ✅ Campaign breakdown (if campaigns data available)
- ✅ Top performers list (if top_performers data available)
- ❌ NO "Error Loading Data" message
- ❌ NO "No optimization runs found" (if optimizer has run)

#### 2.4 Check Browser Console
Open browser developer tools → Console tab

**Expected to see:**
- ✅ "📊 Dashboard: Received optimization results"
- ✅ Log showing result keys and data
- ❌ NO console errors about failed API calls
- ❌ NO missing field warnings (if optimizer provides full data)

---

## Phase 3: Data Completeness

### ✅ Field Verification

Check that all expected fields are present in the data:

```bash
# Get a sample result and check structure
bq query --use_legacy_sql=false --format=prettyjson \
  'SELECT * FROM `amazon-ppc-474902.amazon_ppc.optimization_results` 
   ORDER BY timestamp DESC LIMIT 1' | jq '.[0] | keys'
```

**Expected Fields:**
- ✅ timestamp, run_id, status, profile_id, dry_run
- ✅ duration_seconds
- ✅ campaigns_analyzed, keywords_optimized, bids_increased, bids_decreased
- ✅ negative_keywords_added, budget_changes
- ✅ total_spend, total_sales, average_acos
- ✅ target_acos, lookback_days
- ✅ enabled_features (array)
- ✅ errors (array), warnings (array)
- ✅ campaigns (JSON string or object)
- ✅ top_performers (JSON string or object)
- ✅ features (JSON string or object)
- ✅ config_snapshot (JSON string or object)

### ✅ Data Validation

```bash
# Parse and validate JSON fields
bq query --use_legacy_sql=false --format=prettyjson \
  'SELECT 
     run_id,
     JSON_EXTRACT(campaigns, "$") as campaigns_parsed,
     JSON_EXTRACT(top_performers, "$") as top_performers_parsed,
     JSON_EXTRACT(features, "$") as features_parsed
   FROM `amazon-ppc-474902.amazon_ppc.optimization_results`
   ORDER BY timestamp DESC LIMIT 1' | jq .
```

**Expected:**
- ✅ campaigns_parsed contains array of campaign objects
- ✅ Each campaign has: campaign_id, campaign_name, spend, sales, acos
- ✅ top_performers_parsed contains array of keyword objects
- ✅ Each keyword has: keyword_text, clicks, sales, acos, bid_change
- ✅ features_parsed contains object with feature results

---

## Phase 4: End-to-End Test

Run the integration test script:

```bash
# Test writing to BigQuery (dry-run mode)
python test_bigquery_integration.py --project-id amazon-ppc-474902 --dry-run

# Test writing actual test data
python test_bigquery_integration.py --project-id amazon-ppc-474902

# Test reading data
python test_bigquery_integration.py --project-id amazon-ppc-474902 --read-only
```

**Expected:**
- ✅ "ALL TESTS PASSED"
- ✅ Test data visible in BigQuery
- ✅ Dashboard shows test data

**Cleanup test data:**
```sql
-- Run in BigQuery console or bq command
DELETE FROM `amazon-ppc-474902.amazon_ppc.optimization_results` 
WHERE run_id IN (
  SELECT run_id 
  FROM `amazon-ppc-474902.amazon_ppc.optimization_results` 
  WHERE campaign_name LIKE '%Test%' 
     OR warnings[SAFE_OFFSET(0)] LIKE '%TEST DATA%'
);
```

---

## Phase 5: Performance & Monitoring

### ✅ Query Performance
```bash
# Test query performance
time curl "https://your-dashboard-url.vercel.app/api/bigquery-data?table=optimization_results&limit=50"
```

**Expected:** < 3 seconds response time

### ✅ Data Freshness
```bash
# Check how recent the data is
bq query --use_legacy_sql=false \
  'SELECT 
     MAX(timestamp) as latest_run,
     COUNT(*) as total_runs,
     TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(timestamp), MINUTE) as minutes_ago
   FROM `amazon-ppc-474902.amazon_ppc.optimization_results`'
```

**Expected:** latest_run within expected optimizer schedule

### ✅ Error Rate
```bash
# Check for failed runs
bq query --use_legacy_sql=false \
  'SELECT 
     status,
     COUNT(*) as count
   FROM `amazon-ppc-474902.amazon_ppc.optimization_results`
   WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
   GROUP BY status'
```

**Expected:** Most runs with status = "success"

---

## Troubleshooting Guide

### Issue: "No data in BigQuery tables"

**Diagnosis:**
```bash
# Check if tables exist
bq ls amazon_ppc

# Check table schemas
bq show amazon_ppc.optimization_results
```

**Solutions:**
1. Trigger an optimizer run to create tables
2. Manually create tables using setup-bigquery.sh
3. Check optimizer logs for write errors

### Issue: "Dashboard shows 'Missing Google Cloud credentials'"

**Diagnosis:**
```bash
# Check if credential is set
curl https://your-dashboard-url.vercel.app/api/config-check | jq '.checks.configuration.credentials'
```

**Solutions:**
1. Set GCP_SERVICE_ACCOUNT_KEY in deployment environment
2. Ensure JSON is valid (not just file path)
3. Try base64 encoding: `cat service-account.json | base64 | tr -d '\n'`
4. Redeploy dashboard after setting variables

### Issue: "Access Denied" errors

**Diagnosis:**
```bash
# Check service account permissions
gcloud projects get-iam-policy amazon-ppc-474902 \
  --flatten="bindings[].members" \
  --filter="bindings.members:YOUR_SERVICE_ACCOUNT_EMAIL"
```

**Solutions:**
1. Grant roles/bigquery.dataViewer role
2. Grant roles/bigquery.jobUser role
3. Wait 1-2 minutes for permissions to propagate

### Issue: "Dashboard shows data but missing campaigns/top_performers"

**Diagnosis:**
```bash
# Check if optimizer is collecting enhanced data
bq query --use_legacy_sql=false \
  "SELECT 
     run_id,
     campaigns,
     top_performers
   FROM \`amazon-ppc-474902.amazon_ppc.optimization_results\`
   ORDER BY timestamp DESC LIMIT 1"
```

**Solutions:**
1. Ensure optimizer is using latest version with enhanced data collection
2. Check optimizer_core.py has _extract_campaigns and _extract_top_performers
3. Verify BidOptimizer and CampaignManager are returning enhanced results
4. Check dashboard_client.py is building enhanced payloads

---

## Success Criteria

Your BigQuery integration is working correctly when:

✅ **Optimizer → BigQuery**
- [ ] Optimizer runs successfully without errors
- [ ] BigQuery tables contain recent data
- [ ] All expected fields are populated
- [ ] JSON fields (campaigns, top_performers, features) contain data

✅ **BigQuery → Dashboard**
- [ ] Dashboard `/api/config-check` shows credentials configured
- [ ] Dashboard `/api/bigquery-data` returns data successfully
- [ ] Dashboard UI displays optimization results
- [ ] No error messages on dashboard

✅ **Data Completeness**
- [ ] Summary metrics are accurate (campaigns analyzed, keywords optimized, etc.)
- [ ] Campaign breakdown is available
- [ ] Top performers list is populated
- [ ] Performance metrics (spend, sales, ACOS) are correct
- [ ] Errors and warnings are captured

✅ **Performance**
- [ ] Dashboard loads in < 3 seconds
- [ ] Data is updated within optimizer schedule
- [ ] No timeout errors

---

## Maintenance

### Weekly Checks
- [ ] Review optimization run count and success rate
- [ ] Check for any error trends in logs
- [ ] Verify data freshness (within expected schedule)

### Monthly Tasks
- [ ] Review BigQuery storage costs
- [ ] Archive or delete old test data
- [ ] Rotate service account keys
- [ ] Update dashboard dependencies

### As Needed
- [ ] Update BigQuery schema for new features
- [ ] Optimize queries if performance degrades
- [ ] Review and update IAM permissions

---

## Additional Resources

- **Setup Guide:** [amazon_ppc_dashboard/nextjs_space/DASHBOARD_BIGQUERY_SETUP.md](amazon_ppc_dashboard/nextjs_space/DASHBOARD_BIGQUERY_SETUP.md)
- **Data Flow:** [DATA_FLOW_SUMMARY.md](DATA_FLOW_SUMMARY.md)
- **BigQuery Integration:** [BIGQUERY_INTEGRATION.md](BIGQUERY_INTEGRATION.md)
- **Dashboard Integration:** [DASHBOARD_INTEGRATION.md](DASHBOARD_INTEGRATION.md)
- **Troubleshooting:** Check `/api/setup-guide` for interactive diagnostics

---

**Last Updated:** November 2025  
**Version:** 1.0.0
