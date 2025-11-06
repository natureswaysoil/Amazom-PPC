# GitHub Secrets Configuration Guide

This guide explains how to configure all required GitHub repository secrets for automated CI/CD deployment.

## Overview

The automated deployment workflow (`.github/workflows/deploy-to-cloud.yml`) requires 9 repository secrets to function properly. These secrets contain sensitive credentials that should never be committed to the repository.

## Required Secrets

| Priority | Secret Name | Description | Required | Used For |
|----------|-------------|-------------|----------|----------|
| 🔴 Critical | `GCP_PROJECT_ID` | Your Google Cloud Project ID | ✅ Yes | All GCP operations |
| 🔴 Critical | `GCP_SA_KEY` | Google Cloud service account JSON key | ✅ Yes | Authentication to GCP |
| 🔴 Critical | `AMAZON_CLIENT_ID` | Amazon Ads API Client ID | ✅ Yes | Amazon Ads authentication |
| 🔴 Critical | `AMAZON_CLIENT_SECRET` | Amazon Ads API Client Secret | ✅ Yes | Amazon Ads authentication |
| 🔴 Critical | `AMAZON_REFRESH_TOKEN` | Amazon Ads API Refresh Token | ✅ Yes | Amazon Ads token refresh |
| 🔴 Critical | `AMAZON_PROFILE_ID` | Amazon Ads Profile ID | ✅ Yes | Campaign targeting |
| 🟡 Optional | `GMAIL_USER` | Gmail address for notifications | ⚠️ Optional | Email notifications |
| 🟡 Optional | `GMAIL_PASS` | Gmail App Password | ⚠️ Optional | Email notifications |
| 🟡 Optional | `DASHBOARD_API_KEY` | Dashboard authentication key | ⚠️ Optional | Dashboard updates |

## Step-by-Step Setup

### 1. Navigate to Repository Secrets

1. Go to your GitHub repository: https://github.com/natureswaysoil/Amazom-PPC
2. Click **Settings** (top navigation)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**

### 2. Configure Critical Secrets (Required)

#### GCP_PROJECT_ID

**What it is**: Your Google Cloud Project ID (e.g., `amazon-ppc-474902`)

**How to get it**:
```bash
# List your projects
gcloud projects list

# Or get current project
gcloud config get-value project
```

**Add to GitHub**:
- Name: `GCP_PROJECT_ID`
- Secret: `amazon-ppc-474902` (your project ID)

---

#### GCP_SA_KEY

**What it is**: JSON key for a Google Cloud service account with deployment permissions

**How to create it**:

```bash
# Set your project ID
export PROJECT_ID="amazon-ppc-474902"

# Create service account
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

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.admin"

# Create and download the key
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions-deployer@${PROJECT_ID}.iam.gserviceaccount.com

# Display the key
cat github-actions-key.json
```

**Add to GitHub**:
- Name: `GCP_SA_KEY`
- Secret: Paste the **entire JSON** content from `github-actions-key.json`

**⚠️ Important**: After adding to GitHub, delete the local key file:
```bash
rm github-actions-key.json
```

---

#### AMAZON_CLIENT_ID

**What it is**: Amazon Advertising API Client ID

**Format**: `amzn1.application-oa2-client.xxxxxxxxxx`

**How to get it**:
1. Go to [Amazon Advertising API Console](https://advertising.amazon.com/API/)
2. Navigate to **Security Profiles**
3. Find your application
4. Copy the **Client ID**

**Add to GitHub**:
- Name: `AMAZON_CLIENT_ID`
- Secret: `amzn1.application-oa2-client.xxxxxxxxxx`

---

#### AMAZON_CLIENT_SECRET

**What it is**: Amazon Advertising API Client Secret

**Format**: `amzn1.oa2-cs.v1.xxxxxxxxxx`

**How to get it**:
1. Same location as Client ID (Security Profiles)
2. Copy the **Client Secret**
3. If you don't see it, you may need to rotate it

**Add to GitHub**:
- Name: `AMAZON_CLIENT_SECRET`
- Secret: `amzn1.oa2-cs.v1.xxxxxxxxxx`

---

#### AMAZON_REFRESH_TOKEN

**What it is**: Long-lived token for authenticating with Amazon Ads API

**Format**: `Atzr|IwEBIxxxxxxxxxx` (long string)

**How to get it**:
1. Complete Amazon Advertising API OAuth flow
2. Use the authorization code to get refresh token
3. See [Amazon's OAuth Guide](https://advertising.amazon.com/API/docs/en-us/guides/get-started/generate-api-tokens)

**Alternative**: If you already have a working refresh token from `config.json`, use that.

**Add to GitHub**:
- Name: `AMAZON_REFRESH_TOKEN`
- Secret: `Atzr|IwEBIxxxxxxxxxx` (paste entire token)

---

#### AMAZON_PROFILE_ID

**What it is**: Amazon Advertising Profile ID for your account

**Format**: Numeric string (e.g., `1780498399290938`)

**How to get it**:
1. Log in to [Amazon Advertising Console](https://advertising.amazon.com/)
2. Check the URL or profile switcher for your profile ID
3. Or use the Advertising API to list profiles

**Add to GitHub**:
- Name: `AMAZON_PROFILE_ID`
- Secret: `1780498399290938` (your profile ID)

---

### 3. Configure Optional Secrets (Recommended)

#### GMAIL_USER

**What it is**: Gmail address for sending deployment notifications

**Format**: `your-email@gmail.com`

**Add to GitHub**:
- Name: `GMAIL_USER`
- Secret: `natureswaysoil@gmail.com`

---

#### GMAIL_PASS

**What it is**: Gmail App Password (NOT your regular Gmail password)

**How to create it**:

1. **Enable 2-Factor Authentication** on your Gmail account (required for app passwords)
2. Go to [Google Account App Passwords](https://myaccount.google.com/apppasswords)
3. Sign in to your Gmail account
4. Select app: **Other (Custom name)**
5. Enter name: **GitHub Actions PPC Optimizer**
6. Click **Generate**
7. Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)

**Add to GitHub**:
- Name: `GMAIL_PASS`
- Secret: `xxxxxxxxxxxxxxxx` (16 characters, no spaces)

**Important Notes**:
- Use app password, NOT your regular Gmail password
- App passwords only work with 2-factor authentication enabled
- You can revoke app passwords anytime without changing your main password

---

#### DASHBOARD_API_KEY

**What it is**: Authentication key for dashboard API updates

**How to generate it**:

```bash
# Generate a secure random key
openssl rand -hex 32

# Or use Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Add to GitHub**:
- Name: `DASHBOARD_API_KEY`
- Secret: Paste the generated key

**Note**: Store this same key in your dashboard configuration for authentication.

---

## Verification

After adding all secrets, verify they're configured:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. You should see 9 secrets listed:
   - ✅ AMAZON_CLIENT_ID
   - ✅ AMAZON_CLIENT_SECRET
   - ✅ AMAZON_PROFILE_ID
   - ✅ AMAZON_REFRESH_TOKEN
   - ✅ DASHBOARD_API_KEY
   - ✅ GCP_PROJECT_ID
   - ✅ GCP_SA_KEY
   - ✅ GMAIL_PASS
   - ✅ GMAIL_USER

## Testing the Workflow

After configuring secrets, test the deployment workflow:

### Option 1: Manual Trigger

1. Go to **Actions** tab
2. Select **Deploy to Google Cloud** workflow
3. Click **Run workflow**
4. Select branch: `main`
5. Click **Run workflow**

### Option 2: Push to Main Branch

```bash
# Make a small change
echo "# Test deployment" >> README.md

# Commit and push
git add README.md
git commit -m "Test automated deployment"
git push origin main
```

The workflow will automatically trigger and deploy using your configured secrets.

## Security Best Practices

### ✅ DO

- ✅ Use GitHub Secrets for all sensitive data
- ✅ Use service account keys with minimal permissions
- ✅ Rotate secrets regularly (every 90 days)
- ✅ Use Gmail App Passwords instead of regular passwords
- ✅ Enable 2-factor authentication on all accounts
- ✅ Review secret access logs periodically
- ✅ Delete local copies of keys after uploading
- ✅ Use environment-specific secrets (prod/staging)

### ❌ DON'T

- ❌ Never commit secrets to git
- ❌ Don't share secrets via email or chat
- ❌ Don't use the same secrets for multiple environments
- ❌ Don't give service accounts more permissions than needed
- ❌ Don't use personal accounts for automation
- ❌ Don't skip rotating secrets
- ❌ Don't log or print secret values
- ❌ Don't store secrets in plain text files

## Updating Secrets

To update an existing secret:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Find the secret you want to update
3. Click the secret name
4. Click **Update secret**
5. Enter the new value
6. Click **Update secret**

**Note**: Updating a secret immediately affects all future workflow runs.

## Removing Secrets

To remove a secret:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Find the secret you want to remove
3. Click **Remove**
4. Confirm deletion

**Warning**: Removing required secrets will cause workflow failures.

## Troubleshooting

### Workflow fails with "Secret not found"

**Solution**: Ensure the secret name matches exactly (case-sensitive)

### Workflow fails with "Invalid credentials"

**Solution**: 
1. Verify the secret value is correct
2. Check if credentials have expired
3. Ensure no extra spaces or newlines in secret value

### GCP authentication fails

**Solution**:
1. Verify `GCP_SA_KEY` contains valid JSON
2. Check service account has required permissions
3. Ensure service account is not disabled

### Amazon Ads API fails

**Solution**:
1. Verify refresh token is valid
2. Check if API access is still active
3. Ensure profile ID is correct

### Email notifications not sending

**Solution**:
1. Verify Gmail App Password is correct (not regular password)
2. Ensure 2-factor authentication is enabled
3. Check if app password is revoked

## Additional Resources

- [GitHub Encrypted Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Google Cloud Service Account Keys](https://cloud.google.com/iam/docs/creating-managing-service-account-keys)
- [Amazon Advertising API Authentication](https://advertising.amazon.com/API/docs/en-us/guides/get-started/generate-api-tokens)
- [Gmail App Passwords Guide](https://support.google.com/accounts/answer/185833)

## Support

For issues with secrets setup:

- 📧 Email: james@natureswaysoil.com
- 📚 Documentation: [COMPLETE_DEPLOYMENT_GUIDE.md](COMPLETE_DEPLOYMENT_GUIDE.md)
- 🐛 GitHub Issues: [Create an issue](https://github.com/natureswaysoil/Amazom-PPC/issues)

---

**Last Updated**: November 6, 2024  
**Version**: 1.0.0
