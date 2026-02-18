/**
 * BigQuery Client Library for Amazon PPC Dashboard
 * 
 * This module provides a centralized BigQuery client for querying campaign,
 * keyword, and performance data. It handles authentication, connection setup,
 * and common query patterns.
 * 
 * Usage:
 *   import { getBigQueryClient, queryCampaigns, queryKeywords, queryPerformance } from '@/lib/bigquery';
 * 
 *   const campaigns = await queryCampaigns({ limit: 100 });
 *   const keywords = await queryKeywords({ limit: 100, days: 7 });
 */

import { BigQuery } from '@google-cloud/bigquery';
import { resolveGCPCredentials, getFirstSetEnv } from '../app/api/lib/credentials';

// Environment variable configuration
const PROJECT_ID_ENV_NAMES = [
  'GOOGLE_CLOUD_PROJECT',
  'GCP_PROJECT',
  'GCP_PROJECT_ID',
  'GCLOUD_PROJECT',
];

const DATASET_ID_ENV_NAMES = [
  'BQ_DATASET_ID',
  'BIGQUERY_DATASET',
  'BIGQUERY_DATASET_ID',
  'BQ_DATASET',
  'BQ_DATASET_NAME',
];

const LOCATION_ENV_NAMES = [
  'BQ_LOCATION',
  'BIGQUERY_LOCATION',
  'BQ_REGION',
];

// Default configuration
const DEFAULT_PROJECT_ID = 'amazon-ppc-474902';
const DEFAULT_DATASET_ID = 'amazon_ppc_data';
const DEFAULT_LOCATION = 'us-east4';

// Cached BigQuery client
let cachedClient: BigQuery | null = null;
let cachedConfig: {
  projectId: string;
  datasetId: string;
  location: string;
} | null = null;

export interface BigQueryConfig {
  projectId: string;
  datasetId: string;
  location: string;
}

export interface QueryOptions {
  limit?: number;
  days?: number;
  orderBy?: string;
  orderDirection?: 'ASC' | 'DESC';
}

/**
 * Get the BigQuery configuration from environment variables
 */
export function getBigQueryConfig(): BigQueryConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const projectId =
    getFirstSetEnv(PROJECT_ID_ENV_NAMES) || DEFAULT_PROJECT_ID;
  const datasetId =
    getFirstSetEnv(DATASET_ID_ENV_NAMES) || DEFAULT_DATASET_ID;
  const location =
    getFirstSetEnv(LOCATION_ENV_NAMES) || DEFAULT_LOCATION;

  cachedConfig = { projectId, datasetId, location };
  return cachedConfig;
}

/**
 * Get or create a BigQuery client with proper authentication
 * 
 * In Cloud Run, this uses Application Default Credentials (ADC) automatically.
 * For local development, it uses credentials from GCP_SERVICE_ACCOUNT_KEY env var.
 */
export async function getBigQueryClient(): Promise<BigQuery> {
  if (cachedClient) {
    return cachedClient;
  }

  const config = getBigQueryConfig();
  const isCloudRun = Boolean(
    process.env.K_SERVICE || process.env.CLOUD_RUN_JOB
  );

  console.log(
    `[BigQuery] Initializing client for project: ${config.projectId}, dataset: ${config.datasetId}`
  );

  const bigqueryOptions: any = {
    projectId: config.projectId,
  };

  // In Cloud Run, use Application Default Credentials
  // Otherwise, resolve credentials from environment
  if (!isCloudRun) {
    const credentialResult = await resolveGCPCredentials();
    if (credentialResult.success && credentialResult.credentials) {
      bigqueryOptions.credentials = credentialResult.credentials;
      console.log(
        `[BigQuery] Using explicit credentials from ${credentialResult.source}`
      );
    } else {
      console.log('[BigQuery] Using Application Default Credentials');
    }
  } else {
    console.log('[BigQuery] Running in Cloud Run, using ADC');
  }

  cachedClient = new BigQuery(bigqueryOptions);
  return cachedClient;
}

/**
 * Execute a BigQuery query with proper error handling
 */
export async function executeQuery<T = any>(
  query: string,
  params?: Record<string, any>
): Promise<T[]> {
  const client = await getBigQueryClient();
  const config = getBigQueryConfig();

  console.log(`[BigQuery] Executing query:`, query.substring(0, 100) + '...');

  const [job] = await client.createQueryJob({
    query,
    params,
    location: config.location,
  });

  const [rows] = await job.getQueryResults();
  console.log(`[BigQuery] Query returned ${rows.length} rows`);

  return rows as T[];
}

/**
 * Query campaigns data
 */
export async function queryCampaigns(options: QueryOptions = {}) {
  const config = getBigQueryConfig();
  const limit = options.limit || 100;
  const days = options.days || 0;

  let whereClause = '';
  if (days > 0) {
    whereClause = 'WHERE DATE(lastUpdateDateTime) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)';
  }

  const query = `
    SELECT *
    FROM \`${config.projectId}.${config.datasetId}.campaigns\`
    ${whereClause}
    ORDER BY lastUpdateDateTime DESC
    LIMIT @limit
  `;

  return executeQuery(query, { limit, days });
}

/**
 * Query keywords data
 */
export async function queryKeywords(options: QueryOptions = {}) {
  const config = getBigQueryConfig();
  const limit = options.limit || 100;
  const days = options.days || 0;

  let whereClause = '';
  if (days > 0) {
    whereClause = 'WHERE DATE(fetch_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)';
  }

  const query = `
    SELECT *
    FROM \`${config.projectId}.${config.datasetId}.keywords\`
    ${whereClause}
    ORDER BY fetch_timestamp DESC
    LIMIT @limit
  `;

  return executeQuery(query, { limit, days });
}

/**
 * Query keyword performance data
 */
export async function queryPerformance(options: QueryOptions = {}) {
  const config = getBigQueryConfig();
  const limit = options.limit || 100;
  const days = options.days || 7;

  let whereClause = '';
  if (days > 0) {
    whereClause = 'WHERE DATE(segments_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)';
  }

  const query = `
    SELECT *
    FROM \`${config.projectId}.${config.datasetId}.keyword_performance\`
    ${whereClause}
    ORDER BY segments_date DESC
    LIMIT @limit
  `;

  return executeQuery(query, { limit, days });
}

/**
 * Get table row count
 */
export async function getTableRowCount(tableName: string): Promise<number> {
  const config = getBigQueryConfig();

  const query = `
    SELECT COUNT(*) as count
    FROM \`${config.projectId}.${config.datasetId}.${tableName}\`
  `;

  const rows = await executeQuery<{ count: number }>(query);
  return rows[0]?.count || 0;
}

/**
 * List all tables in the dataset
 */
export async function listTables(): Promise<string[]> {
  const client = await getBigQueryClient();
  const config = getBigQueryConfig();

  const dataset = client.dataset(config.datasetId);
  const [tables] = await dataset.getTables();

  return tables.map((table) => table.id || '');
}

/**
 * Check if BigQuery connection is working
 */
export async function testConnection(): Promise<{
  success: boolean;
  error?: string;
  config?: BigQueryConfig;
}> {
  try {
    const config = getBigQueryConfig();
    const client = await getBigQueryClient();

    // Try a simple query to verify connectivity
    const query = 'SELECT 1 as test';
    await executeQuery(query);

    return {
      success: true,
      config,
    };
  } catch (error: any) {
    console.error('[BigQuery] Connection test failed:', error);
    return {
      success: false,
      error: error.message || String(error),
    };
  }
}
