import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';
import { resolveDashboardApiKey } from '../lib/dashboard-api-key';
import { getFirstSetEnv } from '../lib/credentials';

export const dynamic = 'force-dynamic';

const BIGQUERY_PROJECT_ID = getFirstSetEnv([
  'BQ_PROJECT_ID',
  'BIGQUERY_PROJECT_ID',
  'GOOGLE_CLOUD_PROJECT',
  'GCP_PROJECT',
  'GCP_PROJECT_ID',
  'GCLOUD_PROJECT',
]);

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

    const body = await request.json();
    
    // Log the error
    console.error('Optimization error received:', body);

    // Best-effort persistence into BigQuery so the dashboard can render
    // failures in Recent Automation Events.
    try {
      const runId = body?.run_id || body?.runId;
      const timestamp = body?.timestamp || new Date().toISOString();

      if (runId) {
        const bigquery = BIGQUERY_PROJECT_ID
          ? new BigQuery({ projectId: BIGQUERY_PROJECT_ID })
          : new BigQuery();
        const datasetId =
          getFirstSetEnv([
            'BQ_DATASET_ID',
            'BIGQUERY_DATASET',
            'BIGQUERY_DATASET_ID',
            'BQ_DATASET',
            'BQ_DATASET_NAME',
          ]) || 'amazon_ppc_data';
        const tableId = process.env.BQ_RUN_EVENTS_TABLE_ID || 'optimizer_run_events';

        const rows = [
          {
            timestamp,
            run_id: String(runId),
            status: 'failed',
            details: JSON.stringify(body ?? {}),
          },
        ];

        const dataset = bigquery.dataset(datasetId);
        const table = dataset.table(tableId);

        const ensureEventsTableExists = async () => {
          try {
            const [datasetExists] = await dataset.exists();
            if (!datasetExists) {
              await bigquery.createDataset(datasetId, {
                location: process.env.BQ_LOCATION || process.env.BIGQUERY_LOCATION || 'US',
              });
            }

            const [tableExists] = await table.exists();
            if (!tableExists) {
              await dataset.createTable(tableId, {
                schema: [
                  { name: 'timestamp', type: 'TIMESTAMP', mode: 'REQUIRED' },
                  { name: 'run_id', type: 'STRING', mode: 'REQUIRED' },
                  { name: 'status', type: 'STRING', mode: 'REQUIRED' },
                  { name: 'details', type: 'STRING', mode: 'NULLABLE' },
                ],
              });
            }
          } catch (ensureErr: any) {
            console.warn(
              'Failed ensuring optimizer_run_events table exists (optimization-error):',
              ensureErr?.message || ensureErr,
            );
          }
        };

        const tryInsert = async () => {
          await table.insert(rows);
        };

        try {
          await tryInsert();
        } catch (insertErr: any) {
          const code = insertErr?.code;
          const msg = String(insertErr?.message || insertErr || '');
          const notFound = code === 404 || /not\s*found/i.test(msg);

          if (notFound) {
            await ensureEventsTableExists();
            await tryInsert();
          } else {
            throw insertErr;
          }
        }
      }
    } catch (persistErr: any) {
      console.warn('BigQuery persist for optimization-error failed:', persistErr?.message || persistErr);
    }
    
    // TODO: Store in your database and/or send alerts
    // Example fields in body:
    // - run_id: unique identifier
    // - status: 'error'
    // - profile_id: Amazon profile ID
    // - timestamp: ISO timestamp
    // - error: error message
    // - error_type: error classification
    
    return NextResponse.json({ 
      success: true,
      received: true 
    }, { status: 200 });
    
  } catch (error) {
    console.error('Error processing error report:', error);
    return NextResponse.json({ 
      error: 'Internal server error' 
    }, { status: 500 });
  }
}
