# Amazon PPC Optimizer - Quick Start Guide

This guide walks you through the complete setup process to get the Amazon PPC Optimizer running in production.

## Overview

The setup process consists of five main steps:

1. **Configure GitHub Token** - For CI/CD automation
2. **Set Up BigQuery Credentials** - For data storage and analytics
3. **Run Local Dry-Run Test** - Verify everything works locally
4. **Deploy to Cloud Functions** - Deploy to production
5. **Verify with Real Data** - Confirm production deployment

**Estimated Time**: 30-45 minutes

---

## Step 1: Configure GitHub Token

GitHub tokens enable automated workflows for health checks and deployment notifications.

### 1.1 Create GitHub Personal Access Token (if using GitHub Actions)

If you plan to use the automated health check workflow:

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click **"Generate new token (classic)"**
3. Configure the token:
   - **Note**: `Amazon PPC Optimizer CI/CD`
   - **Expiration**: 90 days (or as needed)
   - **Scopes**: Select `repo` (Full control of private repositories)
4. Click **"Generate token"**
5. **Copy the token immediately** - you won't see it again!

### 1.2 Add GitHub Secrets

Add the following secrets to your repository:

1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"** for each:

| Secret Name | Description | How to Get |
|------------|-------------|------------|
| `GCP_PROJECT_ID` | Your Google Cloud project ID | From GCP Console |
| `GCP_SA_KEY` | Service account JSON key | See Step 2.3 below |
| `FUNCTION_URL` | Cloud Function URL (after deployment) | From deployment output |
| `GMAIL_USER` | Email for notifications | Your Gmail address |
| `GMAIL_PASS` | Gmail App Password | See Section 1.3 |

### 1.3 Configure Gmail App Password (for Email Notifications)

1. Go to [Google Account App Passwords](https://myaccount.google.com/apppasswords)
2. Sign in to your Gmail account
3. Create a new app password:
   - **App**: Other (Custom name)
   - **Name**: `GitHub Actions Amazon PPC`
4. Copy the 16-character password
5. Add it as `GMAIL_PASS` secret in GitHub

---

## Step 2: Set Up BigQuery Credentials

BigQuery stores optimization results for analysis and reporting.

### 2.1 Enable BigQuery API

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Enable BigQuery API
gcloud services enable bigquery.googleapis.com
gcloud services enable bigquerystorage.googleapis.com
```

### 2.2 Run BigQuery Setup Script

```bash
# Clone the repository (if not already done)
git clone https://github.com/natureswaysoil/Amazom-PPC.git
cd Amazom-PPC

# Run the setup script with your project details
./setup-bigquery.sh $PROJECT_ID amazon_ppc us-east4
```

This script:
- Creates the `amazon_ppc` dataset in BigQuery
- Creates all required tables (optimization_results, campaigns, keywords, etc.)
- Configures proper permissions

### 2.3 Create Service Account for Cloud Functions

```bash
# Create service account
gcloud iam service-accounts create ppc-optimizer \
    --display-name="Amazon PPC Optimizer" \
    --project=$PROJECT_ID

# Get service account email
SERVICE_ACCOUNT="ppc-optimizer@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant required permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/cloudfunctions.invoker"

# Create and download service account key (for GitHub Actions)
gcloud iam service-accounts keys create ~/ppc-sa-key.json \
    --iam-account=$SERVICE_ACCOUNT

# Display the key (copy this to GitHub Secrets as GCP_SA_KEY)
cat ~/ppc-sa-key.json
```

**Security Note**: Store the service account key securely in GitHub Secrets, never commit it to the repository.

### 2.4 Update Configuration

Update your `config.json` to enable BigQuery:

```json
{
  "bigquery": {
    "enabled": true,
    "project_id": "your-project-id",
    "dataset_id": "amazon_ppc",
    "location": "us-east4"
  }
}
```

Or set environment variables:
```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export BQ_DATASET_ID=amazon_ppc
export BQ_LOCATION=us-east4
```

---

## Step 3: Run Local Dry-Run Test

Test the optimizer locally before deploying to ensure everything is configured correctly.

### 3.1 Install Dependencies

```bash
cd Amazom-PPC

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3.2 Set Environment Variables

```bash
# Amazon Advertising API credentials
export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
export AMAZON_CLIENT_SECRET="amzn1.oa2-cs.v1.xxxxx"
export AMAZON_REFRESH_TOKEN="Atzr|IwEBIxxxxx"
export AMAZON_PROFILE_ID="1780498399290938"

# Google Cloud (for BigQuery)
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/ppc-sa-key.json"
```

**Getting Amazon API Credentials**:
1. Visit [Amazon Advertising API](https://advertising.amazon.com/API/docs/en-us/setting-up/overview)
2. Register your application
3. Complete OAuth flow to get refresh_token
4. Get Profile ID from Amazon Advertising Console

### 3.3 Verify Amazon Ads Connection

```bash
# Quick connection test (uses sample_config.yaml)
python optimizer_core.py \
  --config sample_config.yaml \
  --profile-id $AMAZON_PROFILE_ID \
  --verify-connection
```

Expected output:
```
✓ Successfully authenticated with Amazon Ads API
✓ Retrieved 5 sample campaigns
✓ Connection verified
```

### 3.4 Run Dry-Run Test

```bash
# Full dry-run (no changes will be made)
python main.py
```

Or run with specific features:
```bash
# Set dry-run mode via environment
export PPC_DRY_RUN=true
export PPC_FEATURES="bid_optimization,dayparting"

python main.py
```

**What to look for**:
- ✅ "Successfully authenticated with Amazon Ads API"
- ✅ "Loading configuration..."
- ✅ "Running optimization (DRY RUN mode)"
- ✅ "Optimization completed successfully"
- ✅ BigQuery write operations (if enabled)

If you see errors, check the troubleshooting section below.

---

## Step 4: Deploy to Cloud Functions

Deploy the optimizer to Google Cloud Functions for production use.

### 4.1 Set Up Secret Manager (Recommended)

Store credentials securely:

```bash
# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Create secrets for Amazon API credentials
echo -n "$AMAZON_CLIENT_ID" | gcloud secrets create amazon-client-id --data-file=-
echo -n "$AMAZON_CLIENT_SECRET" | gcloud secrets create amazon-client-secret --data-file=-
echo -n "$AMAZON_REFRESH_TOKEN" | gcloud secrets create amazon-refresh-token --data-file=-

# Grant access to Cloud Functions service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for secret in amazon-client-id amazon-client-secret amazon-refresh-token; do
  gcloud secrets add-iam-policy-binding $secret \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

### 4.2 Deploy Cloud Function

```bash
# Deploy with Secret Manager (RECOMMENDED)
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
  --min-instances=0 \
  --max-instances=1 \
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest \
  --set-env-vars=AMAZON_PROFILE_ID=$AMAZON_PROFILE_ID,GOOGLE_CLOUD_PROJECT=$PROJECT_ID
```

**Deployment takes 3-5 minutes**. You'll see:
- ✅ Building and uploading code
- ✅ Creating/Updating Cloud Function
- ✅ Function URL output

### 4.3 Get Function URL

```bash
# Get the deployed function URL (Gen2 uses Cloud Run URLs)
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)')

echo "Function URL: $FUNCTION_URL"
```

**Save this URL** - you'll need it for:
- GitHub Secrets (`FUNCTION_URL`)
- Cloud Scheduler
- Manual testing

### 4.4 Set Up Cloud Scheduler (Optional but Recommended)

Automate optimization runs:

```bash
# Create service account for scheduler
gcloud iam service-accounts create ppc-scheduler \
  --display-name="PPC Optimizer Scheduler"

# Grant permission to invoke function
gcloud functions add-iam-policy-binding amazon-ppc-optimizer \
  --region=us-central1 \
  --member="serviceAccount:ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudfunctions.invoker"

# Create daily schedule (3 AM)
gcloud scheduler jobs create http amazon-ppc-optimizer-daily \
  --location=us-central1 \
  --schedule="0 3 * * *" \
  --uri="$FUNCTION_URL" \
  --http-method=POST \
  --time-zone="America/New_York" \
  --oidc-service-account-email="ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="$FUNCTION_URL"
```

---

## Step 5: Verify with Real Data

Confirm the deployment is working correctly with production data.

### 5.1 Health Check

```bash
# Quick health check (doesn't run optimization)
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?health=true"
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-11-06T...",
  "dashboard_ok": true,
  "email_ok": true,
  "environment": "cloud_function"
}
```

### 5.2 Verify Amazon Ads Connection

```bash
# Test API connection without full optimization
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=5"
```

Expected response:
```json
{
  "status": "success",
  "message": "Amazon Ads API connection verified",
  "profile_id": "1780498399290938",
  "timestamp": "2024-11-06T...",
  "sample_size": 5,
  "note": "Connection successful - credentials are valid and API is reachable"
}
```

### 5.3 Run Production Dry-Run

```bash
# Full optimization in dry-run mode (no changes made)
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "$FUNCTION_URL"
```

**Monitor the logs**:
```bash
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=50 \
  --gen2
```

Look for:
- ✅ Authentication successful
- ✅ Optimization started
- ✅ Features executed
- ✅ Results sent to dashboard/BigQuery
- ✅ Optimization completed

### 5.4 Check BigQuery Data

```bash
# Query recent optimization results
bq query --use_legacy_sql=false \
  "SELECT 
     run_id, 
     status, 
     keywords_optimized, 
     bids_adjusted,
     timestamp 
   FROM \`${PROJECT_ID}.amazon_ppc.optimization_results\` 
   ORDER BY timestamp DESC 
   LIMIT 5"
```

### 5.5 Run Live Optimization (Real Changes)

Once you've verified everything works in dry-run mode:

```bash
# Run actual optimization (MAKES REAL CHANGES)
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false, "features": ["bid_optimization", "dayparting"]}' \
  "$FUNCTION_URL"
```

⚠️ **Warning**: This will make actual changes to your Amazon Ads campaigns!

### 5.6 Monitor Dashboard

Check the dashboard for real-time updates:
- **Dashboard URL**: https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app

You should see:
- Recent optimization runs
- Performance metrics
- Campaign changes
- Real-time progress updates

---

## Troubleshooting

### Local Testing Issues

**Problem**: `ModuleNotFoundError: No module named 'functions_framework'`
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

**Problem**: `Authentication failed with Amazon Ads API`
```bash
# Solution: Verify credentials
echo "Client ID: $AMAZON_CLIENT_ID"
echo "Profile ID: $AMAZON_PROFILE_ID"
# Check that refresh token is valid (not expired)
```

**Problem**: `BigQuery dataset not found`
```bash
# Solution: Run setup script
./setup-bigquery.sh $PROJECT_ID amazon_ppc us-east4
```

### Deployment Issues

**Problem**: `Permission denied when deploying`
```bash
# Solution: Ensure you have proper IAM roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/cloudfunctions.developer"
```

**Problem**: `Secret not found`
```bash
# Solution: List and verify secrets exist
gcloud secrets list
# Recreate if missing
echo -n "$AMAZON_CLIENT_ID" | gcloud secrets create amazon-client-id --data-file=-
```

**Problem**: `Function times out`
```bash
# Solution: Increase timeout
gcloud functions deploy amazon-ppc-optimizer \
  --timeout=900s \
  --update-env-vars ...
```

### Runtime Issues

**Problem**: `HTTP 429 Rate Limiting`
```bash
# Solution: Already using --no-allow-unauthenticated
# Reduce scheduler frequency or check for unauthorized access
gcloud functions logs read amazon-ppc-optimizer --limit=20 | grep "429"
```

**Problem**: `BigQuery writes failing`
```bash
# Solution: Check service account permissions
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.dataEditor"
```

---

## Next Steps After Setup

Now that your optimizer is deployed and verified:

### 1. Configure Optimization Rules

Edit `config.json` or use environment variables to customize:
- Bid adjustment thresholds
- ACOS targets
- Dayparting schedules
- Budget limits
- Keyword discovery rules

### 2. Set Up Monitoring

- Configure Cloud Monitoring alerts for failures
- Set up Slack/email notifications
- Create custom BigQuery dashboards
- Monitor costs and usage

### 3. Fine-Tune Performance

- Review initial results after 1-2 weeks
- Adjust optimization thresholds based on performance
- Enable/disable features as needed
- Optimize for your specific campaigns

### 4. Automate Reporting

```bash
# Create scheduled BigQuery queries for reports
# Export to Google Sheets
# Set up automated email reports
```

---

## Support and Resources

### Documentation
- **[README.md](README.md)** - Project overview and features
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Detailed deployment instructions
- **[VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md)** - Testing and verification procedures
- **[BIGQUERY_INTEGRATION.md](BIGQUERY_INTEGRATION.md)** - BigQuery setup details
- **[DASHBOARD_INTEGRATION.md](DASHBOARD_INTEGRATION.md)** - Dashboard integration

### Getting Help
- **Email**: james@natureswaysoil.com
- **Repository**: https://github.com/natureswaysoil/Amazom-PPC
- **Issues**: Report bugs via GitHub Issues

### Useful Commands

```bash
# View logs
gcloud functions logs read amazon-ppc-optimizer --limit=50

# Update environment variable
gcloud functions deploy amazon-ppc-optimizer \
  --update-env-vars KEY=VALUE

# Manual trigger via scheduler
gcloud scheduler jobs run amazon-ppc-optimizer-daily --location=us-central1

# Check function status
gcloud functions describe amazon-ppc-optimizer --region=us-central1 --gen2

# Query BigQuery results
bq query --use_legacy_sql=false "SELECT * FROM \`$PROJECT_ID.amazon_ppc.optimization_results\` LIMIT 10"
```

---

## Security Checklist

Before going to production, verify:

- [ ] Credentials stored in Secret Manager (not environment variables)
- [ ] Function deployed with `--no-allow-unauthenticated`
- [ ] Service accounts use principle of least privilege
- [ ] GitHub secrets properly configured
- [ ] Service account keys secured (not in repository)
- [ ] Cloud Scheduler uses OIDC authentication
- [ ] Regular credential rotation schedule in place
- [ ] Audit logs enabled and monitored
- [ ] Budget alerts configured

---

**Congratulations!** 🎉 Your Amazon PPC Optimizer is now fully deployed and operational.

The optimizer will automatically:
- Refresh Amazon API tokens
- Run on schedule (if Cloud Scheduler configured)
- Send results to dashboard and BigQuery
- Send email notifications
- Handle errors gracefully

**Last Updated**: November 6, 2024
**Version**: 1.0.0
