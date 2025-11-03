# Deploy Updated Code with Enhanced Logging

## From Cloud Shell

1. **Clone or update the repository in Cloud Shell:**
```bash
cd ~
# If you haven't cloned yet:
git clone https://github.com/natureswaysoil/Amazom-PPC.git
cd Amazom-PPC

# Or if already cloned, pull latest:
cd ~/Amazom-PPC
git pull origin main
```

2. **Deploy the function:**
```bash
gcloud functions deploy amazon-ppc-optimizer \
  --gen2 \
  --runtime=python312 \
  --region=us-central1 \
  --source=. \
  --entry-point=run_optimizer \
  --trigger-http \
  --no-allow-unauthenticated \
  --set-secrets='AMAZON_CLIENT_ID=amazon-client-id:latest,AMAZON_CLIENT_SECRET=amazon-client-secret:latest,AMAZON_REFRESH_TOKEN=amazon-refresh-token:latest,PPC_PROFILE_ID=ppc-profile-id:latest,DASHBOARD_URL=dashboard-url:latest,DASHBOARD_API_KEY=dashboard-api-key:latest' \
  --project=amazon-ppc-474902
```

3. **Test the health check:**
```bash
curl "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?health=true"
```

4. **View the logs to see debug info:**
```bash
gcloud functions logs read amazon-ppc-optimizer \
  --region=us-central1 \
  --project=amazon-ppc-474902 \
  --limit=30
```

## Alternative: Deploy directly from GitHub

Or you can commit and push the changes, then deploy from the GitHub repo:

```bash
# In your codespace:
git add main.py
git commit -m "Add enhanced logging for dashboard health check"
git push origin main

# Then in Cloud Shell:
cd ~/Amazom-PPC
git pull origin main
# ... then run the deploy command above
```
