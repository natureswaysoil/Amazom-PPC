# Amazon Sales Dashboard - Deployment Guide

## Quick Start

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set credentials
export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
export AMAZON_CLIENT_SECRET="xxxxxxxx"
export AMAZON_REFRESH_TOKEN="Atzr|IwEBxxxxxxxx"
export AMAZON_PROFILE_ID="1780498399290938"
export FLASK_DEBUG="False"

# Run server
python dashboard_api.py
```

Dashboard: `http://localhost:8080`

### Google Cloud Run (Production)
```bash
gcloud run deploy amazon-sales-dashboard \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars FLASK_DEBUG=False \
  --set-secrets=AMAZON_CLIENT_ID=Amazon_Ads_Client_identifier:latest,\
AMAZON_CLIENT_SECRET=Amazon_Ads_Client_secret:latest,\
AMAZON_REFRESH_TOKEN=Amazon_Ads_Refresh_Token:latest,\
AMAZON_PROFILE_ID=ppc-profile-id:latest
```

## Production Checklist
- [ ] FLASK_DEBUG=False
- [ ] Credentials in Secret Manager
- [ ] HTTPS enabled
- [ ] Monitoring enabled
- [ ] Cache configured

## Environment Variables
- `AMAZON_CLIENT_ID` - Required
- `AMAZON_CLIENT_SECRET` - Required  
- `AMAZON_REFRESH_TOKEN` - Required
- `AMAZON_PROFILE_ID` - Required (default: 1780498399290938)
- `FLASK_DEBUG` - Set to False in production
- `GCP_PROJECT_ID` - Optional (default: amazon-ppc-474902)

## Health Check
```bash
curl https://your-domain.com/api/dashboard/status
```

## Documentation
- See `dashboard/SALES_DASHBOARD_README.md` for usage guide
