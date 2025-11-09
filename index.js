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

    const missing = [];
    if (!clientId) missing.push('clientId');
    if (!clientSecret) missing.push('clientSecret');
    if (!refreshToken) missing.push('refreshToken');
    if (missing.length) {
      throw new Error(`Missing required Amazon Advertising credentials: ${missing.join(', ')}`);
    }

    this.clientId = clientId;
    this.clientSecret = clientSecret;
    this.refreshToken = refreshToken;
    this.profileId = profileId || null;
    this.region = region.toUpperCase();
    this.apiBaseUrl = apiBaseUrl || API_HOSTS[this.region] || API_HOSTS.NA;

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
        },
        body,
      });
    } catch (error) {
      throw new Error(`Failed to refresh access token: ${error.message}`);
    }

    let rawPayload = '';
    let payload;
    try {
      rawPayload = await response.text();
      payload = rawPayload ? JSON.parse(rawPayload) : {};
    } catch (error) {
      throw new Error(`Failed to refresh access token: unable to parse response JSON (${error.message})`);
    }

    if (!response.ok) {
      const details = payload?.error_description || payload?.error || rawPayload || response.statusText;
      throw new Error(`Failed to refresh access token: ${details}`);
    }

    if (!payload.access_token) {
      throw new Error('Failed to refresh access token: response missing access_token');
    }

    const expiresIn = Number(payload.expires_in || 3600);
    this.accessToken = payload.access_token;
    this.tokenExpiresAt = Date.now() + expiresIn * 1000;

    if (payload.refresh_token && payload.refresh_token !== this.refreshToken) {
      // Amazon may rotate refresh tokens; warn so operators can persist the new value.
      console.warn('Received rotated Amazon Ads refresh token. Update Secret Manager to persist the new token.');
      this.refreshToken = payload.refresh_token;
    }

    return this.accessToken;
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

    const url = this._buildUrl(path, query);

    const attempt = async (forceRefresh = false) => {
      const token = await this.getAccessToken({ forceRefresh });
      const requestHeaders = {
        'Authorization': `Bearer ${token}`,
        'Amazon-Advertising-API-ClientId': this.clientId,
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
      query.startIndex = 0;
      query.count = 1000;
    }

    const response = await this.makeRequest('/v2/sp/campaigns', {
      method: 'GET',
      query,
      profileId: scope,
    });

    return Array.isArray(response) ? response : [];
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

  const profileId = AMAZON_PROFILE_ID || PPC_PROFILE_ID;
  const missing = [];

  if (!AMAZON_CLIENT_ID) missing.push('AMAZON_CLIENT_ID');
  if (!AMAZON_CLIENT_SECRET) missing.push('AMAZON_CLIENT_SECRET');
  if (!AMAZON_REFRESH_TOKEN) missing.push('AMAZON_REFRESH_TOKEN');
  if (!profileId) missing.push('AMAZON_PROFILE_ID or PPC_PROFILE_ID');

  if (missing.length) {
    throw new Error(`Missing required environment configuration: ${missing.join(', ')}`);
  }

  return {
    clientId: AMAZON_CLIENT_ID,
    clientSecret: AMAZON_CLIENT_SECRET,
    refreshToken: AMAZON_REFRESH_TOKEN,
    profileId,
    region: AMAZON_REGION || 'NA',
    apiBaseUrl: AMAZON_API_BASE_URL,
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
