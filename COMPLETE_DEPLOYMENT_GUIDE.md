# Complete CI/CD Deployment Automation Guide

This comprehensive guide walks you through deploying the Amazon PPC Optimizer from scratch to a fully functional production system with live data in the dashboard.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Step 1: GitHub Token Setup for CI/CD Automation](#step-1-github-token-setup-for-cicd-automation)
3. [Step 2: BigQuery Credentials and Infrastructure](#step-2-bigquery-credentials-and-infrastructure)
4. [Step 3: Local Dry-Run Testing](#step-3-local-dry-run-testing)
5. [Step 4: Cloud Functions Deployment](#step-4-cloud-functions-deployment)
6. [Step 5: Production Verification](#step-5-production-verification)
7. [Troubleshooting](#troubleshooting)
8. [Security Checklist for Production](#security-checklist-for-production)

---

## Prerequisites

Before starting, ensure you have:

- **Google Cloud Account** with billing enabled
- **Amazon Advertising API** credentials (Client ID, Client Secret, Refresh Token, Profile ID)
- **GitHub Account** with repository access
- **Gmail Account** for notifications (optional)
- **Command Line Tools**:
  - `gcloud` CLI installed and authenticated
  - `git` installed
  - `python3.11+` installed
  - `bq` command line tool (part of gcloud SDK)

---

## Step 1: GitHub Token Setup for CI/CD Automation

### 1.1 Create Personal Access Token (PAT)

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click **Generate new token** → **Generate new token (classic)**
3. Configure your token:
   - **Note**: "Amazon PPC CI/CD Automation"
   - **Expiration**: 90 days (or No expiration for production)
   - **Scopes** (select these):
     - ✅ `repo` (Full control of private repositories)
     - ✅ `workflow` (Update GitHub Action workflows)
     - ✅ `write:packages` (Upload packages to GitHub Package Registry)
     - ✅ `read:org` (Read org and team membership)
4. Click **Generate token**
5. **IMPORTANT**: Copy the token immediately (you won't see it again)

### 1.2 Configure Repository Secrets

Go to your repository: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Configure these **9 required secrets**:

| Secret Name | Description | How to Get | Required |
|------------|-------------|------------|----------|
| `GCP_PROJECT_ID` | Your Google Cloud Project ID | From GCP Console | ✅ Yes |
| `GCP_SA_KEY` | Service account JSON key | Create service account (see 1.3) | ✅ Yes |
| `AMAZON_CLIENT_ID` | Amazon Ads API Client ID | From Amazon Advertising API Console | ✅ Yes |
| `AMAZON_CLIENT_SECRET` | Amazon Ads API Client Secret | From Amazon Advertising API Console | ✅ Yes |
| `AMAZON_REFRESH_TOKEN` | Amazon Ads API Refresh Token | From Amazon OAuth flow | ✅ Yes |
| `AMAZON_PROFILE_ID` | Amazon Ads Profile ID | From Amazon Advertising Console | ✅ Yes |
| `GMAIL_USER` | Gmail address for notifications | Your Gmail address | ⚠️ Optional |
| `GMAIL_PASS` | Gmail App Password | See section 1.4 | ⚠️ Optional |
| `DASHBOARD_API_KEY` | Dashboard authentication key | Generate secure random string | ⚠️ Optional |

### 1.3 Google Cloud Service Account Setup for GitHub Actions

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Create service account for GitHub Actions
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployment Service Account" \
  --project=$PROJECT_ID

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudfunctions.developer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"

# Create and download the key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com

# Display the key (copy this to GCP_SA_KEY secret)
cat github-actions-key.json

# IMPORTANT: Delete the local copy after adding to GitHub Secrets
rm github-actions-key.json
```

### 1.4 Gmail App Password Setup for Notifications

1. Go to [Google Account App Passwords](https://myaccount.google.com/apppasswords)
2. Sign in to your Gmail account (must have 2FA enabled)
3. Click **Select app** → **Other (Custom name)**
4. Enter: "GitHub Actions PPC Optimizer"
5. Click **Generate**
6. Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)
7. Add this as the `GMAIL_PASS` secret in GitHub (without spaces)

**Important Notes**:
- App passwords only work with 2-factor authentication enabled
- Use app password, NOT your regular Gmail password
- You can revoke app passwords anytime without changing your main password

---

## Step 2: BigQuery Credentials and Infrastructure

### 2.1 Enable Required BigQuery APIs

```bash
# Set your project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable the 3 required APIs
gcloud services enable bigquery.googleapis.com
gcloud services enable bigquerystorage.googleapis.com
gcloud services enable bigquerydatatransfer.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled | grep bigquery
```

Expected output:
```
bigquery.googleapis.com
bigquerystorage.googleapis.com
bigquerydatatransfer.googleapis.com
```

### 2.2 Run setup-bigquery.sh Script

```bash
# Clone the repository if not already done
git clone https://github.com/natureswaysoil/Amazom-PPC.git
cd Amazom-PPC

# Make the script executable
chmod +x setup-bigquery.sh

# Run the setup script
# Syntax: ./setup-bigquery.sh <PROJECT_ID> <DATASET_ID> <LOCATION>
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
```

Expected output:
```
=========================================
BigQuery Setup for Amazon PPC Optimizer
=========================================
Project ID: amazon-ppc-474902
Dataset ID: amazon_ppc
Location: us-east4

Setting project to amazon-ppc-474902...
Creating dataset amazon_ppc...
Dataset 'amazon-ppc-474902:amazon_ppc' successfully created.

Creating table: optimization_results...
Table created successfully

Creating table: campaign_details...
Table created successfully

Creating table: optimization_progress...
Table created successfully

Creating table: optimization_errors...
Table created successfully

=========================================
✅ BigQuery Setup Complete!
=========================================
```

### 2.3 Grant Service Account Permissions

```bash
# Get the service account (Cloud Functions uses compute default SA)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Service Account: $SERVICE_ACCOUNT"

# Grant BigQuery Data Editor role (read/write data)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.dataEditor"

# Grant BigQuery Job User role (run queries)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.jobUser"

# Verify permissions
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:${SERVICE_ACCOUNT}"
```

### 2.4 Verify Dataset and Table Creation

```bash
# List datasets
bq ls $PROJECT_ID:

# List tables in the dataset
bq ls $PROJECT_ID:amazon_ppc

# Show table schema for optimization_results
bq show --schema --format=prettyjson $PROJECT_ID:amazon_ppc.optimization_results
```

Expected tables:
- `optimization_results` - Main optimization run data
- `campaign_details` - Campaign-level performance
- `optimization_progress` - Real-time progress updates
- `optimization_errors` - Error tracking

---

## Step 3: Local Dry-Run Testing

### 3.1 Install Dependencies

```bash
# Navigate to project directory
cd Amazom-PPC

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

Expected packages installed:
- functions-framework
- google-cloud-bigquery
- requests
- python-dateutil
- pytz
- PyYAML
- gunicorn

### 3.2 Set Up Environment Variables (.env template)

Create a `.env` file in the project root:

```bash
# Create .env file
cat > .env << 'EOF'
# Amazon Advertising API Credentials
AMAZON_CLIENT_ID=amzn1.application-oa2-client.YOUR_CLIENT_ID
AMAZON_CLIENT_SECRET=amzn1.oa2-cs.v1.YOUR_CLIENT_SECRET
AMAZON_REFRESH_TOKEN=Atzr|IwEBIYOUR_REFRESH_TOKEN
AMAZON_PROFILE_ID=1780498399290938

# Google Cloud Configuration
GCP_PROJECT=amazon-ppc-474902
GOOGLE_CLOUD_PROJECT=amazon-ppc-474902

# Dashboard Configuration (optional)
DASHBOARD_URL=https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app
DASHBOARD_API_KEY=your_dashboard_api_key_here

# Testing Flags
PPC_DRY_RUN=true
PPC_VERIFY_CONNECTION=false
EOF

# Load environment variables
export $(cat .env | xargs)
```

**IMPORTANT**: Never commit `.env` file to git! It's already in `.gitignore`.

### 3.3 Connection Verification Commands

Test Amazon Ads API connection without running full optimization:

```bash
# Basic connection test
python optimizer_core.py \
  --config sample_config.yaml \
  --profile-id $AMAZON_PROFILE_ID \
  --verify-connection

# Test with custom sample size
python optimizer_core.py \
  --config sample_config.yaml \
  --profile-id $AMAZON_PROFILE_ID \
  --verify-connection \
  --verify-sample-size=5
```

**Expected output**:
```
2024-11-06 10:30:00 - INFO - Verifying Amazon Ads API connection...
2024-11-06 10:30:01 - INFO - Successfully authenticated with Amazon Ads API
2024-11-06 10:30:02 - INFO - Retrieved 5 campaigns
2024-11-06 10:30:02 - INFO - Sample campaigns:
  - Campaign: "Brand - Exact Match" (ID: 123456789)
  - Campaign: "Category - Broad Match" (ID: 987654321)
  ...
2024-11-06 10:30:02 - INFO - ✅ Connection verification successful
```

### 3.4 Dry-Run Testing

Run full optimization in dry-run mode (no changes made):

```bash
# Full dry-run test
python main.py

# Or with explicit dry-run flag
PPC_DRY_RUN=true python main.py

# Test specific features only
PPC_DRY_RUN=true PPC_FEATURES=bid_optimization,dayparting python main.py
```

**Expected dry-run outputs**:

1. **Authentication Success**:
   ```
   Successfully authenticated with Amazon Ads API
   Access token expires at: 2024-11-06 11:30:00
   ```

2. **Campaign Analysis**:
   ```
   Analyzing 42 campaigns...
   Found 15 campaigns requiring optimization
   Total spend: $1,234.56
   Average ACOS: 42.3%
   ```

3. **Optimization Summary** (DRY RUN):
   ```
   DRY RUN MODE - No changes will be made
   
   Bid Optimization:
   - 127 keywords analyzed
   - Would increase 34 bids (average +15%)
   - Would decrease 28 bids (average -20%)
   - Would maintain 65 bids
   
   Dayparting:
   - 42 campaigns analyzed
   - Would apply 18 peak hour adjustments
   - Would apply 24 off-peak adjustments
   
   Campaign Management:
   - Would pause 3 high-ACOS campaigns
   - Would activate 2 good-performing campaigns
   ```

4. **Dashboard Update**:
   ```
   Sending results to dashboard...
   Dashboard updated successfully
   ```

5. **BigQuery Insert**:
   ```
   Inserting optimization results to BigQuery...
   Inserted 1 row to optimization_results
   Inserted 42 rows to campaign_details
   ```

---

## Step 4: Cloud Functions Deployment

### 4.1 Secret Manager Setup

Store sensitive credentials in Google Secret Manager:

```bash
# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Create the 6 required secrets
echo -n "amzn1.application-oa2-client.YOUR_ID" | \
  gcloud secrets create amazon-client-id --data-file=-

echo -n "amzn1.oa2-cs.v1.YOUR_SECRET" | \
  gcloud secrets create amazon-client-secret --data-file=-

echo -n "Atzr|IwEBIYOUR_TOKEN" | \
  gcloud secrets create amazon-refresh-token --data-file=-

echo -n "1780498399290938" | \
  gcloud secrets create amazon-profile-id --data-file=-

echo -n "your_dashboard_api_key" | \
  gcloud secrets create dashboard-api-key --data-file=-

echo -n "https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app" | \
  gcloud secrets create dashboard-url --data-file=-

# Grant Cloud Functions service account access to secrets
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in amazon-client-id amazon-client-secret amazon-refresh-token amazon-profile-id dashboard-api-key dashboard-url; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
done

# Verify secrets created
gcloud secrets list
```

### 4.2 Secure Deployment with --no-allow-unauthenticated

Deploy the Cloud Function with proper security:

```bash
# Deploy with Secret Manager integration
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
  --set-secrets='AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=amazon-profile-id:latest,DASHBOARD_API_KEY=dashboard-api-key:latest,DASHBOARD_URL=dashboard-url:latest' \
  --set-env-vars='GCP_PROJECT=amazon-ppc-474902,GOOGLE_CLOUD_PROJECT=amazon-ppc-474902'

# Get the function URL (Gen2 uses Cloud Run URLs)
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)')

echo "Function deployed at: $FUNCTION_URL"
```

**Key Security Flags**:
- `--no-allow-unauthenticated` - Requires authentication (prevents HTTP 429 rate limiting)
- `--set-secrets` - Mounts secrets from Secret Manager (secure credential storage)
- `--min-instances=0` - Scales to zero when not in use (cost optimization)
- `--max-instances=1` - Limits concurrent executions

### 4.3 Cloud Scheduler Configuration with OIDC Authentication

Set up automatic scheduled execution:

```bash
# Create service account for Cloud Scheduler
gcloud iam service-accounts create ppc-scheduler \
  --display-name="PPC Optimizer Scheduler Service Account"

# Grant invoker permission to the function
gcloud functions add-iam-policy-binding amazon-ppc-optimizer \
  --region=us-central1 \
  --member="serviceAccount:ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudfunctions.invoker"

# Create Cloud Scheduler job (runs daily at 3 AM EST)
gcloud scheduler jobs create http amazon-ppc-optimizer-daily \
  --location=us-central1 \
  --schedule="0 3 * * *" \
  --uri="${FUNCTION_URL}" \
  --http-method=POST \
  --time-zone="America/New_York" \
  --oidc-service-account-email="ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="${FUNCTION_URL}" \
  --headers="Content-Type=application/json" \
  --message-body='{"dry_run": false}'

# Create dry-run job (runs every 4 hours for testing)
gcloud scheduler jobs create http amazon-ppc-optimizer-dryrun \
  --location=us-central1 \
  --schedule="0 */4 * * *" \
  --uri="${FUNCTION_URL}" \
  --http-method=POST \
  --time-zone="America/New_York" \
  --oidc-service-account-email="ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="${FUNCTION_URL}" \
  --headers="Content-Type=application/json" \
  --message-body='{"dry_run": true}'

# List scheduled jobs
gcloud scheduler jobs list --location=us-central1
```

**Schedule Examples**:
- Daily at 3 AM: `"0 3 * * *"`
- Every 6 hours: `"0 */6 * * *"`
- Twice daily (9 AM, 9 PM): `"0 9,21 * * *"`
- Weekdays only at noon: `"0 12 * * 1-5"`
- Every Monday at 8 AM: `"0 8 * * 1"`

### 4.4 Service Account Permissions Summary

Verify all required permissions are granted:

```bash
# Cloud Functions compute service account needs:
# - roles/bigquery.dataEditor (write to BigQuery)
# - roles/bigquery.jobUser (run BigQuery jobs)
# - roles/secretmanager.secretAccessor (read secrets)

# Scheduler service account needs:
# - roles/cloudfunctions.invoker (invoke the function)

# Verify permissions
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:*ppc*" \
  --format="table(bindings.role, bindings.members)"
```

---

## Step 5: Production Verification

### 5.1 Health Check Endpoint Testing

Test the lightweight health check endpoint:

```bash
# Get function URL
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)')

# Test health check (no authentication example - adjust if using auth)
curl "${FUNCTION_URL}?health=true"

# With authentication (recommended for production)
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer ${TOKEN}" \
  "${FUNCTION_URL}?health=true"
```

**Expected response**:
```json
{
  "status": "healthy",
  "service": "amazon-ppc-optimizer",
  "timestamp": "2024-11-06T10:30:00.123Z",
  "version": "2.0.0"
}
```

### 5.2 Amazon Ads API Connection Verification

Verify Amazon Ads API connectivity through the deployed function:

```bash
# Test connection verification
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer ${TOKEN}" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=5"
```

**Expected response**:
```json
{
  "status": "success",
  "message": "Amazon Ads API connection verified",
  "campaigns_retrieved": 5,
  "sample_campaigns": [
    {
      "campaignId": "123456789",
      "name": "Brand - Exact Match",
      "state": "enabled",
      "budget": 50.0
    },
    ...
  ],
  "profile_id": "1780498399290938",
  "timestamp": "2024-11-06T10:30:00.123Z"
}
```

### 5.3 BigQuery Data Queries

Query the data to verify optimizer is writing to BigQuery:

```bash
# Query recent optimization runs
bq query --use_legacy_sql=false '
SELECT 
  timestamp,
  run_id,
  status,
  campaigns_analyzed,
  keywords_optimized,
  average_acos,
  target_acos
FROM `amazon-ppc-474902.amazon_ppc.optimization_results`
ORDER BY timestamp DESC
LIMIT 10
'

# Query campaign performance
bq query --use_legacy_sql=false '
SELECT 
  campaign_name,
  spend,
  sales,
  acos,
  impressions,
  clicks,
  conversions
FROM `amazon-ppc-474902.amazon_ppc.campaign_details`
WHERE DATE(timestamp) = CURRENT_DATE()
ORDER BY spend DESC
LIMIT 20
'

# Query optimization progress
bq query --use_legacy_sql=false '
SELECT 
  timestamp,
  run_id,
  status,
  message,
  percent_complete
FROM `amazon-ppc-474902.amazon_ppc.optimization_progress`
WHERE run_id = (
  SELECT run_id 
  FROM `amazon-ppc-474902.amazon_ppc.optimization_results` 
  ORDER BY timestamp DESC 
  LIMIT 1
)
ORDER BY timestamp ASC
'
```

### 5.4 Live Optimization Testing

Trigger a live optimization run:

```bash
# Dry run first (safe testing)
TOKEN=$(gcloud auth print-identity-token)
curl -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "features": ["bid_optimization"]}' \
  "${FUNCTION_URL}"

# Live run (makes actual changes!)
# ⚠️ CAUTION: This will modify your Amazon Ads campaigns
curl -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}' \
  "${FUNCTION_URL}"
```

**Monitor the run**:
```bash
# Follow function logs in real-time
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=50 \
  --follow

# Check for errors
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=100 | grep -i error
```

### 5.5 Dashboard Verification

1. **Open Dashboard**: https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app

2. **Verify Data Display**:
   - ✅ Recent optimization runs shown
   - ✅ Campaign performance metrics displayed
   - ✅ Graphs and charts populated with data
   - ✅ Real-time status updates visible

3. **Check Dashboard API**:
```bash
# Test dashboard API endpoint (if configured)
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_DASHBOARD_API_KEY" \
  -d '{"test": "health_check"}' \
  "https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app/api/health"
```

### 5.6 Complete Production Checklist

- [ ] **Cloud Function Deployed**: Function URL accessible
- [ ] **Health Check Passing**: `/health=true` returns 200 OK
- [ ] **Amazon Ads Connected**: Verification endpoint returns campaigns
- [ ] **BigQuery Tables Populated**: Data visible in all 4 tables
- [ ] **Cloud Scheduler Running**: Jobs listed and scheduled correctly
- [ ] **Dashboard Showing Data**: Live metrics visible
- [ ] **Secrets Secured**: All credentials in Secret Manager
- [ ] **Authentication Working**: OIDC tokens valid
- [ ] **Logs Available**: Can view function execution logs
- [ ] **Dry Run Successful**: Test run completed without errors
- [ ] **Live Run Successful**: Production run completed with changes
- [ ] **Email Notifications Working**: Alerts received (if configured)
- [ ] **Error Handling Working**: Failed runs logged properly
- [ ] **Cost Monitoring**: Billing alerts configured
- [ ] **Backup Strategy**: Data export strategy defined

---

## Troubleshooting

### Common Deployment and Runtime Issues

#### 1. HTTP 429 (Too Many Requests) Errors

**Symptoms**: Function returns 429 before executing, logs show 0ms duration

**Root Cause**: Function deployed with `--allow-unauthenticated` flag

**Solution**:
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
  --set-secrets='AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest'
```

#### 2. "Unauthorized" or "403 Forbidden" Errors

**Symptoms**: Can't invoke function, authentication fails

**Solution**:
```bash
# Verify service account has invoker role
gcloud functions add-iam-policy-binding amazon-ppc-optimizer \
  --region=us-central1 \
  --member="serviceAccount:ppc-scheduler@YOUR-PROJECT.iam.gserviceaccount.com" \
  --role="roles/cloudfunctions.invoker"

# Test with identity token
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer ${TOKEN}" "${FUNCTION_URL}?health=true"
```

#### 3. BigQuery "Dataset Not Found" Error

**Symptoms**: Function fails with "Dataset amazon-ppc-474902:amazon_ppc was not found"

**Solution**:
```bash
# Re-run BigQuery setup
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4

# Verify dataset exists
bq ls amazon-ppc-474902:

# Check permissions
PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.dataEditor"
```

#### 4. Amazon Ads API Authentication Failures

**Symptoms**: "Authentication failed", "Invalid refresh token"

**Solution**:
```bash
# Verify refresh token in Secret Manager
gcloud secrets versions access latest --secret="amazon-refresh-token"

# Update if needed
echo -n "NEW_REFRESH_TOKEN" | gcloud secrets versions add amazon-refresh-token --data-file=-

# Test connection
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer ${TOKEN}" \
  "${FUNCTION_URL}?verify_connection=true"
```

#### 5. Function Timeout Errors

**Symptoms**: Function execution exceeds timeout limit

**Solution**:
```bash
# Increase timeout to maximum (15 minutes)
gcloud functions deploy amazon-ppc-optimizer \
  --region=us-central1 \
  --update-env-vars FUNCTION_TIMEOUT=900 \
  --timeout=900s

# Optimize configuration
# Reduce lookback_days in config.json:
# "lookback_days": 7  # Instead of 14 or 30
```

#### 6. Memory Limit Exceeded

**Symptoms**: Function crashes with "Exceeded memory limit"

**Solution**:
```bash
# Increase memory allocation
gcloud functions deploy amazon-ppc-optimizer \
  --region=us-central1 \
  --memory=1GB  # or 2GB if needed
```

#### 7. Secret Manager Access Denied

**Symptoms**: "Permission denied" when accessing secrets

**Solution**:
```bash
# Grant secretAccessor role to compute service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding amazon-client-id \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

# Repeat for all secrets
for SECRET in amazon-client-secret amazon-refresh-token amazon-profile-id; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
done
```

#### 8. Cloud Scheduler Not Triggering

**Symptoms**: Scheduled jobs don't execute

**Solution**:
```bash
# Verify job exists and is enabled
gcloud scheduler jobs list --location=us-central1

# Test manual trigger
gcloud scheduler jobs run amazon-ppc-optimizer-daily --location=us-central1

# Check scheduler logs
gcloud logging read "resource.type=cloud_scheduler_job" --limit=50 --format=json

# Verify OIDC authentication configured
gcloud scheduler jobs describe amazon-ppc-optimizer-daily \
  --location=us-central1
```

#### 9. Dashboard Not Receiving Data

**Symptoms**: Dashboard shows no data or stale data

**Solution**:
```bash
# Verify dashboard URL in secrets
gcloud secrets versions access latest --secret="dashboard-url"

# Check function logs for dashboard errors
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=50 | grep -i dashboard

# Test dashboard API manually
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"test": true}' \
  "https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app/api/optimization-results"
```

#### 10. Build Failures During Deployment

**Symptoms**: Deployment fails with "Build failed" error

**Solution**:
```bash
# Check requirements.txt syntax
cat requirements.txt

# Verify Python version compatibility
python --version  # Should be 3.11+

# Check .gcloudignore file
cat .gcloudignore

# Try deploying with verbose logging
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --verbosity=debug
```

### Log Inspection Guidance

**View recent logs**:
```bash
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=100
```

**Follow logs in real-time**:
```bash
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --follow
```

**Filter for errors**:
```bash
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --limit=200 | grep -i "error\|exception\|failed"
```

**View specific time range**:
```bash
gcloud logging read "resource.type=cloud_function AND resource.labels.function_name=amazon-ppc-optimizer" \
  --limit=100 \
  --format=json \
  --freshness=1h
```

**Export logs for analysis**:
```bash
gcloud logging read "resource.type=cloud_function" \
  --limit=1000 \
  --format=json > function_logs.json
```

---

## Security Checklist for Production

### Authentication & Authorization (15 items)

- [ ] Cloud Function deployed with `--no-allow-unauthenticated`
- [ ] Cloud Scheduler uses OIDC authentication
- [ ] Service accounts follow principle of least privilege
- [ ] IAM roles reviewed and minimal permissions granted
- [ ] Service account keys rotated regularly (every 90 days)
- [ ] Amazon Ads API credentials stored in Secret Manager only
- [ ] No credentials in environment variables (use secrets)
- [ ] No credentials in source code or config files committed to git
- [ ] Dashboard API uses authentication tokens
- [ ] BigQuery access restricted to specific service accounts
- [ ] Function invoker role granted only to scheduler service account
- [ ] Identity tokens expire appropriately
- [ ] OAuth refresh tokens stored securely
- [ ] Two-factor authentication enabled on all admin accounts
- [ ] Service account permissions audited monthly

### Secrets Management (12 items)

- [ ] All secrets stored in Google Secret Manager
- [ ] Secret versions tracked and can be rolled back
- [ ] Secrets never logged or exposed in error messages
- [ ] Secret access logged and monitored
- [ ] Rotation policy defined for all secrets (90-day max)
- [ ] Secrets automatically versioned on update
- [ ] Old secret versions disabled after rotation
- [ ] Service accounts granted secretAccessor role only
- [ ] Secrets use latest version reference
- [ ] Development and production secrets separated
- [ ] API keys use restricted scopes where possible
- [ ] Emergency secret revocation procedure documented

### Network Security (8 items)

- [ ] HTTPS only (no HTTP endpoints)
- [ ] TLS 1.2+ enforced for all connections
- [ ] VPC Service Controls configured (if using VPC)
- [ ] Ingress settings configured appropriately
- [ ] Egress limited to required endpoints only
- [ ] DNS resolution secured
- [ ] No public IPs exposed unnecessarily
- [ ] Rate limiting enabled to prevent abuse

### Data Protection (10 items)

- [ ] BigQuery datasets encrypted at rest
- [ ] Data encrypted in transit (HTTPS/TLS)
- [ ] PII data handled according to privacy policy
- [ ] Customer data retention policy defined
- [ ] Data deletion procedures documented
- [ ] Backups configured for BigQuery datasets
- [ ] Export to Google Cloud Storage scheduled
- [ ] Data anonymization for development/testing
- [ ] Query results don't expose sensitive data
- [ ] Dashboard API responses sanitized

### Monitoring & Logging (13 items)

- [ ] Cloud Logging enabled for all services
- [ ] Log retention period configured (90 days minimum)
- [ ] Error alerting configured
- [ ] Budget alerts configured
- [ ] Performance monitoring enabled
- [ ] Failed authentication attempts logged and alerted
- [ ] Function invocation metrics tracked
- [ ] BigQuery query costs monitored
- [ ] API rate limits monitored
- [ ] Dashboard access logged
- [ ] Scheduler job failures alerted
- [ ] Health check failures trigger alerts
- [ ] Security audit logs reviewed weekly

### Cost Management (5 items)

- [ ] Billing budget alerts configured
- [ ] Cost breakdown by service reviewed monthly
- [ ] Function min-instances set to 0 (scale to zero)
- [ ] BigQuery table partitioning configured
- [ ] Scheduled query costs tracked

### Compliance & Governance (7 items)

- [ ] Security incident response plan documented
- [ ] Disaster recovery plan documented
- [ ] Data privacy policy compliant with regulations
- [ ] Third-party integrations reviewed and approved
- [ ] Vendor risk assessment completed (Amazon, Google, Vercel)
- [ ] Compliance documentation maintained
- [ ] Regular security assessments scheduled

### Regular Maintenance Tasks

#### Daily
- [ ] Check health check status
- [ ] Review error logs
- [ ] Verify scheduler executions

#### Weekly
- [ ] Review BigQuery data quality
- [ ] Check dashboard functionality
- [ ] Review cost reports
- [ ] Audit security logs

#### Monthly
- [ ] Update dependencies (requirements.txt)
- [ ] Review and update IAM permissions
- [ ] Test disaster recovery procedures
- [ ] Review and optimize configuration
- [ ] Audit secret access logs
- [ ] Review cost optimization opportunities

#### Quarterly (Every 90 Days)
- [ ] Rotate all secrets and API keys
- [ ] Update service account keys
- [ ] Security assessment and penetration testing
- [ ] Review and update documentation
- [ ] Audit compliance with policies
- [ ] Review third-party integrations

---

## Summary

You've now completed the full deployment from setup to production verification! 🎉

**Key Achievements**:
✅ GitHub CI/CD configured with 9 secrets
✅ BigQuery infrastructure deployed and verified
✅ Local testing environment set up
✅ Cloud Function deployed with security best practices
✅ Cloud Scheduler configured with OIDC authentication
✅ Production verification completed
✅ Live data flowing to dashboard
✅ Comprehensive security checklist implemented

**Next Steps**:
1. Monitor the first few optimization runs
2. Fine-tune configuration based on performance
3. Set up additional alerting as needed
4. Schedule regular maintenance tasks
5. Review and improve based on actual usage

**Support**:
- Documentation: [README.md](README.md)
- Troubleshooting: This guide section 6
- Contact: james@natureswaysoil.com

---

**Last Updated**: November 6, 2024
**Version**: 1.0.0
