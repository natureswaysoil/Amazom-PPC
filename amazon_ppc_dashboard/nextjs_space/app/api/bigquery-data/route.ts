import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';
import {
  resolveGCPCredentials,
  getFirstSetEnv,
  PROJECT_ID_ENV_NAMES,
} from '../lib/credentials';
import { resolveDashboardApiKey } from '../lib/dashboard-api-key';

export const dynamic = 'force-dynamic';

const DATASET_ID_ENV_NAMES = [
  'BQ_DATASET_ID',
  'BIGQUERY_DATASET',
  'BIGQUERY_DATASET_ID',
  'BQ_DATASET',
  'BQ_DATASET_NAME',
];

const DEFAULT_DATASET_ID = getFirstSetEnv(DATASET_ID_ENV_NAMES) || 'amazon_ppc_data';
const PROJECT_ID =
  process.env.GOOGLE_CLOUD_PROJECT ||
  process.env.GCP_PROJECT ||
  process.env.GCP_PROJECT_ID ||
  process.env.GCLOUD_PROJECT ||
  'amazon-ppc-474902';

const BIGQUERY_PROJECT_ID_ENV_NAMES = [
  'BQ_PROJECT_ID',
  'BIGQUERY_PROJECT_ID',
  ...PROJECT_ID_ENV_NAMES,
];

let cachedDatasetLocation: string | null = null;
const cachedOrderColumnByTable = new Map<
  string,
  { column: string | null; sqlDateExpr: string | null }
>();

const PREFERRED_DATE_COLUMNS_BY_TABLE: Record<string, string[]> = {
  optimization_results: ['timestamp', 'run_timestamp', 'created_at'],
  optimization_progress: ['timestamp', 'created_at'],
  optimization_errors: ['timestamp', 'created_at'],
  optimizer_run_events: ['timestamp', 'created_at'],
  campaign_details: ['segments_date', 'date'],
  campaign_performance: ['segments_date', 'date'],
  keyword_performance: ['segments_date', 'date'],
  search_term_reports: ['segments_date', 'date'],
  sp_campaigns_v3: ['segments_date', 'date'],
  sp_campaign_metrics: ['startDate', 'segments_date', 'date'],
};

function normalizeBqFieldType(field: any): string {
  const raw =
    (field?.type as string | undefined) ||
    (field?.fieldType as string | undefined) ||
    (field?.dataType?.typeKind as string | undefined) ||
    '';
  return String(raw).toUpperCase();
}

function computeSqlDateExpr(column: string, fieldType: string): string | null {
  // Use a safe, schema-derived column name only.
  const col = `\`${column}\``;
  if (fieldType === 'DATE') return col;
  if (fieldType === 'TIMESTAMP') return `DATE(${col})`;
  if (fieldType === 'DATETIME') return `DATE(${col})`;
  return null;
}

async function getOrderColumnAndDateExpr(
  bigquery: BigQuery,
  projectId: string,
  datasetId: string,
  tableId: string,
) {
  const cacheKey = `${projectId}.${datasetId}.${tableId}`;
  const cached = cachedOrderColumnByTable.get(cacheKey);
  if (cached) return cached;

  try {
    const [metadata] = await bigquery
      .dataset(datasetId)
      .table(tableId)
      .getMetadata();

    const fields: any[] = metadata?.schema?.fields || [];
    const fieldByName = new Map<string, { name: string; type: string }>();
    for (const f of fields) {
      if (f?.name) fieldByName.set(String(f.name), { name: String(f.name), type: normalizeBqFieldType(f) });
    }

    const preferred = PREFERRED_DATE_COLUMNS_BY_TABLE[tableId] || [];
    const fallbackPreferred = [
      'timestamp',
      'run_timestamp',
      'created_at',
      'updated_at',
      'fetch_timestamp',
      'segments_date',
      'startDate',
      'date',
    ];
    const candidates = [...preferred, ...fallbackPreferred];

    for (const name of candidates) {
      const field = fieldByName.get(name);
      if (!field) continue;
      const sqlDateExpr = computeSqlDateExpr(field.name, field.type);
      const resolved = { column: field.name, sqlDateExpr };
      cachedOrderColumnByTable.set(cacheKey, resolved);
      return resolved;
    }

    // Otherwise: pick the first date-ish field.
    for (const field of Array.from(fieldByName.values())) {
      const sqlDateExpr = computeSqlDateExpr(field.name, field.type);
      if (!sqlDateExpr) continue;
      const resolved = { column: field.name, sqlDateExpr };
      cachedOrderColumnByTable.set(cacheKey, resolved);
      return resolved;
    }
  } catch (err: any) {
    console.warn(
      `[BigQuery] Could not fetch table metadata for ${projectId}.${datasetId}.${tableId}:`,
      err?.message || err,
    );
  }

  const resolved = { column: null, sqlDateExpr: null };
  cachedOrderColumnByTable.set(cacheKey, resolved);
  return resolved;
}

/**
 * Auto-detect the dataset location from BigQuery metadata.
 * Falls back to BQ_LOCATION / BIGQUERY_LOCATION if metadata lookup fails.
 */
async function getDatasetLocation(bigquery: BigQuery, datasetId: string) {
  if (cachedDatasetLocation) return cachedDatasetLocation;

  try {
    const [metadata] = await bigquery.dataset(datasetId).getMetadata();
    const loc = (metadata.location as string | undefined) || null;
    if (loc) {
      cachedDatasetLocation = loc;
      console.log(
        `[BigQuery] Auto-detected dataset location for ${datasetId}: ${loc}`,
      );
      return cachedDatasetLocation;
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
    console.log('[BigQuery] No explicit dataset location set; using default.');
  }

  return cachedDatasetLocation;
}

function isAuthorized(request: NextRequest, apiKey: string): boolean {
  const authHeader = request.headers.get('authorization');
  const bearer =
    authHeader && authHeader.startsWith('Bearer ')
      ? authHeader.slice(7)
      : undefined;
  const headerApiKey = request.headers.get('x-api-key') ?? undefined;

  // If an upstream proxy/IAP injects an identity JWT in Authorization: Bearer,
  // treat it as NOT being an API key.
  const bearerLooksLikeJwt =
    typeof bearer === 'string' && bearer.split('.').length === 3;
  const effectiveBearer = bearerLooksLikeJwt ? undefined : bearer;

  return effectiveBearer === apiKey || headerApiKey === apiKey;
}

export async function GET(request: NextRequest) {
  try {
    const runningInGCP = Boolean(
      process.env.K_SERVICE ||
        process.env.FUNCTION_TARGET ||
        process.env.GAE_SERVICE ||
        process.env.CLOUD_RUN_JOB,
    );

    // --- Auth (optional) ---
    // This is a read-only endpoint used by the dashboard UI. The shared
    // DASHBOARD_API_KEY is intended for server-to-server calls (optimizer -> dashboard
    // writes, dashboard -> optimizer reads). Browsers should not need (or see) it.
    //
    // If a caller *does* present a key and it's wrong, reject.
    const resolvedKey = await resolveDashboardApiKey({ required: false });
    const authHeader = request.headers.get('authorization');
    const bearerToken =
      authHeader && authHeader.startsWith('Bearer ')
        ? authHeader.slice(7)
        : null;
    const bearerLooksLikeJwt = Boolean(
      bearerToken && bearerToken.split('.').length === 3,
    );
    const hasBearer = Boolean(bearerToken && !bearerLooksLikeJwt);
    const hasXApiKey = Boolean(request.headers.get('x-api-key'));

    // Only enforce the shared key when the caller is *attempting* to use it.
    // This avoids false 401s when an upstream proxy injects a non-Bearer
    // Authorization header (e.g., Basic/SSO).
    if (resolvedKey.apiKey && (hasBearer || hasXApiKey) && !isAuthorized(request, resolvedKey.apiKey)) {
      return NextResponse.json(
        {
          error: 'Unauthorized',
          message: 'Invalid dashboard API key presented',
          hint: 'If calling via curl, pass Authorization: Bearer <DASHBOARD_API_KEY> or X-API-Key: <DASHBOARD_API_KEY>. Browsers should not send this key.',
          diagnostics: {
            keyConfigured: true,
            keySource: resolvedKey.source,
            hasBearer,
            hasXApiKey,
            bearerLooksLikeJwt,
            authScheme: authHeader ? (authHeader.split(' ', 1)[0] || 'unknown') : null,
          },
        },
        { status: 401 },
      );
    }

    const { searchParams } = new URL(request.url);
    const table = searchParams.get('table') || 'optimization_results';
    const limit = Number.parseInt(searchParams.get('limit') ?? '100', 10) || 100;
    const days = Number.parseInt(searchParams.get('days') ?? '14', 10) || 14;

    // Resolve GCP credentials
    const credentialResult = await resolveGCPCredentials();
    if (!credentialResult.success && !runningInGCP) {
      return NextResponse.json(
        {
          error: 'Failed to resolve GCP credentials',
          message: credentialResult.error?.message || 'Unknown credential error',
          hint: 'Set GCP_SERVICE_ACCOUNT_KEY environment variable with your service account JSON credentials',
        },
        { status: 500 },
      );
    }

    if (!credentialResult.success && runningInGCP) {
      console.warn(
        '[BigQuery API] Explicit credential resolution failed, but running in GCP; continuing with ADC:',
        credentialResult.error?.message || credentialResult.error,
      );
    }

    const explicitProjectId = getFirstSetEnv(['BQ_PROJECT_ID', 'BIGQUERY_PROJECT_ID']);
    const projectId =
      explicitProjectId ||
      credentialResult.projectId ||
      getFirstSetEnv(BIGQUERY_PROJECT_ID_ENV_NAMES) ||
      PROJECT_ID;
    const datasetId = DEFAULT_DATASET_ID;

    console.log(
      `[BigQuery API] Fetching data from ${projectId}.${datasetId}.${table} (limit=${limit})`,
    );

    const bigqueryOptions: any = { projectId };
    if (credentialResult.credentials) {
      bigqueryOptions.credentials = credentialResult.credentials;
    }
    const bigquery = new BigQuery(bigqueryOptions);

    const location = await getDatasetLocation(bigquery, datasetId);

    const { column: orderByColumn, sqlDateExpr } =
      await getOrderColumnAndDateExpr(bigquery, projectId, datasetId, table);

    const whereClause =
      days > 0 && sqlDateExpr
        ? `WHERE ${sqlDateExpr} >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)`
        : '';

    const orderClause = orderByColumn ? `ORDER BY \`${orderByColumn}\` DESC` : '';

    const query = `
      SELECT *
      FROM \`${projectId}.${datasetId}.${table}\`
      ${whereClause}
      ${orderClause}
      LIMIT @limit
    `;

    const [job] = await bigquery.createQueryJob({
      query,
      params: { limit, days },
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

    if (message.includes('Not found: Dataset') || message.includes('Not found: Table')) {
      return NextResponse.json(
        {
          error: 'Dataset or table not found in BigQuery',
          message: 'The dataset/table you requested does not exist in this project.',
          details: message,
          hint:
            'Confirm that the dataset "amazon_ppc_data" and the requested table exist in the configured project. ' +
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
