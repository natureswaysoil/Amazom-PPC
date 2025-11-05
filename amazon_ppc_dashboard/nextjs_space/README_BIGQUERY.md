# Amazon PPC Dashboard with BigQuery Integration

This Next.js dashboard displays real-time Amazon PPC optimization data from BigQuery.

## Features

- 📊 **Real-time Data**: Displays optimization results from BigQuery
- 📈 **Summary Statistics**: 7-day overview of key metrics
- 🔄 **Auto-refresh**: Updates every 5 minutes
- ⚡ **Fast Queries**: Optimized BigQuery queries with partitioning
- 🎨 **Clean UI**: Modern, responsive dashboard design

## Prerequisites

1. **BigQuery Setup**: Run `../../setup-bigquery.sh` to create dataset and tables
2. **Google Cloud Authentication**: Service account with BigQuery access
3. **Node.js 18+**: Required for Next.js 14
4. **Environment Variables**: Configure BigQuery connection

## Local Development

### 1. Install Dependencies

```bash
cd amazon_ppc_dashboard/nextjs_space
npm install
```

### 2. Configure Environment Variables

Create a `.env.local` file:

```bash
# BigQuery Configuration
BQ_DATASET_ID=amazon_ppc
BQ_LOCATION=us-east4

# Optional: Project ID (auto-extracted from service account if not provided)
# GCP_PROJECT=amazon-ppc-474902
# GOOGLE_CLOUD_PROJECT=amazon-ppc-474902

# Dashboard API Key (optional for local dev)
DASHBOARD_API_KEY=your_api_key_here
```

### 3. Set Up Google Cloud Authentication

For local development:

```bash
# Authenticate with gcloud
gcloud auth application-default login

# Or use a service account key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### 4. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the dashboard.

## Deployment to Vercel

### 1. Push to GitHub

Ensure your code is pushed to GitHub:

```bash
git add .
git commit -m "Add BigQuery dashboard"
git push
```

### 2. Import to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Click "Add New Project"
3. Import your GitHub repository
4. Set **Root Directory** to: `amazon_ppc_dashboard/nextjs_space`

### 3. Configure Environment Variables

In Vercel project settings → Environment Variables, add:

```
BQ_DATASET_ID=amazon_ppc
BQ_LOCATION=us-east4
DASHBOARD_API_KEY=your_api_key_here

# Optional: Project ID (auto-extracted from service account credentials if not provided)
# GCP_PROJECT=amazon-ppc-474902
# GOOGLE_CLOUD_PROJECT=amazon-ppc-474902
```

### 4. Add Google Cloud Service Account

Create a service account for Vercel:

```bash
# Create service account
gcloud iam service-accounts create vercel-dashboard \
    --display-name="Vercel Dashboard Service Account" \
    --project=amazon-ppc-474902

# Grant BigQuery permissions
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
    --member="serviceAccount:vercel-dashboard@amazon-ppc-474902.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding amazon-ppc-474902 \
    --member="serviceAccount:vercel-dashboard@amazon-ppc-474902.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"

# Create and download key
gcloud iam service-accounts keys create vercel-key.json \
    --iam-account=vercel-dashboard@amazon-ppc-474902.iam.gserviceaccount.com
```

Add the service account key to Vercel:

1. Copy the contents of `vercel-key.json`
2. In Vercel, add environment variable: `GCP_SERVICE_ACCOUNT_KEY` (recommended) or `GOOGLE_APPLICATION_CREDENTIALS`
3. Paste the entire JSON content as the value
4. **The dashboard will automatically extract the project_id from the JSON**, so you don't need to set GCP_PROJECT/GOOGLE_CLOUD_PROJECT separately

### 5. Deploy

Click "Deploy" in Vercel. Your dashboard will be live at:
```
https://your-project.vercel.app
```

## API Endpoints

### GET /api/bigquery-data

Query optimization data from BigQuery.

**Parameters:**
- `table`: Table to query (`optimization_results`, `campaign_details`, `summary`)
- `limit`: Number of rows to return (default: 10)
- `days`: Number of days to look back (default: 7)

**Examples:**

```bash
# Get recent optimization results
curl "https://your-dashboard.vercel.app/api/bigquery-data?table=optimization_results&limit=5&days=7"

# Get summary statistics
curl "https://your-dashboard.vercel.app/api/bigquery-data?table=summary&days=30"

# Get campaign details
curl "https://your-dashboard.vercel.app/api/bigquery-data?table=campaign_details&limit=20"
```

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "timestamp": "2025-11-03T10:30:00.000Z",
      "run_id": "abc-123",
      "status": "success",
      "keywords_optimized": 45,
      "average_acos": 0.38,
      ...
    }
  ],
  "metadata": {
    "projectId": "amazon-ppc-474902",
    "datasetId": "amazon_ppc",
    "table": "optimization_results",
    "rowCount": 5
  }
}
```

## Dashboard Pages

### Home Page (`/`)

Displays:
- Summary statistics (7-day overview)
- Recent optimization runs table
- Real-time status indicators
- Auto-refresh functionality

### API Health Check (`/api/health`)

Returns dashboard health status:

```bash
curl "https://your-dashboard.vercel.app/api/health"
```

## Troubleshooting

### Error: "GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variable must be set"

**Solution**: This error occurs when neither the project ID environment variables nor service account credentials are configured in your Vercel deployment.

**Quick Diagnosis:**
```bash
# Check what's actually configured
curl "https://your-dashboard.vercel.app/api/config-check"
```

**Quick Fix (Recommended):**

The dashboard can now automatically extract the project ID from your service account credentials, so you only need to provide the credentials:

1. **Go to Vercel** → Your Project → Settings → Environment Variables

2. **Add Service Account Credentials** (choose one method):
   
   **Method A (Recommended):**
   ```
   GCP_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"amazon-ppc-474902",...}
   ```
   Paste the entire JSON from your service account key file. **The dashboard will automatically extract the project_id from this JSON.**
   
   **Method B:**
   ```
   GOOGLE_APPLICATION_CREDENTIALS={"type":"service_account",...}
   ```
   Also paste the entire JSON content (NOT a file path). **The project_id will be auto-extracted.**

3. **Add BigQuery Configuration:**
   ```
   BQ_DATASET_ID=amazon_ppc
   BQ_LOCATION=us-east4
   ```

4. **(Optional) Explicitly Set Project ID:**
   If you prefer to set it explicitly rather than relying on auto-extraction:
   ```
   GCP_PROJECT=amazon-ppc-474902
   GOOGLE_CLOUD_PROJECT=amazon-ppc-474902
   ```

5. **Important:** Select **Production, Preview, and Development** for all variables

6. **Redeploy** the application (Vercel → Deployments → Redeploy)

7. **Verify** the fix:
   ```bash
   curl "https://your-dashboard.vercel.app/api/config-check"
   curl "https://your-dashboard.vercel.app/api/bigquery-data?table=optimization_results&limit=1"
   ```

**Common Mistakes:**
- Using a file path for credentials (won't work on Vercel)
- Forgetting to redeploy after adding variables
- Not selecting all environments (Production/Preview/Development)
- Missing service account credentials entirely

**Good News:** You no longer need to set both the service account credentials AND the project ID separately - just provide the service account JSON and the project ID will be extracted automatically!

For detailed deployment instructions, see [DEPLOYMENT.md](./DEPLOYMENT.md).

### Error: "Dataset not found"

**Solution**: Run the BigQuery setup script:

```bash
cd ../..
./setup-bigquery.sh amazon-ppc-474902 amazon_ppc us-east4
```

### Error: "Permission denied"

**Solution**: Grant BigQuery permissions to the service account:

```bash
gcloud projects add-iam-policy-binding amazon-ppc-474902 \
    --member="serviceAccount:YOUR_SERVICE_ACCOUNT" \
    --role="roles/bigquery.dataViewer"
```

### No Data Showing

**Possible causes:**
1. No optimization runs have been executed yet
2. BigQuery tables are empty
3. Service account doesn't have permissions
4. Incorrect environment variables

**Debug steps:**

1. Check if tables exist:
   ```bash
   bq ls amazon-ppc-474902:amazon_ppc
   ```

2. Check if data exists:
   ```bash
   bq query --use_legacy_sql=false \
     "SELECT COUNT(*) FROM \`amazon-ppc-474902.amazon_ppc.optimization_results\`"
   ```

3. Check Vercel logs for errors:
   ```bash
   vercel logs
   ```

### Dashboard Shows Error on Load

**Solution**: Check browser console for errors. Common issues:
- Environment variables not set in Vercel
- Service account key invalid or missing
- Network/CORS issues (shouldn't occur with Vercel)

## Performance Optimization

### Query Caching

BigQuery results are cached by default. For custom caching:

```typescript
// Add cache control headers in route.ts
return NextResponse.json(data, {
  headers: {
    'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600'
  }
});
```

### Cost Optimization

- Queries use date partitioning to minimize data scanned
- Default lookback is 7 days (adjustable)
- Queries select specific columns (not `SELECT *`)
- Tables are partitioned by day for efficient filtering

**Estimated costs**: <$1/month for typical usage

## Security

### Authentication

Add authentication to protect your dashboard:

1. **NextAuth.js** (recommended):
   ```bash
   npm install next-auth
   ```

2. **API Key Protection**:
   - Already implemented for optimizer endpoints
   - Add to BigQuery endpoint if needed

3. **IP Allowlisting**:
   - Configure in Vercel project settings
   - Or use Cloudflare in front of Vercel

### Service Account Security

- Use separate service accounts for different environments
- Grant minimal required permissions (Principle of Least Privilege)
- Rotate service account keys regularly
- Never commit keys to git

## Monitoring

### View Logs

**Vercel Logs:**
```bash
vercel logs --follow
```

**BigQuery Audit Logs:**
```bash
gcloud logging read "resource.type=bigquery_resource" --limit=50
```

### Set Up Alerts

Create alerts for:
- Failed queries
- High query costs
- Service account errors
- Dashboard downtime

## Support

For issues:
1. Check the logs (Vercel and BigQuery)
2. Review BIGQUERY_INTEGRATION.md in root directory
3. Ensure setup-bigquery.sh was run successfully
4. Verify service account permissions

## Summary Checklist

- [ ] BigQuery dataset and tables created (`setup-bigquery.sh`)
- [ ] Service account created with BigQuery permissions
- [ ] Environment variables configured in Vercel
- [ ] Dashboard deployed and accessible
- [ ] API endpoints returning data
- [ ] Optimization runs writing to BigQuery
- [ ] Dashboard displaying data correctly

🎉 Once all steps are complete, your dashboard will display real-time optimization data from BigQuery!
