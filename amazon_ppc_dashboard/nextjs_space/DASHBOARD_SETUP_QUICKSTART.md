# Dashboard Setup Quickstart

Get your Amazon PPC Dashboard showing live data in **2 minutes**! 🚀

## What You Need

1. A Google Cloud service account key (JSON file)
2. Access to your deployment platform (Vercel, Cloud Run, etc.)

## Quick Setup (2 minutes)

### Step 1: Get Your Service Account Key

1. Go to [Google Cloud Console - Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Select your service account (or create a new one)
3. Click **Keys** tab → **Add Key** → **Create new key**
4. Choose **JSON** format
5. Download the file

### Step 2: Set Environment Variable

**In Vercel:**
1. Go to your project → Settings → Environment Variables
2. Add variable: `GCP_SERVICE_ACCOUNT_KEY`
3. Paste the **entire contents** of your JSON file as the value
4. Save

**In other platforms:**
- Set `GCP_SERVICE_ACCOUNT_KEY` to your service account JSON
- You can use raw JSON or base64-encoded JSON (we auto-detect!)

### Step 3: Grant BigQuery Permissions

Your service account needs these roles:

```bash
# Get your service account email from the JSON file
SERVICE_ACCOUNT_EMAIL="your-service-account@project.iam.gserviceaccount.com"
PROJECT_ID="your-project-id"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.jobUser"
```

Or grant via [IAM Console](https://console.cloud.google.com/iam-admin/iam):
- Find your service account
- Click Edit (pencil icon)
- Add roles: **BigQuery Data Viewer** + **BigQuery Job User**

### Step 4: Deploy and Test

1. Redeploy your dashboard
2. Visit the dashboard homepage
3. You should see live optimization data! 🎉

## Troubleshooting

### No Data Showing?

Check these diagnostic endpoints:
- `/api/setup-guide` - Interactive setup checklist
- `/api/config-check` - Configuration diagnostics
- `/api/bigquery-data?limit=1` - Test BigQuery connection

### Common Issues

**"Missing Google Cloud credentials"**
- Make sure `GCP_SERVICE_ACCOUNT_KEY` is set
- Verify the JSON is complete (starts with `{` and ends with `}`)
- Redeploy after setting the variable

**"Access Denied" or "Permission denied"**
- Grant BigQuery permissions (see Step 3)
- Wait 1-2 minutes for permissions to propagate
- Verify you're using the correct project ID

**"Table not found"**
- Run the optimizer at least once to create tables
- Check that optimizer is configured for BigQuery

**"Invalid JSON" or "base64 decode error"**
- The dashboard auto-detects format - don't worry!
- Copy the entire JSON file contents
- Or encode as base64: `cat service-account.json | base64 | tr -d '\n'`

## Advanced: Running in Google Cloud

If you're deploying the dashboard to **Google Cloud Run** or **Cloud Functions**, you can use Application Default Credentials instead:

1. Skip setting `GCP_SERVICE_ACCOUNT_KEY`
2. Make sure the Cloud Run/Functions service account has BigQuery permissions
3. The dashboard will automatically use ADC

## Need More Help?

- 📖 See `/api/setup-guide` for interactive setup
- 🔍 See `/api/config-check` for configuration status
- 📚 See `README_DASHBOARD_SETUP.md` for detailed docs
- 🐛 See `TROUBLESHOOTING.md` for common issues

## Architecture Note

The dashboard reads optimization data from BigQuery. The **optimizer** (Cloud Function) writes data to BigQuery automatically. You just need to give the **dashboard** read access to that data.

```
┌─────────────┐         ┌──────────┐         ┌───────────┐
│  Optimizer  │ writes  │ BigQuery │  reads  │ Dashboard │
│ (Cloud Fn)  │────────>│          │<────────│ (Vercel)  │
└─────────────┘         └──────────┘         └───────────┘
```

Both need service account credentials, but they can use different service accounts if needed.
