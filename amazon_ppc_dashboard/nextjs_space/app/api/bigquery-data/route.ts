import { NextRequest, NextResponse } from 'next/server';
import { Buffer } from 'buffer';
import { BigQuery } from '@google-cloud/bigquery';

type TruthyEnv = string | undefined;

interface OptimizationResultRow {
  timestamp: string;
  run_id: string;
  status: string;
  profile_id: string;
  dry_run: boolean;
  duration_seconds: number;
  campaigns_analyzed: number;
  keywords_optimized: number;
  bids_increased: number;
  bids_decreased: number;
  negative_keywords_added: number;
  average_acos: number;
  total_spend: number;
  total_sales: number;
}

interface CampaignDetailsRow {
  timestamp: string;
  run_id: string;
  campaign_id: string;
  campaign_name: string;
  spend: number;
  sales: number;
  acos: number;
  impressions: number;
  clicks: number;
  conversions: number;
  budget: number;
  status: string;
}

interface SummaryRow {
  date: string;
  optimization_runs: number;
  total_keywords_optimized: number;
  total_bids_increased: number;
  total_bids_decreased: number;
  avg_acos: number;
  total_spend: number;
  total_sales: number;
}

type MockRow = OptimizationResultRow | CampaignDetailsRow | SummaryRow;

function parseServiceAccount(value: string | undefined, source: string): any | undefined {
  if (!value) {
    return undefined;
  }

  try {
    console.log(`Attempting to parse ${source} as JSON credentials`);
    return JSON.parse(value);
  } catch (jsonError) {
    try {
      console.log(`Value in ${source} is not JSON; attempting base64 decode`);
      const decoded = Buffer.from(value, 'base64').toString('utf8');
      return JSON.parse(decoded);
    } catch (decodeError) {
      console.log(`Value in ${source} is not valid JSON or base64 encoded JSON`);
      return undefined;
    }
  }
}

export async function GET(request: NextRequest) {
  try {
    // Get configuration from environment variables with fallback to default
    // Priority: GCP_PROJECT > GOOGLE_CLOUD_PROJECT > extracted from credentials > default
    let projectId = process.env.GCP_PROJECT || process.env.GOOGLE_CLOUD_PROJECT;
    const datasetId = process.env.BQ_DATASET_ID || 'amazon_ppc';
    const location = process.env.BQ_LOCATION || 'us-east4';
    
    // Default project ID from config.json (fallback when env vars not set)
    const DEFAULT_PROJECT_ID = 'amazon-ppc-474902';
    
    // Handle Google Cloud credentials
    // In Vercel, credentials can be provided as:
    // 1. GCP_SERVICE_ACCOUNT_KEY (JSON string of service account key)
    // 2. GOOGLE_APPLICATION_CREDENTIALS (JSON string, though typically a file path locally)
    // 3. Default application credentials (if running in GCP)
    let credentials: any = undefined;
    
    if (process.env.GCP_SERVICE_ACCOUNT_KEY) {
      credentials = parseServiceAccount(process.env.GCP_SERVICE_ACCOUNT_KEY, 'GCP_SERVICE_ACCOUNT_KEY');
      if (!credentials) {
        return NextResponse.json({
          error: 'Configuration error',
          message: 'GCP_SERVICE_ACCOUNT_KEY is not valid JSON or base64 encoded JSON',
          details: 'Provide the raw JSON service account key or a base64 encoded version of it in the GCP_SERVICE_ACCOUNT_KEY environment variable, then redeploy.',
        }, { status: 500 });
      }

      if (!projectId && typeof credentials === 'object' && credentials.project_id) {
        projectId = credentials.project_id;
        console.log('Using project ID from GCP_SERVICE_ACCOUNT_KEY:', projectId);
      }
    } else if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
      credentials = parseServiceAccount(process.env.GOOGLE_APPLICATION_CREDENTIALS, 'GOOGLE_APPLICATION_CREDENTIALS');

      if (!credentials) {
        // If not JSON or base64 JSON, assume it's a file path (local development)
        credentials = undefined;
      } else if (!projectId && typeof credentials === 'object' && credentials.project_id) {
        projectId = credentials.project_id;
        console.log('Using project ID from GOOGLE_APPLICATION_CREDENTIALS:', projectId);
      }
    }
    
    // Use default project ID if none found in environment or credentials
    if (!projectId) {
      projectId = DEFAULT_PROJECT_ID;
      console.log('Using default project ID from config.json:', projectId);
    }
    
    // Validate that we have a project ID after all fallbacks
    if (!projectId) {
      return NextResponse.json({ 
        error: 'Configuration error',
        message: 'Project ID not found: Set GCP_PROJECT/GOOGLE_CLOUD_PROJECT or provide service account credentials',
        details: 'To fix this: 1) Provide GCP_SERVICE_ACCOUNT_KEY with your service account JSON credentials (includes project_id), OR 2) Set GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variables to your Google Cloud project ID (e.g., amazon-ppc-474902), then 3) Redeploy the application',
        documentation: 'See README_BIGQUERY.md and DEPLOYMENT.md for detailed configuration instructions. Visit https://vercel.com/docs/concepts/projects/environment-variables for help with Vercel environment variables.',
        vercelSetupUrl: 'https://vercel.com/<your-team>/<your-project>/settings/environment-variables'
      }, { status: 500 });
    }
    
    const runningOnVercel = process.env.VERCEL === '1';
    const useMockData = shouldUseMockData(process.env.USE_BIGQUERY_MOCK_DATA) || (!credentials && runningOnVercel);

    if (useMockData) {
      const searchParams = request.nextUrl.searchParams;
      const table = searchParams.get('table') || 'optimization_results';

      const { limit, days } = resolveQueryLimits(searchParams.get('limit'), searchParams.get('days'));
      const mockRows = getMockData(table, limit, days);

      if (!mockRows) {
        return NextResponse.json({
          error: 'Invalid table parameter',
          message: `Table must be one of: optimization_results, campaign_details, summary`
        }, { status: 400 });
      }

      return NextResponse.json({
        success: true,
        data: mockRows.rows,
        metadata: {
          projectId: 'mock-project',
          datasetId: 'mock-dataset',
          table,
          rowCount: mockRows.rows.length,
          source: 'mock-data',
          warning: runningOnVercel && !credentials
            ? 'BigQuery credentials missing; serving fallback dashboard data.'
            : 'Mock data explicitly enabled via USE_BIGQUERY_MOCK_DATA.'
        }
      });
    }

    if (!credentials && runningOnVercel) {
      return NextResponse.json({
        error: 'Missing Google Cloud credentials',
        message: 'BigQuery credentials are not configured for this deployment.',
        details: 'Set the GCP_SERVICE_ACCOUNT_KEY environment variable to the contents of your service account JSON file (or a base64 encoded version) and redeploy.',
        documentation: 'See amazon_ppc_dashboard/nextjs_space/README_BIGQUERY.md for detailed setup instructions.',
        troubleshooting: [
          'In Vercel, add GCP_SERVICE_ACCOUNT_KEY as an Environment Variable (use the JSON from your service account key).',
          'Alternatively, set GOOGLE_APPLICATION_CREDENTIALS to the JSON string (not a file path).',
          'After updating variables, redeploy the dashboard.'
        ],
      }, { status: 500 });
    }

    // Initialize BigQuery client with explicit credentials if provided
    const bigquery = new BigQuery({
      projectId: projectId,
      ...(credentials && { credentials }),
    });

    // Get query parameters with validation
    const searchParams = request.nextUrl.searchParams;
    const table = searchParams.get('table') || 'optimization_results';

    const { limit, days } = resolveQueryLimits(searchParams.get('limit'), searchParams.get('days'));
    
    // Validate table parameter (whitelist approach)
    const validTables = ['optimization_results', 'campaign_details', 'summary'];
    if (!validTables.includes(table)) {
      return NextResponse.json({ 
        error: 'Invalid table parameter',
        message: `Table must be one of: ${validTables.join(', ')}`
      }, { status: 400 });
    }
    
    // Build fully qualified table name (safely)
    const fullTableName = `\`${projectId}.${datasetId}.optimization_results\``;
    const campaignTableName = `\`${projectId}.${datasetId}.campaign_details\``;
    
    // Build query based on table with parameterized values
    let query = '';
    let queryParams: any[] = [];
    
    switch (table) {
      case 'optimization_results':
        query = `
          SELECT 
            timestamp,
            run_id,
            status,
            profile_id,
            dry_run,
            duration_seconds,
            campaigns_analyzed,
            keywords_optimized,
            bids_increased,
            bids_decreased,
            negative_keywords_added,
            average_acos,
            total_spend,
            total_sales
          FROM ${fullTableName}
          WHERE DATE(timestamp) >= CURRENT_DATE() - @days
          ORDER BY timestamp DESC
          LIMIT @limit
        `;
        queryParams = [
          { name: 'days', value: days },
          { name: 'limit', value: limit }
        ];
        break;
        
      case 'campaign_details':
        query = `
          SELECT 
            timestamp,
            run_id,
            campaign_id,
            campaign_name,
            spend,
            sales,
            acos,
            impressions,
            clicks,
            conversions,
            budget,
            status
          FROM ${campaignTableName}
          WHERE DATE(timestamp) >= CURRENT_DATE() - @days
          ORDER BY timestamp DESC
          LIMIT @limit
        `;
        queryParams = [
          { name: 'days', value: days },
          { name: 'limit', value: limit }
        ];
        break;
        
      case 'summary':
        query = `
          SELECT 
            DATE(timestamp) as date,
            COUNT(*) as optimization_runs,
            SUM(keywords_optimized) as total_keywords_optimized,
            SUM(bids_increased) as total_bids_increased,
            SUM(bids_decreased) as total_bids_decreased,
            AVG(average_acos) as avg_acos,
            SUM(total_spend) as total_spend,
            SUM(total_sales) as total_sales
          FROM ${fullTableName}
          WHERE DATE(timestamp) >= CURRENT_DATE() - @days
          GROUP BY DATE(timestamp)
          ORDER BY date DESC
        `;
        queryParams = [
          { name: 'days', value: days }
        ];
        break;
    }
    
    // Execute query with parameters
    const [rows] = await bigquery.query({
      query: query,
      location: location,
      params: queryParams,
    });
    
    return NextResponse.json({
      success: true,
      data: rows,
      metadata: {
        projectId,
        datasetId,
        table,
        rowCount: rows.length
      }
    }, { status: 200 });
    
  } catch (error: any) {
    console.error('BigQuery query error:', error);
    
    // Check if it's a "not found" error
    if (error.message && error.message.includes('Not found')) {
      return NextResponse.json({
        error: 'Dataset or table not found',
        message: 'Please run setup-bigquery.sh to create the BigQuery dataset and tables',
        details: error.message
      }, { status: 404 });
    }

    if (error.message && error.message.includes('Could not load the default credentials')) {
      return NextResponse.json({
        error: 'Missing Google Cloud credentials',
        message: 'Could not load Google Cloud credentials for BigQuery.',
        details: 'Provide service account credentials via the GCP_SERVICE_ACCOUNT_KEY environment variable (preferred) or GOOGLE_APPLICATION_CREDENTIALS as a JSON string.',
        documentation: 'See amazon_ppc_dashboard/nextjs_space/README_BIGQUERY.md for deployment steps.',
        next_steps: [
          'Add the service account JSON to GCP_SERVICE_ACCOUNT_KEY in your deployment environment.',
          'If using GOOGLE_APPLICATION_CREDENTIALS, paste the JSON contents directly instead of a file path.',
          'Redeploy the dashboard after saving the variables.',
          'Re-run /api/config-check to verify configuration.'
        ],
      }, { status: 500 });
    }

    return NextResponse.json({
      error: 'Failed to query BigQuery',
      message: error.message || 'Unknown error'
    }, { status: 500 });
  }
}

function shouldUseMockData(value: TruthyEnv): boolean {
  if (!value) {
    return false;
  }

  const normalised = value.trim().toLowerCase();
  return ['1', 'true', 'yes', 'on', 'mock', 'demo'].includes(normalised);
}

function resolveQueryLimits(limitParam: string | null, daysParam: string | null) {
  let limit = parseInt(limitParam || '10', 10);
  if (isNaN(limit) || limit < 1) {
    limit = 10;
  } else if (limit > 100) {
    limit = 100;
  }

  let days = parseInt(daysParam || '7', 10);
  if (isNaN(days) || days < 1) {
    days = 7;
  } else if (days > 365) {
    days = 365;
  }

  return { limit, days };
}

function getMockData(table: string, limit: number, days: number): { rows: MockRow[] } | null {
  const now = new Date();
  const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);

  switch (table) {
    case 'optimization_results': {
      const rows = generateMockOptimizationResults(now)
        .filter(row => new Date(row.timestamp) >= cutoff)
        .slice(0, limit);
      return { rows };
    }
    case 'campaign_details': {
      const rows = generateMockCampaignDetails(now)
        .filter(row => new Date(row.timestamp) >= cutoff)
        .slice(0, limit);
      return { rows };
    }
    case 'summary': {
      const rows = generateMockSummary(now)
        .filter(row => new Date(row.date + 'T00:00:00Z') >= cutoff)
        .slice(0, Math.min(limit || 7, 30));
      return { rows };
    }
    default:
      return null;
  }
}

function generateMockOptimizationResults(baseDate: Date): OptimizationResultRow[] {
  const entries: OptimizationResultRow[] = [];
  for (let index = 0; index < 18; index++) {
    const timestamp = new Date(baseDate.getTime() - index * 6 * 60 * 60 * 1000);
    entries.push({
      timestamp: timestamp.toISOString(),
      run_id: `demo-run-${String(index + 1).padStart(3, '0')}`,
      status: index % 7 === 3 ? 'PARTIAL_SUCCESS' : 'SUCCESS',
      profile_id: 'demo-profile-123',
      dry_run: index % 5 === 0,
      duration_seconds: 120 + (index % 5) * 18,
      campaigns_analyzed: 6 + (index % 4),
      keywords_optimized: 28 + index * 2,
      bids_increased: 12 + (index % 6),
      bids_decreased: 9 + (index % 5),
      negative_keywords_added: 3 + (index % 4),
      average_acos: parseFloat((0.28 + (index % 5) * 0.015).toFixed(3)),
      total_spend: parseFloat((215 + index * 17.35).toFixed(2)),
      total_sales: parseFloat((640 + index * 32.8).toFixed(2))
    });
  }
  return entries;
}

function generateMockCampaignDetails(baseDate: Date): CampaignDetailsRow[] {
  const entries: CampaignDetailsRow[] = [];
  const campaignNames = ['Auto - Brand', 'Manual - Best Sellers', 'Defensive ASIN', 'Top of Search Boost'];

  for (let index = 0; index < 24; index++) {
    const timestamp = new Date(baseDate.getTime() - index * 4 * 60 * 60 * 1000);
    const campaignIndex = index % campaignNames.length;
    entries.push({
      timestamp: timestamp.toISOString(),
      run_id: `demo-run-${String(Math.floor(index / 2) + 1).padStart(3, '0')}`,
      campaign_id: `cmp-${1000 + index}`,
      campaign_name: campaignNames[campaignIndex],
      spend: parseFloat((45 + campaignIndex * 12 + index * 1.35).toFixed(2)),
      sales: parseFloat((120 + campaignIndex * 24 + index * 3.4).toFixed(2)),
      acos: parseFloat((0.25 + (campaignIndex * 0.03) + ((index % 3) * 0.01)).toFixed(3)),
      impressions: 1500 + campaignIndex * 320 + index * 45,
      clicks: 65 + campaignIndex * 8 + index * 2,
      conversions: 7 + campaignIndex * 2 + (index % 4),
      budget: parseFloat((80 + campaignIndex * 10).toFixed(2)),
      status: index % 11 === 0 ? 'PAUSED' : 'ENABLED'
    });
  }

  return entries;
}

function generateMockSummary(baseDate: Date): SummaryRow[] {
  const entries: SummaryRow[] = [];

  for (let index = 0; index < 14; index++) {
    const date = new Date(baseDate.getTime() - index * 24 * 60 * 60 * 1000);
    entries.push({
      date: date.toISOString().slice(0, 10),
      optimization_runs: 2 + (index % 3),
      total_keywords_optimized: 60 + index * 5,
      total_bids_increased: 28 + index * 3,
      total_bids_decreased: 22 + index * 2,
      avg_acos: parseFloat((0.29 + (index % 4) * 0.012).toFixed(3)),
      total_spend: parseFloat((480 + index * 21.5).toFixed(2)),
      total_sales: parseFloat((1350 + index * 49.8).toFixed(2))
    });
  }

  return entries;
}
