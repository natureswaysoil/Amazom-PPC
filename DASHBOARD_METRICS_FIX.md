# Dashboard Metrics Inflation Fix

## Problem Summary

The dashboard was showing inflated sales and spend numbers (9-10x) with ACOS of 111.75%, indicating significant duplicate counting of metrics.

## Root Cause

Amazon Advertising API uses **attribution windows** for sales metrics:
- `attributedSales7d` = Sales attributed to ad clicks over the next 7 days
- `attributedSales14d` = Sales attributed to ad clicks over the next 14 days  
- `attributedSales30d` = Sales attributed to ad clicks over the next 30 days

When data with 14-day attribution windows is stored in BigQuery:
- Row for 2024-02-01: Contains sales from 2024-02-01 through 2024-02-14 (14 days)
- Row for 2024-02-02: Contains sales from 2024-02-02 through 2024-02-15 (14 days)
- **13 days of overlap!**

The dashboard was **summing 7 days** of this data, counting most metrics **7+ times**.

## Solution Implemented

### 1. Enhanced Logging in `bigquery_client.py`

Added comprehensive logging to track data quality:

```python
# Always log performance source selection (not just in debug mode)
logger.info("Daily overview perf source: table=%s deduplication=%s lookback_attribution=%s ...")

# Detect lookback attribution in sales columns
has_lookback_attribution = any(
    indicator in sales_col.lower()
    for indicator in ["7d", "14d", "30d", "_7_", "_14_", "_30_"]
)

# Warn when lookback detected
if has_lookback:
    logger.warning(
        "⚠️ LOOKBACK ATTRIBUTION DETECTED: Sales column '%s' contains multi-day attribution window. "
        "Dashboard should NOT sum daily values - use most recent day only!"
    )

# Lower ACOS threshold from 5.0 (500%) to 1.0 (100%) to catch issues earlier
ACOS_SUSPICIOUS_HIGH = 1.0
```

### 2. API Metadata in `main.py`

Added metadata to API responses to inform consumers about data structure:

```python
metadata = {
    'has_lookback_attribution': True,
    'lookback_warning': 'Daily metrics contain multi-day attribution windows. Use latest day for totals, do not sum across days.',
}

return {
    'status': 'success',
    'recent_results': recent_results,
    'daily': daily,
    'metadata': metadata,  # NEW
}, 200
```

### 3. Dashboard Logic Fix in `page.tsx`

Updated metric calculation to handle lookback attribution correctly:

```typescript
// OLD CODE (Incorrect - causes inflation):
const totalSpend = summary.reduce((sum, s) => sum + s.total_spend, 0);
const totalSales = summary.reduce((sum, s) => sum + s.total_sales, 0);

// NEW CODE (Correct):
let totalSpend: number;
let totalSales: number;

if (dataMetadata?.has_lookback_attribution && summary.length > 0) {
    // Use most recent day only - it already contains the lookback window
    const latestDay = summary[0]; // summary is sorted by date descending
    totalSpend = latestDay.total_spend;
    totalSales = latestDay.total_sales;
} else {
    // No lookback attribution - safe to sum daily values
    totalSpend = summary.reduce((sum, s) => sum + s.total_spend, 0);
    totalSales = summary.reduce((sum, s) => sum + s.total_sales, 0);
}
```

### 4. Visual Indicators

Added UI feedback for data quality:

```typescript
// Color-coded ACOS display
<div style={{
    color: avgAcos > 1.0 ? '#f44336' : avgAcos > 0.7 ? '#ff9800' : '#4caf50'
}}>
    {formatPercent(avgAcos)}
</div>

// Warning banner when ACOS > 100%
{avgAcos > 1.0 && (
    <div style={{ color: '#f44336' }}>
        ⚠️ ACOS > 100% - Spending more than revenue generated
    </div>
)}

// Info banner explaining attribution windows
{dataMetadata?.has_lookback_attribution && (
    <div style={{ background: '#e3f2fd' }}>
        ℹ️ Metrics use Amazon's multi-day attribution windows.
        Displayed totals represent the most recent attribution period.
    </div>
)}
```

### 5. Diagnostic Script

Created `scripts/verify_deduplication.py` to diagnose data quality issues:

- Checks campaign_details table structure
- Analyzes lookback window configuration
- Compares deduplicated vs non-deduplicated metrics
- Identifies overlapping windows
- Calculates metrics both ways (sum vs latest only)
- Provides specific recommendations

Usage:
```bash
python scripts/verify_deduplication.py
```

## Expected Behavior After Fix

### Before Fix (Incorrect)
- Dashboard sums 7 days of lookback data
- ACOS: 111.75% (inflated due to duplicate counting)
- Spend: $16,053.54 (9-10x inflated)
- Sales: $18,343.52 (9-10x inflated)

### After Fix (Correct)
- Dashboard uses latest day's lookback data only
- ACOS: 20-50% (realistic range)
- Spend: ~$1,600-$2,000 (actual 14-day window)
- Sales: ~$4,000-$8,000 (actual 14-day window)

## Testing Checklist

- [x] Python syntax validation passed
- [x] TypeScript syntax validation passed
- [ ] Run diagnostic script with real data
- [ ] Verify ACOS shows realistic values (20-50%)
- [ ] Confirm metrics match Amazon Ads console
- [ ] Test with multiple daily runs
- [ ] Verify visual indicators appear correctly

## Files Modified

1. **bigquery_client.py** (506 lines changed)
   - Enhanced logging for performance source selection
   - Added lookback attribution detection
   - Lowered ACOS threshold to 1.0
   - Added warnings for data quality issues

2. **main.py** (18 lines changed)
   - Added metadata to API responses
   - Included lookback attribution flags

3. **amazon_ppc_dashboard/nextjs_space/app/page.tsx** (94 lines changed)
   - Added metadata state
   - Fixed metric calculation logic
   - Added visual ACOS indicators
   - Added info/warning banners

4. **scripts/verify_deduplication.py** (NEW - 446 lines)
   - Comprehensive diagnostic tool
   - Identifies inflation sources
   - Provides recommendations

## Background: Amazon Attribution Windows

Amazon's attribution windows track which ads led to which sales over time:

- **Click Attribution**: When someone clicks an ad, Amazon tracks purchases for N days
- **7d Attribution**: Sales within 7 days of ad click
- **14d Attribution**: Sales within 14 days of ad click (most common)
- **30d Attribution**: Sales within 30 days of ad click

This is why:
1. You can't simply sum daily attributed sales (they overlap)
2. The most recent day's data represents the latest N-day window
3. Historical comparison requires consistent window sizes

## References

- Amazon Ads API Documentation: [Reporting API](https://advertising.amazon.com/API/docs/en-us/reference/2/reports)
- PR #137: Previous deduplication implementation
- Issue: Dashboard showing 111.75% ACOS with inflated metrics
