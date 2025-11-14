'use strict';

if (typeof fetch !== 'function') {
  throw new Error('Global fetch API is not available. Ensure the service runs on Node.js 18 or later.');
}

const API_HOSTS = {
  NA: 'https://advertising-api.amazon.com',
  EU: 'https://advertising-api-eu.amazon.com',
  FE: 'https://advertising-api-fe.amazon.com',
};

const TOKEN_ENDPOINT = 'https://api.amazon.com/auth/o2/token';
const TOKEN_EXPIRY_BUFFER_MS = 60 * 1000; // refresh one minute before expiry
const TOKEN_REFRESH_MAX_ATTEMPTS = 3;
const TOKEN_REFRESH_RETRYABLE_STATUS = new Set([429, 500, 502, 503, 504]);
const TOKEN_REFRESH_RETRY_BASE_DELAY_MS = 250;
const SP_API_VERSION = '2024-05-01';
const REPORTS_API_VERSION = '2024-05-01';

class AmazonAdvertisingClient {
  constructor(options = {}) {
    const {
      clientId,
      clientSecret,
      refreshToken,
      region = 'NA',
      profileId,
      apiBaseUrl,
    } = options;

    const normalizedClientId = sanitizeSecret(clientId);
    const normalizedClientSecret = sanitizeSecret(clientSecret);
    const normalizedRefreshToken = sanitizeSecret(refreshToken);
    const normalizedProfileId = sanitizeSecret(profileId) || null;
    const normalizedRegion = sanitizeSecret(region) || 'NA';
    const normalizedApiBaseUrl = sanitizeSecret(apiBaseUrl);

    const missing = [];
    if (!normalizedClientId) missing.push('clientId');
    if (!normalizedClientSecret) missing.push('clientSecret');
    if (!normalizedRefreshToken) missing.push('refreshToken');
    if (missing.length) {
      throw new Error(`Missing required Amazon Advertising credentials: ${missing.join(', ')}`);
    }

    this.clientId = normalizedClientId;
    this.clientSecret = normalizedClientSecret;
    this.refreshToken = normalizedRefreshToken;
    this.profileId = normalizedProfileId;
    this.region = normalizedRegion.toUpperCase();
    this.apiBaseUrl = normalizedApiBaseUrl || API_HOSTS[this.region] || API_HOSTS.NA;

    this.accessToken = null;
    this.tokenExpiresAt = 0;
    this._refreshInFlight = null;
  }

  async getAccessToken({ forceRefresh = false } = {}) {
    const now = Date.now();
    if (!forceRefresh && this.accessToken && now + TOKEN_EXPIRY_BUFFER_MS < this.tokenExpiresAt) {
      return this.accessToken;
    }

    if (this._refreshInFlight && !forceRefresh) {
      return this._refreshInFlight;
    }

    const refreshPromise = this._performTokenRefresh();
    if (!forceRefresh) {
      this._refreshInFlight = refreshPromise;
    }

    try {
      const token = await refreshPromise;
      return token;
    } finally {
      if (!forceRefresh) {
        this._refreshInFlight = null;
      }
    }
  }

  async _performTokenRefresh() {
    let lastError = null;

    for (let attempt = 1; attempt <= TOKEN_REFRESH_MAX_ATTEMPTS; attempt += 1) {
      const body = new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: this.refreshToken,
        client_id: this.clientId,
        client_secret: this.clientSecret,
      });

      let response;
      try {
        response = await fetch(TOKEN_ENDPOINT, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
          },
          body,
        });
      } catch (error) {
        lastError = new Error(`network error: ${error.message}`);
        if (attempt === TOKEN_REFRESH_MAX_ATTEMPTS) {
          break;
        }
        await delay(calculateRetryDelay(attempt));
        continue;
      }

      let rawPayload = '';
      let payload = null;
      try {
        rawPayload = await response.text();
        if (rawPayload) {
          payload = JSON.parse(rawPayload);
        }
      } catch (error) {
        if (response.ok) {
          lastError = new Error(`invalid JSON payload: ${error.message}`);
          if (attempt === TOKEN_REFRESH_MAX_ATTEMPTS) {
            break;
          }
          await delay(calculateRetryDelay(attempt));
          continue;
        }
        payload = null;
      }

      if (!response.ok) {
        const statusDetails = `${response.status} ${response.statusText}`.trim();
        const message = extractErrorMessage(payload, rawPayload, statusDetails);
        const error = new Error(message);

        if (TOKEN_REFRESH_RETRYABLE_STATUS.has(response.status) && attempt < TOKEN_REFRESH_MAX_ATTEMPTS) {
          lastError = error;
          await delay(calculateRetryDelay(attempt));
          continue;
        }

        throw error;
      }

      if (!payload || typeof payload !== 'object' || !payload.access_token) {
        lastError = new Error('response missing access_token');
        if (attempt === TOKEN_REFRESH_MAX_ATTEMPTS) {
          break;
        }
        await delay(calculateRetryDelay(attempt));
        continue;
      }

      const expiresIn = Number(payload.expires_in || 3600);
      this.accessToken = payload.access_token;
      this.tokenExpiresAt = Date.now() + expiresIn * 1000;

      const rotatedRefreshToken = sanitizeSecret(payload.refresh_token);
      if (rotatedRefreshToken && rotatedRefreshToken !== this.refreshToken) {
        // Amazon may rotate refresh tokens; warn so operators can persist the new value.
        console.warn('Received rotated Amazon Ads refresh token. Update Secret Manager to persist the new token.');
        this.refreshToken = rotatedRefreshToken;
      }

      return this.accessToken;
    }

    const errorMessage = lastError ? lastError.message : 'unknown error';
    throw new Error(`Failed to refresh access token after ${TOKEN_REFRESH_MAX_ATTEMPTS} attempts: ${errorMessage}`);
  }

  async makeRequest(path, options = {}) {
    const {
      method = 'GET',
      query,
      headers = {},
      body,
      profileId,
      retryOnUnauthorized = true,
      signal,
    } = options;

    const upgradedPath = this._upgradePath(typeof path === 'string' ? path : '');
    const url = this._buildUrl(upgradedPath, query);

    const attempt = async (forceRefresh = false) => {
      const token = await this.getAccessToken({ forceRefresh });
      const requestHeaders = {
        'Authorization': `Bearer ${token}`,
        'Amazon-Advertising-API-ClientId': this.clientId,
        'Accept': 'application/json',
        ...headers,
      };

      const scope = profileId || this.profileId;
      if (scope) {
        requestHeaders['Amazon-Advertising-API-Scope'] = scope;
      }

      let requestBody = body;
      if (body && typeof body === 'object' && !(body instanceof URLSearchParams) && !Buffer.isBuffer(body)) {
        requestHeaders['Content-Type'] = requestHeaders['Content-Type'] || 'application/json';
        requestBody = JSON.stringify(body);
      }

      let response;
      try {
        response = await fetch(url, {
          method,
          headers: requestHeaders,
          body: method === 'GET' ? undefined : requestBody,
          signal,
        });
      } catch (error) {
        throw new Error(`Amazon Ads API request failed: ${error.message}`);
      }

      const responseText = await response.text();
      let payload = null;
      if (responseText) {
        try {
          payload = JSON.parse(responseText);
        } catch (parseErr) {
          payload = responseText;
        }
      }

      if (response.status === 401 && retryOnUnauthorized && !forceRefresh) {
        return attempt(true);
      }

      if (!response.ok) {
        const details = typeof payload === 'string'
          ? payload
          : (payload && (payload.error_description || payload.error || JSON.stringify(payload))) || response.statusText;
        throw new Error(`Amazon Ads API request failed (${response.status} ${response.statusText}): ${details}`);
      }

      return payload ?? {};
    };

    return attempt(false);
  }

  async requestPerformanceReport({
    profileId,
    startDate,
    endDate,
    stateFilter = 'enabled,paused',
    campaignType = 'sponsoredProducts',
  } = {}) {
    const scope = profileId || this.profileId;
    if (!scope) {
      throw new Error('Amazon profile ID is required to request performance reports.');
    }

    const query = {
      stateFilter,
      campaignType,
    };

    if (startDate) {
      query.startDate = startDate;
      query.startIndex = 0;
      query.count = 1000;
    }

    if (endDate) {
      query.endDate = endDate;
    }

    const response = await this.makeRequest('/v2/sp/campaigns', {
      method: 'GET',
      query,
      profileId: scope,
    });

    return Array.isArray(response) ? response : [];
  }

  _upgradePath(path) {
    if (!path.startsWith('/v2/')) {
      return path;
    }

    const replacements = [
      ['/v2/sp/campaigns', `/sp/campaigns/${SP_API_VERSION}`],
      ['/v2/sp/adGroups', `/sp/adGroups/${SP_API_VERSION}`],
      ['/v2/sp/keywords/extended', `/sp/keywords/extended/${SP_API_VERSION}`],
      ['/v2/sp/keywords', `/sp/keywords/${SP_API_VERSION}`],
      ['/v2/sp/negativeKeywords', `/sp/negativeKeywords/${SP_API_VERSION}`],
      ['/v2/sp/targets/keywords/recommendations', `/sp/targets/keywords/recommendations/${SP_API_VERSION}`],
      ['/v2/reports', `/reports/${REPORTS_API_VERSION}`],
    ];

    for (const [legacy, modern] of replacements) {
      if (path.startsWith(legacy)) {
        return `${modern}${path.slice(legacy.length)}`;
      }
    }

    return path;
  }

  _buildUrl(path, query) {
    const base = path.startsWith('http') ? path : `${this.apiBaseUrl}${path.startsWith('/') ? '' : '/'}${path}`;
    const url = new URL(base);
    if (query && typeof query === 'object') {
      Object.entries(query).forEach(([key, value]) => {
        if (value === undefined || value === null) {
          return;
        }
        if (Array.isArray(value)) {
          value.forEach((entry) => url.searchParams.append(key, entry));
        } else {
          url.searchParams.set(key, String(value));
        }
      });
    }
    return url;
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function calculateRetryDelay(attempt) {
  const exponent = attempt - 1;
  return TOKEN_REFRESH_RETRY_BASE_DELAY_MS * 2 ** exponent;
}

function extractErrorMessage(payload, rawPayload, statusDetails) {
  const description = payload?.error_description || payload?.error;
  if (description) {
    return `Failed to refresh access token (${statusDetails}): ${description}`;
  }

  if (rawPayload) {
    return `Failed to refresh access token (${statusDetails}): ${rawPayload}`;
  }

  return `Failed to refresh access token (${statusDetails})`;
}

function sanitizeSecret(value) {
  if (typeof value !== 'string') {
    return value ?? null;
  }

  const trimmed = value.trim();
  return trimmed.length ? trimmed : null;
}

function loadConfigFromEnv() {
  const {
    AMAZON_CLIENT_ID,
    AMAZON_CLIENT_SECRET,
    AMAZON_REFRESH_TOKEN,
    AMAZON_PROFILE_ID,
    PPC_PROFILE_ID,
    AMAZON_REGION,
    AMAZON_API_BASE_URL,
  } = process.env;

  const profileId = sanitizeSecret(AMAZON_PROFILE_ID) || sanitizeSecret(PPC_PROFILE_ID);
  const missing = [];

  const clientId = sanitizeSecret(AMAZON_CLIENT_ID);
  const clientSecret = sanitizeSecret(AMAZON_CLIENT_SECRET);
  const refreshToken = sanitizeSecret(AMAZON_REFRESH_TOKEN);

  if (!clientId) missing.push('AMAZON_CLIENT_ID');
  if (!clientSecret) missing.push('AMAZON_CLIENT_SECRET');
  if (!refreshToken) missing.push('AMAZON_REFRESH_TOKEN');
  if (!profileId) missing.push('AMAZON_PROFILE_ID or PPC_PROFILE_ID');

  if (missing.length) {
    throw new Error(`Missing required environment configuration: ${missing.join(', ')}`);
  }

  const region = sanitizeSecret(AMAZON_REGION) || 'NA';
  const apiBaseUrl = sanitizeSecret(AMAZON_API_BASE_URL);

  return {
    clientId,
    clientSecret,
    refreshToken,
    profileId,
    region,
    apiBaseUrl,
  };
}

async function syncAmazonData() {
  const config = loadConfigFromEnv();
  const client = new AmazonAdvertisingClient(config);

  const today = new Date();
  const report = await client.requestPerformanceReport({
    profileId: config.profileId,
    startDate: today.toISOString().slice(0, 10),
  });

  console.log(`✅ Sync succeeded: retrieved ${report.length} sponsored products campaigns`);
  return report;
}

if (require.main === module) {
  syncAmazonData().catch((error) => {
    console.error(`❌ Sync failed: ${error.stack || error.message || error}`);
    process.exitCode = 1;
  });
}

module.exports = {
  AmazonAdvertisingClient,
  syncAmazonData,
};
