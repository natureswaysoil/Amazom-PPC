cat > app/api/bigquery-data/route.ts << 'EOF'
import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

export const dynamic = 'force-dynamic';

function getProjectId(): string {
  return (
    process.env.GCP_PROJECT ||
    process.env.GOOGLE_CLOUD_PROJECT ||
    process.env.GCLOUD_PROJECT ||
    process.env.PROJECT_ID ||
    'amazon-ppc-474902'
  );
}

function getDatasetId(): string {
  return (
    process.env.BIGQUERY_DATASET ||
    process.env.BIGQUERY_DATASET_ID ||
    'amazon_ppc'
  );
}

function getLocation(): string {
  return (
    process.env.BIGQUERY_LOCATION ||
    process.env.BQ_LOCATION ||
    'US'
  );
}

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const table = url.searchParams.get('table') || 'optimization_results';

  // Limit guard
  let limit = 50;
  const limitParam = url.searchParams.get('limit');
  if (limitParam) {
    const parsed = Number(limitParam);
    if (Number.isFinite(parsed) && parsed > 0 && parsed <= 1000) {
      limit = parsed;
    }
  }

  const projectId = getProjectId();
  const datasetId = getDatasetId();
  const location = getLocation();

  const bigquery = new BigQuery({ projectId });

  const query = `
    SELECT *
    FROM \`${projectId}.${datasetId}.${table}\`
    ORDER BY timestamp DESC
    LIMIT ${limit}
  `;

  try {
    const [rawRows] = await bigquery.query({
      query,
      location,
      useLegacySql: false,
    });

    // ✅ Flatten BigQuery special fields (timestamp.value → string)
    const rows = rawRows.map((row: any) => {
      const cleaned: any = {};
      for (const [key, val] of Object.entries(row)) {
        if (val && typeof val === 'object' && 'value' in val) {
          cleaned[key] = (val as any).value;
        } else {
          cleaned[key] = val;
        }
      }
      return cleaned;
    });

    return NextResponse.json({
      status: 'ok',
      table,
      projectId,
      datasetId,
      location,
      rowCount: rows.length,
      rows,
    });
  } catch (err: any) {
    console.error('BigQuery error in /api/bigquery-data:', err);
    return NextResponse.json(
      {
        status: 'error',
        error: 'Failed to query BigQuery',
        message: err?.message || String(err),
      },
      { status: 500 }
    );
  }
}
EOF
