# Amazon PPC Optimizer - Complete Deployment & Setup Guide

This comprehensive guide walks you through the complete setup and deployment process for the Amazon PPC Optimizer, from initial GitHub configuration to production verification.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: GitHub Token Setup for CI/CD Automation](#step-1-github-token-setup-for-cicd-automation)
3. [Step 2: BigQuery Credentials and Infrastructure](#step-2-bigquery-credentials-and-infrastructure)
4. [Step 3: Local Dry-Run Testing](#step-3-local-dry-run-testing)
5. [Step 4: Cloud Functions Deployment](#step-4-cloud-functions-deployment)
6. [Step 5: Production Verification](#step-5-production-verification)
7. [Troubleshooting Common Issues](#troubleshooting-common-issues)
8. [Security Checklist for Production](#security-checklist-for-production)

---

## Prerequisites

Before you begin, ensure you have:

### Required Accounts & Access
- ✅ Google Cloud account with billing enabled
- ✅ GitHub account with repository access
- ✅ Amazon Advertising API credentials (Client ID, Client Secret, Refresh Token, Profile ID)
- ✅ Gmail account for notifications (optional but recommended)

### Required Software
- ✅ [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and configured
- ✅ [Git](https://git-scm.com/downloads) installed
- ✅ Python 3.11+ installed locally (for testing)
- ✅ [bq command-line tool](https://cloud.google.com/bigquery/docs/bq-command-line-tool) (included with gcloud)

### Required Permissions
- ✅ Project Owner or Editor role on Google Cloud project
- ✅ Admin access to GitHub repository

---

## Step 1: GitHub Token Setup for CI/CD Automation

This step configures GitHub Actions for automated health checks and notifications.

### 1.1 Create a GitHub Personal Access Token (PAT)

The PAT is used for GitHub Actions to interact with your repository and Google Cloud.

**Steps:**

1. Go to GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Click **Generate new token** → **Generate new token (classic)**
3. Configure the token:
   - **Note**: "Amazon PPC Optimizer CI/CD"
   - **Expiration**: 90 days (or your preference)
   - **Select scopes**:
     - ✅ `repo` (Full control of private repositories)
     - ✅ `workflow` (Update GitHub Action workflows)
     - ✅ `write:packages` (if using container registry)
4. Click **Generate token**
5. **⚠️ IMPORTANT**: Copy the token immediately - you won't see it again!

### 1.2 Configure Repository Secrets

Store sensitive credentials securely in GitHub Secrets.

**Steps:**

1. Go to your repository: **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each of the following:

#### Required Secrets for Google Cloud Authentication

| Secret Name | Description | Example / How to Get |
|-------------|-------------|----------------------|
| `GCP_PROJECT_ID` | Your Google Cloud project ID | `amazon-ppc-474902` |
| `GCP_SA_KEY` | Service account JSON key | See instructions below |
| `FUNCTION_URL` | Deployed Cloud Function URL | `https://amazon-ppc-optimizer-xyz-uc.a.run.app` |

#### Required Secrets for Email Notifications

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `GMAIL_USER` | Gmail address for notifications | Your email: `natureswaysoil@gmail.com` |
| `GMAIL_PASS` | Gmail App Password | See Gmail App Password setup below |

#### Optional Secrets for Dashboard Integration

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `DASHBOARD_API_ENDPOINT` | Dashboard health check endpoint | `https://amazonppcdashboard.vercel.app/api/health-check` |
| `DASHBOARD_API_KEY` | Dashboard API authentication token | Your dashboard API key |

### 1.3 Create Google Cloud Service Account for GitHub Actions

This service account allows GitHub Actions to authenticate with Google Cloud.

**Run these commands in Google Cloud Shell or local terminal:**

```bash
# Set your project ID
export PROJECT_ID="amazon-ppc-474902"
gcloud config set project $PROJECT_ID

# Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions CI/CD" \
  --description="Service account for GitHub Actions workflows"

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudfunctions.viewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/logging.viewer"

# Create and download JSON key
gcloud iam service-accounts keys create ~/github-actions-key.json \
  --iam-account=github-actions@${PROJECT_ID}.iam.gserviceaccount.com

# Display the key content (copy this to GCP_SA_KEY secret)
cat ~/github-actions-key.json

# Delete the local key file for security
rm ~/github-actions-key.json
```

**⚠️ Security Note**: The JSON key provides access to your Google Cloud project. Store it securely in GitHub Secrets and never commit it to your repository.

### 1.4 Set Up Gmail App Password

Gmail App Passwords allow GitHub Actions to send email notifications without using your main Gmail password.

**Steps:**

1. Go to [Google Account App Passwords](https://myaccount.google.com/apppasswords)
2. Sign in to your Gmail account
3. Click **Select app** → Choose **Other (Custom name)**
4. Enter name: **GitHub Actions Notifications**
5. Click **Generate**
6. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)
7. Add this password to GitHub Secrets as `GMAIL_PASS`

**Important Notes:**
- ✅ Use App Password, NOT your regular Gmail password
- ✅ Enable 2-Step Verification on your Google Account (required for App Passwords)
- ✅ App Passwords can be revoked anytime from your Google Account settings

### 1.5 Verify GitHub Actions Configuration

After setting up secrets, verify the health check workflow is configured:

**Steps:**

1. Check if `.github/workflows/health-check.yml` exists
2. Go to **Actions** tab in your GitHub repository
3. You should see **Health Check and Notifications** workflow
4. Click **Run workflow** to test manually (optional)

**What the workflow does:**
- ✅ Runs after successful deployments
- ✅ Tests the Cloud Function health endpoint
- ✅ Sends email notification with results
- ✅ Posts to dashboard (if configured)

---

## Step 2: BigQuery Credentials and Infrastructure

BigQuery is used for storing and analyzing PPC optimization data, campaign metrics, and historical performance.

### 2.1 Enable BigQuery API

Enable the required Google Cloud APIs for BigQuery integration.

**Run these commands:**

```bash
# Set your project
export PROJECT_ID="amazon-ppc-474902"
gcloud config set project $PROJECT_ID

# Enable BigQuery API
gcloud services enable bigquery.googleapis.com

# Enable BigQuery Data Transfer API (for scheduled queries)
gcloud services enable bigquerydatatransfer.googleapis.com

# Enable BigQuery Connection API
gcloud services enable bigqueryconnection.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled | grep bigquery
```

**Expected output:**
```
bigquery.googleapis.com
bigqueryconnection.googleapis.com
bigquerydatatransfer.googleapis.com
```

### 2.2 Run setup-bigquery.sh Script

The repository includes a script that creates the BigQuery dataset and tables with proper schema.

**Run the setup script:**

```bash
# Navigate to repository
cd ~/Amazom-PPC

# Make script executable (if not already)
chmod +x setup-bigquery.sh

# Run the script with your configuration
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
```

**Parameters:**
- `amazon-ppc-474902` - Your Google Cloud project ID
- `amazon_ppc` - BigQuery dataset name (use this default)
- `us-east4` - BigQuery region (match your Cloud Function region if possible)

**What the script creates:**

1. **Dataset**: `amazon_ppc`
2. **Tables**:
   - `optimization_runs` - Logs of each optimization execution
   - `campaign_metrics` - Campaign performance data
   - `keyword_metrics` - Keyword-level performance data
   - `bid_changes` - History of bid adjustments
   - `budget_changes` - History of budget modifications

**Expected output:**
```
=========================================
BigQuery Setup for Amazon PPC Optimizer
=========================================
Project ID: amazon-ppc-474902
Dataset ID: amazon_ppc
Location: us-east4

✓ Dataset amazon_ppc already exists
✓ Creating table: optimization_runs
Table created successfully
✓ Creating table: campaign_metrics
Table created successfully
...
✅ BigQuery setup complete!
```

### 2.3 Grant Service Account Permissions

Grant the Cloud Functions service account permission to write to BigQuery.

**Run these commands:**

```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Service account used by Cloud Functions
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant BigQuery Data Editor role
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.dataEditor"

# Grant BigQuery Job User role (required to run queries)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.jobUser"

# Verify permissions
echo "Verifying service account: $SERVICE_ACCOUNT"
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:$SERVICE_ACCOUNT" \
  --format="table(bindings.role)"
```

**Expected output:**
```
ROLE
roles/bigquery.dataEditor
roles/bigquery.jobUser
roles/compute.serviceAgent
...
```

### 2.4 Verify BigQuery Setup

Verify the dataset and tables were created correctly.

**Run these commands:**

```bash
# List datasets
bq ls --project_id=$PROJECT_ID

# List tables in amazon_ppc dataset
bq ls $PROJECT_ID:amazon_ppc

# Check table schema
bq show --schema $PROJECT_ID:amazon_ppc.optimization_runs

# Test write permission with a sample query
bq query --use_legacy_sql=false --project_id=$PROJECT_ID \
"SELECT COUNT(*) as count FROM \`$PROJECT_ID.amazon_ppc.optimization_runs\`"
```

**Expected output:**
```
# Dataset list should show amazon_ppc
# Table list should show all 5 tables
# Schema should display JSON with field definitions
# Query should return "0" (no data yet)
```

### 2.5 Configure BigQuery in Application

The application automatically detects BigQuery configuration from environment variables.

**Environment variables** (set during Cloud Function deployment):

```bash
# Project ID (usually auto-detected)
BIGQUERY_PROJECT_ID=amazon-ppc-474902

# Dataset ID (default: amazon_ppc)
BIGQUERY_DATASET=amazon_ppc

# Region (default: us-east4)
BIGQUERY_LOCATION=us-east4
```

**Note**: These are typically set automatically from your `config.json` or can be added as Cloud Function environment variables.

---

## Step 3: Local Dry-Run Testing

Test the optimizer locally before deploying to ensure credentials work and configuration is correct.

### 3.1 Clone the Repository

```bash
# Clone repository
git clone https://github.com/natureswaysoil/Amazom-PPC.git
cd Amazom-PPC
```

### 3.2 Install Dependencies

Install required Python packages locally.

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed requests google-cloud-bigquery google-auth ...
```

### 3.3 Set Environment Variables

Configure your local environment with Amazon API credentials.

**Create a `.env` file** (not committed to Git):

```bash
# Create .env file
cat > .env << 'EOF'
# Amazon Advertising API Credentials
AMAZON_CLIENT_ID=amzn1.application-oa2-client.xxxxx
AMAZON_CLIENT_SECRET=amzn1.oa2-cs.v1.xxxxx
AMAZON_REFRESH_TOKEN=Atzr|IwEBIxxxxx
AMAZON_PROFILE_ID=1780498399290938

# Dashboard Configuration (optional for local testing)
DASHBOARD_URL=https://amazonppcdashboard.vercel.app
DASHBOARD_API_KEY=your_dashboard_api_key

# BigQuery Configuration (optional for local testing)
BIGQUERY_PROJECT_ID=amazon-ppc-474902
BIGQUERY_DATASET=amazon_ppc

# Enable dry run mode for testing
PPC_DRY_RUN=true
EOF

# Load environment variables
set -a; source .env; set +a
```

**Or export manually:**

```bash
export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
export AMAZON_CLIENT_SECRET="amzn1.oa2-cs.v1.xxxxx"
export AMAZON_REFRESH_TOKEN="Atzr|IwEBIxxxxx"
export AMAZON_PROFILE_ID="1780498399290938"
export PPC_DRY_RUN=true
```

### 3.4 Verify Amazon Ads Connection

Test connectivity to Amazon Advertising API without running optimization.

**Run the verification command:**

```bash
python optimizer_core.py \
  --config sample_config.yaml \
  --profile-id $AMAZON_PROFILE_ID \
  --verify-connection \
  --verify-sample-size 5
```

**Expected output:**
```
✅ Successfully authenticated with Amazon Ads API
📊 Connection verified! Retrieved 5 sample campaigns:

Campaign: "Brand Campaign 1"
  ID: 123456789
  Status: enabled
  Budget: $50.00
  
Campaign: "Auto Campaign - Electronics"
  ID: 987654321
  Status: enabled
  Budget: $75.00
  
...

✅ Amazon Ads API connection verified successfully!
```

**Troubleshooting verification failures:**

- ❌ **401 Unauthorized**: Check Client ID and Client Secret
- ❌ **Invalid refresh token**: Regenerate refresh token in Amazon console
- ❌ **Profile not found**: Verify Profile ID is correct
- ❌ **Rate limit exceeded**: Wait a few minutes and retry

### 3.5 Run Local Dry-Run Test

Execute a full optimization cycle locally in dry-run mode (no changes applied).

**Run dry-run optimization:**

```bash
# Dry run with all features
python main.py --dry-run

# Or run specific features
python main.py --dry-run --features bid_optimization,dayparting

# Or use environment variable
export PPC_DRY_RUN=true
python main.py
```

**Expected output:**
```
=== Amazon PPC Optimizer Started at 2025-11-06 10:30:00 ===
🔒 DRY RUN MODE - No changes will be applied

📋 Configuration loaded successfully
✅ Successfully authenticated with Amazon Ads API
🔄 Token refreshed, expires at: 2025-11-06 11:30:00

🎯 Running optimization features:
  - bid_optimization
  - dayparting
  - campaign_management
  - keyword_discovery
  - negative_keywords
  - budget_optimization
  - placement_bids

📊 Analyzing 15 active campaigns...

[Bid Optimization]
  Campaign: "Brand Campaign 1"
    - Keyword "running shoes" ACOS: 22% → Increase bid by $0.15 (DRY RUN)
    - Keyword "athletic shoes" ACOS: 45% → Decrease bid by $0.08 (DRY RUN)
    
[Dayparting]
  Campaign: "Auto Campaign"
    - Hour 2-6 AM: Low performance → Decrease bid by 30% (DRY RUN)
    - Hour 6-10 PM: High conversion → Increase bid by 20% (DRY RUN)

...

✅ Optimization completed successfully!
📊 Summary:
  - Campaigns analyzed: 15
  - Bid adjustments: 42 (not applied - DRY RUN)
  - Keywords discovered: 8 (not applied - DRY RUN)
  - Negative keywords: 5 (not applied - DRY RUN)
  - Budget changes: 3 (not applied - DRY RUN)
  
🕐 Execution time: 127 seconds
```

### 3.6 Test Configuration Options

Test different configuration scenarios to ensure flexibility.

**Test with custom config file:**

```bash
# Create custom config
cp sample_config.yaml my_config.yaml
# Edit my_config.yaml with your preferences

# Run with custom config
python main.py --config my_config.yaml --dry-run
```

**Test with specific features:**

```bash
# Test only bid optimization
python main.py --dry-run --features bid_optimization

# Test multiple features
python main.py --dry-run --features bid_optimization,dayparting,budget_optimization
```

**Test with different profile IDs:**

```bash
# Override profile ID
python main.py --dry-run --profile-id 9876543210
```

### 3.7 Review Logs and Output

Check that the optimizer is generating appropriate logs and output.

**What to verify:**

- ✅ Successfully authenticates with Amazon API
- ✅ Retrieves campaigns and performance data
- ✅ Analyzes data and generates recommendations
- ✅ Shows "DRY RUN" indicators for all changes
- ✅ Completes without errors
- ✅ Shows execution summary with metrics

**Common issues during dry-run:**

- ❌ **No campaigns found**: Check profile ID and API permissions
- ❌ **Insufficient data**: Campaigns need at least 7 days of data
- ❌ **Configuration errors**: Verify config.json or environment variables
- ❌ **API rate limiting**: Add delays between requests or reduce lookback days

---

## Step 4: Cloud Functions Deployment

Deploy the optimizer to Google Cloud Functions with secure configuration using Secret Manager.

### 4.1 Create Secrets in Secret Manager

Store all sensitive credentials in Google Cloud Secret Manager.

**Enable Secret Manager API:**

```bash
export PROJECT_ID="amazon-ppc-474902"
gcloud config set project $PROJECT_ID

# Enable Secret Manager
gcloud services enable secretmanager.googleapis.com
```

**Create secrets for Amazon API:**

```bash
# Amazon Client ID
echo -n "amzn1.application-oa2-client.xxxxx" | \
  gcloud secrets create amazon-client-id \
  --data-file=- \
  --replication-policy="automatic"

# Amazon Client Secret
echo -n "amzn1.oa2-cs.v1.xxxxx" | \
  gcloud secrets create amazon-client-secret \
  --data-file=- \
  --replication-policy="automatic"

# Amazon Refresh Token
echo -n "Atzr|IwEBIxxxxx" | \
  gcloud secrets create amazon-refresh-token \
  --data-file=- \
  --replication-policy="automatic"

# Amazon Profile ID
echo -n "1780498399290938" | \
  gcloud secrets create amazon-profile-id \
  --data-file=- \
  --replication-policy="automatic"
```

**Create secrets for Dashboard (optional):**

```bash
# Dashboard URL
echo -n "https://amazonppcdashboard.vercel.app" | \
  gcloud secrets create dashboard-url \
  --data-file=- \
  --replication-policy="automatic"

# Dashboard API Key
echo -n "your_dashboard_api_key_here" | \
  gcloud secrets create dashboard-api-key \
  --data-file=- \
  --replication-policy="automatic"
```

**Verify secrets were created:**

```bash
gcloud secrets list
```

**Expected output:**
```
NAME                     CREATED              REPLICATION_POLICY
amazon-client-id         2025-11-06T10:00:00  automatic
amazon-client-secret     2025-11-06T10:00:01  automatic
amazon-refresh-token     2025-11-06T10:00:02  automatic
amazon-profile-id        2025-11-06T10:00:03  automatic
dashboard-url            2025-11-06T10:00:04  automatic
dashboard-api-key        2025-11-06T10:00:05  automatic
```

### 4.2 Grant Secret Manager Access

Grant the Cloud Functions service account permission to read secrets.

**Run these commands:**

```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Compute service account (used by Cloud Functions)
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant Secret Manager accessor role for each secret
for secret in amazon-client-id amazon-client-secret amazon-refresh-token amazon-profile-id dashboard-url dashboard-api-key
do
  gcloud secrets add-iam-policy-binding $secret \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor"
  echo "✅ Granted access to $secret"
done
```

**Verify permissions:**

```bash
# Check access for one secret
gcloud secrets get-iam-policy amazon-client-id
```

### 4.3 Deploy Cloud Function with Secure Flags

Deploy using the recommended secure configuration.

**Deployment command with all security best practices:**

```bash
export PROJECT_ID="amazon-ppc-474902"
export REGION="us-central1"
export FUNCTION_NAME="amazon-ppc-optimizer"

gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --min-instances=0 \
  --max-instances=1 \
  --set-secrets="AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=amazon-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest" \
  --service-account="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
```

**Deployment flags explained:**

| Flag | Purpose | Security Impact |
|------|---------|-----------------|
| `--gen2` | Use Cloud Functions Gen2 (Cloud Run) | Better security, scalability |
| `--no-allow-unauthenticated` | Require authentication | ✅ Prevents unauthorized access |
| `--set-secrets` | Mount secrets from Secret Manager | ✅ Credentials never in code |
| `--min-instances=0` | Scale to zero when idle | ✅ Cost optimization |
| `--max-instances=1` | Limit concurrent executions | ✅ Prevents rate limiting |
| `--timeout=540s` | 9-minute maximum runtime | Allows long-running optimization |
| `--memory=512MB` | Memory allocation | Sufficient for typical workloads |

**Expected deployment output:**

```
Deploying function (may take a while - up to 2 minutes)...
⠹ Creating 2nd gen function...
✓ Function deployed successfully!
availableMemoryMb: 512
buildId: ...
name: projects/amazon-ppc-474902/locations/us-central1/functions/amazon-ppc-optimizer
serviceConfig:
  uri: https://amazon-ppc-optimizer-xyz123-uc.a.run.app
state: ACTIVE
```

**⚠️ Important**: Copy the `uri` value - this is your Function URL needed for step 5 and GitHub Actions.

### 4.4 Quick Deploy Script

Alternatively, use the provided quick deploy script:

```bash
# Make script executable
chmod +x QUICK_DEPLOY.sh

# Run deployment
./QUICK_DEPLOY.sh amazon-ppc-474902 us-central1
```

### 4.5 Configure Cloud Scheduler

Set up automatic scheduled execution of the optimizer.

**Create service account for Cloud Scheduler:**

```bash
export PROJECT_ID="amazon-ppc-474902"
export SERVICE_ACCOUNT_NAME="ppc-optimizer-scheduler"

# Create service account
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
  --display-name="PPC Optimizer Scheduler" \
  --project=$PROJECT_ID

# Grant invoker permission to the function
gcloud functions add-invoker-policy-binding $FUNCTION_NAME \
  --region=$REGION \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project=$PROJECT_ID
```

**Get the Function URL:**

```bash
FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME \
  --region=$REGION \
  --gen2 \
  --format='value(serviceConfig.uri)' \
  --project=$PROJECT_ID)

echo "Function URL: $FUNCTION_URL"
```

**Create Cloud Scheduler job:**

```bash
# Daily execution at 3 AM UTC
gcloud scheduler jobs create http ppc-optimizer-daily \
  --location=$REGION \
  --schedule="0 3 * * *" \
  --uri="$FUNCTION_URL" \
  --http-method=POST \
  --time-zone="America/New_York" \
  --oidc-service-account-email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="$FUNCTION_URL" \
  --project=$PROJECT_ID

# Optional: Create dry-run job (every 6 hours for testing)
gcloud scheduler jobs create http ppc-optimizer-dryrun \
  --location=$REGION \
  --schedule="0 */6 * * *" \
  --uri="${FUNCTION_URL}?dry_run=true" \
  --http-method=POST \
  --time-zone="America/New_York" \
  --oidc-service-account-email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="$FUNCTION_URL" \
  --project=$PROJECT_ID
```

**Schedule examples:**

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Daily at 3 AM | `0 3 * * *` | Once per day |
| Every 6 hours | `0 */6 * * *` | 4 times per day |
| Twice daily | `0 9,21 * * *` | 9 AM and 9 PM |
| Weekdays at noon | `0 12 * * 1-5` | Monday-Friday only |

**Verify scheduler jobs:**

```bash
gcloud scheduler jobs list --location=$REGION --project=$PROJECT_ID
```

### 4.6 Update GitHub Repository Secret

Add the deployed function URL to GitHub for automated health checks.

**Steps:**

1. Copy the Function URL from deployment output
2. Go to GitHub repository → **Settings** → **Secrets and variables** → **Actions**
3. Create or update secret: `FUNCTION_URL`
4. Paste the URL: `https://amazon-ppc-optimizer-xyz123-uc.a.run.app`

---

## Step 5: Production Verification

Comprehensive testing to ensure everything works correctly in production.

### 5.1 Health Check Endpoint

Verify the Cloud Function is deployed and accessible.

**Run health check:**

```bash
export FUNCTION_URL="https://amazon-ppc-optimizer-xyz123-uc.a.run.app"

curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?health=true"
```

**Expected response:**

```json
{
  "status": "healthy",
  "service": "amazon-ppc-optimizer",
  "timestamp": "2025-11-06T10:15:30.123Z",
  "dashboard_ok": true,
  "bigquery_ok": true,
  "environment": "cloud_function"
}
```

**What each field means:**

- `status: "healthy"` - Function is running ✅
- `dashboard_ok: true` - Dashboard endpoint is reachable ✅
- `bigquery_ok: true` - BigQuery connection works ✅
- `environment: "cloud_function"` - Running in production ✅

### 5.2 Verify Amazon Ads Connection

Test API connectivity without running optimization.

**Run connection test:**

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=5"
```

**Expected response:**

```json
{
  "status": "success",
  "message": "Amazon Ads API connection verified",
  "sample_campaigns": [
    {
      "campaignId": "123456789",
      "name": "Brand Campaign 1",
      "state": "enabled",
      "budget": 50.0
    },
    ...
  ],
  "total_campaigns_available": 15,
  "profile_id": "1780498399290938",
  "timestamp": "2025-11-06T10:16:45.678Z"
}
```

**Troubleshooting connection failures:**

- ❌ **401 error**: Check secrets in Secret Manager
- ❌ **Timeout**: Increase function timeout or check Amazon API status
- ❌ **Empty campaigns**: Verify profile ID is correct

### 5.3 Run Production Dry-Run Test

Execute full optimization in dry-run mode (no changes applied).

**Run dry-run via Cloud Function:**

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": true,
    "features": ["bid_optimization", "dayparting"],
    "profile_id": "1780498399290938"
  }' \
  "${FUNCTION_URL}"
```

**Expected response:**

```json
{
  "status": "success",
  "message": "Optimization completed successfully (DRY RUN)",
  "execution_time_seconds": 127,
  "summary": {
    "campaigns_analyzed": 15,
    "bid_adjustments": 42,
    "keywords_discovered": 8,
    "negative_keywords_added": 5,
    "budget_changes": 3
  },
  "dry_run": true,
  "timestamp": "2025-11-06T10:20:15.890Z"
}
```

### 5.4 Check BigQuery Data

Verify optimization data is being written to BigQuery.

**Query optimization runs:**

```bash
export PROJECT_ID="amazon-ppc-474902"

# Check latest optimization run
bq query --use_legacy_sql=false --project_id=$PROJECT_ID \
"SELECT 
  run_id,
  start_time,
  end_time,
  status,
  campaigns_analyzed,
  total_bid_changes
FROM \`$PROJECT_ID.amazon_ppc.optimization_runs\`
ORDER BY start_time DESC
LIMIT 5"
```

**Query campaign metrics:**

```bash
# Check latest campaign metrics
bq query --use_legacy_sql=false --project_id=$PROJECT_ID \
"SELECT 
  campaign_id,
  campaign_name,
  impressions,
  clicks,
  spend,
  sales,
  acos,
  date
FROM \`$PROJECT_ID.amazon_ppc.campaign_metrics\`
ORDER BY date DESC
LIMIT 10"
```

**Expected output:**

```
+----------+---------------------+---------------------+-----------+-------------------+------------------+
|  run_id  |     start_time      |      end_time       |  status   | campaigns_analyzed| total_bid_changes|
+----------+---------------------+---------------------+-----------+-------------------+------------------+
| run_001  | 2025-11-06 10:20:00 | 2025-11-06 10:22:07 | completed |        15         |        42        |
| run_002  | 2025-11-06 03:00:00 | 2025-11-06 03:02:15 | completed |        15         |        38        |
+----------+---------------------+---------------------+-----------+-------------------+------------------+
```

### 5.5 Test Cloud Scheduler Execution

Manually trigger the scheduled job to verify it works.

**Trigger scheduler job:**

```bash
export PROJECT_ID="amazon-ppc-474902"
export REGION="us-central1"

# Trigger the daily job
gcloud scheduler jobs run ppc-optimizer-daily \
  --location=$REGION \
  --project=$PROJECT_ID

# Or trigger dry-run job
gcloud scheduler jobs run ppc-optimizer-dryrun \
  --location=$REGION \
  --project=$PROJECT_ID
```

**Check scheduler job status:**

```bash
gcloud scheduler jobs describe ppc-optimizer-daily \
  --location=$REGION \
  --project=$PROJECT_ID
```

**View recent executions:**

```bash
# Check Cloud Scheduler logs
gcloud logging read "resource.type=cloud_scheduler_job AND resource.labels.job_id=ppc-optimizer-daily" \
  --limit=10 \
  --format=json \
  --project=$PROJECT_ID
```

### 5.6 Monitor Cloud Function Logs

View function execution logs to verify everything is working.

**View recent logs:**

```bash
# Last 50 log entries
gcloud functions logs read $FUNCTION_NAME \
  --region=$REGION \
  --gen2 \
  --limit=50 \
  --project=$PROJECT_ID

# Follow logs in real-time
gcloud functions logs read $FUNCTION_NAME \
  --region=$REGION \
  --gen2 \
  --follow \
  --project=$PROJECT_ID

# Filter for errors only
gcloud functions logs read $FUNCTION_NAME \
  --region=$REGION \
  --gen2 \
  --limit=50 \
  --project=$PROJECT_ID | grep -i error
```

**Key log messages to look for:**

✅ **Success indicators:**
- "Successfully authenticated with Amazon Ads API"
- "Optimization completed successfully"
- "Dashboard updated successfully"
- "BigQuery write completed"

❌ **Error indicators:**
- "Authentication failed"
- "Rate limit exceeded"
- "Timeout"
- "BigQuery write failed"

### 5.7 Test Live Optimization (Production Run)

After confirming dry-run works, execute a real optimization.

**⚠️ CAUTION**: This will make actual changes to your Amazon PPC campaigns!

**Run live optimization:**

```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": false,
    "features": ["bid_optimization"],
    "profile_id": "1780498399290938"
  }' \
  "${FUNCTION_URL}"
```

**Best practices for first live run:**

1. ✅ Start with a single feature (e.g., `bid_optimization` only)
2. ✅ Monitor Amazon Ads console during execution
3. ✅ Check function logs for any errors
4. ✅ Review changes in BigQuery after completion
5. ✅ Verify dashboard shows updated data
6. ✅ Gradually enable more features after validation

**Expected response:**

```json
{
  "status": "success",
  "message": "Optimization completed successfully",
  "execution_time_seconds": 145,
  "summary": {
    "campaigns_analyzed": 15,
    "bid_adjustments_applied": 42,
    "keywords_discovered": 8,
    "negative_keywords_added": 5,
    "budget_changes_applied": 3
  },
  "dry_run": false,
  "timestamp": "2025-11-06T10:45:30.123Z"
}
```

### 5.8 Dashboard Verification

Check the dashboard to see optimization results.

**Dashboard URL**: https://amazonppcdashboard.vercel.app

**What to verify on dashboard:**

1. ✅ Latest optimization run is displayed
2. ✅ Metrics show correct values (campaigns, keywords, spend, etc.)
3. ✅ Charts display performance trends
4. ✅ Campaign breakdown shows individual campaigns
5. ✅ No error messages displayed

**If dashboard is not updating:**

1. Check `DASHBOARD_URL` secret in Secret Manager
2. Verify `DASHBOARD_API_KEY` is correct
3. Check Cloud Function logs for dashboard POST errors
4. Test dashboard health endpoint manually

### 5.9 Email Notification Test

Verify GitHub Actions health check sends email correctly.

**Trigger health check workflow:**

1. Go to GitHub → **Actions** tab
2. Select **Health Check and Notifications** workflow
3. Click **Run workflow**
4. Select `main` branch
5. Click **Run workflow** button

**Check email:**

- ✅ Email received at configured address
- ✅ Subject indicates PASSED or FAILED
- ✅ Body contains health check results
- ✅ Includes Function URL and timestamp

### 5.10 Complete Production Checklist

Before considering deployment complete, verify all items:

- [ ] ✅ Health endpoint returns `"healthy"`
- [ ] ✅ Amazon Ads connection verified
- [ ] ✅ Dry-run test completes successfully
- [ ] ✅ BigQuery tables contain data
- [ ] ✅ Cloud Scheduler triggers function
- [ ] ✅ Function logs show no errors
- [ ] ✅ Dashboard displays optimization results
- [ ] ✅ Email notifications working
- [ ] ✅ Live optimization test successful
- [ ] ✅ All secrets configured in Secret Manager
- [ ] ✅ Service account permissions granted
- [ ] ✅ GitHub Actions workflow passing

---

## Troubleshooting Common Issues

### Issue: HTTP 429 Rate Limiting Errors

**Symptoms:**
- Function returns "429 Too Many Requests"
- Logs show 0ms execution time
- Response size is 14B

**Root Cause:**
Function deployed with `--allow-unauthenticated` flag, causing GCP to rate-limit before function executes.

**Solution:**

```bash
# Redeploy with authentication required
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

# Update Cloud Scheduler to use OIDC authentication
gcloud scheduler jobs update http ppc-optimizer-daily \
  --location=us-central1 \
  --oidc-service-account-email="ppc-optimizer-scheduler@amazon-ppc-474902.iam.gserviceaccount.com" \
  --oidc-token-audience="$FUNCTION_URL"
```

### Issue: "Permission Denied" during Deployment

**Symptoms:**
- Deployment fails with "403 Forbidden"
- Error: "User does not have permission"

**Solution:**

```bash
# Grant yourself deployment permissions
export PROJECT_ID="amazon-ppc-474902"
export YOUR_EMAIL="your-email@gmail.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$YOUR_EMAIL" \
  --role="roles/cloudfunctions.developer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$YOUR_EMAIL" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$YOUR_EMAIL" \
  --role="roles/storage.admin"
```

### Issue: "Secret Not Found" Error

**Symptoms:**
- Function fails with "Secret not found"
- Error: "Unable to access secret"

**Solution:**

```bash
# Check if secrets exist
gcloud secrets list --project=$PROJECT_ID

# If missing, create the secret
echo -n "YOUR_VALUE" | gcloud secrets create SECRET_NAME \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# Grant access to service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

### Issue: Amazon API Authentication Failed

**Symptoms:**
- Function returns "401 Unauthorized"
- Logs show "Authentication failed"

**Solution:**

```bash
# Update secrets with correct values
echo -n "NEW_REFRESH_TOKEN" | gcloud secrets versions add amazon-refresh-token \
  --data-file=- \
  --project=$PROJECT_ID

# Verify secrets have correct values (last 4 characters only)
gcloud secrets versions access latest --secret=amazon-refresh-token --project=$PROJECT_ID | tail -c 4
```

### Issue: BigQuery "Dataset Not Found"

**Symptoms:**
- Error: "Dataset amazon_ppc was not found"
- Function fails during BigQuery write

**Solution:**

```bash
# Run BigQuery setup script
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4

# Grant permissions
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.jobUser"
```

### Issue: Function Timeout

**Symptoms:**
- Function returns "Function execution took too long"
- Error: "DeadlineExceeded"

**Solution:**

```bash
# Increase timeout to maximum (9 minutes for Gen2)
gcloud functions deploy amazon-ppc-optimizer \
  --timeout=540s \
  --update-env-vars=LOOKBACK_DAYS=7 \
  --project=$PROJECT_ID

# Or reduce data processing:
# - Decrease lookback_days in config
# - Reduce number of enabled features
# - Filter campaigns by name pattern
```

### Issue: Dashboard Not Updating

**Symptoms:**
- Optimization completes but dashboard shows no data
- Logs show "Dashboard update failed"

**Solution:**

```bash
# Check dashboard secrets
gcloud secrets versions access latest --secret=dashboard-url --project=$PROJECT_ID
gcloud secrets versions access latest --secret=dashboard-api-key --project=$PROJECT_ID

# Update dashboard URL
echo -n "https://amazonppcdashboard.vercel.app" | \
  gcloud secrets versions add dashboard-url --data-file=- --project=$PROJECT_ID

# Test dashboard connectivity
curl -X POST "https://amazonppcdashboard.vercel.app/api/health-check" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Issue: Cloud Scheduler Not Triggering

**Symptoms:**
- Scheduled jobs don't execute
- No function invocations at scheduled time

**Solution:**

```bash
# Check scheduler job exists
gcloud scheduler jobs list --location=$REGION --project=$PROJECT_ID

# Verify service account has invoker permission
gcloud functions get-iam-policy amazon-ppc-optimizer \
  --region=$REGION \
  --project=$PROJECT_ID

# Grant invoker permission if missing
gcloud functions add-invoker-policy-binding amazon-ppc-optimizer \
  --region=$REGION \
  --member="serviceAccount:ppc-optimizer-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project=$PROJECT_ID

# Test scheduler manually
gcloud scheduler jobs run ppc-optimizer-daily \
  --location=$REGION \
  --project=$PROJECT_ID
```

### Issue: Email Notifications Not Sent

**Symptoms:**
- GitHub Actions workflow completes but no email received

**Solution:**

1. Verify GitHub Secrets are set:
   - `GMAIL_USER`
   - `GMAIL_PASS` (must be App Password, not regular password)

2. Check Gmail App Password:
   - Must enable 2-Step Verification first
   - Generate new App Password at https://myaccount.google.com/apppasswords

3. Test workflow manually:
   - Go to Actions → Health Check and Notifications
   - Click "Run workflow"
   - Check workflow logs for email errors

### Issue: Memory Limit Exceeded

**Symptoms:**
- Function fails with "Exceeded memory limit"
- Error: "OOMKilled"

**Solution:**

```bash
# Increase memory allocation
gcloud functions deploy amazon-ppc-optimizer \
  --memory=1GB \
  --project=$PROJECT_ID

# Or reduce memory usage:
# - Process fewer campaigns per run
# - Reduce lookback_days in config
# - Disable memory-intensive features
```

### Issue: Invalid JSON in Request

**Symptoms:**
- Error: "Invalid JSON payload"
- Function returns 400 Bad Request

**Solution:**

```bash
# Ensure JSON is properly formatted
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "${FUNCTION_URL}"

# Use jq to validate JSON
echo '{"dry_run": true}' | jq .
```

### Getting More Help

**View logs for detailed errors:**

```bash
# Function logs
gcloud functions logs read amazon-ppc-optimizer \
  --region=$REGION \
  --gen2 \
  --limit=100 \
  --project=$PROJECT_ID

# Cloud Scheduler logs
gcloud logging read "resource.type=cloud_scheduler_job" \
  --limit=50 \
  --project=$PROJECT_ID

# BigQuery job logs
gcloud logging read "resource.type=bigquery_project" \
  --limit=50 \
  --project=$PROJECT_ID
```

**Check Cloud Console:**
- [Cloud Functions Dashboard](https://console.cloud.google.com/functions/list)
- [Cloud Scheduler Dashboard](https://console.cloud.google.com/cloudscheduler)
- [Secret Manager Dashboard](https://console.cloud.google.com/security/secret-manager)
- [BigQuery Console](https://console.cloud.google.com/bigquery)
- [IAM & Admin](https://console.cloud.google.com/iam-admin)

---

## Security Checklist for Production

Use this checklist to ensure your deployment is secure and ready for production use.

### Authentication & Authorization

- [ ] ✅ Cloud Function deployed with `--no-allow-unauthenticated`
- [ ] ✅ Cloud Scheduler uses OIDC service account authentication
- [ ] ✅ Service accounts follow principle of least privilege
- [ ] ✅ No credentials hardcoded in code or config files
- [ ] ✅ All secrets stored in Google Secret Manager
- [ ] ✅ Secret Manager IAM policies grant access only to required service accounts
- [ ] ✅ Personal Access Tokens (PAT) have minimum required scopes
- [ ] ✅ Gmail uses App Password, not main account password

### Secrets Management

- [ ] ✅ All Amazon API credentials in Secret Manager
- [ ] ✅ Dashboard API key in Secret Manager
- [ ] ✅ No secrets in environment variables (use `--set-secrets` instead)
- [ ] ✅ Secrets have `--replication-policy="automatic"` for availability
- [ ] ✅ Regular rotation schedule for API keys (every 90 days recommended)
- [ ] ✅ `.gitignore` excludes `.env`, `config.json`, and credentials
- [ ] ✅ GitHub repository secrets configured correctly
- [ ] ✅ No secrets in Cloud Function environment variables

### Network Security

- [ ] ✅ Function URL uses HTTPS only (automatic with Cloud Functions)
- [ ] ✅ No public access to function (requires Bearer token)
- [ ] ✅ VPC connector configured (if accessing internal resources)
- [ ] ✅ Egress settings configured appropriately
- [ ] ✅ Rate limiting enabled (handled by optimizer code)

### Data Protection

- [ ] ✅ BigQuery dataset in appropriate region (consider data residency)
- [ ] ✅ BigQuery tables have proper access controls
- [ ] ✅ No PII (Personally Identifiable Information) stored unnecessarily
- [ ] ✅ Audit logs enabled for data access
- [ ] ✅ Encryption at rest (automatic with GCP services)
- [ ] ✅ Encryption in transit (HTTPS for all API calls)

### Monitoring & Logging

- [ ] ✅ Cloud Logging enabled and retained appropriately
- [ ] ✅ Log retention policy configured (90 days minimum)
- [ ] ✅ Alerts configured for critical errors
- [ ] ✅ Dashboard monitoring active
- [ ] ✅ Email notifications configured
- [ ] ✅ BigQuery audit logs enabled
- [ ] ✅ No sensitive data logged (tokens, passwords, etc.)

### Access Control

- [ ] ✅ Project Owner/Admin role limited to necessary users
- [ ] ✅ Service accounts have minimal required permissions
- [ ] ✅ IAM policies reviewed and documented
- [ ] ✅ No overly permissive roles (e.g., `roles/owner` on service accounts)
- [ ] ✅ Regular access reviews scheduled (quarterly recommended)
- [ ] ✅ Unused service accounts disabled or deleted

### Compliance & Governance

- [ ] ✅ Data handling complies with privacy regulations (GDPR, CCPA, etc.)
- [ ] ✅ Terms of Service reviewed for Amazon Ads API
- [ ] ✅ Google Cloud Terms of Service acknowledged
- [ ] ✅ Budget alerts configured to prevent cost overruns
- [ ] ✅ Resource quotas set appropriately
- [ ] ✅ Disaster recovery plan documented

### Code Security

- [ ] ✅ Dependencies up to date (`pip install --upgrade`)
- [ ] ✅ No known vulnerabilities in dependencies
- [ ] ✅ Code review completed before deployment
- [ ] ✅ No debug mode enabled in production
- [ ] ✅ Error messages don't expose sensitive information
- [ ] ✅ Input validation for all user-provided data
- [ ] ✅ Rate limiting prevents API abuse

### Operational Security

- [ ] ✅ Deployment process documented
- [ ] ✅ Rollback procedure tested
- [ ] ✅ Incident response plan in place
- [ ] ✅ Contact information for support team documented
- [ ] ✅ Regular backups of critical data (BigQuery exports)
- [ ] ✅ Testing environment separate from production
- [ ] ✅ Change management process followed

### Regular Maintenance Tasks

**Weekly:**
- [ ] Review Cloud Function logs for errors
- [ ] Check BigQuery data quality
- [ ] Verify dashboard is updating correctly

**Monthly:**
- [ ] Review IAM permissions and access logs
- [ ] Check for dependency updates
- [ ] Review optimization performance and adjust rules

**Quarterly:**
- [ ] Rotate API keys and secrets
- [ ] Conduct access review (who has what permissions)
- [ ] Review and update documentation
- [ ] Test disaster recovery procedures
- [ ] Review costs and optimize resources

**Annually:**
- [ ] Complete security audit
- [ ] Review compliance with updated regulations
- [ ] Update Terms of Service acknowledgments
- [ ] Review and update incident response plan

### Verification Commands

Run these commands to verify security configuration:

```bash
export PROJECT_ID="amazon-ppc-474902"
export REGION="us-central1"
export FUNCTION_NAME="amazon-ppc-optimizer"

# Check function authentication requirement
gcloud functions describe $FUNCTION_NAME \
  --region=$REGION \
  --gen2 \
  --format="value(serviceConfig.ingressSettings)" \
  --project=$PROJECT_ID

# List all secrets
gcloud secrets list --project=$PROJECT_ID

# Check service account permissions
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:${COMPUTE_SA}" \
  --format="table(bindings.role)"

# Check for publicly accessible resources
gcloud functions get-iam-policy $FUNCTION_NAME \
  --region=$REGION \
  --project=$PROJECT_ID | grep allUsers

# If output contains allUsers, function is publicly accessible (fix required)
```

---

## Summary

You've now completed the full deployment and setup of the Amazon PPC Optimizer! 

**What you've accomplished:**

1. ✅ Set up GitHub CI/CD with automated health checks and email notifications
2. ✅ Configured BigQuery infrastructure for data storage and analysis
3. ✅ Tested the optimizer locally in dry-run mode
4. ✅ Deployed to Google Cloud Functions with secure Secret Manager configuration
5. ✅ Verified production deployment with comprehensive testing
6. ✅ Established monitoring, logging, and alerting
7. ✅ Implemented security best practices

**Next steps:**

1. Monitor the first few automated runs via Cloud Scheduler
2. Review optimization results on the dashboard
3. Fine-tune configuration based on performance
4. Set up alerts for critical errors
5. Schedule regular security reviews

**Resources:**

- [README.md](README.md) - Main project documentation
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Detailed deployment reference
- [VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md) - Testing and verification procedures
- [BIGQUERY_INTEGRATION.md](BIGQUERY_INTEGRATION.md) - BigQuery setup and troubleshooting
- [DASHBOARD_INTEGRATION.md](DASHBOARD_INTEGRATION.md) - Dashboard integration details

**Support:**

For issues or questions:
- Check Cloud Function logs: `gcloud functions logs read amazon-ppc-optimizer --region=$REGION --gen2 --limit=50`
- Review troubleshooting section above
- Contact: james@natureswaysoil.com

---

**Last Updated**: November 6, 2025  
**Version**: 1.0.0
