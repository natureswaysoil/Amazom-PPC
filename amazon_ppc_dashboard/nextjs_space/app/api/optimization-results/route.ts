import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';
import { resolveDashboardApiKey } from '../lib/dashboard-api-key';

type OptimizationResultPayload = {
  run_id?: string;
  status?: string;
  profile_id?: string;
  timestamp?: string;
  [key: string]: unknown;
};

export async function POST(request: NextRequest) {
  try {
    // Verify API key (Authorization: Bearer or x-api-key header)
    const { apiKey } = await resolveDashboardApiKey({ required: false });
    const authHeader = request.headers.get('authorization');
    const bearerToken = authHeader?.startsWith('Bearer ')
      ? authHeader.slice(7)
      : authHeader || undefined;
    const headerApiKey = request.headers.get('x-api-key') ?? undefined;

    if (apiKey) {
      if (bearerToken !== apiKey && headerApiKey !== apiKey) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
      }
    } else {
      console.warn('DASHBOARD_API_KEY is not set. Skipping authentication.');
    }

    const body: OptimizationResultPayload = await request.json();

    if (!body.run_id || !body.status) {
      return NextResponse.json(
        { error: 'Missing required fields: run_id, status' },
        { status: 400 }
      );
    }

    const timestamp = body.timestamp || new Date().toISOString();

    const bigquery = new BigQuery();
    const datasetId = process.env.BQ_DATASET_ID || 'amazon_ppc';
    const tableId = process.env.BQ_TABLE_ID || 'optimization_results';

    await bigquery.dataset(datasetId).table(tableId).insert([
      {
        ...body,
        timestamp,
      },
    ]);

    return NextResponse.json(
      {
        success: true,
        received: true,
        run_id: body.run_id,
      },
      { status: 200 }
    );
  } catch (err: any) {
    console.error('Error in optimization-results route:', err);
    return NextResponse.json(
      { error: err?.message || 'Internal server error' },
      { status: 500 }
    );
  }
}
