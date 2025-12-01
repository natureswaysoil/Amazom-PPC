cd /workspaces/Amazom-PPC/amazon_ppc_dashboard/nextjs_space

cat << 'EOF' > app/api/optimization-results/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

export async function POST(request: NextRequest) {
  try {
    // Optional API key auth
    const apiKey = process.env.DASHBOARD_API_KEY;
    const authHeader = request.headers.get('authorization');
    const bearerToken = authHeader?.startsWith('Bearer ')
      ? authHeader.slice(7)
      : undefined;

    if (apiKey && bearerToken !== apiKey) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();

    // Basic validation
    if (!body.run_id || !body.status || !body.timestamp) {
      return NextResponse.json(
        { error: 'Missing required fields: run_id, status, timestamp' },
        { status: 400 }
      );
    }

    // Use Application Default Credentials (Vercel/GCP-friendly)
    const bigquery = new BigQuery();
    const datasetId = process.env.BQ_DATASET_ID || 'amazon_ppc';

    await bigquery
      .dataset(datasetId)
      .table('optimization_results')
      .insert([
        {
          ...body,
          timestamp: body.timestamp || new Date().toISOString(),
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
EOF
