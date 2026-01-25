# Backend hotfix: reporting + budget pacer

This hotfix overlays the deployed `amazon-ppc-backend` image (used by Cloud Run Jobs like `ads-data-sync` and `budget-pacer`) by injecting a `sitecustomize.py`.

## What it does

- **Amazon Ads reporting**: improves report creation for `ads-data-sync` by trying a more compatible payload/schema for `POST /reporting/reports` and logging response bodies for 400/403 to aid debugging.
- **Budget pacer**: fixes the BigQuery filter for `campaign_performance` to use an ET date (avoids UTC/ET date skew).
- **Node CSV processor** (when present in the base image): patches `/app/dist/config-validator.*` so `getConfig()` lazily calls `validateConfig()` instead of throwing `"Config not validated yet. Call validateConfig() first."`.

## Build & deploy (Cloud Build)

```bash
export PROJECT=amazon-ppc-474902
export REGION=us-central1
export REPO=ppc-automation
export IMAGE=amazon-ppc-backend-hotfix
export BASE_IMAGE=gcr.io/amazon-ppc-bid-optimizer/amazon-ppc-backend:latest
export TAG=backend-hotfix-$(date +%Y%m%d-%H%M%S)
export DEST_IMAGE=$REGION-docker.pkg.dev/$PROJECT/$REPO/$IMAGE:$TAG

gcloud builds submit hotfix/backend-reporting \
  --project=$PROJECT \
  --config=cloudbuild.yaml \
  --substitutions=_BASE_IMAGE=$BASE_IMAGE,_DEST_IMAGE=$DEST_IMAGE \
  .
```

Update jobs:

```bash
gcloud run jobs update ads-data-sync --project=$PROJECT --region=$REGION --image=$DEST_IMAGE

# (Optional) budget pacer image update too.
gcloud run jobs update budget-pacer --project=$PROJECT --region=$REGION --image=$DEST_IMAGE
```

Run and inspect logs:

```bash
gcloud run jobs execute ads-data-sync --project=$PROJECT --region=$REGION --wait

gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name="ads-data-sync"' \
  --project=$PROJECT --freshness=1d --limit=200 --format='value(textPayload)'
```
