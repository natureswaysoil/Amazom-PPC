/**
 * Amazon Sales & Accounting Data Cloud Function
 * Retrieves order and settlement data from Amazon Selling Partner API (SP-API).
 *
 * Credentials are loaded from Google Secret Manager:
 * - AMAZON_SP_API_CLIENT_ID
 * - AMAZON_SP_API_CLIENT_SECRET
 * - AMAZON_SP_API_REFRESH_TOKEN
 * - AMAZON_MARKETPLACE_ID (optional; defaults to US)
 * - SP_API_HOST (optional)
 *
 * Entry point: amazonSalesData
 */

const https = require('https');
const querystring = require('querystring');
const zlib = require('zlib');

const DEFAULT_SP_API_HOST = 'sellingpartnerapi-na.amazon.com';
const DEFAULT_MARKETPLACE_ID = 'ATVPDKIKX0DER';
const SETTLEMENT_REPORT_TYPE = 'GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2';
const USER_AGENT = 'NaturesWaySoilAccounting/2.0 (Language=Node.js/20)';

let secretManagerClient;
try {
  const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');
  secretManagerClient = new SecretManagerServiceClient();
} catch (err) {
  console.warn('Secret Manager not available, using environment variables');
}

async function getSecret(secretName) {
  if (!secretManagerClient) return process.env[secretName];

  try {
    const projectId = process.env.GCP_PROJECT || process.env.GCLOUD_PROJECT;
    const name = `projects/${projectId}/secrets/${secretName}/versions/latest`;
    const [version] = await secretManagerClient.accessSecretVersion({ name });
    return version.payload.data.toString('utf8').trim();
  } catch (err) {
    console.warn(`Secret ${secretName} unavailable from Secret Manager; checking env var`);
    return process.env[secretName];
  }
}

async function getAccessToken(clientId, clientSecret, refreshToken) {
  return new Promise((resolve, reject) => {
    const postData = querystring.stringify({
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
      client_id: clientId,
      client_secret: clientSecret,
    });

    const req = https.request({
      hostname: 'api.amazon.com',
      path: '/auth/o2/token',
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'Content-Length': Buffer.byteLength(postData),
      },
    }, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.access_token) return resolve(parsed.access_token);
          reject(new Error(`LWA token response missing access_token: ${data}`));
        } catch (err) {
          reject(new Error(`Failed to parse LWA token response: ${err.message}`));
        }
      });
    });

    req.on('error', err => reject(new Error(`LWA token request failed: ${err.message}`)));
    req.setTimeout(30000, () => req.destroy(new Error('LWA token request timed out')));
    req.write(postData);
    req.end();
  });
}

function amazonDate() {
  return new Date().toISOString().replace(/[:-]|\.\d{3}/g, '');
}

async function callSpApi({ host, endpoint, accessToken, method = 'GET', body }) {
  return new Promise((resolve, reject) => {
    const payload = body === undefined ? null : JSON.stringify(body);
    const headers = {
      'x-amz-access-token': accessToken,
      'x-amz-date': amazonDate(),
      'user-agent': USER_AGENT,
      'accept': 'application/json',
    };

    if (payload !== null) {
      headers['content-type'] = 'application/json';
      headers['content-length'] = Buffer.byteLength(payload);
    }

    const req = https.request({
      hostname: host,
      path: endpoint,
      method,
      headers,
    }, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        let parsed = data;
        try { parsed = data ? JSON.parse(data) : {}; } catch (_) {}
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          data: parsed,
        });
      });
    });

    req.on('error', err => reject(new Error(`SP-API request failed: ${err.message}`)));
    req.setTimeout(60000, () => req.destroy(new Error('SP-API request timed out')));
    if (payload !== null) req.write(payload);
    req.end();
  });
}

async function downloadUrl(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          return reject(new Error(`Report document download failed with HTTP ${res.statusCode}`));
        }
        resolve({
          buffer: Buffer.concat(chunks),
          contentType: res.headers['content-type'] || '',
        });
      });
    }).on('error', reject);
  });
}

function parseFlatFile(text) {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean);
  if (!lines.length) return { headers: [], rows: [] };
  const headers = lines[0].split('\t');
  const rows = lines.slice(1).map(line => {
    const cells = line.split('\t');
    const row = {};
    headers.forEach((header, i) => { row[header] = cells[i] ?? ''; });
    return row;
  });
  return { headers, rows };
}

function accountingSummary(rows) {
  const summary = {
    rowCount: rows.length,
    currency: {},
    byTransactionType: {},
    byAmountDescription: {},
  };

  for (const row of rows) {
    const transactionType = row['transaction-type'] || row['transaction_type'] || row['Transaction Type'] || 'UNKNOWN';
    const amountDescription = row['amount-description'] || row['amount_description'] || row['Amount Description'] || 'UNKNOWN';
    const currency = row['currency'] || row['currency-code'] || row['currency_code'] || row['Currency'] || 'UNKNOWN';
    const rawAmount = row['amount'] || row['Amount'] || row['total-amount'] || row['total_amount'] || '0';
    const amount = Number(String(rawAmount).replace(/,/g, '')) || 0;

    summary.byTransactionType[transactionType] = (summary.byTransactionType[transactionType] || 0) + amount;
    summary.byAmountDescription[amountDescription] = (summary.byAmountDescription[amountDescription] || 0) + amount;
    summary.currency[currency] = (summary.currency[currency] || 0) + amount;
  }

  return summary;
}

async function getSettlementReports({ host, accessToken, marketplaceId, start, end, maxReports = 100 }) {
  const params = new URLSearchParams();
  params.append('reportTypes', SETTLEMENT_REPORT_TYPE);
  params.set('marketplaceIds', marketplaceId);
  params.set('createdSince', start.toISOString());
  params.set('createdUntil', end.toISOString());
  params.set('pageSize', String(Math.min(Math.max(maxReports, 1), 100)));

  const endpoint = `/reports/2021-06-30/reports?${params.toString()}`;
  const response = await callSpApi({ host, endpoint, accessToken });

  if (response.statusCode < 200 || response.statusCode >= 300) {
    const err = new Error(`getReports failed with HTTP ${response.statusCode}`);
    err.details = response.data;
    throw err;
  }

  return response.data.reports || [];
}

async function getReportDocument({ host, accessToken, reportDocumentId }) {
  const endpoint = `/reports/2021-06-30/documents/${encodeURIComponent(reportDocumentId)}`;
  const response = await callSpApi({ host, endpoint, accessToken });

  if (response.statusCode < 200 || response.statusCode >= 300) {
    const err = new Error(`getReportDocument failed with HTTP ${response.statusCode}`);
    err.details = response.data;
    throw err;
  }

  const doc = response.data;
  const downloaded = await downloadUrl(doc.url);
  let buffer = downloaded.buffer;

  if (doc.compressionAlgorithm === 'GZIP') {
    buffer = zlib.gunzipSync(buffer);
  }

  const text = buffer.toString('utf8');
  return {
    reportDocumentId,
    compressionAlgorithm: doc.compressionAlgorithm || null,
    text,
    parsed: parseFlatFile(text),
  };
}

exports.amazonSalesData = async (req, res) => {
  res.set('Access-Control-Allow-Origin', '*');
  res.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.set('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(204).send('');

  try {
    const clientId = await getSecret('AMAZON_SP_API_CLIENT_ID');
    const clientSecret = await getSecret('AMAZON_SP_API_CLIENT_SECRET');
    const refreshToken = await getSecret('AMAZON_SP_API_REFRESH_TOKEN');
    const marketplaceId = (await getSecret('AMAZON_MARKETPLACE_ID')) || DEFAULT_MARKETPLACE_ID;
    const host = (await getSecret('SP_API_HOST')) || DEFAULT_SP_API_HOST;

    if (!clientId || !clientSecret || !refreshToken) {
      const diagnosticStatus = req.body?.debugResponse200 ? 200 : 500;
      return res.status(diagnosticStatus).json({
        success: false,
        error: 'Configuration error',
        message: 'Missing Amazon SP-API LWA credentials',
      });
    }

    const accessToken = await getAccessToken(clientId, clientSecret, refreshToken);
    const input = req.method === 'POST' ? (req.body || {}) : (req.query || {});
    const action = String(input.action || input.reportType || 'orders').toLowerCase();

    const end = input.endDate ? new Date(input.endDate) : new Date();
    const start = input.startDate
      ? new Date(input.startDate)
      : new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);

    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return res.status(400).json({ success: false, error: 'Invalid date range' });
    }

    if (action === 'health') {
      return res.status(200).json({
        success: true,
        service: 'amazonSalesData',
        marketplaceId,
        host,
        auth: 'LWA',
        settlementReportType: SETTLEMENT_REPORT_TYPE,
      });
    }

    if (action === 'settlements' || action === 'settlement_reports' || action === 'accounting') {
      const reports = await getSettlementReports({
        host,
        accessToken,
        marketplaceId,
        start,
        end,
        maxReports: Number(input.maxReports || 100),
      });

      const completed = reports.filter(r => r.processingStatus === 'DONE' && r.reportDocumentId);
      const includeRows = String(input.includeRows || 'true').toLowerCase() !== 'false';
      const maxDocuments = Math.min(Math.max(Number(input.maxDocuments || 25), 1), 50);
      const documents = [];

      if (includeRows) {
        for (const report of completed.slice(0, maxDocuments)) {
          const document = await getReportDocument({
            host,
            accessToken,
            reportDocumentId: report.reportDocumentId,
          });

          documents.push({
            reportId: report.reportId,
            reportDocumentId: report.reportDocumentId,
            dataStartTime: report.dataStartTime,
            dataEndTime: report.dataEndTime,
            createdTime: report.createdTime,
            headers: document.parsed.headers,
            rows: document.parsed.rows,
            accountingSummary: accountingSummary(document.parsed.rows),
          });
        }
      }

      return res.status(200).json({
        success: true,
        action: 'settlements',
        metadata: {
          startDate: start.toISOString(),
          endDate: end.toISOString(),
          marketplaceId,
          reportType: SETTLEMENT_REPORT_TYPE,
          reportsFound: reports.length,
          completedReports: completed.length,
          documentsReturned: documents.length,
        },
        reports,
        documents,
      });
    }

    if (action === 'report_document') {
      if (!input.reportDocumentId) {
        return res.status(400).json({ success: false, error: 'reportDocumentId is required' });
      }
      const document = await getReportDocument({
        host,
        accessToken,
        reportDocumentId: input.reportDocumentId,
      });
      return res.status(200).json({
        success: true,
        reportDocumentId: input.reportDocumentId,
        headers: document.parsed.headers,
        rows: document.parsed.rows,
        accountingSummary: accountingSummary(document.parsed.rows),
      });
    }

    const ordersEndpoint = `/orders/v0/orders?MarketplaceIds=${encodeURIComponent(marketplaceId)}&CreatedAfter=${encodeURIComponent(start.toISOString())}`;
    const result = await callSpApi({ host, endpoint: ordersEndpoint, accessToken });

    if (result.statusCode >= 200 && result.statusCode < 300) {
      return res.status(200).json({
        success: true,
        action: 'orders',
        data: result.data,
        metadata: {
          startDate: start.toISOString(),
          endDate: end.toISOString(),
          marketplaceId,
        },
      });
    }

    return res.status(result.statusCode).json({
      success: false,
      error: 'SP-API request failed',
      details: result.data,
    });
  } catch (err) {
    console.error('Error in amazonSalesData:', err);
    const diagnosticStatus = req.body?.debugResponse200 ? 200 : 500;
    return res.status(diagnosticStatus).json({
      success: false,
      error: 'Internal server error',
      message: err.message,
      details: err.details,
    });
  }
};
