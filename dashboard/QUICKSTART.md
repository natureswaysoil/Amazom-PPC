# Dashboard Quick Start Guide

Get the Amazon PPC BigQuery Dashboard running in under 5 minutes.

## 🚀 Quick Local Setup

### 1. Install Dependencies

```bash
cd dashboard
pip install -r requirements.txt
```

### 2. Set Environment Variables

Choose one of these methods:

**Option A: Environment File**
```bash
cp .env.example .env
# Edit .env with your values
export $(cat .env | xargs)
```

**Option B: Direct Export**
```bash
export GCP_PROJECT_ID="your-project-id"
export BIGQUERY_DATASET="amazon_ppc"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
```

**Option C: Use Existing Credentials**
```bash
export GCP_PROJECT_ID="your-project-id"
export BIGQUERY_DATASET="amazon_ppc"
# Credentials will be loaded from GCP_CREDENTIALS_JSON or GCP_CREDENTIALS_BASE64
```

### 3. Run the Dashboard

```bash
# For local development with debug mode (never use in production)
FLASK_DEBUG=True python app.py

# For production-like testing (recommended)
python app.py
```

Open your browser to `http://localhost:8080`

**Security Note**: Debug mode is disabled by default for security. Only enable it for local development.

## 🐳 Docker Quick Start

### Build and Run

```bash
cd dashboard

# Build the image
docker build -t ppc-dashboard .

# Run the container
docker run -p 8080:8080 \
  -e GCP_PROJECT_ID="your-project-id" \
  -e BIGQUERY_DATASET="amazon_ppc" \
  -e GCP_CREDENTIALS_JSON='{"type":"service_account",...}' \
  ppc-dashboard
```

Open `http://localhost:8080`

## ☁️ Cloud Run Quick Deploy

### Prerequisites
- gcloud CLI installed and configured
- Google Cloud project with billing enabled
- BigQuery API enabled

### Deploy

```bash
cd dashboard
./deploy-to-cloud-run.sh
```

The script will:
1. Build a container image
2. Push to Google Container Registry
3. Deploy to Cloud Run
4. Output the public URL

**That's it!** Your dashboard will be live.

## 📊 What You'll See

### Summary Cards
- Total optimization runs
- Keywords optimized
- Average ACOS
- Total spend and sales

### Charts
- Daily performance trends (spend vs sales)
- Top campaigns by spend

### Table Browser
Click any table to view its data:
- **optimization_results** - Main optimization metrics
- **campaign_details** - Campaign performance
- **optimization_progress** - Run progress tracking
- **optimization_errors** - Error logs
- **optimizer_run_events** - Event history

### Features
- **Filter by date range** - Last 7, 30, 90 days, or 1 year
- **Pagination** - Browse large datasets
- **Export to CSV** - Download any table
- **Auto-refresh** - Updates every 5 minutes

## 🔧 Troubleshooting

### No data showing?
```bash
# Verify BigQuery has data
bq query --nouse_legacy_sql \
  "SELECT COUNT(*) FROM \`your-project.amazon_ppc.optimization_results\`"
```

### Authentication errors?
```bash
# Check credentials are set
echo $GOOGLE_APPLICATION_CREDENTIALS
# or
echo $GCP_CREDENTIALS_JSON | jq .project_id

# Test BigQuery access
python -c "from google.cloud import bigquery; print(bigquery.Client().project)"
```

### Port already in use?
```bash
# Use a different port
PORT=8081 python app.py
```

## 📝 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GCP_PROJECT_ID` | No | `nature-way-soils` | Google Cloud Project ID |
| `BIGQUERY_DATASET` | No | `amazon_ppc` | BigQuery dataset name |
| `PORT` | No | `8080` | Server port |
| `GOOGLE_APPLICATION_CREDENTIALS` | No | - | Path to service account JSON |
| `GCP_CREDENTIALS_JSON` | No | - | Service account JSON string |
| `GCP_CREDENTIALS_BASE64` | No | - | Base64 encoded credentials |

**Note:** Only one credential method is needed. The app will try them in order.

## 🎯 Next Steps

- **Customize**: Edit `templates/index.html` to modify the UI
- **Add Charts**: Modify `static/js/app.js` to add more visualizations
- **New Endpoints**: Add routes in `app.py` for custom queries
- **Styling**: Update `static/css/style.css` for different colors/layouts

## 💡 Tips

- The dashboard auto-refreshes every 5 minutes
- Use the date range filter to control query performance
- Export data to CSV for offline analysis
- Check the browser console for any JavaScript errors
- View server logs for backend issues

## 📚 Documentation

- [Full README](README.md) - Comprehensive documentation
- [API Reference](README.md#api-endpoints) - All API endpoints
- [Deployment Guide](README.md#deployment) - Production deployment

## 🆘 Need Help?

Check the logs:
```bash
# Local
python app.py  # See console output

# Docker
docker logs <container-id>

# Cloud Run
gcloud logs tail --service=ppc-dashboard
```

Common issues:
- **Blank page**: Check browser console for errors
- **500 errors**: Verify BigQuery credentials
- **No tables**: Ensure dataset exists and has tables
- **Slow loading**: Check BigQuery query limits

---

**You're all set!** The dashboard is ready to visualize your Amazon PPC data. 🎉
