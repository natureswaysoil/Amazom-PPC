# Quick Start Guide - Amazon PPC Optimizer

Get up and running in 15 minutes! This guide provides the fastest path to deployment.

## Prerequisites Checklist

- [ ] Google Cloud account with billing enabled
- [ ] Amazon Advertising API credentials (Client ID, Secret, Refresh Token, Profile ID)
- [ ] `gcloud` CLI installed: [Install Guide](https://cloud.google.com/sdk/docs/install)
- [ ] GitHub account with repo access

## 🚀 Option 1: Automated Deployment (Recommended)

Use the automated deployment script for a guided setup:

```bash
# Clone the repository
git clone https://github.com/natureswaysoil/Amazom-PPC.git
cd Amazom-PPC

# Run the automated deployment script
./deploy-complete.sh
```

The script will:
1. ✅ Check prerequisites
2. ✅ Set up Google Cloud project and APIs
3. ✅ Configure BigQuery infrastructure
4. ✅ Set up Secret Manager
5. ✅ Deploy Cloud Function
6. ✅ Configure Cloud Scheduler
7. ✅ Verify deployment

**Time**: ~10 minutes

---

## 🧪 Option 2: Local Testing First

Test locally before deploying to production:

```bash
# Clone and navigate
git clone https://github.com/natureswaysoil/Amazom-PPC.git
cd Amazom-PPC

# Create .env file from template
cp .env.template .env

# Edit .env and add your credentials
nano .env  # or use your favorite editor

# Run the local test script
./local-test.sh
```

Follow the interactive menu to:
- Check environment setup
- Test Amazon Ads API connection
- Run dry-run optimization
- Test individual features

**Time**: ~5 minutes

---

## ⚡ Option 3: Manual Quick Deploy

For experienced users who want full control:

### Step 1: Set up Google Cloud (3 minutes)

```bash
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable APIs
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  bigquery.googleapis.com

# Set up BigQuery
./setup-bigquery.sh $PROJECT_ID amazon_ppc us-east4
```

### Step 2: Create Secrets (2 minutes)

```bash
# Store your credentials in Secret Manager
echo -n "YOUR_CLIENT_ID" | gcloud secrets create amazon-client-id --data-file=-
echo -n "YOUR_CLIENT_SECRET" | gcloud secrets create amazon-client-secret --data-file=-
echo -n "YOUR_REFRESH_TOKEN" | gcloud secrets create amazon-refresh-token --data-file=-
echo -n "YOUR_PROFILE_ID" | gcloud secrets create amazon-profile-id --data-file=-

# Grant access to compute service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in amazon-client-id amazon-client-secret amazon-refresh-token amazon-profile-id; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

### Step 3: Deploy Function (5 minutes)

```bash
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

# If this prints "(unset)", set your active project first:
# gcloud config set project YOUR_PROJECT_ID

gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --project="$PROJECT_ID" \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --set-secrets='AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,AMAZON_PROFILE_ID=amazon-profile-id:latest' \
  --set-env-vars="GCP_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
```

### Step 4: Test Deployment (2 minutes)

```bash
# Get function URL
FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
  --region=us-central1 --gen2 --format='value(serviceConfig.uri)')

# Test health check
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer $TOKEN" "${FUNCTION_URL}?health=true"

# Test connection verification
curl -H "Authorization: Bearer $TOKEN" \
  "${FUNCTION_URL}?verify_connection=true&verify_sample_size=3"
```

**Time**: ~10 minutes

---

## 📋 Post-Deployment Checklist

After deployment, verify:

- [ ] **Health Check**: Returns `{"status": "healthy"}`
- [ ] **API Connection**: Retrieves sample campaigns
- [ ] **BigQuery Tables**: 4 tables created in dataset
- [ ] **Cloud Scheduler**: Jobs listed and scheduled
- [ ] **Dashboard**: Shows data at https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app

## 🔍 Quick Verification Commands

```bash
# Check function logs
gcloud functions logs read amazon-ppc-optimizer --region=us-central1 --limit=20

# Query BigQuery data
bq query --use_legacy_sql=false \
  'SELECT * FROM `amazon-ppc-474902.amazon_ppc.optimization_results` ORDER BY timestamp DESC LIMIT 5'

# List scheduler jobs
gcloud scheduler jobs list --location=us-central1

# Manually trigger a dry-run
TOKEN=$(gcloud auth print-identity-token)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}' \
  "${FUNCTION_URL}"
```

## 🆘 Common Issues & Quick Fixes

### Issue: "Permission denied" errors

**Fix**: Grant proper IAM roles
```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA}" \
  --role="roles/bigquery.dataEditor"
```

### Issue: "Dataset not found" errors

**Fix**: Re-run BigQuery setup
```bash
./setup-bigquery.sh $PROJECT_ID amazon_ppc us-east4
```

### Issue: "Authentication failed" with Amazon Ads API

**Fix**: Verify and update refresh token
```bash
gcloud secrets versions access latest --secret=amazon-refresh-token
echo -n "NEW_TOKEN" | gcloud secrets versions add amazon-refresh-token --data-file=-
```

### Issue: HTTP 429 (Too Many Requests)

**Fix**: Ensure `--no-allow-unauthenticated` flag is used
```bash
# Redeploy with authentication required
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

# If this prints "(unset)", set your active project first:
# gcloud config set project YOUR_PROJECT_ID

gcloud functions deploy amazon-ppc-optimizer \
  --no-allow-unauthenticated \
  # ... other flags
```

## 📚 Next Steps

1. **Set up Cloud Scheduler** for automatic daily runs:
   ```bash
   FUNCTION_URL=$(gcloud functions describe amazon-ppc-optimizer \
     --region=us-central1 --gen2 --format='value(serviceConfig.uri)')
   
   # Create service account
   gcloud iam service-accounts create ppc-scheduler \
     --display-name="PPC Optimizer Scheduler"
   
   # Grant invoker permission
   gcloud functions add-iam-policy-binding amazon-ppc-optimizer \
     --region=us-central1 \
     --member="serviceAccount:ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/cloudfunctions.invoker"
   
   # Create daily job at 3 AM
   gcloud scheduler jobs create http amazon-ppc-optimizer-daily \
     --location=us-central1 \
     --schedule="0 3 * * *" \
     --uri="${FUNCTION_URL}" \
     --http-method=POST \
     --time-zone="America/New_York" \
     --oidc-service-account-email="ppc-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
     --oidc-token-audience="${FUNCTION_URL}" \
     --message-body='{"dry_run": false}'
   ```

2. **Configure GitHub Actions** for CI/CD:
   - Add required secrets to your GitHub repository
   - Push to main branch triggers automatic deployment
   - See `.github/workflows/deploy-to-cloud.yml`

3. **Monitor your deployment**:
   - Check logs regularly: `gcloud functions logs read amazon-ppc-optimizer --follow`
   - Review BigQuery data for trends
   - Visit dashboard for visualizations

4. **Fine-tune configuration**:
   - Adjust `config.json` settings based on performance
   - Modify scheduler frequency as needed
   - Update bid optimization thresholds

## 📖 Additional Resources

- **[COMPLETE_DEPLOYMENT_GUIDE.md](COMPLETE_DEPLOYMENT_GUIDE.md)**: Comprehensive 500+ line deployment guide with all details
- **[README.md](README.md)**: Main project documentation
- **[VERIFICATION_GUIDE.md](VERIFICATION_GUIDE.md)**: Detailed verification and testing procedures
- **[TROUBLESHOOTING.md](DEPLOYMENT_GUIDE.md#troubleshooting)**: Complete troubleshooting reference

## 🎯 Success Criteria

You're ready for production when:

✅ Health check returns 200 OK  
✅ Amazon Ads API connection verified  
✅ BigQuery tables receiving data  
✅ Cloud Scheduler jobs running  
✅ Dashboard shows live metrics  
✅ No errors in function logs  
✅ Dry-run completes successfully  

## 💡 Pro Tips

1. **Always test with dry-run first**: Set `dry_run: true` in requests
2. **Monitor costs**: Set up budget alerts in Google Cloud Console
3. **Keep secrets secure**: Use Secret Manager, never commit to git
4. **Review logs regularly**: Catch issues early
5. **Update dependencies**: Check for security updates monthly
6. **Backup configuration**: Export config regularly

---

**Need Help?**

- 📧 Email: james@natureswaysoil.com
- 📚 Full documentation: [COMPLETE_DEPLOYMENT_GUIDE.md](COMPLETE_DEPLOYMENT_GUIDE.md)
- 🐛 Issues: GitHub Issues tab

**Last Updated**: November 6, 2024  
**Version**: 1.0.0
