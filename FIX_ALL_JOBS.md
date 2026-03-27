# COMPLETE FIX FOR AMAZON PPC SYSTEM

## THE PROBLEM

Your Cloud Scheduler jobs run successfully BUT:
- **keyword_performance table exists but has NO sales data**
- **Optimizer finds 0 keywords because sales field is missing/null**
- **Jobs process 2000 keywords blindly without performance filtering**

## THE ROOT CAUSE

The `bigquery_client.fetch_top_performing_keywords()` method:
1. Queries `keyword_performance` table
2. Expects: `keyword_id`, `clicks`, `cost`, **`sales`**, `orders`
3. Finds table but sales = NULL for all rows
4. Returns empty list → optimizer can't filter by performance

## THE COMPLETE FIX

### Step 1: Create Data Sync Job (REQUIRED)

You need a Cloud Run job that syncs Amazon Ads data to BigQuery.

**File: `jobs/sync/amazon_to_bigquery_sync.py`** (CREATE THIS)
```python
#!/usr/bin/env python3
"""
Amazon Ads → BigQuery Data Sync
Populates keyword_performance table with sales data
"""

import os
import logging
from datetime import datetime, timedelta
from google.cloud import bigquery
from services.amazon_ads_client import AmazonAdsClient

logger = logging.getLogger(__name__)

def sync_keyword_performance(days=30):
    """Sync keyword performance from Amazon Ads to BigQuery"""
    
    ads = AmazonAdsClient()
    bq = bigquery.Client(project=os.getenv('GCP_PROJECT', 'amazon-ppc-bid-optimizer'))
    
    dataset_id = "amazon_ppc"
    table_id = f"{dataset_id}.keyword_performance"
    
    # Create table if needed
    schema = [
        bigquery.SchemaField("date", "DATE"),
        bigquery.SchemaField("keywordId", "INT64"),
        bigquery.SchemaField("keyword_text", "STRING"),
        bigquery.SchemaField("campaignId", "INT64"),
        bigquery.SchemaField("adGroupId", "INT64"),
        bigquery.SchemaField("matchType", "STRING"),
        bigquery.SchemaField("clicks", "INT64"),
        bigquery.SchemaField("cost", "FLOAT64"),
        bigquery.SchemaField("sales", "FLOAT64"),  # THIS IS THE MISSING FIELD!
        bigquery.SchemaField("orders", "INT64"),
        bigquery.SchemaField("impressions", "INT64"),
    ]
    
    try:
        table = bq.get_table(table_id)
        logger.info(f"Table {table_id} exists")
    except:
        table = bigquery.Table(table_id, schema=schema)
        table = bq.create_table(table)
        logger.info(f"Created table {table_id}")
    
    # Get keyword performance from Amazon Ads API
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    # Use Amazon Ads reporting API to get keyword performance
    report = ads.create_keyword_performance_report(start_date, end_date)
    
    # Insert into BigQuery
    rows_to_insert = []
    for row in report:
        rows_to_insert.append({
            "date": row['date'],
            "keywordId": int(row['keywordId']),
            "keyword_text": row.get('keywordText', ''),
            "campaignId": int(row['campaignId']),
            "adGroupId": int(row['adGroupId']),
            "matchType": row.get('matchType', 'EXACT'),
            "clicks": int(row.get('clicks', 0)),
            "cost": float(row.get('cost', 0)),
            "sales": float(row.get('attributedSales14d', 0)),  # CRITICAL!
            "orders": int(row.get('attributedConversions14d', 0)),
            "impressions": int(row.get('impressions', 0)),
        })
    
    if rows_to_insert:
        errors = bq.insert_rows_json(table_id, rows_to_insert)
        if errors:
            logger.error(f"Errors inserting rows: {errors}")
        else:
            logger.info(f"✅ Inserted {len(rows_to_insert)} rows")

if __name__ == "__main__":
    sync_keyword_performance()
```

### Step 2: Deploy the Data Sync Job
```bash
# Build and deploy to Cloud Run
gcloud run jobs create keyword-performance-sync \
  --image=gcr.io/amazon-ppc-bid-optimizer/keyword-sync \
  --region=us-central1 \
  --project=amazon-ppc-bid-optimizer \
  --set-secrets=AMAZON_CLIENT_ID=Amazon_Ads_Client_identifier:latest,AMAZON_CLIENT_SECRET=Amazon_Ads_Client_secret:latest,AMAZON_REFRESH_TOKEN=Amazon_Ads_Refresh_Token:latest

# Schedule it to run daily at 2 AM
gcloud scheduler jobs create http keyword-performance-sync-daily \
  --location=us-central1 \
  --schedule="0 2 * * *" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/amazon-ppc-bid-optimizer/jobs/keyword-performance-sync:run" \
  --http-method=POST \
  --oauth-service-account-email=amazon-ppc-bid-optimizer@appspot.gserviceaccount.com
```

### Step 3: Fix optimizer_core.py (OPTIONAL - BETTER ERROR HANDLING)

Add a fallback when sales data is missing:
```python
# In optimizer_core.py, around line 3590
def _load_keyword_performance(self) -> List[Dict]:
    """Load keyword performance data from BigQuery."""
    if not self.bigquery_client:
        return []
    
    try:
        keywords = self.bigquery_client.fetch_top_performing_keywords(
            days=30, limit=500
        )
        
        if not keywords:
            logger.warning("No keyword performance data found")
            return []
        
        sample = keywords[0]
        sales_missing = "sales" not in sample or sample.get("sales") is None
        
        if sales_missing:
            logger.warning(
                "⚠️  keyword_performance table missing sales data! "
                "Run the keyword-performance-sync job to populate it."
            )
            # INSTEAD OF RETURNING EMPTY, TRY ALTERNATIVE SOURCE
            return self._load_keywords_from_amazon_ads_api()
        
        return keywords
        
    except Exception as exc:
        logger.error(f"Failed to load keyword performance: {exc}")
        return []

def _load_keywords_from_amazon_ads_api(self) -> List[Dict]:
    """Fallback: Get keywords directly from Amazon Ads API"""
    logger.info("Fetching keywords directly from Amazon Ads API...")
    # Implementation here
    pass
```

## VERIFICATION

After deploying, verify the fix:
```bash
# 1. Run the sync job manually first time
gcloud run jobs execute keyword-performance-sync \
  --region=us-central1 \
  --project=amazon-ppc-bid-optimizer

# 2. Check BigQuery table has data
bq query --project_id=amazon-ppc-bid-optimizer \
  "SELECT COUNT(*) as total, SUM(sales) as total_sales 
   FROM amazon_ppc.keyword_performance 
   WHERE sales > 0"

# 3. Check optimizer logs
gcloud logging read "resource.type=cloud_run_job 
  AND resource.labels.job_name=suggested-bid-optimizer" \
  --limit=20 \
  --project=amazon-ppc-bid-optimizer

# Should now show: "Loaded 500 keywords for optimization" (NOT 0!)
```

## SUMMARY

**Before Fix:**
- ❌ keyword_performance table exists but sales = NULL
- ❌ Optimizer finds 0 keywords
- ❌ Processes all 2000 keywords blindly

**After Fix:**
- ✅ Data sync job populates sales data daily
- ✅ Optimizer finds 500 top-performing keywords
- ✅ Filters by ACOS and performance metrics
- ✅ Only optimizes winning keywords

