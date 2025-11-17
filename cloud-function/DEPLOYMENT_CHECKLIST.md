# Cloud Function Deployment Checklist

Use this checklist to ensure a smooth deployment of the Amazon Sales Data Cloud Function.

## Pre-Deployment ✓

- [ ] Google Cloud account created
- [ ] Billing enabled for project `amazon-ppc-474902`
- [ ] gcloud CLI installed on your machine
- [ ] Amazon Seller Central account with SP-API access
- [ ] Amazon SP-API credentials obtained:
  - [ ] Client ID
  - [ ] Client Secret
  - [ ] Refresh Token

## Deployment Steps ✓

- [ ] **Step 1:** Authenticate with Google Cloud
  ```bash
  gcloud auth login
  gcloud config set project amazon-ppc-474902
  ```

- [ ] **Step 2:** Enable required APIs
  ```bash
  gcloud services enable secretmanager.googleapis.com
  gcloud services enable cloudfunctions.googleapis.com
  gcloud services enable cloudbuild.googleapis.com
  ```

- [ ] **Step 3:** Create secrets in Secret Manager
  ```bash
  echo -n "YOUR_CLIENT_ID" | gcloud secrets create AMAZON_SP_API_CLIENT_ID --data-file=-
  echo -n "YOUR_CLIENT_SECRET" | gcloud secrets create AMAZON_SP_API_CLIENT_SECRET --data-file=-
  echo -n "YOUR_REFRESH_TOKEN" | gcloud secrets create AMAZON_SP_API_REFRESH_TOKEN --data-file=-
  echo -n "ATVPDKIKX0DER" | gcloud secrets create AMAZON_MARKETPLACE_ID --data-file=-
  ```

- [ ] **Step 4:** Grant secret access to Cloud Function service account
  ```bash
  PROJECT_NUMBER=$(gcloud projects describe amazon-ppc-474902 --format="value(projectNumber)")
  for SECRET in AMAZON_SP_API_CLIENT_ID AMAZON_SP_API_CLIENT_SECRET AMAZON_SP_API_REFRESH_TOKEN AMAZON_MARKETPLACE_ID; do
    gcloud secrets add-iam-policy-binding $SECRET \
      --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
  done
  ```

- [ ] **Step 5:** Deploy the Cloud Function
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

- [ ] **Step 6:** Get and save the function URL
  ```bash
  gcloud functions describe amazonSalesData \
    --region us-central1 \
    --project amazon-ppc-474902 \
    --gen2 \
    --format="value(serviceConfig.uri)"
  ```
  Function URL: `_______________________________________`

## Post-Deployment Testing ✓

- [ ] **Test the function** with curl:
  ```bash
  FUNCTION_URL=$(gcloud functions describe amazonSalesData --region us-central1 --project amazon-ppc-474902 --gen2 --format="value(serviceConfig.uri)")
  
  curl -X POST $FUNCTION_URL \
    -H "Content-Type: application/json" \
    -d '{"startDate": "2024-01-01T00:00:00Z", "endDate": "2024-01-31T23:59:59Z"}'
  ```

- [ ] Function returns successful response (HTTP 200)
- [ ] Response contains sales data or meaningful error message

## Frontend Integration ✓

- [ ] Update `.env` file with function URL
  ```bash
  cd .. # back to project root
  echo "VITE_CLOUD_FUNCTION_URL=YOUR_FUNCTION_URL_HERE" > .env
  ```

- [ ] Test frontend locally
  ```bash
  npm run dev
  ```

- [ ] Frontend can successfully call the Cloud Function
- [ ] Sales data displays correctly in dashboard

## Monitoring Setup (Optional) ✓

- [ ] View function logs to verify operation
  ```bash
  gcloud functions logs read amazonSalesData \
    --region us-central1 \
    --project amazon-ppc-474902 \
    --gen2 \
    --limit 50
  ```

- [ ] Set up Cloud Monitoring alerts (optional)
- [ ] Configure error reporting notifications (optional)

## Security Review ✓

- [ ] Secrets are stored in Secret Manager (not hardcoded)
- [ ] `.env` file is in `.gitignore`
- [ ] No credentials committed to git
- [ ] Service account has minimal required permissions
- [ ] Function timeout is reasonable (540s)

## Common Issues Troubleshooting ✓

If you encounter issues, check:

- [ ] All required APIs are enabled
- [ ] Service account has `secretAccessor` role for all secrets
- [ ] Amazon SP-API credentials are valid
- [ ] Marketplace ID matches your region
- [ ] Billing is enabled for the project
- [ ] Function logs for detailed error messages

## Success Criteria ✓

Your deployment is successful when:

- ✅ Cloud Function deploys without errors
- ✅ Function returns HTTP 200 on test requests
- ✅ Sales data is retrieved from Amazon SP-API
- ✅ Frontend can communicate with the function
- ✅ No errors in Cloud Function logs
- ✅ Cost monitoring shows reasonable usage

---

## Quick Commands Reference

**View logs:**
```bash
gcloud functions logs read amazonSalesData --region us-central1 --project amazon-ppc-474902 --gen2 --limit 50
```

**Redeploy:**
```bash
cd cloud-function && gcloud functions deploy amazonSalesData --gen2 --runtime nodejs20 --trigger-http --allow-unauthenticated --entry-point amazonSalesData --region us-central1 --memory 512MB --timeout 540s --project amazon-ppc-474902
```

**Check status:**
```bash
gcloud functions describe amazonSalesData --region us-central1 --project amazon-ppc-474902 --gen2
```

---

**Need help?** See [INSTALL_CLOUD_FUNCTION.md](INSTALL_CLOUD_FUNCTION.md) for detailed instructions.
