# Amazon PPC Optimizer - Complete Setup Guide

This guide walks you through setting up the complete Amazon PPC Optimizer with verification, audit trail, and multi-dashboard integration.

## Prerequisites

- Google Cloud Project with billing enabled
- Amazon Advertising API credentials (Client ID, Secret, Refresh Token, Profile ID)
- GitHub account (for GitHub Pages dashboard)
- gcloud CLI installed and configured

## Step 1: Clone and Configure

### 1.1 Clone Repository

```bash
git clone https://github.com/natureswaysoil/Amazom-PPC.git
cd Amazom-PPC
```

### 1.2 Install Dependencies

```bash
pip install -r requirements.txt
```

### 1.3 Configure Settings

Copy the sample config and update with your credentials:

```bash
cp sample_config.yaml config.yaml
```

Edit `config.yaml` with your credentials:

```yaml
amazon_api:
  region: NA
  profile_id: YOUR_PROFILE_ID
  client_id: amzn1.application-oa2-client.xxxxx
  client_secret: amzn1.oa2-cs.v1.xxxxx
  refresh_token: Atzr|IwEBIxxxxx

dashboard:
  url: https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app
  api_key: YOUR_DASHBOARD_API_KEY
  enabled: true

bigquery:
  enabled: true
  project_id: your-gcp-project-id
  dataset_id: amazon_ppc
  location: us-east4

github_pages_dashboard:
  enabled: true
  repo_owner: natureswaysoil
  repo_name: best
  branch: main
  data_path: data/ppc-data.json
  github_token: YOUR_GITHUB_TOKEN
  dashboard_url: https://natureswaysoil.github.io/best/
```

## Step 2: Set Up Amazon Advertising API

### 2.1 Register Application

1. Go to https://advertising.amazon.com/API/
2. Register your application
3. Get your Client ID and Client Secret

### 2.2 Get Refresh Token

Follow Amazon's OAuth flow to get a refresh token:

```bash
# Use the provided script or manual OAuth flow
./auto-refresh-token.sh
```

### 2.3 Get Profile ID

```bash
# List available profiles
python optimizer_core.py --config config.yaml --verify-connection
```

## Step 3: Set Up BigQuery

### 3.1 Create Dataset

```bash
# Run the setup script
./setup-bigquery.sh YOUR_GCP_PROJECT_ID amazon_ppc us-east4
```

Or manually:

```bash
# Create dataset
bq mk --dataset \
  --location=us-east4 \
  --description="Amazon PPC Optimization Data" \
  YOUR_GCP_PROJECT_ID:amazon_ppc

# Grant permissions to service account
PROJECT_NUMBER=$(gcloud projects describe YOUR_GCP_PROJECT_ID --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding YOUR_GCP_PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.jobUser"
```

### 3.2 Verify BigQuery Setup

```bash
# List tables (should be empty initially)
bq ls YOUR_GCP_PROJECT_ID:amazon_ppc

# Tables will be created automatically on first run
```

## Step 4: Set Up GitHub Pages Dashboard

### 4.1 Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens/new
2. Select scopes:
   - ✅ `repo` (Full control of private repositories)
3. Generate token
4. Copy token to config.yaml

### 4.2 Prepare Dashboard Repository

```bash
# Create data directory in your repository
cd /path/to/best
mkdir -p data
touch data/ppc-data.json

# Initialize with empty data
echo '{"runs": [], "statistics": {}}' > data/ppc-data.json

# Commit and push
git add data/ppc-data.json
git commit -m "Initialize PPC data file"
git push
```

### 4.3 Enable GitHub Pages

1. Go to repository Settings → Pages
2. Select source: `main` branch
3. Choose root directory
4. Save

Your dashboard will be available at: https://natureswaysoil.github.io/best/

## Step 5: Test Locally

### 5.1 Run Verification Tests

```bash
# Test verification system
python test_verification.py
```

Expected output:
```
✓ All tests passed
✓ Verification system working correctly
```

### 5.2 Dry Run

```bash
# Set environment variables
export AMAZON_CLIENT_ID="your_client_id"
export AMAZON_CLIENT_SECRET="your_client_secret"
export AMAZON_REFRESH_TOKEN="your_refresh_token"

# Run dry run (no actual changes)
python main.py
```

Check output:
```
✓ VERIFICATION CHECKS
  ✓ API connection: passed
  ✓ BigQuery connection: passed
  ✓ Dashboard connection: passed

✓ OPTIMIZATION RUN (DRY RUN)
  Campaigns analyzed: X
  Keywords optimized: Y
  ...

✓ DATA WRITTEN TO:
  ✓ BigQuery: amazon_ppc.optimization_results
  ✓ Dashboard: https://amazonppcdashboard-...
  ✓ GitHub Pages: https://natureswaysoil.github.io/best/
  ✓ Audit Trail: logs/ppc_audit_*.csv
```

## Step 6: Deploy to Google Cloud Functions

### 6.1 Create Secrets

```bash
# Create secrets in Secret Manager
echo -n "YOUR_CLIENT_ID" | gcloud secrets create amazon-client-id --data-file=-
echo -n "YOUR_CLIENT_SECRET" | gcloud secrets create amazon-client-secret --data-file=-
echo -n "YOUR_REFRESH_TOKEN" | gcloud secrets create amazon-refresh-token --data-file=-

# Create config secret
cat config.yaml | gcloud secrets create ppc-config --data-file=-

# Create GitHub token secret
echo -n "YOUR_GITHUB_TOKEN" | gcloud secrets create github-pages-token --data-file=-
```

### 6.2 Deploy Function

```bash
# Deploy with all secrets
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
  --set-secrets=AMAZON_CLIENT_ID=amazon-client-id:latest,\
AMAZON_CLIENT_SECRET=amazon-client-secret:latest,\
AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,\
PPC_CONFIG=ppc-config:latest,\
GITHUB_TOKEN=github-pages-token:latest
```

### 6.3 Get Function URL

```bash
gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 \
  --gen2 \
  --format='value(serviceConfig.uri)'
```

## Step 7: Set Up Cloud Scheduler

### 7.1 Create Scheduler Job

```bash
# Run optimization every 6 hours
gcloud scheduler jobs create http ppc-optimizer-schedule \
  --location=us-central1 \
  --schedule="0 */6 * * *" \
  --uri="YOUR_FUNCTION_URL" \
  --http-method=POST \
  --oidc-service-account-email="YOUR_SERVICE_ACCOUNT" \
  --oidc-token-audience="YOUR_FUNCTION_URL"
```

### 7.2 Test Scheduler

```bash
# Trigger manually
gcloud scheduler jobs run ppc-optimizer-schedule --location=us-central1

# Check logs
gcloud functions logs read amazon-ppc-optimizer --limit=50
```

## Step 8: Verify Complete Data Flow

### 8.1 Check Audit Trail

```bash
# Local CSV (if running locally)
ls -lh logs/ppc_audit_*.csv
cat logs/ppc_audit_*.csv | tail -20

# Or check Cloud Function logs
gcloud functions logs read amazon-ppc-optimizer | grep "AUDIT"
```

### 8.2 Verify BigQuery Data

```bash
# Check tables created
bq ls YOUR_GCP_PROJECT_ID:amazon_ppc

# Query recent results
bq query --use_legacy_sql=false '
  SELECT 
    timestamp,
    run_id,
    campaigns_analyzed,
    keywords_optimized,
    total_spend,
    total_sales,
    average_acos
  FROM amazon_ppc.optimization_results
  ORDER BY timestamp DESC
  LIMIT 10
'
```

### 8.3 Verify Vercel Dashboard

```bash
# Make a test request
curl "https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app/api/health"
```

Visit dashboard: https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app

### 8.4 Verify GitHub Pages Dashboard

Visit: https://natureswaysoil.github.io/best/

Check that data is being updated:
```bash
# View raw data
curl https://raw.githubusercontent.com/natureswaysoil/best/main/data/ppc-data.json | jq .
```

## Step 9: Monitor and Maintain

### 9.1 Set Up Monitoring

```bash
# Create log-based metric for errors
gcloud logging metrics create ppc_optimizer_errors \
  --description="PPC Optimizer Errors" \
  --log-filter='resource.type="cloud_function"
    resource.labels.function_name="amazon-ppc-optimizer"
    severity>=ERROR'

# Create alert policy
gcloud alpha monitoring policies create \
  --notification-channels=YOUR_NOTIFICATION_CHANNEL \
  --display-name="PPC Optimizer Errors" \
  --condition-display-name="Error rate high" \
  --condition-threshold-value=5 \
  --condition-threshold-duration=300s
```

### 9.2 Regular Checks

Daily:
- Review optimization results in dashboards
- Check for any verification failures
- Monitor ACOS trends

Weekly:
- Review audit trail for unusual patterns
- Check BigQuery data quality
- Verify all integrations are working

Monthly:
- Review and update bid optimization thresholds
- Analyze campaign performance trends
- Backup audit trail and BigQuery data
- Rotate GitHub tokens and API credentials

### 9.3 Troubleshooting

**Verification Failures:**
```bash
# Check logs
gcloud functions logs read amazon-ppc-optimizer | grep "VERIFICATION"

# Check specific integration
gcloud functions logs read amazon-ppc-optimizer | grep "BigQuery"
gcloud functions logs read amazon-ppc-optimizer | grep "Dashboard"
```

**BigQuery Errors:**
```bash
# Verify permissions
gcloud projects get-iam-policy YOUR_GCP_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:YOUR_SERVICE_ACCOUNT"

# Recreate dataset if needed
./setup-bigquery.sh YOUR_GCP_PROJECT_ID amazon_ppc us-east4
```

**GitHub Pages Not Updating:**
```bash
# Check GitHub token permissions
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
  https://api.github.com/repos/natureswaysoil/best

# Check function logs for GitHub API errors
gcloud functions logs read amazon-ppc-optimizer | grep "GitHub"
```

## Step 10: Advanced Configuration

### 10.1 Custom Verification Checks

Add custom checks in `verification_system.py`:

```python
def verify_custom_metric(self, data: Dict) -> VerificationResult:
    # Your custom verification logic
    pass
```

### 10.2 Custom Audit Trail Fields

Extend audit trail in `optimizer_core.py`:

```python
self.audit.log(
    action_type='CUSTOM_ACTION',
    entity_type='CUSTOM_ENTITY',
    entity_id='123',
    old_value='old',
    new_value='new',
    reason='Custom reason',
    dry_run=False
)
```

### 10.3 Additional Dashboards

Add more dashboard integrations in `main.py`:

```python
# Add custom dashboard client
custom_dashboard = CustomDashboardClient(config)
custom_dashboard.send_results(results)
```

## Support

For issues or questions:
- Check logs: `gcloud functions logs read amazon-ppc-optimizer`
- Review audit trail: `cat logs/ppc_audit_*.csv`
- Query BigQuery: See verification guide
- Review documentation: [VERIFICATION_AND_AUDIT.md](VERIFICATION_AND_AUDIT.md)
- Contact: james@natureswaysoil.com

## Next Steps

1. ✅ Complete setup following this guide
2. ✅ Run initial dry-run test
3. ✅ Verify all integrations working
4. ✅ Monitor first production run
5. ✅ Review audit trail and dashboards
6. ✅ Set up monitoring and alerts
7. ✅ Schedule regular reviews

## Resources

- [Amazon Advertising API Documentation](https://advertising.amazon.com/API/)
- [Google Cloud Functions Documentation](https://cloud.google.com/functions/docs)
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [GitHub API Documentation](https://docs.github.com/en/rest)
- [Project README](README.md)
- [Verification Guide](VERIFICATION_AND_AUDIT.md)
