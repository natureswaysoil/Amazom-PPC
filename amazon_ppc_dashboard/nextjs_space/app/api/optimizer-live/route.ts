import { NextRequest, NextResponse } from 'next/server';

import { resolveDashboardApiKey } from '../lib/dashboard-api-key';

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

export async function GET(request: NextRequest) {
  try {
    const resolved = await resolveDashboardApiKey({ required: true });
    const apiKey = resolved.apiKey;
    if (!apiKey) {
      throw new Error(
        'DASHBOARD_API_KEY is not configured. Set DASHBOARD_API_KEY or configure Secret Manager via DASHBOARD_API_SECRET_NAME / DASHBOARD_API_SECRET_RESOURCE.',
      );
    }

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

    // Retry on rate limiting / transient backend errors.
    for (let attempt = 0; attempt < 3; attempt++) {
      resp = await fetch(target.toString(), {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'X-API-Key': apiKey,
          ...(profileId ? { 'X-Profile-ID': profileId } : {}),
        },
        cache: 'no-store',
      });

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
