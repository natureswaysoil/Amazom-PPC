
# Amazon PPC Optimizer - Cloud Function

Automated Amazon Advertising campaign optimization deployed on Google Cloud Functions with automatic token refresh.

## 📚 Quick Links

- **[🚀 Quick Start Guide](QUICK_START.md)** - Get up and running in 15 minutes
- **[📖 Complete Deployment Guide](COMPLETE_DEPLOYMENT_GUIDE.md)** - Comprehensive 500+ line guide covering all deployment steps
- **[🔧 Local Testing Script](local-test.sh)** - Interactive script for local testing
- **[⚙️ Automated Deployment](deploy-complete.sh)** - One-command deployment automation
- **[🔐 Environment Template](.env.template)** - Template for local development environment

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
Use the `config.json` or `sample_config.yaml` files in the repository as **sanitized examples only**. All credentials are placeholders – replace them with your own values via environment variables or Secret Manager before running in any non-local environment.

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
  "bid_optimization": { ... },
  "dashboard": {
    "url": "https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app"
  }
}
```

### Runtime Overrides & Secret Sources

At runtime the Cloud Function inspects the following environment variables to
resolve credentials and execution preferences before falling back to the bundled
`config.json`/`sample_config.yaml` examples:

- `PPC_CONFIG_PATH` – absolute path to a YAML/JSON configuration file mounted at runtime
- `PPC_CONFIG` – JSON string containing the optimizer configuration (for Secret Manager bindings)
- `AMAZON_PROFILE_ID` / `PPC_PROFILE_ID` – override the Amazon Ads profile ID without editing config files
- `PPC_DRY_RUN` – set to `true` to execute without applying changes
- `PPC_FEATURES` – comma separated list of feature modules to execute
- `PPC_VERIFY_CONNECTION` and `PPC_VERIFY_SAMPLE_SIZE` – defaults for the verification helper

This means you can keep sensitive values exclusively in Google Secret Manager or
environment configuration; the repository examples remain sanitized.

### Verify Amazon Ads Connectivity

After providing valid credentials, run a lightweight verification to confirm the
optimizer can retrieve data from Amazon Ads (omit `--profile-id` if it's set in
the config file):

```bash
python optimizer_core.py \
  --config sample_config.yaml \
  --profile-id 1780498399290938 \
  --verify-connection
```

The command exits with a non-zero status if the API call fails and prints a
small sample of retrieved campaigns when successful. Use
`--verify-sample-size=N` to adjust how many campaigns are returned in the
verification payload.

### Triggering the Optimizer via Cloud Function

When deployed to Google Cloud Functions (entry point: `run_optimizer`), send an
authenticated `POST` request with an optional JSON payload to run the
automation:

```bash
curl -X POST "https://YOUR-FUNCTION-URL" \
  -H "Authorization: Bearer $FUNCTION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "profile_id": "1780498399290938",
        "dry_run": true,
        "features": ["bid_optimization", "dayparting"]
      }'
```

Omit `features` to execute every module enabled inside the configuration file.
To verify Amazon Ads connectivity through the deployed function instead of the
CLI helper, call the endpoint with `?verify_connection=true` and (optionally)
`verify_sample_size=10`. The handler returns a JSON payload containing the
verification sample or a descriptive error when credentials are misconfigured.

## 🚀 Deployment

For complete end-to-end setup from scratch, see:
- **[COMPLETE_DEPLOYMENT_GUIDE.md](COMPLETE_DEPLOYMENT_GUIDE.md)** - Comprehensive setup guide covering all 5 steps from GitHub tokens to production verification

For specific deployment details, see:
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Detailed deployment reference and configuration options

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

The optimizer includes comprehensive dashboard integration with real-time updates:

**Dashboard URL**: https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app

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
    "url": "https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app",
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

### Verification & Testing

The optimizer includes built-in verification endpoints:

**Health Check** (lightweight, no optimization):
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://YOUR-FUNCTION-URL?health=true"
```

**Verify Amazon Ads Connection** (test API without full optimization):
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://YOUR-FUNCTION-URL?verify_connection=true&verify_sample_size=3"
```

**Dry Run** (full optimization without making changes):
```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "https://YOUR-FUNCTION-URL"
```

For complete verification procedures, see:
- **[VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md)**: Comprehensive verification guide
- **[DATA_FLOW_SUMMARY.md](DATA_FLOW_SUMMARY.md)**: Complete data flow documentation
- **[DASHBOARD_INTEGRATION.md](DASHBOARD_INTEGRATION.md)**: Dashboard integration details

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
| `DASHBOARD_API_ENDPOINT` | Dashboard API URL | `https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app/api/health-check` |
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

### BigQuery "Dataset Not Found" Error

If you see errors like "Dataset amazon-ppc-474902:amazon_ppc was not found in location us-east4":

**Solution**:
1. Run the BigQuery setup script:
   ```bash
   ./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
   ```

2. Grant permissions to your service account:
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format='value(projectNumber)')
   SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
   gcloud projects add-iam-policy-binding amazon-ppc-474902 \
     --member="serviceAccount:${SERVICE_ACCOUNT}" \
     --role="roles/bigquery.dataEditor"
   gcloud projects add-iam-policy-binding amazon-ppc-474902 \
     --member="serviceAccount:${SERVICE_ACCOUNT}" \
     --role="roles/bigquery.jobUser"
   ```

3. Verify the setup:
   ```bash
   bq ls amazon-ppc-474902:amazon_ppc
   ```

See [BIGQUERY_INTEGRATION.md](BIGQUERY_INTEGRATION.md) for complete BigQuery setup and troubleshooting.

### Uptime Check Configuration

To avoid triggering the main optimization logic with uptime checks:

```bash
# Use health check endpoint
curl "https://YOUR-FUNCTION-URL?health=true"
```

Or configure less frequent checks (e.g., every 5-10 minutes instead of every 5-6 seconds)

## 📚 Documentation Index

### Getting Started
| Document | Description | Use Case |
|----------|-------------|----------|
| [QUICK_START.md](QUICK_START.md) | Get running in 15 minutes | First-time setup |
| [COMPLETE_DEPLOYMENT_GUIDE.md](COMPLETE_DEPLOYMENT_GUIDE.md) | Comprehensive deployment guide (500+ lines) | Complete CI/CD setup |
| [local-test.sh](local-test.sh) | Interactive local testing script | Local development |
| [deploy-complete.sh](deploy-complete.sh) | Automated deployment script | One-command deployment |
| [.env.template](.env.template) | Environment variables template | Local configuration |

### Deployment & Operations
| Document | Description |
|----------|-------------|
| [README.md](README.md) | Main project documentation (this file) |
| [COMPLETE_DEPLOYMENT_GUIDE.md](COMPLETE_DEPLOYMENT_GUIDE.md) | **⭐ Complete end-to-end setup guide** (GitHub, BigQuery, testing, deployment, verification) |
| [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) | Complete verification procedures and testing guide |
| [DATA_FLOW_SUMMARY.md](DATA_FLOW_SUMMARY.md) | Data flow from optimizer to dashboard with examples |
| [DASHBOARD_INTEGRATION.md](DASHBOARD_INTEGRATION.md) | Detailed dashboard integration documentation |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Step-by-step deployment instructions |
| [DEPLOY_NOW.md](DEPLOY_NOW.md) | Quick deployment commands |
| [DEPLOYMENT_COMPLETE.md](DEPLOYMENT_COMPLETE.md) | Post-deployment verification checklist |

### Verification & Testing
| Document | Description |
|----------|-------------|
| [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) | Complete verification procedures and testing guide |
| [DATA_FLOW_SUMMARY.md](DATA_FLOW_SUMMARY.md) | Data flow from optimizer to dashboard with examples |

### Integration Guides
| Document | Description |
|----------|-------------|
| [DASHBOARD_INTEGRATION.md](DASHBOARD_INTEGRATION.md) | Detailed dashboard integration documentation |
| [BIGQUERY_INTEGRATION.md](BIGQUERY_INTEGRATION.md) | BigQuery setup and integration guide |

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Support

For issues or questions:
- Check Cloud Function logs
- Review the [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) for troubleshooting
- Review the [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for deployment help
- Contact: james@natureswaysoil.com
