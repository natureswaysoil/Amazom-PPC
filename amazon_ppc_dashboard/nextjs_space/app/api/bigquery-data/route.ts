import { NextRequest, NextResponse } from 'next/server';
import { Buffer } from 'buffer';
import { BigQuery } from '@google-cloud/bigquery';

type ServiceAccountCredentials = {
  project_id?: string;
  client_email: string;
  private_key: string;
};

const SERVICE_ACCOUNT_JSON_ENV_NAMES = [
  'GCP_SERVICE_ACCOUNT_KEY',
  'GCP_SA_KEY',
  'GCP_SERVICE_ACCOUNT_JSON',
  'GCP_SERVICE_ACCOUNT',
  'GCP_SERVICE_KEY',
  'GCP_CREDENTIALS',
  'GOOGLE_CREDENTIALS',
  'GOOGLE_APPLICATION_CREDENTIALS_JSON',
  'GOOGLE_APPLICATION_CREDENTIALS_BASE64',
  'GOOGLE_APPLICATION_CREDENTIALS_B64',
  'SERVICE_ACCOUNT_JSON',
  'BIGQUERY_SERVICE_ACCOUNT_KEY',
  'BIGQUERY_CREDENTIALS',
  'BQ_SERVICE_ACCOUNT_KEY',
];

const SERVICE_ACCOUNT_EMAIL_ENV_NAMES = [
  'GCP_SERVICE_ACCOUNT_EMAIL',
  'GCP_CLIENT_EMAIL',
  'GOOGLE_CLIENT_EMAIL',
  'BIGQUERY_CLIENT_EMAIL',
  'BQ_CLIENT_EMAIL',
  'SERVICE_ACCOUNT_EMAIL',
  'GOOGLE_SERVICE_ACCOUNT_EMAIL',
  'GCP_SERVICE_ACCOUNT_USER',
];

const SERVICE_ACCOUNT_KEY_ENV_NAMES = [
  'GCP_SERVICE_ACCOUNT_KEY_RAW',
  'GCP_PRIVATE_KEY',
  'GOOGLE_PRIVATE_KEY',
  'BIGQUERY_PRIVATE_KEY',
  'BQ_PRIVATE_KEY',
  'SERVICE_ACCOUNT_PRIVATE_KEY',
  'GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY',
  'GCP_SERVICE_ACCOUNT_PRIVATE_KEY',
];

const PROJECT_ID_ENV_NAMES = [
  'GCP_PROJECT',
  'GOOGLE_CLOUD_PROJECT',
  'GOOGLE_PROJECT_ID',
  'GCP_PROJECT_ID',
  'BIGQUERY_PROJECT_ID',
  'BQ_PROJECT_ID',
  'GOOGLE_PROJECT',
  'GCLOUD_PROJECT',
];

type EnvLookupResult = {
  name: string;
  value: string;
};

function getFirstSetEnvWithName(names: string[]): EnvLookupResult | undefined {
  for (const name of names) {
    const value = process.env[name];
    if (value && value.trim()) {
      return { name, value: value.trim() };
    }
  }

  for (const name of names) {
    const combined = combineSplitEnv(name);
    if (combined && combined.trim()) {
      return { name: `${name} (split parts)`, value: combined.trim() };
    }
  }

  return undefined;
}

function getFirstSetEnv(names: string[]): string | undefined {
  return getFirstSetEnvWithName(names)?.value;
}

function combineSplitEnv(baseName: string): string | undefined {
  const parts: { index: number; value: string }[] = [];

  for (const [envName, envValue] of Object.entries(process.env)) {
    if (!envValue || !envName.startsWith(baseName)) {
      continue;
    }

    const suffix = envName.slice(baseName.length);
    if (!suffix) {
      continue;
    }

    const trimmed = suffix.replace(/^[\s_-]+/, '');
    if (!trimmed) {
      continue;
    }

    let indexString: string | undefined;
    const upper = trimmed.toUpperCase();

    if (upper.startsWith('PART')) {
      const remainder = trimmed.slice(4).replace(/^[\s_-]+/, '');
      if (remainder && /^\d+$/.test(remainder)) {
        indexString = remainder;
      }
    } else if (/^\d+$/.test(trimmed)) {
      indexString = trimmed;
    }

    if (indexString) {
      parts.push({ index: parseInt(indexString, 10), value: envValue });
    }
  }

  if (!parts.length) {
    return undefined;
  }

  parts.sort((a, b) => a.index - b.index);
  return parts.map((part) => part.value).join('');
}

function normalisePrivateKey(value: string | undefined): string | undefined {
  if (!value) {
    return undefined;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }

  // Many hosting providers require escaped newlines for private keys.
  if (trimmed.includes('\\n')) {
    return trimmed.replace(/\\n/g, '\n');
  }

  return trimmed;
}

function buildCredentialsFromEnvironmentParts(): ServiceAccountCredentials | undefined {
  const clientEmail = getFirstSetEnv(SERVICE_ACCOUNT_EMAIL_ENV_NAMES);
  const privateKey = normalisePrivateKey(getFirstSetEnv(SERVICE_ACCOUNT_KEY_ENV_NAMES));
  const projectId = getFirstSetEnv(PROJECT_ID_ENV_NAMES);

  if (clientEmail && privateKey) {
    const credentials: ServiceAccountCredentials = {
      client_email: clientEmail,
      private_key: privateKey,
    };

    if (projectId) {
      credentials.project_id = projectId;
    }

    return credentials;
  }

  return undefined;
}

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
    
    const serviceAccountKeyResult = getFirstSetEnvWithName(SERVICE_ACCOUNT_JSON_ENV_NAMES);
    const serviceAccountKey = serviceAccountKeyResult?.value;
    const serviceAccountSource = serviceAccountKeyResult?.name || 'GCP_SERVICE_ACCOUNT_KEY';
    const googleCredentialsResult = getFirstSetEnvWithName(['GOOGLE_APPLICATION_CREDENTIALS']);
    const googleCredentialsEnv = googleCredentialsResult?.value;

    if (serviceAccountKey) {
      credentials = parseServiceAccount(serviceAccountKey, serviceAccountSource);
      if (!credentials) {
        return NextResponse.json({
          error: 'Configuration error',
          message: `${serviceAccountSource} is not valid JSON or base64 encoded JSON`,
          details: `Provide the raw JSON service account key or a base64 encoded version of it in the ${serviceAccountSource} environment variable, then redeploy.`,
        }, { status: 500 });
      }

      if (!projectId && typeof credentials === 'object' && credentials.project_id) {
        projectId = credentials.project_id;
        console.log(`Using project ID from ${serviceAccountSource}:`, projectId);
      }
    } else if (googleCredentialsEnv) {
      const googleSource = googleCredentialsResult?.name || 'GOOGLE_APPLICATION_CREDENTIALS';

      credentials = parseServiceAccount(googleCredentialsEnv, googleSource);

      if (!credentials) {
        // If not JSON or base64 JSON, assume it's a file path (local development)
        credentials = undefined;
      } else if (!projectId && typeof credentials === 'object' && credentials.project_id) {
        projectId = credentials.project_id;
        console.log(`Using project ID from ${googleSource}:`, projectId);
      }
    } else {
      const credentialsFromParts = buildCredentialsFromEnvironmentParts();
      if (credentialsFromParts) {
        credentials = {
          client_email: credentialsFromParts.client_email,
          private_key: credentialsFromParts.private_key,
          project_id: credentialsFromParts.project_id,
          type: 'service_account',
        };

        if (!projectId && credentialsFromParts.project_id) {
          projectId = credentialsFromParts.project_id;
          console.log('Using project ID from credential parts:', projectId);
        }
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

    if (!credentials && runningOnVercel) {
      return NextResponse.json({
        error: 'Missing Google Cloud credentials',
        message: 'BigQuery credentials are not configured for this deployment.',
        details: 'Set a supported environment variable such as GCP_SERVICE_ACCOUNT_KEY, GCP_CREDENTIALS, GOOGLE_CREDENTIALS, or BIGQUERY_SERVICE_ACCOUNT_KEY to the contents of your service account JSON (raw or base64 encoded) and redeploy.',
        documentation: 'See amazon_ppc_dashboard/nextjs_space/README_BIGQUERY.md for detailed setup instructions.',
        troubleshooting: [
          'In Vercel, add GCP_SERVICE_ACCOUNT_KEY (or GOOGLE_CREDENTIALS/BIGQUERY_SERVICE_ACCOUNT_KEY) as an Environment Variable and paste the JSON from your service account key.',
          'Alternatively, provide credential parts: GCP_CLIENT_EMAIL / GOOGLE_CLIENT_EMAIL and GCP_PRIVATE_KEY / GOOGLE_PRIVATE_KEY (with newlines escaped as \\n).',
          'You can also set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS_JSON to the JSON string (not a file path).',
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
    
    // Validate and sanitize limit parameter (max 100)
    let limit = parseInt(searchParams.get('limit') || '10');
    if (isNaN(limit) || limit < 1) {
      limit = 10;
    } else if (limit > 100) {
      limit = 100;
    }
    
    // Validate and sanitize days parameter (max 365)
    let days = parseInt(searchParams.get('days') || '7');
    if (isNaN(days) || days < 1) {
      days = 7;
    } else if (days > 365) {
      days = 365;
    }
    
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
