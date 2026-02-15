# Deployment Diagnostics Scripts

This directory contains comprehensive diagnostic and validation scripts for troubleshooting deployment failures across the Amazon PPC Optimizer infrastructure.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Script Descriptions](#script-descriptions)
3. [Common Issues and Fixes](#common-issues-and-fixes)
4. [Manual Deployment Steps](#manual-deployment-steps)
5. [Debugging Tips](#debugging-tips)
6. [Contact/Support](#contactsupport)

---

## Quick Start

### Before Deployment

Run pre-deployment checks to ensure everything is configured correctly:

```bash
./scripts/pre-deployment-check.sh
```

This validates:
- Git status (no uncommitted changes, on main branch)
- All secrets exist in Secret Manager
- gcloud authentication
- Required files present
- Python requirements syntax

### After Deployment

Verify deployment health:

```bash
./scripts/post-deployment-check.sh ppc-optimizer
```

This checks:
- Function is ACTIVE
- Health endpoint responding
- BigQuery connectivity
- Secret Manager access
- Dashboard reachability

### When Deployment Fails

Run comprehensive diagnostics:

```bash
./scripts/comprehensive-diagnostics.sh
```

Then apply automated fixes:

```bash
./scripts/fix-common-issues.sh
```

---

## Script Descriptions

### 1. `validate-secrets.sh`

**Purpose**: Validate all required secrets in Google Cloud Secret Manager

**Usage**:
```bash
./scripts/validate-secrets.sh [PROJECT_ID]
```

**What it checks**:
- All 6 required secrets exist:
  - `amazon-client-id`
  - `amazon-client-secret`
  - `amazon-refresh-token`
  - `ppc-profile-id`
  - `dashboard-url`
  - `dashboard-api-key`
- Secret versions are enabled
- Values are not empty or placeholder (`YOUR_*`)

**Exit codes**:
- `0`: All secrets valid
- `1`: Missing or invalid secrets

**Example output**:
```
🔍 Secret Manager Validation
Project: amazon-ppc-474902
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Validating secret: amazon-client-id
  ✅ Valid (42 characters, version: 1)

❌ Missing: dashboard-api-key
  Create with: gcloud secrets create dashboard-api-key --project=amazon-ppc-474902

📋 Validation Summary
✅ Valid secrets:    5/6
❌ Missing secrets:  1/6
```

---

### 2. `comprehensive-diagnostics.sh`

**Purpose**: Main diagnostic script that runs all health checks

**Usage**:
```bash
./scripts/comprehensive-diagnostics.sh [PROJECT_ID] [FUNCTION_NAME]
```

**What it checks**:
- **Section 1**: Cloud Function status and configuration
- **Section 2**: Secret Manager validation
- **Section 3**: Vercel Dashboard health
- **Section 4**: Cloud Function health endpoint
- **Section 5**: Recent error logs (last 1 hour)
- **Section 6**: BigQuery dataset validation

**Output**: Saved to `/tmp/diagnostics.log`

**When to use**:
- After deployment failure
- When investigating errors
- For periodic health checks

---

### 3. `get-deployment-logs.sh`

**Purpose**: Retrieve Cloud Build and Cloud Function logs

**Usage**:
```bash
./scripts/get-deployment-logs.sh [PROJECT_ID]
```

**What it retrieves**:
- Last 10 Cloud Build jobs with status
- Most recent failed build logs
- Cloud Function errors (last 24 hours)
- Recent deployment events

**Output**: Saved to `/tmp/deployment-logs.txt`

**When to use**:
- Deployment failed
- Need to investigate build errors
- Checking recent error patterns

---

### 4. `pre-deployment-check.sh`

**Purpose**: Validation before deploying to prevent common issues

**Usage**:
```bash
./scripts/pre-deployment-check.sh [PROJECT_ID]
```

**Checks performed**:
1. Git status (on main, no uncommitted changes)
2. Secrets exist in Secret Manager
3. gcloud authentication
4. gcloud project configuration
5. Required files exist (`main.py`, `requirements.txt`, etc.)
6. Entry point functions defined
7. `requirements.txt` syntax validation
8. Common issues (`.env` in git, `__pycache__`, large files)

**Exit codes**:
- `0`: All checks passed, ready to deploy
- `1`: Issues detected, fix before deploying

**When to use**:
- **ALWAYS** before deploying
- As part of CI/CD pipeline
- Before manual deployments

---

### 5. `post-deployment-check.sh`

**Purpose**: Verify deployment succeeded and services are healthy

**Usage**:
```bash
./scripts/post-deployment-check.sh [FUNCTION_NAME] [PROJECT_ID]
# or
./scripts/post-deployment-check.sh https://function-url.a.run.app
```

**Checks performed**:
- Function is ACTIVE (with 5-minute timeout)
- Health endpoint responds
- BigQuery connection works
- Secrets are accessible
- Dashboard is reachable

**Exit codes**:
- `0`: Deployment healthy
- `1`: Issues detected

**When to use**:
- Immediately after deployment
- As part of CI/CD pipeline
- For periodic health monitoring

---

### 6. `fix-common-issues.sh`

**Purpose**: Automated fix script for common deployment problems

**Usage**:
```bash
./scripts/fix-common-issues.sh [PROJECT_ID]
```

**What it fixes**:
1. **Missing secrets**: Creates secrets with user-provided values
2. **IAM permissions**: Grants required roles to service account
3. **Required APIs**: Enables disabled APIs
4. **Function cache**: Provides instructions for cache clearing
5. **Dashboard API key**: Syncs between Secret Manager and Vercel
6. **BigQuery permissions**: Grants dataset access

**Interactive**: Prompts for confirmation before each fix

**When to use**:
- After `comprehensive-diagnostics.sh` identifies issues
- When deployment fails with permission errors
- When secrets are missing or invalid

---

## Common Issues and Fixes

### Issue: "Secret not found"

**Symptoms**:
- Deployment succeeds but function fails at runtime
- Error: `Secret 'amazon-client-id' not found`

**Fix**:
```bash
# Create missing secret
echo 'YOUR_VALUE' | gcloud secrets create SECRET_NAME \
  --data-file=- \
  --project=amazon-ppc-474902

# Or use automated fix
./scripts/fix-common-issues.sh
```

### Issue: "Permission denied: Secret Manager"

**Symptoms**:
- Error: `Permission 'secretmanager.versions.access' denied`

**Fix**:
```bash
# Grant access to default service account
PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

### Issue: "Function not ACTIVE"

**Symptoms**:
- Function stuck in "DEPLOYING" state
- Health checks fail

**Fix**:
```bash
# Check logs for errors
./scripts/get-deployment-logs.sh

# View function status
gcloud functions describe ppc-optimizer \
  --gen2 \
  --region=us-central1 \
  --project=amazon-ppc-474902

# If needed, redeploy
gcloud functions deploy ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --project=amazon-ppc-474902
```

### Issue: "BigQuery dataset not found"

**Symptoms**:
- Error: `Dataset 'amazon_ppc' does not exist`

**Fix**:
```bash
# Create dataset
bq mk --project_id=amazon-ppc-474902 --location=US amazon_ppc

# Grant permissions
PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.dataEditor"
```

### Issue: "Build failed: requirements.txt"

**Symptoms**:
- Cloud Build fails during `pip install`
- Error: `Could not find a version that satisfies the requirement`

**Fix**:
```bash
# Test requirements locally
pip install --dry-run -r requirements.txt

# Check for version conflicts
pip install -r requirements.txt

# Fix any conflicts, then redeploy
```

---

## Manual Deployment Steps

If automated deployment fails, deploy manually:

### Step 1: Pre-deployment Validation

```bash
./scripts/pre-deployment-check.sh
```

Fix any issues reported before proceeding.

### Step 2: Deploy Function (Gen2)

```bash
gcloud functions deploy ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --allow-unauthenticated \
  --memory=512MB \
  --timeout=540s \
  --set-env-vars=PROJECT_ID=amazon-ppc-474902 \
  --set-secrets='AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest' \
  --project=amazon-ppc-474902
```

### Step 3: Post-deployment Validation

```bash
# Wait for function to be active
./scripts/post-deployment-check.sh ppc-optimizer

# Test health endpoint
FUNCTION_URL=$(gcloud functions describe ppc-optimizer \
  --gen2 \
  --region=us-central1 \
  --project=amazon-ppc-474902 \
  --format="value(serviceConfig.uri)")

curl "${FUNCTION_URL}/health"
```

### Step 4: Verify All Services

```bash
./scripts/comprehensive-diagnostics.sh
```

---

## Debugging Tips

### 1. Enable Verbose Logging

Set environment variable:
```bash
export LOG_LEVEL=DEBUG
```

### 2. View Real-time Logs

```bash
# Stream function logs
gcloud functions logs read ppc-optimizer \
  --limit=50 \
  --project=amazon-ppc-474902

# Follow logs in real-time
gcloud functions logs read ppc-optimizer \
  --limit=50 \
  --project=amazon-ppc-474902 \
  --follow
```

### 3. Test Function Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export PROJECT_ID=amazon-ppc-474902
export PPC_DRY_RUN=true

# Run locally
python main.py
```

### 4. Check Cloud Console

Direct links:
- [Cloud Functions](https://console.cloud.google.com/functions?project=amazon-ppc-474902)
- [Cloud Build](https://console.cloud.google.com/cloud-build/builds?project=amazon-ppc-474902)
- [Secret Manager](https://console.cloud.google.com/security/secret-manager?project=amazon-ppc-474902)
- [BigQuery](https://console.cloud.google.com/bigquery?project=amazon-ppc-474902)
- [Cloud Logging](https://console.cloud.google.com/logs?project=amazon-ppc-474902)

### 5. Common gcloud Commands

```bash
# List functions
gcloud functions list --project=amazon-ppc-474902

# Describe function
gcloud functions describe ppc-optimizer \
  --gen2 \
  --region=us-central1 \
  --project=amazon-ppc-474902

# List secrets
gcloud secrets list --project=amazon-ppc-474902

# View secret value
gcloud secrets versions access latest \
  --secret=amazon-client-id \
  --project=amazon-ppc-474902

# List BigQuery datasets
bq ls --project_id=amazon-ppc-474902

# List BigQuery tables
bq ls --project_id=amazon-ppc-474902 amazon_ppc
```

### 6. Debugging Failed Builds

```bash
# List recent builds
gcloud builds list --limit=10 --project=amazon-ppc-474902

# Get build details
gcloud builds describe BUILD_ID --project=amazon-ppc-474902

# View build logs
gcloud builds log BUILD_ID --project=amazon-ppc-474902
```

---

## Contact/Support

### Documentation

- [Main README](../README.md)
- [Deployment Guide](../DEPLOYMENT_GUIDE.md)
- [Troubleshooting Guide](../TROUBLESHOOTING.md)

### GitHub

- [Open an issue](https://github.com/natureswaysoil/Amazom-PPC/issues)
- [View existing issues](https://github.com/natureswaysoil/Amazom-PPC/issues?q=is%3Aissue)

### Automated Diagnostics

The GitHub Actions workflow automatically runs diagnostics on deployment failures:
- Workflow: `.github/workflows/deployment-diagnostics.yml`
- Creates issues automatically with diagnostic output
- Uploads artifacts with full logs

### Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│  Amazon PPC Optimizer - Diagnostics Quick Reference     │
├─────────────────────────────────────────────────────────┤
│  Before Deploy:                                         │
│    ./scripts/pre-deployment-check.sh                    │
│                                                          │
│  After Deploy:                                          │
│    ./scripts/post-deployment-check.sh                   │
│                                                          │
│  If Failed:                                             │
│    ./scripts/comprehensive-diagnostics.sh               │
│    ./scripts/get-deployment-logs.sh                     │
│    ./scripts/fix-common-issues.sh                       │
│                                                          │
│  Validate Secrets:                                      │
│    ./scripts/validate-secrets.sh                        │
│                                                          │
│  Manual Deploy:                                         │
│    gcloud functions deploy ppc-optimizer --gen2 ...     │
└─────────────────────────────────────────────────────────┘
```

---

## Script Dependencies

All scripts require:
- `gcloud` CLI installed and authenticated
- `bash` 4.0 or later
- Basic Unix tools: `curl`, `jq`, `grep`, `sed`

Optional:
- `bq` CLI (for BigQuery checks)
- `python3` and `pip` (for requirements validation)

## Exit Codes

All scripts follow this convention:
- `0`: Success, all checks passed
- `1`: Failure or issues detected

Use in CI/CD:
```bash
if ./scripts/pre-deployment-check.sh; then
  echo "✅ Ready to deploy"
  gcloud functions deploy ...
else
  echo "❌ Fix issues before deploying"
  exit 1
fi
```

---

**Last Updated**: 2024-02-15  
**Version**: 1.0.0
