# Amazon Sales Data Cloud Function

This directory contains a Node.js-based Google Cloud Function for retrieving sales data from Amazon Selling Partner API (SP-API).

## What is this?

This Cloud Function provides a serverless endpoint to fetch sales data from Amazon. It's designed to be deployed to Google Cloud Functions and can be called from your frontend or other services.

## Key Features

- 🔐 **Secure credential management** using Google Secret Manager
- 🔄 **Automatic token refresh** for Amazon SP-API
- 🌍 **CORS enabled** for frontend integration
- ⚡ **Serverless** - scales automatically, pay only for usage
- 📊 **Flexible date range queries**

## Quick Start

See [INSTALL_CLOUD_FUNCTION.md](INSTALL_CLOUD_FUNCTION.md) for complete deployment instructions.

### Prerequisites

- Google Cloud account with billing enabled
- Amazon Seller Central account with SP-API access
- gcloud CLI installed

### Minimal Deploy

```bash
# 1. Set up your project
gcloud config set project amazon-ppc-474902

# 2. Deploy the function
gcloud functions deploy amazonSalesData \
  --gen2 \
  --runtime nodejs20 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point amazonSalesData \
  --region us-central1 \
  --memory 512MB \
  --timeout 540s
```

## File Structure

```
cloud-function/
├── index.js                      # Main Cloud Function code
├── package.json                  # Node.js dependencies
├── .gcloudignore                 # Files to exclude from deployment
├── INSTALL_CLOUD_FUNCTION.md     # Detailed installation guide
└── README.md                     # This file
```

## Environment Variables / Secrets

The function expects these secrets in Google Secret Manager:

- `AMAZON_SP_API_CLIENT_ID` - Your Amazon SP-API Client ID
- `AMAZON_SP_API_CLIENT_SECRET` - Your Amazon SP-API Client Secret
- `AMAZON_SP_API_REFRESH_TOKEN` - Your Amazon SP-API Refresh Token
- `AMAZON_MARKETPLACE_ID` - Target marketplace (default: ATVPDKIKX0DER for US)

## API Usage

### Request Format

```bash
curl -X POST https://YOUR-FUNCTION-URL \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2024-01-01T00:00:00Z",
    "endDate": "2024-01-31T23:59:59Z"
  }'
```

### Response Format

```json
{
  "success": true,
  "data": {
    // Amazon SP-API response data
  },
  "metadata": {
    "startDate": "2024-01-01T00:00:00.000Z",
    "endDate": "2024-01-31T23:59:59.000Z",
    "marketplaceId": "ATVPDKIKX0DER"
  }
}
```

## Development

### Local Testing

You can test the function locally using the Functions Framework:

```bash
npm install
npm install -g @google-cloud/functions-framework

# Set environment variables
export AMAZON_SP_API_CLIENT_ID="your_client_id"
export AMAZON_SP_API_CLIENT_SECRET="your_client_secret"
export AMAZON_SP_API_REFRESH_TOKEN="your_refresh_token"
export AMAZON_MARKETPLACE_ID="ATVPDKIKX0DER"

# Run locally
npx functions-framework --target=amazonSalesData --port=8080

# Test
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{"startDate": "2024-01-01T00:00:00Z", "endDate": "2024-01-31T23:59:59Z"}'
```

## Differences from Main Project

This Cloud Function is separate from the main Python-based PPC optimizer:

| Feature | Main Project (Python) | This Cloud Function (Node.js) |
|---------|----------------------|-------------------------------|
| Purpose | Amazon Advertising API (PPC optimization) | Amazon Selling Partner API (Sales data) |
| Language | Python 3.11 | Node.js 20 |
| API | Amazon Ads API | Amazon SP-API |
| Data Type | Advertising campaigns, keywords, bids | Orders, inventory, reports |
| Entry Point | `main.py:run_optimizer` | `index.js:amazonSalesData` |

## Troubleshooting

### Function fails to deploy
- Check that all required APIs are enabled (Cloud Functions, Cloud Build, Secret Manager)
- Verify your gcloud CLI is authenticated: `gcloud auth list`
- Ensure billing is enabled for your project

### "Secret not found" error
- Make sure secrets are created in Secret Manager
- Verify the service account has `secretAccessor` role
- Check the project ID matches in all commands

### SP-API returns 403 errors
- Verify your Amazon SP-API credentials are correct
- Check that your app is registered in Amazon Seller Central
- Ensure you've authorized the app for the correct marketplace

## Security Best Practices

✅ **DO:**
- Use Google Secret Manager for credentials
- Rotate credentials regularly
- Monitor Cloud Function logs
- Set appropriate timeout limits

❌ **DON'T:**
- Commit credentials to git
- Use `--allow-unauthenticated` in production without security measures
- Share credentials via email or chat
- Hardcode secrets in the function code

## Cost Optimization

- First 2 million invocations per month are **FREE**
- Function scales to zero when not in use (no idle costs)
- Secrets in Secret Manager: First 6 versions **FREE**
- Estimated cost for moderate use: **$0-3/month**

## Support

- **Installation Guide:** [INSTALL_CLOUD_FUNCTION.md](INSTALL_CLOUD_FUNCTION.md)
- **Amazon SP-API Docs:** https://developer-docs.amazon.com/sp-api/
- **Google Cloud Functions:** https://cloud.google.com/functions/docs
- **Issues:** Contact james@natureswaysoil.com

---

**Note:** This is a separate component from the main PPC optimizer. The main optimizer is Python-based and focuses on advertising data, while this function is Node.js-based and focuses on sales data.
