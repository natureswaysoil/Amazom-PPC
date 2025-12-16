cd /workspaces/Amazom-PPC/amazon_ppc_dashboard/nextjs_space

cat > app/api/bigquery-data/route.ts << 'EOF'
import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

export async function GET(request: NextRequest) {
  // Get configuration from environment variables with fallback to default
  const datasetId = process.env.BQ_DATASET_ID || 'amazon_ppc_data';
  const location = process.env.BQ_LOCATION || 'us-east4';
  const DEFAULT_PROJECT_ID = 'amazon-ppc-474902';

  // These variables need to be accessible inside the catch block for error reporting
  let credentials: any = undefined;
  let projectId = getFirstSetEnv(PROJECT_ID_ENV_NAMES);
  let credentialSource = 'Application Default Credentials';

  try {
    // Resolve credentials using the new shared utility
    const credentialResult = resolveGCPCredentials();

let cachedDatasetLocation: string | null = null;

/**
 * Auto-detect the dataset location from BigQuery metadata.
 * Falls back to BQ_LOCATION / BIGQUERY_LOCATION if metadata lookup fails.
 */
async function getDatasetLocation(bigquery: BigQuery, datasetId: string) {
  if (cachedDatasetLocation) {
    return cachedDatasetLocation;
  }

  try {
    const [metadata] = await bigquery.dataset(datasetId).getMetadata();
    const loc = (metadata.location as string | undefined) || null;
    if (loc) {
      cachedDatasetLocation = loc;
      console.log(
        `[BigQuery] Auto-detected dataset location for ${datasetId}: ${loc}`,
      );
      return loc;
    }
  } catch (err: any) {
    console.warn(
      `[BigQuery] Could not auto-detect location for dataset ${datasetId}:`,
      err?.message || err,
    );
  }

  const envLoc =
    process.env.BQ_LOCATION ||
    process.env.BIGQUERY_LOCATION ||
    process.env.BQ_REGION ||
    null;

  if (envLoc) {
    cachedDatasetLocation = envLoc;
    console.log(
      `[BigQuery] Using dataset location from env for ${datasetId}: ${envLoc}`,
    );
  } else {
    console.log(
      `[BigQuery] No explicit dataset location set; letting BigQuery choose default.`,
    );
  }

  return cachedDatasetLocation;
}

/**
 * Optional API key check for external callers.
 * If DASHBOARD_API_KEY is unset, auth is skipped (handy for local dev).
 */
function verifyApiKey(req: NextRequest): string | null {
  const apiKey = process.env.DASHBOARD_API_KEY;
  if (!apiKey) return null;

  const authHeader = req.headers.get('authorization');
  const bearer =
    authHeader && authHeader.startsWith('Bearer ')
      ? authHeader.slice(7)
      : undefined;
  const headerApiKey = req.headers.get('x-api-key') ?? undefined;

  if (bearer === apiKey || headerApiKey === apiKey) {
    return null;
  }

  return 'Unauthorized';
}

export async function GET(request: NextRequest) {
  try {
    // --- Auth (optional) ---
    const authError = verifyApiKey(request);
    if (authError) {
      return NextResponse.json({ error: authError }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const table = searchParams.get('table') || 'optimization_results';
    const limit = Number.parseInt(searchParams.get('limit') ?? '100', 10) || 100;

    const projectId = PROJECT_ID;
    const datasetId = DEFAULT_DATASET_ID;

    console.log(
      `[BigQuery API] Fetching data from ${projectId}.${datasetId}.${table} (limit=${limit})`,
    );

    const bigquery = new BigQuery({ projectId });

    // Auto-detect dataset location for the query job
    const location = await getDatasetLocation(bigquery, datasetId);

    const query = `
      SELECT *
      FROM \`${projectId}.${datasetId}.${table}\`
      ORDER BY timestamp DESC
      LIMIT @limit
    `;

    const [job] = await bigquery.createQueryJob({
      query,
      params: { limit },
      // Only set location if we know it; otherwise let BigQuery decide.
      ...(location ? { location } : {}),
    });

    const [rows] = await job.getQueryResults();

    return NextResponse.json(
      {
        ok: true,
        projectId,
        datasetId,
        location: location || 'auto',
        table,
        rowCount: processedRows.length,
        credentialSource: credentialSource
      }
    }, { status: 200 });
    
  } catch (error: any) {
    console.error('BigQuery query error:', error);
    
    // Check if it's a "not found" error
    if (error.message && error.message.includes('Not found')) {
      return NextResponse.json({
        error: 'Dataset or table not found',
        message: 'Please run setup-bigquery.sh to create the BigQuery dataset and tables',
        details: error.message,
        troubleshooting: [
          'Run ./setup-bigquery.sh (or bash setup-bigquery.sh <PROJECT_ID> <DATASET_ID> <LOCATION>)',
          'Confirm BQ_DATASET_ID and BQ_LOCATION match where your optimizer writes data',
          'After creating the dataset, trigger a new optimization run to populate rows'
        ]
      }, { status: 404 });
    }

    const activeProjectId = projectId || getFirstSetEnv(PROJECT_ID_ENV_NAMES) || DEFAULT_PROJECT_ID;
    const datasetPath = `${activeProjectId}.${datasetId}`;

    // Check for BigQuery permission errors
    if (error.message && (
      error.message.includes('bigquery.jobs.create') ||
      error.message.includes('bigquery.tables.get') ||
      error.message.includes('Access Denied') ||
      error.message.includes('does not have bigquery') ||
      (error.code === 403 || error.code === 7) // 403 Forbidden or gRPC PERMISSION_DENIED
    )) {
      return NextResponse.json({
        error: 'Access Denied',
        message: 'The service account does not have sufficient BigQuery permissions',
        details: error.message,
        projectId: activeProjectId,
        datasetId,
        datasetPath,
        troubleshooting: [
          'The service account needs these BigQuery IAM roles:',
          '  • roles/bigquery.dataViewer (or roles/bigquery.dataEditor) - to read/write data',
          '  • roles/bigquery.jobUser - to create and run query jobs',
          '',
          `Active project/dataset: ${datasetPath} (location: ${location})`,
          'If your optimizer writes to a different dataset, set BQ_DATASET_ID to match.',
          'Ensure the dataset ID is amazon_ppc_data when using the default deployment settings.',
          '',
          'To grant the required permissions, run these commands in Google Cloud Shell:',
          '',
          `# Get the service account email from your credentials`,
          `SERVICE_ACCOUNT_EMAIL=$(echo "$GCP_SERVICE_ACCOUNT_KEY" | jq -r .client_email)`,
          '',
          `# Grant BigQuery Data Viewer role`,
          `gcloud projects add-iam-policy-binding ${projectId} \\`,
          `  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \\`,
          `  --role="roles/bigquery.dataViewer"`,
          '',
          `# Grant BigQuery Job User role (required to run queries)`,
          `gcloud projects add-iam-policy-binding ${projectId} \\`,
          `  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \\`,
          `  --role="roles/bigquery.jobUser"`,
          '',
          'Alternatively, you can grant these roles in the Google Cloud Console:',
          `  1. Go to https://console.cloud.google.com/iam-admin/iam?project=${projectId}`,
          '  2. Find your service account in the list',
          '  3. Click "Edit principal" (pencil icon)',
          '  4. Add the roles: BigQuery Data Viewer + BigQuery Job User',
          '  5. Click "Save"',
          '',
          'After granting permissions, refresh this page to try again.',
        ],
        documentation: 'See BIGQUERY_DATASET_FIX.md and ACCESS_GUIDE.md for more details.',
      }, { status: 403 });
    }

    console.error('[BigQuery API] Unexpected error:', err);

    return NextResponse.json(
      {
        error: 'Failed to query BigQuery',
        message,
      },
      { status: 500 },
    );
  }
}
EOF
