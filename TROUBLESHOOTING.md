# Troubleshooting Guide

## Common Issues

### Inflated Sales and Spend Data in Dashboard

#### Problem
The dashboard shows significantly inflated sales and spend numbers (e.g., 5-10x higher than actual Amazon Seller Central data).

**Symptoms:**
- Dashboard shows: Total Spend (7d): $14,867.53, Total Sales (7d): $16,994.00
- Amazon Seller Central shows: Total Sales (7d): $1,849.52
- ACOS appears suspiciously high (> 5.0) or low (< 0.01)

#### Root Cause
Data is being counted multiple times across different BigQuery tables:
- Campaign-level data (`campaign_performance`, `sp_campaign_metrics`, `campaign_details`)
- Keyword-level data (`keyword_performance`) 
- Search-term data (`search_term_reports`)

When these tables are aggregated naively (summed together), the same sales/spend metrics get counted multiple times, leading to massive inflation.

#### Solution

**1. Run the Diagnostic Script**

First, diagnose which tables contain data and identify duplication:

```bash
python scripts/diagnose_sales_data.py \
  --project amazon-ppc-474902 \
  --dataset amazon_ppc_data \
  --days 7
```

The script will:
- Check all performance tables for data
- Show spend/sales totals per table
- Calculate inflation ratios
- Recommend which table to use as primary source

**Example Output:**
```
📊 campaign_performance
   ├─ Rows: 245
   ├─ Unique Campaigns: 15
   ├─ Total Spend: $1,847.23
   └─ Total Sales: $1,849.52

📊 keyword_performance
   ├─ Rows: 1,234
   ├─ Total Spend: $12,935.61
   └─ Total Sales: $13,146.08

⚠️ WARNING: Multiple tables contain data!
   If summed naively: $14,782.84 spend, $14,995.60 sales
   Using campaign_performance alone: $1,847.23 spend, $1,849.52 sales
   
   ⚠️ INFLATION RATIO: 8.0x
```

**2. Configure the Correct Data Source**

Add to your `config.json` or `sample_config.yaml`:

```yaml
bigquery:
  performance_dataset_id: amazon_ppc_data
  preferred_performance_table: campaign_performance  # Use campaign-level data
```

Or set environment variable:
```bash
export BQ_PREFERRED_PERFORMANCE_TABLE=campaign_performance
```

**Priority Order (default):**
1. `campaign_performance` (Amazon Ads API - RECOMMENDED)
2. `sp_campaign_metrics` (Sponsored Products metrics)
3. `campaign_details` (Optimizer-written data)

**3. Verify the Fix**

Enable debug logging to see which table is being used:
```bash
export PPC_DEBUG_BIGQUERY=true
```

Check logs for:
```
Daily overview perf source selected: table=campaign_performance ...
Daily overview summary: spend=$1847.23 sales=$1849.52 acos=1.00 days=7 source=table=campaign_performance
```

**4. Monitor for Warnings**

The system now includes automatic ACOS sanity checks:
- **ACOS > 5.0**: Likely data duplication (multiple tables being counted)
- **ACOS < 0.01**: Missing spend data or inflated sales

Watch for warnings like:
```
⚠️ Suspicious ACOS=8.04 (spend=$14,867.53, sales=$1,849.52).
ACOS > 5.0 may indicate duplicate counting across tables.
Consider running scripts/diagnose_sales_data.py to investigate.
```

#### Why This Happens

**Campaign-level vs Keyword-level Data:**
- `campaign_performance`: 1 row per campaign per day
- `keyword_performance`: Many rows per campaign per day (one per keyword)

If you have a campaign with 50 keywords:
- Campaign-level: $100 spend (counted once)
- Keyword-level: $100 spend counted 50 times = $5,000 total!

**The Fix:**
The optimizer now:
1. Uses ONLY campaign-level tables for dashboard totals
2. Applies deduplication (ROW_NUMBER by date + campaign_id)
3. Validates ACOS to detect issues early
4. Provides clear logging about data sources

#### Best Practices

1. **Always use campaign-level tables** for dashboard metrics:
   - ✅ `campaign_performance`
   - ✅ `sp_campaign_metrics`
   - ✅ `campaign_details`
   - ❌ `keyword_performance` (keyword-level - causes duplication)
   - ❌ `search_term_reports` (search-term-level - causes duplication)

2. **Set performance dataset explicitly:**
   ```yaml
   bigquery:
     dataset_id: amazon_ppc_data        # Optimizer tables
     performance_dataset_id: ppc_reports # Performance tables (if separate)
   ```

3. **Enable debug logging** when troubleshooting:
   ```bash
   export PPC_DEBUG_BIGQUERY=true
   ```

4. **Run diagnostics regularly** after data pipeline changes:
   ```bash
   python scripts/diagnose_sales_data.py --project PROJECT_ID --dataset DATASET_ID
   ```

#### Additional Resources

- **Configuration Guide**: See `sample_config.yaml` for all BigQuery options
- **API Documentation**: `BIGQUERY_INTEGRATION.md`
- **Data Flow**: `DATA_FLOW_SUMMARY.md`

---

### UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b

#### Problem

When syncing placement performance or downloading reports, you may encounter:

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8b in position 1: invalid start byte
```

**Symptoms:**
- Error occurs during API response processing
- Byte sequence `0x1f 0x8b` appears in error messages
- Happens intermittently with Amazon Ads API

#### Root Cause

The byte sequence `0x1f 0x8b` is the **gzip magic number**, indicating that the Amazon Ads API returned a gzip-compressed response instead of plain UTF-8 text. This can happen even when the `Content-Encoding` header is not set.

The code tries to decode the response as UTF-8:
```python
content = data_bytes.decode('utf-8')  # ❌ Fails on gzip data
```

#### Solution

Use the `decode_api_response()` utility function from `amazon_api_utils.py`:

```python
from amazon_api_utils import decode_api_response

# Instead of:
# content = data_bytes.decode('utf-8')

# Use:
content = decode_api_response(data_bytes)
```

This function:
1. Detects gzip magic number (`0x1f 0x8b`)
2. Decompresses gzip data if present
3. Falls back to plain UTF-8 decoding for non-compressed data
4. Handles both cases automatically

**Example Integration:**

```python
import requests
from amazon_api_utils import decode_api_response

response = requests.get(api_url, headers=headers)
response.raise_for_status()

# Safely decode response (works with both plain and gzip)
content = decode_api_response(response.content)

# Now parse as JSON, CSV, etc.
data = json.loads(content)
```

#### Testing

The utility is fully tested with:
- ✅ Plain UTF-8 responses
- ✅ Gzip-compressed responses
- ✅ Empty responses
- ✅ Unicode characters
- ✅ Large responses
- ❌ Invalid gzip data (raises `gzip.BadGzipFile`)
- ❌ Invalid UTF-8 (raises `UnicodeDecodeError`)

Run tests:
```bash
python test_amazon_api_utils.py
```

#### For Container Deployments

If the error occurs in `/app/jobs/data_sync/amazon_ads_sync.py` (inside Docker container):

1. Ensure `amazon_api_utils.py` is included in your Docker image
2. Update the import in `amazon_ads_sync.py`:
   ```python
   from amazon_api_utils import decode_api_response
   ```
3. Replace all `data_bytes.decode('utf-8')` calls with `decode_api_response(data_bytes)`

#### Related Files

- **Utility Module**: `amazon_api_utils.py`
- **Tests**: `test_amazon_api_utils.py`
- **Example Usage**: `optimizer_core.py` (lines 1766-1780)

---

## Other Common Issues

### Dashboard Shows All Zeros

If the dashboard shows zero for all metrics:

1. **Check table existence:**
   ```bash
   python scripts/find_bigquery_perf_tables.py --project PROJECT_ID --sample
   ```

2. **Verify dataset permissions:**
   - Service account needs `BigQuery Data Viewer` role
   - Service account needs `BigQuery Job User` role

3. **Check performance dataset configuration:**
   ```bash
   # If performance tables are in a different dataset
   export BQ_PERFORMANCE_DATASET_ID=your_perf_dataset_id
   ```

4. **Enable debug mode:**
   ```bash
   export PPC_DEBUG_BIGQUERY=true
   ```

### Credentials Issues

**Error: "Failed to initialize BigQuery client"**

1. Check environment variables:
   ```bash
   echo $GOOGLE_APPLICATION_CREDENTIALS
   echo $GCP_SERVICE_ACCOUNT_KEY
   ```

2. Validate service account JSON:
   ```bash
   python -c "import json; print(json.load(open('key.json'))['project_id'])"
   ```

3. Test BigQuery access:
   ```bash
   gcloud auth activate-service-account --key-file=key.json
   bq ls --project_id=PROJECT_ID
   ```

### Permission Errors

**Error: "Access Denied: BigQuery BigQuery: Permission denied"**

Required IAM roles:
- `roles/bigquery.dataViewer` (read tables)
- `roles/bigquery.jobUser` (run queries)
- `roles/bigquery.dataEditor` (write results - optional)

Grant permissions:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.jobUser"
```

---

## Getting Help

If you're still experiencing issues:

1. **Enable debug mode** and collect logs:
   ```bash
   export PPC_DEBUG_BIGQUERY=true
   export LOG_LEVEL=DEBUG
   ```

2. **Run diagnostic script** with verbose output:
   ```bash
   python scripts/diagnose_sales_data.py \
     --project PROJECT_ID \
     --dataset DATASET_ID \
     --verbose
   ```

3. **Check Cloud Run/Function logs:**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision" --limit 50
   ```

4. **Open an issue** with:
   - Diagnostic script output
   - Relevant log snippets (with sensitive data redacted)
   - Expected vs actual metrics
   - Configuration (with credentials redacted)
