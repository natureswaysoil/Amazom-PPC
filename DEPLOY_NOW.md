# Amazon PPC Optimizer - Deployment Instructions

## Quick Deploy

### Option 1: Using the Deploy Script (Recommended)

Open [Google Cloud Shell](https://shell.cloud.google.com/) and run:

```bash
# Clone or navigate to your repo
cd ~/Amazom-PPC

# Pull latest changes
git pull origin main

# Run deploy script
./deploy.sh
```

### Option 2: Manual Deploy Command

```bash
gcloud config set project amazon-ppc-474902

gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest
```

## What's New in This Deployment

✅ **Health Endpoint**: `?health=true` returns lightweight status with `dashboard_ok` check  
✅ **Dashboard Integration**: Sends optimization status and results to your dashboard  
✅ **Verify Connection**: `?verify_connection=true` tests Amazon Ads API without running full optimization  
✅ **Non-blocking Dashboard**: Dashboard failures won't stop optimization runs  

## Verify Dashboard Secrets

Before deploying, ensure these secrets exist in Secret Manager:

```bash
# Check existing secrets
gcloud secrets list --filter="name:dashboard"

# Create if missing
echo -n "https://ppc-dashboard.abacusai.app" | gcloud secrets create dashboard-url --data-file=-
echo -n "YOUR_DASHBOARD_API_KEY" | gcloud secrets create dashboard-api-key --data-file=-
```

## Post-Deploy Testing

After deployment completes, test the new endpoints:

### 1. Health Check
```bash
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer --region=us-central1 --gen2 --format='value(serviceConfig.uri)')

curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?health=true"
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-18T...",
  "dashboard_ok": true,
  "email_ok": false
}
```

### 2. Verify Amazon Ads Connection
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=3"
```

Expected: Campaign sample with `"success": true`

### 3. Dry Run (Tests Dashboard Integration)
```bash
curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "${FUNCTION_URL}"
```

Expected: Optimization results + dashboard receives status/results posts

## Dashboard Endpoints

Your function will POST to these dashboard endpoints:

- `POST /api/optimization-status` - Start and progress updates
- `POST /api/optimization-results` - Final results with enhanced payload
- `POST /api/optimization-error` - Error reporting if failures occur

## Monitoring

- **Logs**: `gcloud functions logs read amazon-ppc-optimizer --region=us-central1 --gen2 --limit=100`
- **Monitoring**: https://console.cloud.google.com/monitoring?project=amazon-ppc-474902
- **Dashboard**: https://ppc-dashboard.abacusai.app

## Troubleshooting

### Dashboard shows dashboard_ok: false
- Check Secret Manager has `dashboard-url` and `dashboard-api-key`
- Verify the dashboard API endpoint is accessible
- Check function logs for connection errors

### Rate limiting (429 errors)
- Function is deployed with `--no-allow-unauthenticated` (correct)
- Ensure Cloud Scheduler uses OIDC authentication
- Use identity tokens for manual calls

### Deployment fails
- Ensure you're in the project root directory
- Check all required secrets exist in Secret Manager
- Verify billing is enabled on the project
