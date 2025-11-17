# Install Cloud Function to Google Cloud

## Project Information
**Project ID:** `amazon-ppc-474902`  
**Region:** `us-central1`  
**Function Name:** `amazonSalesData`

> 📋 **Quick Reference:** See [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) for a step-by-step deployment checklist.

---

## Quick Install (3 Steps)

### Step 1: Authenticate and Set Project

```bash
gcloud auth login
gcloud config set project amazon-ppc-474902
```

### Step 2: Enable Required APIs

```bash
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### Step 3: Setup Secrets (if not already done)

You need to store your Amazon SP-API credentials in Google Secret Manager:

```bash
# Replace these values with your actual credentials
echo -n "YOUR_CLIENT_ID_HERE" | gcloud secrets create AMAZON_SP_API_CLIENT_ID --data-file=-
echo -n "YOUR_CLIENT_SECRET_HERE" | gcloud secrets create AMAZON_SP_API_CLIENT_SECRET --data-file=-
echo -n "YOUR_REFRESH_TOKEN_HERE" | gcloud secrets create AMAZON_SP_API_REFRESH_TOKEN --data-file=-
echo -n "ATVPDKIKX0DER" | gcloud secrets create AMAZON_MARKETPLACE_ID --data-file=-
```

**Note:** Replace the placeholder values with your actual Amazon SP-API credentials.

**Common Marketplace IDs:**
- 🇺🇸 United States: `ATVPDKIKX0DER`
- 🇨🇦 Canada: `A2EUQ1WTGCTBG2`
- 🇬🇧 United Kingdom: `A1F83G8C2ARO7P`
- 🇩🇪 Germany: `A1PA6795UKMFR9`

### Step 4: Grant Secret Access

```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format="value(projectNumber)")

# Grant access to secrets
for SECRET in AMAZON_SP_API_CLIENT_ID AMAZON_SP_API_CLIENT_SECRET AMAZON_SP_API_REFRESH_TOKEN AMAZON_MARKETPLACE_ID; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

### Step 5: Deploy the Cloud Function

```bash
cd cloud-function

gcloud functions deploy amazonSalesData \
  --gen2 \
  --runtime nodejs20 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point amazonSalesData \
  --region us-central1 \
  --memory 512MB \
  --timeout 540s \
  --project amazon-ppc-474902
```

**This will take 2-5 minutes.** You'll see output like:

```
Deploying function...done.
httpsTrigger:
  url: https://us-central1-amazon-ppc-474902.cloudfunctions.net/amazonSalesData
```

### Step 6: Get the Function URL

```bash
gcloud functions describe amazonSalesData \
  --region us-central1 \
  --project amazon-ppc-474902 \
  --gen2 \
  --format="value(serviceConfig.uri)"
```

Copy this URL - you'll need it for your frontend.

### Step 7: Update Your Frontend

Navigate back to the project root and create/update `.env`:

```bash
cd ..
echo "VITE_CLOUD_FUNCTION_URL=YOUR_FUNCTION_URL_HERE" > .env
```

Replace `YOUR_FUNCTION_URL_HERE` with the URL from Step 6.

### Step 8: Test Locally

```bash
npm run dev
```

Open http://localhost:5173 and test the dashboard.

---

## One-Line Deploy (After Initial Setup)

If secrets are already configured, redeploy with:

```bash
cd cloud-function && gcloud functions deploy amazonSalesData --gen2 --runtime nodejs20 --trigger-http --allow-unauthenticated --entry-point amazonSalesData --region us-central1 --memory 512MB --timeout 540s --project amazon-ppc-474902
```

---

## Test the Function

Test with curl:

```bash
FUNCTION_URL=$(gcloud functions describe amazonSalesData --region us-central1 --project amazon-ppc-474902 --gen2 --format="value(serviceConfig.uri)")

curl -X POST $FUNCTION_URL \
  -H "Content-Type: application/json" \
  -d '{
    "startDate": "2024-01-01T00:00:00Z",
    "endDate": "2024-01-31T23:59:59Z"
  }'
```

---

## View Logs

```bash
gcloud functions logs read amazonSalesData \
  --region us-central1 \
  --project amazon-ppc-474902 \
  --gen2 \
  --limit 50
```

---

## Check Function Status

```bash
gcloud functions describe amazonSalesData \
  --region us-central1 \
  --project amazon-ppc-474902 \
  --gen2
```

---

## Troubleshooting

### "Permission denied" errors
Make sure you've run Step 4 to grant secret access.

### "Secret not found"
Make sure you've run Step 3 to create the secrets.

### "Function timeout"
Increase the timeout:
```bash
--timeout 540s
```

### View detailed logs
```bash
gcloud functions logs read amazonSalesData \
  --region us-central1 \
  --project amazon-ppc-474902 \
  --gen2 \
  --limit 100 \
  --format="table(time_utc, log)"
```

---

## Cost Estimate

- **Cloud Functions:** First 2M invocations/month FREE, then $0.40/million
- **Secret Manager:** First 6 secret versions FREE
- **Typical monthly cost:** $0-3 for personal use

---

## Next Steps

After successful deployment:

1. ✅ Test the function with the curl command above
2. ✅ Update your `.env` file with the function URL
3. ✅ Run `npm run dev` to test locally
4. ✅ Deploy your frontend to your preferred hosting platform

---

## Where to Get Amazon SP-API Credentials

1. Go to [Amazon Seller Central](https://sellercentral.amazon.com/)
2. Navigate to **Apps & Services** → **Develop Apps**
3. Create a new app to get your Client ID and Client Secret
4. Follow the OAuth flow to get your Refresh Token

See `DEPLOYMENT.md` for detailed instructions on obtaining these credentials.

---

## Security Note

Never commit secrets to git. The `.env` file is already in `.gitignore`.

---

## Support

- **Amazon SP-API Docs:** https://developer-docs.amazon.com/sp-api/
- **Google Cloud Functions:** https://cloud.google.com/functions/docs
- **Project Console:** https://console.cloud.google.com/functions/list?project=amazon-ppc-474902
