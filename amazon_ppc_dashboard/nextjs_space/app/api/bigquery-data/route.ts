import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';
import { resolveGCPCredentials, getFirstSetEnv, PROJECT_ID_ENV_NAMES } from '../lib/credentials';

const DEFAULT_DATASET_ID = process.env.BQ_DATASET_ID || 'amazon_ppc_data';
const PROJECT_ID =
  process.env.GOOGLE_CLOUD_PROJECT ||
  process.env.GCP_PROJECT ||
  process.env.GCLOUD_PROJECT ||
  'amazon-ppc-474902';

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

    // Resolve GCP credentials
    const credentialResult = await resolveGCPCredentials();
    if (!credentialResult.success) {
      return NextResponse.json(
        {
          error: 'Failed to resolve GCP credentials',
          message: credentialResult.error?.message || 'Unknown credential error',
          hint: 'Set GCP_SERVICE_ACCOUNT_KEY environment variable with your service account JSON credentials',
        },
        { status: 500 },
      );
    }

    const projectId = credentialResult.projectId || getFirstSetEnv(PROJECT_ID_ENV_NAMES) || PROJECT_ID;
    const datasetId = DEFAULT_DATASET_ID;

    console.log(
      `[BigQuery API] Fetching data from ${projectId}.${datasetId}.${table} (limit=${limit})`,
    );

    // Initialize BigQuery client with credentials if available
    const bigqueryOptions = credentialResult.credentials 
      ? { projectId, credentials: credentialResult.credentials }
      : { projectId };
    const bigquery = new BigQuery(bigqueryOptions);

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
        rowCount: rows.length,
        rows,
      },
      { status: 200 },
    );
  } catch (err: any) {
    const message = err?.message || String(err);

    // 404-style: dataset or table missing
    if (
      message.includes('Not found: Dataset') ||
      message.includes('Not found: Table') ||
      message.includes('Not found: Dataset') ||
      (message.includes('Not found:') && message.includes('amazon_ppc_data'))
    ) {
      return NextResponse.json(
        {
          error: 'Dataset or table not found in BigQuery',
          message:
            'The dataset/table you requested does not exist in this project.',
          details: message,
          hint:
            'Confirm that the dataset "amazon_ppc_data" and the requested table exist in project "amazon-ppc-474902". ' +
            'You do NOT need to run any setup script; just ensure the dataset and table names match.',
        },
        { status: 404 },
      );
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
