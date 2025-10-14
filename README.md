
# Amazon PPC Optimizer - Cloud Function

Automated Amazon Advertising campaign optimization deployed on Google Cloud Functions with automatic token refresh.

## 🚀 Features

- **Automatic Token Refresh**: Tokens are automatically refreshed before API calls
- **Serverless Deployment**: Runs on Google Cloud Functions
- **Scheduled Execution**: Triggered by Cloud Scheduler
- **Comprehensive Optimization**:
  - Bid optimization based on ACOS/performance
  - Dayparting (time-based bid adjustments)
  - Campaign management (auto-pause/activate)
  - Keyword discovery and harvesting
  - Negative keyword management
  - Budget optimization
  - Placement bid adjustments

## 📋 Prerequisites

- Google Cloud Project with billing enabled
- Amazon Advertising API credentials:
  - Client ID
  - Client Secret
  - Refresh Token
  - Profile ID
- gcloud CLI installed and configured

## 🔧 Configuration

The optimizer can be configured in two ways:

### 1. Environment Variable (Recommended for Production)
Set the `PPC_CONFIG` environment variable with a JSON string containing all configuration.

### 2. Config File (For Development)
Use the `config.json` file in the repository.

### Required Configuration Keys

```json
{
  "amazon_api": {
    "client_id": "amzn1.application-oa2-client.xxxxx",
    "client_secret": "amzn1.oa2-cs.v1.xxxxx",
    "refresh_token": "Atzr|IwEBIxxxxx",
    "profile_id": "1780498399290938",
    "region": "NA"
  },
  "optimization_rules": { ... },
  "dashboard": {
    "url": "https://ppc-dashboard.abacusai.app"
  }
}
```

## 🚀 Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed deployment instructions.

### Quick Deploy (Secure - Recommended)

```bash
# Deploy with authentication and Secret Manager (RECOMMENDED)
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
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest
```

**Important Security Notes:**
- ✅ **DO** use `--no-allow-unauthenticated` for production
- ✅ **DO** use Google Secret Manager for credentials
- ✅ **DO** configure Cloud Scheduler with proper authentication
- ❌ **DON'T** use `--allow-unauthenticated` (causes rate limiting issues)
- ❌ **DON'T** pass secrets as environment variables in command line

## 🔄 Token Refresh

The optimizer **automatically refreshes** the Amazon Advertising API access token:

1. Before each API call, it checks if the token has expired
2. If expired (or within 60 seconds of expiry), it automatically fetches a new token
3. Uses the refresh_token stored in environment variables
4. No manual intervention required

The token refresh logic is built into `optimizer_core.py`:
- `_authenticate()`: Fetches a new access token using refresh_token
- `_refresh_auth_if_needed()`: Checks expiration and refreshes if needed
- Called automatically before each API request

## 🔐 Security

- **Never commit** `config.json` with real credentials to Git
- Use environment variables in production
- The `.gitignore` excludes sensitive files
- Rotate credentials regularly

## 📊 Dashboard Integration

The optimizer includes comprehensive dashboard integration with real-time updates:

**Dashboard URL**: https://ppc-dashboard.abacusai.app

### Features

- **Enhanced Results Payload**: Detailed metrics including summary, campaigns, and top performers
- **Real-time Progress Updates**: Live status during optimization runs
- **Error Reporting**: Automatic error notification with full context
- **Retry Logic**: Exponential backoff for reliable delivery
- **API Key Authentication**: Secure communication with the dashboard
- **Health Checks**: Verify optimizer connectivity from dashboard
- **Dashboard Triggers**: Allow dashboard to trigger optimization runs

### Configuration

Add to your `config.json`:

```json
{
  "dashboard": {
    "url": "https://ppc-dashboard.abacusai.app",
    "api_key": "your_dashboard_api_key_here",
    "enabled": true,
    "send_real_time_updates": true,
    "timeout": 30
  }
}
```

### Dashboard Endpoints

The optimizer communicates with these dashboard endpoints:

- `POST /api/optimization-results` - Send completed optimization results
- `POST /api/optimization-status` - Send real-time progress updates
- `POST /api/optimization-error` - Report errors during optimization
- `GET /api/health` - Health check endpoint

### Triggering from Dashboard

The dashboard can trigger optimization runs using:

```bash
curl -X POST "https://YOUR-FUNCTION-URL?trigger=dashboard" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json"
```

### Payload Structure

The enhanced payload includes:

- **Summary Metrics**: Campaigns analyzed, keywords optimized, budget changes
- **Feature Results**: Detailed results for each optimization feature
- **Campaign Breakdown**: Per-campaign performance and changes
- **Top Performers**: Best performing keywords with metrics
- **Errors & Warnings**: Complete error context and warnings
- **Configuration Snapshot**: Settings used for this run

### Non-Blocking Design

Dashboard communication is designed to be non-blocking:
- Failures don't stop optimization
- Automatic retries with exponential backoff
- Comprehensive logging of all interactions
- Graceful degradation if dashboard is unavailable

## 🧪 Testing

### Local Testing
```bash
# Set environment variables
export AMAZON_CLIENT_ID="your_client_id"
export AMAZON_CLIENT_SECRET="your_client_secret"
export AMAZON_REFRESH_TOKEN="your_refresh_token"

# Run locally
python main.py
```

### Dry Run (No Changes Made)
```bash
# Test without making actual changes
curl "https://YOUR-FUNCTION-URL?dry_run=true"
```

## 📁 Project Structure

```
.
├── main.py                 # Cloud Function entry point
├── optimizer_core.py       # Core optimization logic with auto token refresh
├── requirements.txt        # Python dependencies
├── config.json            # Configuration (template, use env vars in production)
├── .gcloudignore          # Files to exclude from deployment
├── .gitignore             # Git ignore patterns
├── README.md              # This file
└── DEPLOYMENT_GUIDE.md    # Detailed deployment instructions
```

## 🐛 Troubleshooting

### HTTP 429 (Too Many Requests) Errors

If you're experiencing HTTP 429 errors:

**Cause**: Function deployed with `--allow-unauthenticated` flag
- Unauthenticated functions have stricter rate limits
- Uptime checks hit the function too frequently
- All requests are rate-limited before function execution

**Solution**:
1. Redeploy with `--no-allow-unauthenticated` flag (see deployment section)
2. Configure Cloud Scheduler with proper authentication (service account)
3. Use the `/health` endpoint for uptime checks: `?health=true`
4. Reduce uptime check frequency or disable for this function

**Verify Fix**:
```bash
# Check logs - successful requests should show execution time > 0ms
gcloud functions logs read amazon-ppc-optimizer --limit=10
```

### Token Issues
- The optimizer automatically handles token refresh
- Check Cloud Function logs if authentication fails
- Verify refresh_token is valid and not expired

### Deployment Issues
- Ensure all required dependencies are in `requirements.txt`
- Check function timeout (increase if needed)
- Verify secrets are properly configured in Secret Manager
- Use `--no-allow-unauthenticated` for production deployments

### API Rate Limits
- The optimizer includes rate limiting (10 requests/second)
- Automatic retry with exponential backoff
- Cloud Function rate limits: use authenticated deployment to avoid issues

### Uptime Check Configuration

To avoid triggering the main optimization logic with uptime checks:

```bash
# Use health check endpoint
curl "https://YOUR-FUNCTION-URL?health=true"
```

Or configure less frequent checks (e.g., every 5-10 minutes instead of every 5-6 seconds)

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Support

For issues or questions:
- Check Cloud Function logs
- Review the DEPLOYMENT_GUIDE.md
- Contact: james@natureswaysoil.com
