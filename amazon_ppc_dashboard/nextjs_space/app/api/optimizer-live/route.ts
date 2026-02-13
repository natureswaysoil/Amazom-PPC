import { NextRequest, NextResponse } from 'next/server';
import { GoogleAuth } from 'google-auth-library';
import { BigQuery } from '@google-cloud/bigquery';

import { resolveDashboardApiKey } from '../lib/dashboard-api-key';
import { resolveGCPCredentials, getFirstSetEnv } from '../lib/credentials';

export const dynamic = 'force-dynamic';

type CachedResponse = {
  expiresAt: number;
  status: number;
  body: any;
};

const CACHE_TTL_MS = Number.parseInt(
  process.env.OPTIMIZER_LIVE_CACHE_TTL_MS || '15000',
  10,
);

const liveCache = new Map<string, CachedResponse>();

type OptimizerFetchResult = {
  resp: Response;
  usedIdToken: boolean;
};

function includesRunIntervalNotMet(payload: any, rawText: string): boolean {
  const textCandidates: Array<string> = [];

  if (typeof rawText === 'string' && rawText.trim()) textCandidates.push(rawText);
  if (typeof payload === 'string' && payload.trim()) textCandidates.push(payload);
  if (payload && typeof payload === 'object') {
    const message = payload?.message;
    const error = payload?.error;
    const detail = payload?.details;
    if (typeof message === 'string') textCandidates.push(message);
    if (typeof error === 'string') textCandidates.push(error);
    if (typeof detail === 'string') textCandidates.push(detail);
  }

  return textCandidates.some((t) => t.toLowerCase().includes('run interval not met'));
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getOptimizerBaseUrl(): string {
  const envUrl =
    process.env.PPC_OPTIMIZER_URL ||
    process.env.OPTIMIZER_URL ||
    process.env.PPC_OPTIMIZER_API_BASE ||
    process.env.PPC_OPTIMIZER_BASE_URL ||
    '';

  const url = envUrl.trim();
  if (url) return url.replace(/\/+$/, '');

  // Fallback to the known production service URL in this project.
  return 'https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app';
}

async function getIdTokenHeaders(audience: string): Promise<Record<string, string>> {
  const resolved = await resolveGCPCredentials();

  const auth = new GoogleAuth({
    scopes: ['https://www.googleapis.com/auth/cloud-platform'],
    ...(resolved.success && resolved.credentials ? { credentials: resolved.credentials } : {}),
  });

  // For Cloud Run, the audience should be the service base URL.
  // google-auth-library will mint an ID token using ADC.
  const client: any = await (auth as any).getIdTokenClient(audience);
  const headers: any = await client.getRequestHeaders(audience);

  const authHeader = headers?.Authorization || headers?.authorization;
  if (!authHeader || typeof authHeader !== 'string') {
    throw new Error('Failed to mint ID token headers for optimizer audience');
  }

  return { Authorization: authHeader };
}

async function fetchOptimizerWithRetry(options: {
  url: string;
  apiKey?: string;
  profileId?: string;
  allowIdTokenRetry: boolean;
}): Promise<OptimizerFetchResult> {
  const { url, apiKey, profileId, allowIdTokenRetry } = options;

  const baseHeaders: Record<string, string> = {
    ...(apiKey ? { 'X-API-Key': apiKey } : {}),
    ...(profileId ? { 'X-Profile-ID': profileId } : {}),
  };

  // First attempt: API-key only. This works when the optimizer allows unauthenticated
  // invocations (or is behind some other layer) and enforces app-level auth.
  let resp = await fetch(url, {
    method: 'GET',
    headers: baseHeaders,
    cache: 'no-store',
  });

  // Cloud Run/Functions return 401 or 403 when IAM auth is required.
  if ((resp.status !== 403 && resp.status !== 401) || !allowIdTokenRetry) {
    return { resp, usedIdToken: false };
  }

  // Second attempt: Cloud Run IAM auth via ID token + still pass X-API-Key for
  // the optimizer app-level auth.
  const audience = new URL(url).origin;
  const idHeaders = await getIdTokenHeaders(audience);
  resp = await fetch(url, {
    method: 'GET',
    headers: {
      ...baseHeaders,
      ...idHeaders,
    },
    cache: 'no-store',
  });

  return { resp, usedIdToken: true };
}

async function handleAnalyticsSection(days: string): Promise<any> {
  const daysNum = Number.parseInt(days || '30', 10) || 30;
  
  try {
    const credentialResult = await resolveGCPCredentials();
    const projectId = getFirstSetEnv([
      'BQ_PROJECT_ID',
      'BIGQUERY_PROJECT_ID',
      'GOOGLE_CLOUD_PROJECT',
      'GCP_PROJECT',
      'GCP_PROJECT_ID',
      'GCLOUD_PROJECT',
    ]) || 'amazon-ppc-474902';
    
    const datasetId = getFirstSetEnv([
      'BQ_DATASET_ID',
      'BIGQUERY_DATASET',
      'BIGQUERY_DATASET_ID',
      'BQ_DATASET',
      'BQ_DATASET_NAME',
    ]) || 'amazon_ppc_data';

    const bigqueryOptions: any = { projectId };
    if (credentialResult.credentials) {
      bigqueryOptions.credentials = credentialResult.credentials;
    }
    const bigquery = new BigQuery(bigqueryOptions);

    // Query 1: Daily trends (last N days)
    const trendsQuery = `
      SELECT
        DATE(timestamp) as date,
        COUNT(DISTINCT run_id) as runs,
        SUM(CAST(keywords_optimized AS INT64)) as keywords,
        SUM(CAST(bids_increased AS INT64)) as bids_increased,
        SUM(CAST(bids_decreased AS INT64)) as bids_decreased,
        AVG(CAST(average_acos AS FLOAT64)) as acos,
        SUM(CAST(total_spend AS FLOAT64)) as spend,
        SUM(CAST(total_sales AS FLOAT64)) as sales
      FROM \`${projectId}.${datasetId}.optimization_results\`
      WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
        AND status = 'success'
      GROUP BY date
      ORDER BY date ASC
    `;

    const [trendsJob] = await bigquery.createQueryJob({
      query: trendsQuery,
      params: { days: daysNum },
    });
    const [trendsRows] = await trendsJob.getQueryResults();

    // Query 2: Overall metrics
    const metricsQuery = `
      SELECT
        COUNT(DISTINCT run_id) as total_runs,
        SUM(CAST(keywords_optimized AS INT64)) as total_keywords,
        AVG(CAST(average_acos AS FLOAT64)) as avg_acos,
        AVG(CAST(duration_seconds AS FLOAT64)) as avg_duration,
        COUNT(DISTINCT 
          CASE 
            WHEN JSON_EXTRACT_SCALAR(features, '$.campaigns') IS NOT NULL 
            THEN JSON_EXTRACT_SCALAR(features, '$.campaigns')
          END
        ) as total_campaigns,
        COUNTIF(status = 'success') * 100.0 / COUNT(*) as success_rate
      FROM \`${projectId}.${datasetId}.optimization_results\`
      WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
    `;

    const [metricsJob] = await bigquery.createQueryJob({
      query: metricsQuery,
      params: { days: daysNum },
    });
    const [metricsRows] = await metricsJob.getQueryResults();
    const metrics = metricsRows[0] || {};

    // Query 3: Campaign performance (if campaign_details table exists)
    let campaigns: any[] = [];
    try {
      const campaignsQuery = `
        SELECT
          campaign_id,
          campaign_name,
          SUM(CAST(spend AS FLOAT64)) as spend,
          SUM(CAST(sales AS FLOAT64)) as sales,
          SAFE_DIVIDE(SUM(CAST(spend AS FLOAT64)), SUM(CAST(sales AS FLOAT64))) * 100 as acos,
          COUNT(*) as changes
        FROM \`${projectId}.${datasetId}.campaign_details\`
        WHERE segments_date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
        GROUP BY campaign_id, campaign_name
        ORDER BY spend DESC
        LIMIT 10
      `;

      const [campaignsJob] = await bigquery.createQueryJob({
        query: campaignsQuery,
        params: { days: daysNum },
      });
      const [campaignsRows] = await campaignsJob.getQueryResults();
      campaigns = campaignsRows;
    } catch (err) {
      console.warn('[Analytics] Campaign details query failed (table may not exist):', err);
    }

    // Query 4: Comparative analysis (week-over-week)
    const compareQuery = `
      WITH current_week AS (
        SELECT
          SUM(CAST(total_spend AS FLOAT64)) as spend,
          SUM(CAST(total_sales AS FLOAT64)) as sales,
          AVG(CAST(average_acos AS FLOAT64)) as acos
        FROM \`${projectId}.${datasetId}.optimization_results\`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
          AND status = 'success'
      ),
      previous_week AS (
        SELECT
          SUM(CAST(total_spend AS FLOAT64)) as spend,
          SUM(CAST(total_sales AS FLOAT64)) as sales,
          AVG(CAST(average_acos AS FLOAT64)) as acos
        FROM \`${projectId}.${datasetId}.optimization_results\`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
          AND DATE(timestamp) < DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
          AND status = 'success'
      )
      SELECT
        SAFE_DIVIDE((c.spend - p.spend), p.spend) * 100 as spend_change,
        SAFE_DIVIDE((c.sales - p.sales), p.sales) * 100 as sales_change,
        SAFE_DIVIDE((c.acos - p.acos), p.acos) * 100 as acos_change
      FROM current_week c, previous_week p
    `;

    const [compareJob] = await bigquery.createQueryJob({
      query: compareQuery,
      params: {},
    });
    const [compareRows] = await compareJob.getQueryResults();
    const comparative = compareRows[0] || { spend_change: 0, sales_change: 0, acos_change: 0 };

    // Calculate predictions
    const totalRuns = Number(metrics.total_runs) || 0;
    const totalKeywords = Number(metrics.total_keywords) || 0;
    const totalSales = trendsRows.reduce((sum: number, row: any) => sum + (Number(row.sales) || 0), 0);
    
    const predictions = {
      runs_per_week: totalRuns > 0 ? (totalRuns / daysNum) * 7 : 0,
      keywords_per_run: totalRuns > 0 ? totalKeywords / totalRuns : 0,
      efficiency_score: totalKeywords > 0 ? totalSales / totalKeywords : 0,
    };

    return {
      status: 'success',
      data: {
        trends: {
          daily: trendsRows.map((row: any) => ({
            date: row.date?.value || row.date,
            runs: Number(row.runs) || 0,
            keywords: Number(row.keywords) || 0,
            bids_increased: Number(row.bids_increased) || 0,
            bids_decreased: Number(row.bids_decreased) || 0,
            acos: Number(row.acos) || 0,
            spend: Number(row.spend) || 0,
            sales: Number(row.sales) || 0,
          })),
        },
        metrics: {
          total_runs: Number(metrics.total_runs) || 0,
          total_keywords: Number(metrics.total_keywords) || 0,
          avg_acos: Number(metrics.avg_acos) || 0,
          success_rate: Number(metrics.success_rate) || 0,
          avg_duration: Number(metrics.avg_duration) || 0,
          total_campaigns: Number(metrics.total_campaigns) || 0,
        },
        campaigns: campaigns.map((row: any) => ({
          campaign_id: row.campaign_id,
          campaign_name: row.campaign_name,
          spend: Number(row.spend) || 0,
          sales: Number(row.sales) || 0,
          acos: Number(row.acos) || 0,
          changes: Number(row.changes) || 0,
        })),
        comparative: {
          wow: {
            spend_change: Number(comparative.spend_change) || 0,
            sales_change: Number(comparative.sales_change) || 0,
            acos_change: Number(comparative.acos_change) || 0,
          },
        },
        predictions,
      },
    };
  } catch (err: any) {
    console.error('[Analytics] Error querying BigQuery:', err);
    throw err;
  }
}


export async function GET(request: NextRequest) {
  try {
    const resolved = await resolveDashboardApiKey({ required: false });
    const apiKey = resolved.apiKey || undefined;

    const baseUrl = getOptimizerBaseUrl();
    const { searchParams } = new URL(request.url);

    const section = (searchParams.get('section') || searchParams.get('live') || 'overview').trim();
    const days = (searchParams.get('days') || '').trim();
    const limit = (searchParams.get('limit') || '').trim();
    const profileId = (searchParams.get('profile_id') || '').trim();

    const cacheKey = `${baseUrl}|${section}|${days}|${limit}|${profileId}`;
    const now = Date.now();
    const cached = liveCache.get(cacheKey);
    if (cached && cached.expiresAt > now) {
      return NextResponse.json(cached.body, { status: cached.status });
    }

    // Handle analytics section with direct BigQuery queries
    if (section === 'analytics') {
      try {
        const analyticsData = await handleAnalyticsSection(days || '30');
        const body = {
          ok: true,
          optimizerBaseUrl: baseUrl,
          section,
          status: 200,
          auth: 'bigquery-direct',
          data: analyticsData,
        };

        // Cache the result
        if (CACHE_TTL_MS > 0) {
          liveCache.set(cacheKey, {
            expiresAt: now + CACHE_TTL_MS,
            status: 200,
            body,
          });
        }

        return NextResponse.json(body, { status: 200 });
      } catch (err: any) {
        console.error('[Analytics] Failed to fetch analytics data:', err);
        return NextResponse.json(
          {
            ok: false,
            error: 'Failed to fetch analytics data',
            message: err?.message || String(err),
          },
          { status: 500 },
        );
      }
    }

    const target = new URL(baseUrl);
    // Optimizer routes live data on query params.
    target.searchParams.set('live', section);
    if (days) target.searchParams.set('days', days);
    if (limit) target.searchParams.set('limit', limit);
    if (profileId) target.searchParams.set('profile_id', profileId);

    let resp: Response | undefined;
    let text = '';

    const allowIdTokenRetry =
      (process.env.OPTIMIZER_USE_ID_TOKEN || '').trim().toLowerCase() === 'true' ||
      Boolean(process.env.K_SERVICE || process.env.FUNCTION_TARGET || process.env.GAE_SERVICE || process.env.CLOUD_RUN_JOB) ||
      Boolean(
        (process.env.GCP_SERVICE_ACCOUNT_KEY || '').trim() ||
          (process.env.GCP_SA_KEY || '').trim() ||
          (process.env.GCP_SERVICE_ACCOUNT_KEY_JSON || '').trim(),
      );

    // Retry on rate limiting / transient backend errors.
    // If the optimizer requires IAM auth (403), retry once with an ID token.
    let usedIdToken = false;
    for (let attempt = 0; attempt < 3; attempt++) {
      const result = await fetchOptimizerWithRetry({
        url: target.toString(),
        apiKey,
        profileId: profileId || undefined,
        allowIdTokenRetry,
      });
      resp = result.resp;
      usedIdToken = result.usedIdToken;

      if (resp.status !== 429 && resp.status !== 503) break;
      await sleep(400 * (attempt + 1));
    }

    if (!resp) throw new Error('Optimizer request did not return a response');

    text = await resp.text();
    let payload: any;
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { raw: text };
    }

    // The optimizer sometimes returns a non-200 status for "Run interval not met",
    // but the dashboard UX should treat that as a normal skipped state.
    if (!resp.ok && includesRunIntervalNotMet(payload, text)) {
      const skipped = {
        ok: true,
        optimizerBaseUrl: baseUrl,
        section,
        status: 200,
        data: {
          status: 'skipped',
          message:
            payload?.message || payload?.error || 'Run interval not met. Skipping run.',
          upstreamStatus: resp.status,
        },
      };

      if (CACHE_TTL_MS > 0) {
        liveCache.set(cacheKey, {
          expiresAt: now + CACHE_TTL_MS,
          status: 200,
          body: skipped,
        });
      }

      return NextResponse.json(skipped, { status: 200 });
    }

    const body = {
      ok: resp.ok,
      optimizerBaseUrl: baseUrl,
      section,
      status: resp.status,
      auth: usedIdToken ? 'id-token' : apiKey ? 'api-key' : 'none',
      data: payload,
    };
    const statusCode = resp.ok ? 200 : resp.status;

    // Cache successes briefly to avoid hammering the optimizer/BigQuery.
    if (resp.ok && CACHE_TTL_MS > 0) {
      liveCache.set(cacheKey, {
        expiresAt: now + CACHE_TTL_MS,
        status: statusCode,
        body,
      });
    }

    return NextResponse.json(body, { status: statusCode });
  } catch (err: any) {
    return NextResponse.json(
      {
        ok: false,
        error: 'Failed to call optimizer live endpoint',
        message: err?.message || String(err),
      },
      { status: 500 },
    );
  }
}
