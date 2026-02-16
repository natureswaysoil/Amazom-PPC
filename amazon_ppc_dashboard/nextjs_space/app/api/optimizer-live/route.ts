import { NextRequest, NextResponse } from 'next/server';
import { GoogleAuth } from 'google-auth-library';

import { resolveDashboardApiKey } from '../lib/dashboard-api-key';
import { resolveGCPCredentials } from '../lib/credentials';

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

  // Prioritize API key authentication - if we have an API key, use it exclusively
  if (apiKey) {
    console.log('[optimizer-live] Using API key authentication');
    const headers: Record<string, string> = {
      'X-API-Key': apiKey,
      ...(profileId ? { 'X-Profile-ID': profileId } : {}),
    };

    const resp = await fetch(url, {
      method: 'GET',
      headers,
      cache: 'no-store',
    });
    return { resp, usedIdToken: false };
  }

  // Only use ID token if API key is not available
  if (allowIdTokenRetry) {
    console.log('[optimizer-live] Using ID token authentication');
    try {
      // The audience should be the target service's origin for proper IAM auth
      const audience = new URL(url).origin;
      const idTokenHeaders = await getIdTokenHeaders(audience);
      const headers: Record<string, string> = {
        ...idTokenHeaders,
        ...(profileId ? { 'X-Profile-ID': profileId } : {}),
      };

      const resp = await fetch(url, {
        method: 'GET',
        headers,
        cache: 'no-store',
      });
      return { resp, usedIdToken: true };
    } catch (err) {
      console.error('[optimizer-live] Failed to mint ID token:', err);
      // Fall back to unauthenticated request
      const headers: Record<string, string> = {
        ...(profileId ? { 'X-Profile-ID': profileId } : {}),
      };
      const resp = await fetch(url, {
        method: 'GET',
        headers,
        cache: 'no-store',
      });
      return { resp, usedIdToken: false };
    }
  }

  // Fallback: unauthenticated request
  console.log('[optimizer-live] Using unauthenticated request');
  const baseHeaders: Record<string, string> = {
    ...(profileId ? { 'X-Profile-ID': profileId } : {}),
  };

  const resp = await fetch(url, {
    method: 'GET',
    headers: baseHeaders,
    cache: 'no-store',
  });

  return { resp, usedIdToken: false };
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

    const target = new URL(baseUrl);
    // Optimizer routes live data on query params.
    target.searchParams.set('live', section);
    if (days) target.searchParams.set('days', days);
    if (limit) target.searchParams.set('limit', limit);
    if (profileId) target.searchParams.set('profile_id', profileId);

    let resp: Response | undefined;
    let text = '';

    // Don't retry with ID token if we have API key - use mutually exclusive auth
    // OPTIMIZER_LIVE_ALLOW_ID_TOKEN_RETRY: Set to 'false' to disable ID token retry (defaults to true)
    const allowIdTokenRetry =
      process.env.OPTIMIZER_LIVE_ALLOW_ID_TOKEN_RETRY !== 'false' &&
      !apiKey && // Only use ID token if API key is not available
      ((process.env.OPTIMIZER_USE_ID_TOKEN || '').trim().toLowerCase() === 'true' ||
        Boolean(process.env.K_SERVICE || process.env.FUNCTION_TARGET || process.env.GAE_SERVICE || process.env.CLOUD_RUN_JOB) ||
        Boolean(
          (process.env.GCP_SERVICE_ACCOUNT_KEY || '').trim() ||
            (process.env.GCP_SA_KEY || '').trim() ||
            (process.env.GCP_SERVICE_ACCOUNT_KEY_JSON || '').trim(),
        ));

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
    const apiKey = (await resolveDashboardApiKey({ required: false })).apiKey || undefined;
    return NextResponse.json(
      {
        ok: false,
        error: 'Failed to call optimizer live endpoint',
        message: err?.message || String(err),
        authMethod: apiKey ? 'api-key' : 'id-token',
        suggestion: apiKey
          ? 'Verify DASHBOARD_API_KEY matches optimizer configuration'
          : 'Consider setting DASHBOARD_API_KEY for more reliable authentication'
      },
      { status: 500 },
    );
  }
}
