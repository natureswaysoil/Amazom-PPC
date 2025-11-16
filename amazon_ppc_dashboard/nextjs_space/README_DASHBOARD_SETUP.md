# Amazon PPC Dashboard - Setup Guide

This Next.js dashboard displays live Amazon PPC optimization data from BigQuery.

## Quick Start

### 1. Install Dependencies

```bash
cd amazon_ppc_dashboard/nextjs_space
npm install
```

### 2. Configure Environment Variables

Create a `.env.local` file:

```bash
# GCP Credentials (choose one method)
GCP_SERVICE_ACCOUNT_KEY='{"type":"service_account","project_id":"...","private_key":"...","client_email":"..."}'

# GCP Project Configuration
GCP_PROJECT=your-project-id
GOOGLE_CLOUD_PROJECT=your-project-id

# BigQuery Configuration
BQ_DATASET_ID=amazon_ppc
BQ_LOCATION=us-east4

# Dashboard API Key (must match optimizer)
DASHBOARD_API_KEY=your-secret-key-here

# Node Environment
NODE_ENV=development
```

### 3. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Verify Configuration

Visit these diagnostic endpoints:

- **Credentials Check:** [http://localhost:3000/api/credentials-debug](http://localhost:3000/api/credentials-debug)
- **Config Check:** [http://localhost:3000/api/config-check](http://localhost:3000/api/config-check)
- **BigQuery Test:** [http://localhost:3000/api/bigquery-data?table=optimization_results&limit=1](http://localhost:3000/api/bigquery-data?table=optimization_results&limit=1)

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `GCP_SERVICE_ACCOUNT_KEY` | Service account credentials (raw JSON or base64) | `{"type":"service_account",...}` |
| `GCP_PROJECT` | Google Cloud project ID | `amazon-ppc-474902` |
| `DASHBOARD_API_KEY` | Secret key for optimizer integration | `your-secret-key` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `BQ_DATASET_ID` | BigQuery dataset name | `amazon_ppc` |
| `BQ_LOCATION` | BigQuery dataset location | `us-east4` |
| `NODE_ENV` | Node environment | `production` |

## Credential Formats

### Method 1: Raw JSON (Recommended)

Set `GCP_SERVICE_ACCOUNT_KEY` to the complete service account JSON:

```bash
export GCP_SERVICE_ACCOUNT_KEY='{"type":"service_account","project_id":"your-project","private_key_id":"abc123...","private_key":"-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n","client_email":"service-account@project.iam.gserviceaccount.com",...}'
```

**Advantages:**
- ✅ Most reliable method
- ✅ Works on all platforms
- ✅ No encoding issues

### Method 2: Base64 Encoded

For platforms with special character issues:

```bash
# Encode credentials
cat service-account.json | base64 | tr -d '\n' > encoded.txt

# Set environment variable
export GCP_SERVICE_ACCOUNT_KEY="$(cat encoded.txt)"
```

**Advantages:**
- ✅ Avoids special character issues
- ✅ Works on platforms with strict env var rules

### Method 3: Component Credentials

Provide credentials as separate variables:

```bash
export GCP_CLIENT_EMAIL="service-account@project.iam.gserviceaccount.com"
export GCP_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n"
export GCP_PROJECT="your-project-id"
```

**Note:** Private key must use `\n` for newlines.

## Deployment

### Vercel

1. Go to your Vercel project → **Settings** → **Environment Variables**
2. Add all required environment variables
3. Deploy:
   ```bash
   vercel --prod
   ```

**Important for Vercel:**
- Use raw JSON for `GCP_SERVICE_ACCOUNT_KEY` (preferred)
- Vercel handles JSON correctly in environment variables
- No need for base64 encoding on Vercel

### Other Platforms

For platforms like Netlify, Railway, etc.:

1. Add environment variables in platform dashboard
2. Use raw JSON or base64 encoding as needed
3. Deploy using platform-specific method

## API Endpoints

### `/api/bigquery-data`

Query BigQuery tables.

**Query Parameters:**
- `table`: Table name (`optimization_results`, `campaign_details`, `summary`)
- `limit`: Max rows to return (1-100, default: 10)
- `days`: Days of historical data (1-365, default: 7)

**Example:**
```bash
curl 'http://localhost:3000/api/bigquery-data?table=optimization_results&limit=10&days=7'
```

### `/api/config-check`

Check configuration status.

**Example:**
```bash
curl http://localhost:3000/api/config-check
```

### `/api/credentials-debug`

Debug credential configuration (shows diagnostics without exposing secrets).

**Example:**
```bash
curl http://localhost:3000/api/credentials-debug
```

### `/api/optimization-results` (POST)

Receive optimization results from the optimizer.

**Headers:**
- `Authorization: Bearer <DASHBOARD_API_KEY>`
- `Content-Type: application/json`

**Example:**
```bash
curl -X POST http://localhost:3000/api/optimization-results \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"status":"success","results":{...}}'
```

## Troubleshooting

### Issue: "No Google Cloud credentials found"

**Solution:**
1. Check variable name is exactly `GCP_SERVICE_ACCOUNT_KEY`
2. Verify value is set: `echo $GCP_SERVICE_ACCOUNT_KEY | wc -c`
3. Visit `/api/credentials-debug` for detailed diagnostics

### Issue: "Base64 decoded but not valid JSON"

**Solution:**
1. **Recommended:** Switch to raw JSON method
2. Or verify base64 encoding:
   ```bash
   # Test decode locally
   echo "$GCP_SERVICE_ACCOUNT_KEY" | base64 -d | jq .
   ```
3. Re-encode if needed:
   ```bash
   cat service-account.json | base64 | tr -d '\n'
   ```

### Issue: "Access Denied" when querying BigQuery

**Solution:**
```bash
# Grant required permissions
SA_EMAIL="your-service-account@project.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding your-project-id \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.jobUser"
```

### Issue: "Dataset not found"

**Solution:**
1. Ensure optimizer has run at least once
2. Run BigQuery setup script from repository root:
   ```bash
   ./setup-bigquery.sh your-project-id amazon_ppc us-east4
   ```

### Issue: Dashboard shows loading but no data

**Causes & Solutions:**

1. **No data in BigQuery:**
   - Run optimizer: `curl -X POST $FUNCTION_URL -H "Authorization: Bearer $(gcloud auth print-identity-token)"`
   - Verify data: `bq query 'SELECT COUNT(*) FROM \`project.amazon_ppc.optimization_results\`'`

2. **Credentials issue:**
   - Visit `/api/credentials-debug`
   - Check for ✅ in diagnostics

3. **Wrong project/dataset:**
   - Verify `GCP_PROJECT` matches actual project
   - Verify `BQ_DATASET_ID` matches where optimizer writes

4. **API errors:**
   - Check browser console for errors
   - Test API directly: `curl http://localhost:3000/api/bigquery-data`

## Development

### Build for Production

```bash
npm run build
npm start
```

### Lint Code

```bash
npm run lint
```

### Project Structure

```
nextjs_space/
├── app/
│   ├── api/              # API routes
│   │   ├── bigquery-data/
│   │   ├── config-check/
│   │   ├── credentials-debug/
│   │   └── lib/          # Shared utilities
│   │       └── credentials.ts
│   ├── page.tsx          # Main dashboard page
│   └── layout.tsx        # Root layout
├── public/               # Static assets
├── package.json
└── next.config.js
```

## Security Notes

- ✅ **DO** store credentials in environment variables (never commit to Git)
- ✅ **DO** use separate service accounts for dev/prod
- ✅ **DO** grant minimum required permissions
- ✅ **DO** rotate credentials every 90 days
- ❌ **DON'T** expose credentials in client-side code
- ❌ **DON'T** log full credentials (only previews/diagnostics)
- ❌ **DON'T** commit `.env.local` to version control

## Support

For help with:
- **Credentials:** See `/api/credentials-debug` and `DASHBOARD_BIGQUERY_SETUP.md`
- **BigQuery:** See `BIGQUERY_INTEGRATION.md`
- **Optimizer:** See main repository `README.md`

## Related Documentation

- [DASHBOARD_BIGQUERY_SETUP.md](../../DASHBOARD_BIGQUERY_SETUP.md) - Complete setup guide
- [README.md](../../README.md) - Main project documentation
- [BIGQUERY_INTEGRATION.md](../../BIGQUERY_INTEGRATION.md) - BigQuery setup
