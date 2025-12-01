import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

const PROJECT_ID =
  process.env.GOOGLE_CLOUD_PROJECT ||
  process.env.GCP_PROJECT ||
  'amazon-ppc-474902';

const DATASET_ID = process.env.BQ_DATASET_ID || 'amazon_ppc';

// Single BigQuery client – location is auto–detected by dataset metadata
const bigquery = new BigQuery({ projectId: PROJECT_ID });

async function runQuery<T = any>(
  sql: string,
  params: Record<string, any> = {}
): Promise<T[]> {
  const [rows] = await bigquery.query({
    query: sql,
    params,
    // ⚠️ No location here – lets BigQuery use the dataset’s own location (US in your case)
  });
  return rows as T[];
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const table = searchParams.get('table') || 'optimization_results';
  const limit = Number(searchParams.get('limit') || '100');

  try {
    //
    // SPECIAL CASE: optimization_results with fallback to campaign_performance
    //
    if (table === 'optimization_results') {
      const optTable = `\`${PROJECT_ID}.${DATASET_ID}.optimization_results\``;

      // 1) Try the optimizer results first (what the UI expects)
      const optRows = await runQuery(
        `
        SELECT *
        FROM ${optTable}
        ORDER BY timestamp DESC
        LIMIT @limit
        `,
        { limit }
      );

      if (optRows.length > 0) {
        return NextResponse.json({
          table: 'optimization_results',
          source: 'optimization_results',
          rows: optRows,
        });
      }

      // 2) Fallback: derive a “summary-like” dataset from campaign_performance
      const perfTable = `\`${PROJECT_ID}.${DATASET_ID}.campaign_performance\``;

      const fallbackRows = await runQuery(
        `
        -- Aggregate recent performance as a stand-in for optimizer summary
        SELECT
          date,
          campaign_id,
          campaign_name,
          impressions,
          clicks,
          cost,
          sales,
          orders,
          SAFE_DIVIDE(cost, GREATEST(clicks, 1)) AS cpc,
          SAFE_DIVIDE(clicks, GREATEST(impressions, 1)) AS ctr,
          SAFE_DIVIDE(cost, GREATEST(sales, 0.01))  AS acos,
          SAFE_DIVIDE(sales, GREATEST(cost, 0.01)) AS roas
        FROM ${perfTable}
        ORDER BY date DESC
        LIMIT @limit
        `,
        { limit }
      );

      return NextResponse.json({
        table: 'campaign_performance',
        source: 'fallback_campaign_performance',
        rows: fallbackRows,
      });
    }

    //
    // GENERIC: /api/bigquery-data?table=some_table&limit=50
    //
    const fullTable = `\`${PROJECT_ID}.${DATASET_ID}.${table}\``;

    const rows = await runQuery(
      `
      SELECT *
      FROM ${fullTable}
      LIMIT @limit
      `,
      { limit }
    );

    return NextResponse.json({
      table,
      source: 'direct',
      rows,
    });
  } catch (err: any) {
    console.error('[bigquery-data] Error:', err?.message || err);

    return NextResponse.json(
      {
        error: 'BigQuery query failed',
        message: err?.message || String(err),
      },
      { status: 500 }
    );
  }
}
