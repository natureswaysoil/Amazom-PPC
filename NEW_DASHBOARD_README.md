# 🎉 New BigQuery Dashboard Available!

## Overview

A **brand new dashboard** has been created to display all Amazon PPC data from BigQuery tables. This dashboard was built from scratch with modern technologies and best practices.

📂 **Location**: `/dashboard/` directory

🔗 **Quick Start**: See [`dashboard/QUICKSTART.md`](dashboard/QUICKSTART.md)

📸 **Preview**: 

![Dashboard Screenshot](https://github.com/user-attachments/assets/269c4a50-9995-4beb-8372-b7ee28acde04)

## Why a New Dashboard?

The new dashboard provides:
- ✅ **All BigQuery tables** - Browse all 5 tables with full data access
- ✅ **Simpler deployment** - Python/Flask (no build step)
- ✅ **Better features** - Pagination, filtering, CSV export
- ✅ **Fully tested** - 11 tests, 100% passing
- ✅ **Security audited** - 0 vulnerabilities (CodeQL verified)
- ✅ **Complete docs** - 4 comprehensive guides

## Quick Comparison

| Feature | Old Dashboard | New Dashboard |
|---------|---------------|---------------|
| **Framework** | Next.js/React | Flask + Vanilla JS |
| **Setup Time** | 10-15 min | 2-5 min |
| **Build Required** | Yes (npm) | No |
| **Table Browser** | Limited | All tables |
| **Pagination** | No | Yes |
| **CSV Export** | No | Yes |
| **Tests** | None | 11 tests |
| **Security Scan** | Unknown | 0 issues |

See [`dashboard/COMPARISON.md`](dashboard/COMPARISON.md) for detailed comparison.

## Quick Start

### 1. Install & Run Locally
```bash
cd dashboard
pip install -r requirements.txt
export GCP_PROJECT_ID="your-project-id"
python app.py
```
Open http://localhost:8080

### 2. Deploy to Cloud Run
```bash
cd dashboard
./deploy-to-cloud-run.sh
```

### 3. Or Use Docker
```bash
docker build -t ppc-dashboard dashboard/
docker run -p 8080:8080 -e GCP_PROJECT_ID=your-project ppc-dashboard
```

## Features

### 📊 Dashboard Views
- **Summary Cards** - Total runs, keywords optimized, ACOS, spend, sales
- **Daily Performance Chart** - Spend vs sales trends over time
- **Top Campaigns Chart** - Bar chart of campaigns by spend
- **Table Browser** - Click any table to view detailed data

### 🗂️ All BigQuery Tables
1. **optimization_results** - Main optimization metrics
2. **campaign_details** - Campaign performance data
3. **optimization_progress** - Real-time progress tracking
4. **optimization_errors** - Error logs
5. **optimizer_run_events** - Event history

### 🎛️ Controls
- **Date Range Filter** - 7, 30, 90 days, or 1 year
- **Pagination** - 50, 100, 500, or 1000 rows per page
- **CSV Export** - Download any table data
- **Auto-refresh** - Updates every 5 minutes

## 💡 Where is the Data?

**The dashboard displays data from BigQuery tables populated by the optimizer.**

If you see "No data available" or error messages:

1. **Set up BigQuery credentials** - Dashboard needs GCP credentials to connect
2. **Run the optimizer** - Tables are populated when you run `python optimizer_core.py`
3. **Wait for results** - Data appears after the optimizer completes a run

See [`dashboard/README.md#where-is-the-data`](dashboard/README.md#where-is-the-data) for detailed troubleshooting.

## Documentation

| Document | Description |
|----------|-------------|
| [`dashboard/README.md`](dashboard/README.md) | Complete documentation with API reference |
| [`dashboard/QUICKSTART.md`](dashboard/QUICKSTART.md) | 5-minute setup guide |
| [`dashboard/IMPLEMENTATION_SUMMARY.md`](dashboard/IMPLEMENTATION_SUMMARY.md) | Implementation overview |
| [`dashboard/COMPARISON.md`](dashboard/COMPARISON.md) | Old vs new dashboard comparison |

## API Endpoints

The dashboard exposes these REST API endpoints:

- `GET /` - Main dashboard page (HTML)
- `GET /api/tables` - List all BigQuery tables
- `GET /api/table/<name>` - Get table data with pagination
- `GET /api/table/<name>/schema` - Get table schema
- `GET /api/summary` - Summary statistics
- `GET /api/chart-data/<type>` - Chart data
- `GET /health` - Health check

## Requirements

- Python 3.11+
- Google Cloud credentials with BigQuery access
- Environment variables:
  - `GCP_PROJECT_ID` - Your GCP project ID
  - `BIGQUERY_DATASET` - Dataset name (default: `amazon_ppc`)
  - Credentials (one of):
    - `GOOGLE_APPLICATION_CREDENTIALS` - Path to JSON
    - `GCP_CREDENTIALS_JSON` - JSON string
    - `GCP_CREDENTIALS_BASE64` - Base64 encoded

## Testing

Run the test suite:
```bash
cd dashboard
python -m unittest test_dashboard.py -v
```

All 11 tests should pass ✅

## Security

✅ **CodeQL Verified** - 0 vulnerabilities
✅ **Debug Mode** - Disabled by default (production-safe)
✅ **Secure Credentials** - Multiple authentication methods
✅ **Input Validation** - All endpoints protected

## Technology Stack

- **Backend**: Flask 3.0.0 (Python 3.11+)
- **Frontend**: HTML5, CSS3, JavaScript ES6+
- **Charts**: Chart.js
- **Database**: Google BigQuery
- **Testing**: Python unittest
- **Deployment**: Docker, Google Cloud Run

## Support

- 📖 Read the docs: [`dashboard/README.md`](dashboard/README.md)
- 🚀 Quick start: [`dashboard/QUICKSTART.md`](dashboard/QUICKSTART.md)
- 🔍 Compare: [`dashboard/COMPARISON.md`](dashboard/COMPARISON.md)
- 📊 Overview: [`dashboard/IMPLEMENTATION_SUMMARY.md`](dashboard/IMPLEMENTATION_SUMMARY.md)

## Status

✅ **Production Ready**
- All features implemented
- Fully tested (11/11 tests passing)
- Security audited (0 vulnerabilities)
- Completely documented
- Ready to deploy

## Next Steps

1. **Try it locally**: `cd dashboard && python app.py`
2. **Deploy to Cloud Run**: `cd dashboard && ./deploy-to-cloud-run.sh`
3. **Customize**: Modify templates/static files as needed
4. **Integrate**: Use the API endpoints in your applications

---

**The new dashboard is ready to use!** 🚀

For detailed information, see the documentation in the `dashboard/` directory.
