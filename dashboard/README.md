# Amazon PPC BigQuery Dashboard

A fresh, modern dashboard to display all BigQuery Amazon PPC data tables with real-time analytics and data visualization.

## Features

- **Real-time Data Display**: View all BigQuery tables with live data
- **Summary Statistics**: Key metrics displayed in cards (total runs, keywords optimized, ACOS, spend, sales)
- **Interactive Charts**: 
  - Daily performance trends (spend vs sales)
  - Top campaigns by spend
- **Table Explorer**: Browse and filter all BigQuery tables
- **Data Export**: Export table data to CSV
- **Pagination**: Handle large datasets efficiently
- **Responsive Design**: Works on desktop and mobile devices

## Tables Displayed

1. **optimization_results** - Main optimization results with summary metrics
2. **campaign_details** - Campaign-level performance data
3. **optimization_progress** - Progress tracking during optimization runs
4. **optimization_errors** - Error logs from optimization runs
5. **optimizer_run_events** - Event tracking for optimizer runs

## Installation

### Prerequisites

- Python 3.11 or higher
- Google Cloud Project with BigQuery enabled
- Service account credentials with BigQuery access

### Setup

1. Install dependencies:
```bash
cd dashboard
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export GCP_PROJECT_ID="your-project-id"
export BIGQUERY_DATASET="amazon_ppc"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
```

Or set the credentials in environment variables (same as the main optimizer):
```bash
export GCP_CREDENTIALS_JSON='{"type": "service_account", ...}'
# or
export GCP_CREDENTIALS_BASE64='base64-encoded-credentials'
```

3. Run the dashboard:
```bash
python app.py
```

The dashboard will be available at `http://localhost:8080`

## Deployment

### Local Deployment

```bash
python app.py
```

### Production Deployment with Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

### Docker Deployment

Create a `Dockerfile` in the dashboard directory:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "app:app"]
```

Build and run:
```bash
docker build -t ppc-dashboard .
docker run -p 8080:8080 -e GCP_PROJECT_ID=your-project ppc-dashboard
```

### Google Cloud Run Deployment

1. Build container:
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ppc-dashboard
```

2. Deploy to Cloud Run:
```bash
gcloud run deploy ppc-dashboard \
  --image gcr.io/YOUR_PROJECT_ID/ppc-dashboard \
  --platform managed \
  --region us-east4 \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=YOUR_PROJECT_ID,BIGQUERY_DATASET=amazon_ppc
```

## API Endpoints

### GET `/`
Main dashboard page (HTML)

### GET `/api/tables`
List all available BigQuery tables
Response: `{tables: [{table_id, num_rows, size_bytes, created, modified}]}`

### GET `/api/table/<table_name>`
Get data from a specific table
Query params: `limit`, `offset`, `days`, `order_by`
Response: `{table_name, rows, total_count, limit, offset}`

### GET `/api/table/<table_name>/schema`
Get schema information for a table
Response: `{table_name, schema, num_rows, size_bytes}`

### GET `/api/summary`
Get summary statistics
Response: `{summary: {total_runs, total_keywords_optimized, avg_acos, total_spend, total_sales, last_run}}`

### GET `/api/chart-data/<chart_type>`
Get data for charts
Chart types: `daily_performance`, `campaign_performance`, `error_distribution`
Query params: `days`
Response: `{chart_type, data}`

### GET `/health`
Health check endpoint
Response: `{status: "healthy", timestamp}`

## Configuration

Environment variables:

- `GCP_PROJECT_ID` - Google Cloud Project ID (default: `nature-way-soils`)
- `BIGQUERY_DATASET` - BigQuery dataset name (default: `amazon_ppc`)
- `PORT` - Server port (default: `8080`)
- `FLASK_DEBUG` - Enable debug mode (default: `False`, set to `True` only for local development)
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account JSON file
- `GCP_CREDENTIALS_JSON` - Service account credentials as JSON string
- `GCP_CREDENTIALS_BASE64` - Service account credentials as base64 string

## Usage

1. **View Summary**: The dashboard loads with summary cards showing key metrics
2. **View Charts**: Scroll down to see daily performance and campaign charts
3. **Browse Tables**: Click on any table in the "Available BigQuery Tables" section
4. **Filter Data**: Use the dropdowns to filter by time range and limit
5. **Navigate Pages**: Use Previous/Next buttons to browse through data
6. **Export Data**: Click "Export CSV" to download current view
7. **Refresh**: Click "Refresh" to reload table data

## Troubleshooting

### "Failed to initialize BigQuery client"
- Check that your GCP credentials are properly set
- Verify the service account has BigQuery access
- Ensure the project ID is correct

### "Error fetching table data"
- Verify the BigQuery dataset exists
- Check that tables have data
- Ensure the service account has read permissions

### Charts not displaying
- Check browser console for JavaScript errors
- Verify Chart.js is loading (CDN connection required)
- Ensure API endpoints are returning data

## Development

To modify the dashboard:

1. **Backend** (`app.py`): Add new API endpoints or modify queries
2. **Frontend** (`templates/index.html`): Modify HTML structure
3. **Styles** (`static/css/style.css`): Customize appearance
4. **JavaScript** (`static/js/app.js`): Add new features or modify behavior

## License

This dashboard is part of the Amazon PPC Optimizer project.
