
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

# Get the deployed function URL (Gen2 uses Cloud Run URLs)
gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)'
```

> **Note**: Gen2 Cloud Functions use Cloud Run URLs (format: `https://FUNCTION_NAME-HASH-REGION.a.run.app`), not the older Gen1 format (`https://REGION-PROJECT.cloudfunctions.net/FUNCTION_NAME`).

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

The optimizer sends results to the dashboard at:
https://ppc-dashboard.abacusai.app

Dashboard receives:
- Optimization results
- Performance metrics
- Execution status

## 🏥 Automated Health Check Workflow

The repository includes an automated health check workflow (`.github/workflows/health-check.yml`) that runs after each deployment to ensure the Cloud Function is healthy and ready to use.

### How It Works

1. **Triggered automatically** after the "Deploy to Google Cloud" workflow completes
   - Note: If you haven't set up a deployment workflow yet, you can still manually trigger this workflow
   - Or create a deployment workflow named "Deploy to Google Cloud" to enable automatic triggering
2. **Runs health check** by calling the health endpoint: `https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app/?health=true`
3. **Sends email notification** to natureswaysoil@gmail.com with results
4. **Posts to dashboard** (optional) for visual monitoring

### Configure Email Notifications

To enable email notifications, add these GitHub Secrets:

1. Go to your repository: **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add:

| Secret Name | Description | How to Get |
|------------|-------------|------------|
| `GMAIL_USER` | Your Gmail address | e.g., `natureswaysoil@gmail.com` |
| `GMAIL_PASS` | Gmail App Password | See below ⬇️ |

#### Getting a Gmail App Password

1. Go to [Google Account App Passwords](https://myaccount.google.com/apppasswords)
2. Sign in to your Gmail account
3. Create a new app password:
   - App: **Other (Custom name)**
   - Name: **GitHub Actions**
4. Copy the 16-character password
5. Add it as the `GMAIL_PASS` secret in GitHub

**Important**: Use an App Password, NOT your regular Gmail password! App passwords are more secure and can be revoked without changing your main password.

### Configure Dashboard Integration (Optional)

To enable dashboard API integration, add these GitHub Secrets:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `DASHBOARD_API_ENDPOINT` | Dashboard API URL | `https://ppc-dashboard.abacusai.app/api/health-check` |
| `DASHBOARD_API_KEY` | Authentication token | Your dashboard API key |

The workflow will automatically post health check results to the dashboard if these secrets are configured. If not configured, the workflow will still complete successfully - dashboard integration is optional.

### Manual Testing

You can manually trigger the health check workflow:

1. Go to **Actions** tab in GitHub
2. Select **Health Check and Notifications** workflow
3. Click **Run workflow**
4. Select the branch and click **Run workflow**

### What Gets Sent

**Email includes**:
- ✅ Health check status (PASSED/FAILED)
- HTTP response code and body
- Deployment details (commit, branch, timestamp)
- Cloud Function URL
- Links to logs and dashboard

**Dashboard receives** (if configured):
- Health check status and timestamp
- Deployment information
- Cloud Function endpoint details

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
