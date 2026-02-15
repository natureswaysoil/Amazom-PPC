# Amazon Sales Dashboard - Live Data Integration

## Overview

The Amazon Sales Dashboard provides real-time analytics for your Amazon sales data, integrating with:
- **Amazon Selling Partner API (SP-API)** for orders, inventory, and product data
- **Amazon Advertising API** for advertising metrics
- **BigQuery** for historical data storage and analysis

This is a **new comprehensive dashboard** separate from the existing PPC dashboard, focusing on sales, revenue, and inventory metrics.

## Features

### 📊 Real-Time Metrics
- **Revenue Analytics**: Total revenue, trends, and period comparisons
- **Order Volume**: Order counts by status (pending, shipped, delivered, cancelled)
- **Product Performance**: Top products by revenue and units sold
- **Inventory Management**: Current stock levels with low-stock alerts
- **Customer Metrics**: New vs returning customers, lifetime value, reviews

### 📅 Date Range Filtering
- Predefined ranges: Today, Yesterday, Last 7/30/90 days, This/Last Month, This Year
- Custom date range selection
- URL parameter persistence

### 📈 Interactive Visualizations
- Revenue trend line charts
- Order status pie charts
- Top products bar charts
- Real-time data updates (Chart.js)

### 🔄 Auto-Refresh
- Automatic data refresh every 5 minutes
- Manual refresh button
- Last updated timestamp display

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials
The dashboard reuses existing authentication from `gcp_credentials.py`:

```bash
export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
export AMAZON_CLIENT_SECRET="xxxxxxxx"
export AMAZON_REFRESH_TOKEN="Atzr|IwEBxxxxxxxx"
export AMAZON_PROFILE_ID="1780498399290938"
```

Or use Google Secret Manager (recommended for production):
- `Amazon_Ads_Client_identifier`
- `Amazon_Ads_Client_secret`
- `Amazon_Ads_Refresh_Token`
- `ppc-profile-id`

### 3. Run the Dashboard
```bash
python dashboard_api.py
```

### 4. Open in Browser
```
http://localhost:8080
```

## Files Created

- `amazon_sp_api.py` - Amazon SP-API wrapper
- `dashboard_api.py` - Flask REST API backend
- `cache_manager.py` - In-memory caching layer
- `dashboard/index.html` - Main dashboard page
- `dashboard/static/css/dashboard.css` - Styles
- `dashboard/static/js/dashboard.js` - Main controller
- `dashboard/static/js/charts.js` - Chart rendering
- `dashboard/static/js/api.js` - API client
- `dashboard/static/js/filters.js` - Date filtering

## API Endpoints

All endpoints are prefixed with `/api/dashboard/`:

- `GET /api/dashboard/revenue` - Revenue metrics
- `GET /api/dashboard/orders` - Order metrics
- `GET /api/dashboard/products/top` - Top products
- `GET /api/dashboard/inventory` - Inventory status
- `GET /api/dashboard/customers` - Customer metrics
- `GET /api/dashboard/status` - System health

## Architecture

```
Frontend (HTML/JS/Chart.js)
    ↓
Backend API (Flask)
    ↓
    ├── Amazon SP-API (amazon_sp_api.py)
    ├── Cache Manager (cache_manager.py)
    └── BigQuery (bigquery_client.py)
```

## Deployment

### Google Cloud Run
```bash
gcloud run deploy amazon-sales-dashboard \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-secrets=AMAZON_CLIENT_ID=Amazon_Ads_Client_identifier:latest,\
AMAZON_CLIENT_SECRET=Amazon_Ads_Client_secret:latest,\
AMAZON_REFRESH_TOKEN=Amazon_Ads_Refresh_Token:latest,\
AMAZON_PROFILE_ID=ppc-profile-id:latest
```

## Troubleshooting

### Dashboard won't load
- Ensure `dashboard_api.py` is running
- Check browser console for errors
- Verify credentials are configured

### No data showing
- Check Amazon SP-API credentials
- Verify profile ID: `1780498399290938`
- Review API logs for errors

### Authentication errors
- Refresh token may be expired
- Check Secret Manager values
- Verify SP-API access in Seller Central

## Notes

- This dashboard is **separate** from the existing PPC dashboard (`dashboard/app.py`)
- It uses **mock data** initially until full SP-API integration
- Caching reduces API calls and improves performance
- Auto-refresh keeps data current

## Next Steps

1. Complete SP-API integration (Orders, Inventory, Catalog endpoints)
2. Add real-time WebSocket updates
3. Implement export to CSV/Excel
4. Add more advanced analytics

## License

MIT License
