cat << 'EOF' > app/api/optimization-results/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

export async function POST(request: NextRequest) {
  try {
    const apiKey = process.env.DASHBOARD_API_KEY;
    const authHeader = request.headers.get('authorization');
    const bearerToken = authHeader?.startsWith('Bearer ')
      ? authHeader.slice(7)
      : undefined;

    if (apiKey && bearerToken !== apiKey) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();

    if (!body.run_id || !body.status || !body.timestamp) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 },
      );
    }

    const bigquery = new BigQuery();

    const datasetId = process.env.BQ_DATASET_ID || 'amazon_ppc';

    await bigquery
      .dataset(datasetId)
      .table('optimization_results')
      .insert([{
        ...body,
        timestamp: body.timestamp || new Date().toISOString(),
      }]);

    return NextResponse.json({ success: true }, { status: 200 });
  } catch (err: any) {
    console.error(err);
    return NextResponse.json(
      { error: err.message || 'Internal error' },
      { status: 500 },
    );
  }
}
EOF
