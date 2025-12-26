# Job Type Usage Examples

## Overview
The PPC Optimizer now supports job-type-based execution, allowing you to run specific features independently via Cloud Run jobs or Cloud Functions.

## Supported Job Types

| Job Type | Feature | Description |
|----------|---------|-------------|
| `keyword_harvest` | keyword_discovery | Discover and add new keywords |
| `bid_optimization` | bid_optimization | Optimize bids based on performance |
| `dayparting` | dayparting | Apply time-based bid adjustments |
| `campaign_management` | campaign_management | Manage campaign activation/deactivation |
| `negative_keywords` | negative_keywords | Add negative keywords |

## Usage

### Cloud Function / Cloud Run HTTP Request

#### Using Query Parameters
```bash
curl -X POST "https://your-function-url?job_type=keyword_harvest&dry_run=true" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

#### Using JSON Body
```bash
curl -X POST "https://your-function-url" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "keyword_harvest",
    "dry_run": true
  }'
```

### Cloud Scheduler Configuration

Create a scheduler job for keyword harvesting:
```bash
gcloud scheduler jobs create http keyword-harvest-daily \
  --location=us-central1 \
  --schedule="0 2 * * *" \
  --uri="https://your-function-url" \
  --http-method=POST \
  --time-zone="America/New_York" \
  --oidc-service-account-email="your-sa@project.iam.gserviceaccount.com" \
  --oidc-token-audience="https://your-function-url" \
  --headers="Content-Type=application/json" \
  --message-body='{"job_type": "keyword_harvest", "dry_run": false}'
```

### Multiple Job Types Example

Run different jobs at different times:
```bash
# Keyword harvest at 2 AM
gcloud scheduler jobs create http keyword-harvest-daily \
  --schedule="0 2 * * *" \
  --message-body='{"job_type": "keyword_harvest"}'

# Bid optimization at 6 AM
gcloud scheduler jobs create http bid-optimization-daily \
  --schedule="0 6 * * *" \
  --message-body='{"job_type": "bid_optimization"}'

# Dayparting at noon
gcloud scheduler jobs create http dayparting-daily \
  --schedule="0 12 * * *" \
  --message-body='{"job_type": "dayparting"}'
```

## Response Format

### Success Response (200 OK)
```json
{
  "status": "success",
  "job_type": "keyword_harvest",
  "feature": "keyword_discovery",
  "results": {
    "keyword_discovery": {
      "keywords_found": 10,
      "keywords_added": 5
    }
  },
  "run_id": "run-12345",
  "duration": 45.2
}
```

### Error Response (400 Bad Request)
```json
{
  "status": "error",
  "message": "Unknown job type: invalid_job",
  "supported_types": "keyword_harvest, bid_optimization, dayparting, campaign_management, negative_keywords"
}
```

## Environment Variables

All job types use the same environment variables:
- `AMAZON_CLIENT_ID` - Amazon Advertising API client ID
- `AMAZON_CLIENT_SECRET` - Amazon Advertising API client secret  
- `AMAZON_REFRESH_TOKEN` - Amazon Advertising API refresh token
- `AMAZON_PROFILE_ID` - Amazon Advertising profile ID
- `GCP_PROJECT` - Google Cloud project ID (for BigQuery)
- `DASHBOARD_URL` - Dashboard URL for results (optional)
- `DASHBOARD_API_KEY` - Dashboard API key (optional)

## Backwards Compatibility

The optimizer still works without specifying a job type - it will run all enabled features from the config:
```bash
# Run all enabled features (default behavior)
curl -X POST "https://your-function-url?dry_run=true" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

## Testing

Test with dry run mode:
```bash
curl -X POST "https://your-function-url?job_type=keyword_harvest&dry_run=true" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

This will execute the keyword harvest logic without making actual changes to campaigns.
