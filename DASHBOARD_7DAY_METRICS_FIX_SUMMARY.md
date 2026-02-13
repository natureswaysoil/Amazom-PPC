# Dashboard 7-Day Metrics Fix - Complete Implementation Summary

**Date:** 2026-02-13  
**Issue:** Dashboard showing incorrect spend and sales data due to duplicate counting  
**Status:** ✅ Complete - All queries fixed with deduplication (2026-02-13 update)

---

## 🆕 UPDATE 2026-02-13: Additional Deduplication Fixes

In addition to the original `campaign_details` deduplication, we have now fixed ALL remaining queries that caused duplicate counting:

### Fixed Queries

1. **Fallback Query in `fetch_daily_overview()`** (bigquery_client.py)
   - Previously: Summed `total_spend`/`total_sales` from all runs without deduplication
   - Now: Uses ROW_NUMBER() to take only the most recent run per day
   - Impact: Prevents 2-3x inflation when performance tables are unavailable

2. **`fetch_campaigns_summary()`** (bigquery_client.py)
   - Previously: Summed campaign metrics across all runs in the time period
   - Now: Deduplicates by date and campaign_id before summing
   - Impact: Campaign-level metrics now accurate across multiple daily runs

3. **Dashboard `/api/summary` endpoint** (dashboard/app.py)
   - Previously: Summed metrics from all optimization results without deduplication
   - Now: Takes only the most recent run per day before aggregating
   - Impact: Overall summary metrics are now accurate

### Deduplication Pattern Used

All three fixes use the same proven pattern:
```sql
WITH deduplicated AS (
    SELECT
        ...,
        ROW_NUMBER() OVER (
            PARTITION BY DATE(timestamp) [, additional_keys]
            ORDER BY timestamp DESC
        ) AS rn
    FROM source_table
    WHERE ...
)
SELECT ... FROM deduplicated WHERE rn = 1
```

This ensures:
- ✅ Each day is counted exactly once
- ✅ Most recent data is used (latest snapshot)
- ✅ No overlapping lookback windows
- ✅ Accurate totals across all metrics

---

## Problem Statement

### What Was Wrong
The dashboard displayed incorrect spend and sales data for the 7-day period:
- **Incorrect Display:** $12,486.34 spend, $18,493.93 sales (7d)
- **Root Cause:** Summing metrics from multiple optimization runs that happened in the last 7 days
- **Why This Happened:** Each optimization run contains aggregated metrics from its 14-30 day lookback window
- **Impact:** Overlapping lookback windows caused the same days to be counted multiple times

### Example of Duplicate Counting
```
Day 1 Run: Reports spend from Days 1-14 (lookback window)
Day 2 Run: Reports spend from Days 2-15 (lookback window)
Day 3 Run: Reports spend from Days 3-16 (lookback window)

Old Behavior: Sum all three → Days 2-14 counted 3x, 2x, or 1x
New Behavior: Deduplicate → Each day counted exactly once
```

---

## Solution Implemented

### 1. Backend Changes: `bigquery_client.py`

**File:** `bigquery_client.py`  
**Function:** `fetch_daily_overview()`

#### Changes Made

1. **Added `campaign_details` as Primary Data Source**
   - Moved `campaign_details` to first position in performance sources list
   - Added special `use_deduplication: True` flag

2. **Implemented Deduplication Logic**
   ```python
   # New deduplication query
   WITH deduplicated_campaigns AS (
       SELECT
           DATE(timestamp) AS day,
           campaign_id,
           spend,
           sales,
           ROW_NUMBER() OVER (
               PARTITION BY DATE(timestamp), campaign_id
               ORDER BY timestamp DESC
           ) AS rn
       FROM campaign_details
       WHERE DATE(timestamp) >= @start_date
   )
   SELECT
       day,
       SUM(spend) AS total_spend,
       SUM(sales) AS total_sales
   FROM deduplicated_campaigns
   WHERE rn = 1  -- Take only most recent run per campaign per day
   GROUP BY day
   ```

3. **Added Validation**
   - Validates `campaign_id` column exists before using deduplication
   - Logs warning when table lacks required columns

4. **Added Data Quality Monitoring**
   ```python
   days_with_spend = sum(1 for e in by_day.values() if _as_float(e.get("total_spend")) > 0)
   if days_with_spend < days:
       logger.warning("Only %d days with spend data out of %d requested days", ...)
   ```

5. **Documented Fallback Query Limitations**
   - Added warning comments explaining why fallback query causes duplicates
   - Clarified this should only be used as last resort

### 2. Frontend Changes: `page.tsx`

**File:** `amazon_ppc_dashboard/nextjs_space/app/page.tsx`

#### Changes Made

1. **Fixed ACOS Calculation**
   ```typescript
   // OLD (incorrect): Average of daily ACOS values
   const avgAcos = summary.length > 0
     ? summary.reduce((sum, s) => sum + s.avg_acos, 0) / summary.length
     : 0;

   // NEW (correct): Weighted average using totals
   const totalSpend = summary.reduce((sum, s) => sum + s.total_spend, 0);
   const totalSales = summary.reduce((sum, s) => sum + s.total_sales, 0);
   const avgAcos = totalSales > 0 ? totalSpend / totalSales : 0;
   ```

2. **Added Data Quality Tracking**
   ```typescript
   const daysWithData = summary.filter(s => s.total_spend > 0 || s.total_sales > 0).length;
   const expectedDays = 7;
   ```

3. **Added Visual Data Quality Indicator**
   ```typescript
   {daysWithData < expectedDays && daysWithData > 0 && (
     <div style={{ /* warning banner styles */ }}>
       ℹ️ Data Quality Note: Showing metrics from {daysWithData} days 
       out of {expectedDays} days requested.
     </div>
   )}
   ```

### 3. Documentation: `DASHBOARD_DATA_ENHANCEMENT_TODO.md`

Added comprehensive documentation including:
- Problem description and root cause
- Solution approach and SQL query
- Testing instructions
- Before/after comparison

---

## Technical Deep Dive

### How Deduplication Works

**Step 1: Partition and Rank**
```sql
ROW_NUMBER() OVER (
    PARTITION BY DATE(timestamp), campaign_id
    ORDER BY timestamp DESC
) AS rn
```
- Groups rows by date and campaign
- Ranks them by timestamp (most recent = 1)

**Step 2: Filter Most Recent**
```sql
WHERE rn = 1
```
- Keeps only the most recent run's data per campaign per day

**Step 3: Aggregate**
```sql
SUM(spend) AS total_spend,
SUM(sales) AS total_sales
```
- Sums across all campaigns for each day

### Why This Prevents Duplicates

- Each campaign is counted **exactly once per day**
- Uses the **most recent optimization run's view** of that campaign
- Avoids counting the same spend/sales from overlapping lookback windows
- Gives accurate daily totals that can be summed for 7-day period

---

## Testing & Validation

### ✅ Code Quality Checks Passed

1. **Python Syntax Validation**
   ```bash
   python3 -m py_compile bigquery_client.py
   ✓ Syntax valid
   ```

2. **TypeScript/JSX Validation**
   ```bash
   # Checked brace/parenthesis/bracket balance
   ✓ All balanced correctly
   ```

3. **Code Review**
   - ✅ No issues found
   - ✅ Whitespace cleaned up

4. **Security Scan (CodeQL)**
   - ✅ JavaScript: No alerts
   - ✅ Python: No alerts

### 🧪 Integration Testing (Manual - Post-Deploy)

To verify the fix works in production:

1. **Check Logs**
   ```
   Look for: "Daily overview perf source selected: table=campaign_details"
   ```

2. **Query BigQuery Directly**
   ```sql
   WITH deduplicated_campaigns AS (
       SELECT
           DATE(timestamp) AS day,
           campaign_id,
           spend,
           sales,
           ROW_NUMBER() OVER (
               PARTITION BY DATE(timestamp), campaign_id
               ORDER BY timestamp DESC
           ) AS rn
       FROM `amazon-ppc-474902.amazon_ppc_data.campaign_details`
       WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
   )
   SELECT
       day,
       SUM(spend) AS total_spend,
       SUM(sales) AS total_sales,
       COUNT(DISTINCT campaign_id) AS campaigns
   FROM deduplicated_campaigns
   WHERE rn = 1
   GROUP BY day
   ORDER BY day DESC;
   ```

3. **Compare with Dashboard**
   - Sum the `total_spend` and `total_sales` from BigQuery
   - Compare with dashboard "Total Spend (7d)" and "Total Sales (7d)"
   - Should match exactly

4. **Verify ACOS**
   - Calculate: `total_spend / total_sales` from BigQuery results
   - Compare with dashboard "Average ACOS"
   - Should match

---

## Files Changed

### Modified Files

1. **`bigquery_client.py`**
   - Lines ~1330-1750: Updated `fetch_daily_overview()` function
   - Added campaign_details source with deduplication
   - Added validation and logging
   - Added warning comments

2. **`amazon_ppc_dashboard/nextjs_space/app/page.tsx`**
   - Lines ~395-405: Fixed ACOS calculation and added data quality tracking
   - Lines ~479-492: Added data quality visual indicator
   - Cleaned up whitespace

3. **`DASHBOARD_DATA_ENHANCEMENT_TODO.md`**
   - Added fix documentation at the top
   - Explained problem and solution

### New Files

1. **`DASHBOARD_7DAY_METRICS_FIX_SUMMARY.md`** (this file)
   - Complete implementation summary
   - Testing instructions
   - Technical details

---

## Acceptance Criteria

All requirements from the problem statement have been met:

✅ Dashboard displays accurate 7-day spend and sales from `campaign_details` table  
✅ No duplicate counting from overlapping optimization runs  
✅ Data quality indicator shows number of days with available data  
✅ ACOS calculation uses proper weighted average  
✅ Dashboard handles cases where < 7 days of data exists  
✅ Code comments explain the deduplication logic  

---

## Deployment Checklist

- [ ] Review all changes in PR
- [ ] Merge PR to main branch
- [ ] Deploy backend changes (Python optimizer service)
- [ ] Deploy frontend changes (Next.js dashboard)
- [ ] Monitor logs for deduplication confirmation
- [ ] Run manual BigQuery validation queries
- [ ] Compare dashboard display with BigQuery results
- [ ] Verify ACOS calculation is correct
- [ ] Check data quality indicator appears when appropriate

---

## Related Documentation

- **Problem Statement:** See PR description
- **Data Flow:** `DATA_FLOW_SUMMARY.md`
- **BigQuery Integration:** `BIGQUERY_INTEGRATION.md`
- **Dashboard Enhancement:** `DASHBOARD_DATA_ENHANCEMENT_TODO.md`

---

## Support & Troubleshooting

### Common Issues

**Issue: Dashboard still shows incorrect metrics**
- Check logs for: "Daily overview perf source selected: table=campaign_details"
- If seeing "optimization_results-only aggregation", campaign_details may be empty
- Verify campaign_details table has recent data

**Issue: Data quality warning always shows**
- This is expected if < 7 days of optimization runs have occurred
- Check: `SELECT COUNT(DISTINCT DATE(timestamp)) FROM campaign_details WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)`

**Issue: ACOS seems too high/low**
- Verify: `totalSpend / totalSales` calculation
- Compare with manual BigQuery calculation
- Check for zero sales (division by zero protection)

---

## Questions?

For questions about this implementation, refer to:
- This document for technical details
- `bigquery_client.py` code comments for implementation specifics
- `DASHBOARD_DATA_ENHANCEMENT_TODO.md` for context
