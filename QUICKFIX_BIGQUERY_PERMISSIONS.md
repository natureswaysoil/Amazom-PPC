# Quick Fix: BigQuery Permission Error

**ERROR:** `User does not have bigquery.jobs.create permission`

## 🚀 Fastest Fix (2 minutes)

```bash
./fix-bigquery-permissions.sh
```

That's it! The script will:
- Auto-detect your service account
- Grant required permissions
- Confirm success

## ⚡ Manual Fix (3 minutes)

```bash
# Get your service account email
SERVICE_ACCOUNT_EMAIL=$(echo "$GCP_SERVICE_ACCOUNT_KEY" | jq -r .client_email)

# Grant the two required roles
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding amazon-ppc-474902 \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/bigquery.jobUser"
```

## 🖱️ UI Fix (5 minutes)

1. Go to: https://console.cloud.google.com/iam-admin/iam?project=amazon-ppc-474902
2. Find your service account
3. Click **Edit** (pencil icon)
4. Click **+ ADD ANOTHER ROLE**
5. Add: **BigQuery Data Viewer**
6. Add: **BigQuery Job User**
7. Click **Save**

## 📚 Need More Help?

- **Full guide:** [BIGQUERY_PERMISSIONS_FIX.md](BIGQUERY_PERMISSIONS_FIX.md)
- **Technical details:** [BIGQUERY_PERMISSION_FIX_SUMMARY.md](BIGQUERY_PERMISSION_FIX_SUMMARY.md)
- **Before/After:** [BEFORE_AFTER_COMPARISON.md](BEFORE_AFTER_COMPARISON.md)

## ❓ Why This Happens

Your service account can see BigQuery data but can't run queries. You need **two** roles:
- `bigquery.dataViewer` - to read data
- `bigquery.jobUser` - to create query jobs ⭐ (this is what's missing)

## ✅ After Fixing

1. Wait 1-2 minutes for permissions to propagate
2. Refresh your dashboard
3. Data should now load successfully

---

**Still stuck?** See the full troubleshooting guide in [BIGQUERY_PERMISSIONS_FIX.md](BIGQUERY_PERMISSIONS_FIX.md)
