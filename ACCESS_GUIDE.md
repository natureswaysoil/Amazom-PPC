# Access Configuration Guide

## Quick Start - Grant All Access

Run this script in [Google Cloud Shell](https://shell.cloud.google.com/?project=amazon-ppc-474902):

```bash
cd ~/Amazom-PPC
./grant-access.sh
```

## What Access is Needed?

### 1. **Your User Account** (for deployment)

You need these roles to deploy the function:

```bash
# Get your current user email
gcloud config get-value account

# Grant deployment permissions (requires Project Owner/Admin)
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="user:YOUR_EMAIL@gmail.com" \
  --role="roles/cloudfunctions.developer"

gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="user:YOUR_EMAIL@gmail.com" \
  --role="roles/iam.serviceAccountUser"
```

### 2. **Cloud Function Service Account** (to read secrets)

The function needs to read secrets from Secret Manager:

```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format="value(projectNumber)")

# Grant Secret Manager access for each secret
for secret in amazon-client-id amazon-client-secret amazon-refresh-token ppc-profile-id dashboard-url dashboard-api-key; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

### 3. **Cloud Scheduler Service Account** (for scheduled runs)

To allow Cloud Scheduler to invoke your function:

```bash
# Create scheduler service account
gcloud iam service-accounts create ppc-optimizer-scheduler \
  --display-name="PPC Optimizer Scheduler"

# Grant invoker permission (run AFTER deploying function)
gcloud functions add-invoker-policy-binding amazon-ppc-optimizer \
  --region=us-central1 \
  --member="serviceAccount:ppc-optimizer-scheduler@amazon-ppc-474902.iam.gserviceaccount.com"
```

## Check Current Permissions

### Check Your Roles
```bash
gcloud projects get-iam-policy amazon-ppc-474902 \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:$(gcloud config get-value account)"
```

### Check Secret Access
```bash
# List all secrets
gcloud secrets list

# Check who has access to a specific secret
gcloud secrets get-iam-policy dashboard-url
```

### Check Service Account
```bash
# List service accounts
gcloud iam service-accounts list

# Check if scheduler service account exists
gcloud iam service-accounts describe ppc-optimizer-scheduler@amazon-ppc-474902.iam.gserviceaccount.com
```

## Common Access Issues

### Issue: "Permission denied" during deployment

**Solution**: You need `cloudfunctions.developer` role:
```bash
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/cloudfunctions.developer"
```

### Issue: "Cannot access secret"

**Solution**: Grant Secret Manager access to compute service account:
```bash
PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Issue: Function deployed but can't be invoked

**Solution**: Grant yourself or Cloud Scheduler the invoker role:
```bash
# For your user
gcloud functions add-invoker-policy-binding amazon-ppc-optimizer \
  --region=us-central1 \
  --member="user:$(gcloud config get-value account)"

# For Cloud Scheduler
gcloud functions add-invoker-policy-binding amazon-ppc-optimizer \
  --region=us-central1 \
  --member="serviceAccount:ppc-optimizer-scheduler@amazon-ppc-474902.iam.gserviceaccount.com"
```

### Issue: Dashboard secrets not found

**Solution**: Create the secrets if they don't exist:
```bash
echo -n "https://ppc-dashboard.abacusai.app" | gcloud secrets create dashboard-url --data-file=-
echo -n "YOUR_DASHBOARD_API_KEY" | gcloud secrets create dashboard-api-key --data-file=-
```

## Required Secrets Checklist

Make sure these secrets exist in Secret Manager:

- ✅ `amazon-client-id`
- ✅ `amazon-client-secret`
- ✅ `amazon-refresh-token`
- ✅ `ppc-profile-id`
- ✅ `dashboard-url`
- ✅ `dashboard-api-key`

Check with:
```bash
gcloud secrets list
```

## Enable Required APIs

```bash
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable run.googleapis.com
```

## Complete Setup Flow

1. **Grant yourself deployment permissions** (if you're Project Owner, you already have these)
2. **Enable required APIs**
3. **Create secrets** (if they don't exist)
4. **Grant Secret Manager access** to function service account
5. **Deploy function** (`./deploy.sh`)
6. **Grant invoker permission** to Cloud Scheduler service account
7. **Set up Cloud Scheduler** job (optional)

## Quick Commands Reference

```bash
# One-liner to check everything is ready
gcloud secrets list && \
gcloud services list --enabled | grep -E "(functions|build|scheduler|secretmanager)" && \
echo "✅ Ready to deploy!"

# One-liner to deploy after access is granted
./grant-access.sh && ./deploy.sh
```

## Get Help

If you're stuck:
1. Check [Cloud Console IAM](https://console.cloud.google.com/iam-admin/iam?project=amazon-ppc-474902)
2. View [Secret Manager](https://console.cloud.google.com/security/secret-manager?project=amazon-ppc-474902)
3. Check function logs: `gcloud functions logs read amazon-ppc-optimizer --region=us-central1 --gen2 --limit=50`
