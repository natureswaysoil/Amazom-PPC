/**
 * Amazon Sales Data Cloud Function
 * Retrieves sales data from Amazon Selling Partner API (SP-API)
 * 
 * Entry point: amazonSalesData
 */

const https = require('https');
const querystring = require('querystring');
const aws4 = require('aws4');

// SP-API endpoints
const TOKEN_URL = 'https://api.amazon.com/auth/o2/token';
const DEFAULT_SP_API_HOST = 'sellingpartnerapi-na.amazon.com';
const DEFAULT_SP_API_REGION = 'us-east-1';

// Secret Manager client (for production)
let secretManagerClient;
try {
  const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');
  secretManagerClient = new SecretManagerServiceClient();
} catch (err) {
  console.warn('Secret Manager not available, using environment variables');
}

/**
 * Retrieve a secret from Google Secret Manager
 */
async function getSecret(secretName) {
  if (!secretManagerClient) {
    // Fallback to environment variables
    return process.env[secretName];
  }

  try {
    const projectId = process.env.GCP_PROJECT || process.env.GCLOUD_PROJECT;
    const name = `projects/${projectId}/secrets/${secretName}/versions/latest`;
    const [version] = await secretManagerClient.accessSecretVersion({ name });
    return version.payload.data.toString('utf8');
  } catch (err) {
    console.error(`Error retrieving secret ${secretName}:`, err.message);
    // Fallback to environment variables
    return process.env[secretName];
  }
}

/**
 * Get access token from Amazon SP-API using refresh token
 */
async function getAccessToken(clientId, clientSecret, refreshToken) {
  return new Promise((resolve, reject) => {
    const postData = querystring.stringify({
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
      client_id: clientId,
      client_secret: clientSecret,
    });

    const options = {
      hostname: 'api.amazon.com',
      path: '/auth/o2/token',
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(postData),
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.access_token) {
            resolve(parsed.access_token);
          } else {
            reject(new Error(`Token response missing access_token: ${data}`));
          }
        } catch (err) {
          reject(new Error(`Failed to parse token response: ${err.message}`));
        }
      });
    });

    req.on('error', (err) => {
      reject(new Error(`Token request failed: ${err.message}`));
    });

    req.write(postData);
    req.end();
  });
}

/**
 * Make an authenticated request to Amazon SP-API
 */
async function callSpApi(endpoint, accessToken, awsCredentials, spApiConfig) {
  return new Promise((resolve, reject) => {
    const { host, region } = spApiConfig;
    const { accessKeyId, secretAccessKey, sessionToken } = awsCredentials;

    const unsignedRequest = {
      host,
      path: endpoint,
      method: 'GET',
      service: 'execute-api',
      region,
      headers: {
        'x-amz-access-token': accessToken,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    };

    const signedRequest = aws4.sign(unsignedRequest, {
      accessKeyId,
      secretAccessKey,
      sessionToken: sessionToken || undefined,
    });

    const options = {
      hostname: signedRequest.host,
      path: signedRequest.path,
      method: signedRequest.method,
      headers: signedRequest.headers,
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          resolve({ statusCode: res.statusCode, data: parsed });
        } catch (err) {
          // If not JSON, return raw data
          resolve({ statusCode: res.statusCode, data: data });
        }
      });
    });

    req.on('error', (err) => {
      reject(new Error(`SP-API request failed: ${err.message}`));
    });

    req.setTimeout(30000, () => {
      req.destroy(new Error('SP-API request timed out after 30 seconds'));
    });

    req.end();
  });
}

/**
 * Cloud Function entry point
 * 
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 */
exports.amazonSalesData = async (req, res) => {
  // Enable CORS
  res.set('Access-Control-Allow-Origin', '*');
  res.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.set('Access-Control-Allow-Headers', 'Content-Type');

  // Handle preflight OPTIONS request
  if (req.method === 'OPTIONS') {
    return res.status(204).send('');
  }

  console.log('Amazon Sales Data function triggered');
  console.log('Request method:', req.method);
  console.log('Request body:', JSON.stringify(req.body));

  try {
    // Retrieve credentials from Secret Manager or environment
    const clientId = await getSecret('AMAZON_SP_API_CLIENT_ID');
    const clientSecret = await getSecret('AMAZON_SP_API_CLIENT_SECRET');
    const refreshToken = await getSecret('AMAZON_SP_API_REFRESH_TOKEN');
    const marketplaceId = await getSecret('AMAZON_MARKETPLACE_ID') || 'ATVPDKIKX0DER'; // Default to US
    const accessKeyId = await getSecret('AWS_ACCESS_KEY_ID');
    const secretAccessKey = await getSecret('AWS_SECRET_ACCESS_KEY');
    const sessionToken = await getSecret('AWS_SESSION_TOKEN');
    const spApiHost = (await getSecret('SP_API_HOST')) || DEFAULT_SP_API_HOST;
    const spApiRegion = (await getSecret('SP_API_REGION')) ||
      process.env.AWS_REGION ||
      process.env.AWS_DEFAULT_REGION ||
      DEFAULT_SP_API_REGION;

    if (!clientId || !clientSecret || !refreshToken) {
      console.error('Missing required credentials');
      return res.status(500).json({
        error: 'Configuration error',
        message: 'Missing Amazon SP-API credentials',
      });
    }

    if (!accessKeyId || !secretAccessKey) {
      console.error('Missing AWS credentials for SP-API signing');
      return res.status(500).json({
        error: 'Configuration error',
        message: 'Missing AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY for SP-API signing',
      });
    }

    console.log('Credentials loaded successfully');
    console.log('Marketplace ID:', marketplaceId);
    console.log('SP-API host:', spApiHost);
    console.log('SP-API region:', spApiRegion);

    // Get access token
    console.log('Requesting access token...');
    const accessToken = await getAccessToken(clientId, clientSecret, refreshToken);
    console.log('Access token obtained');

    // Parse request parameters
    const { startDate, endDate, reportType } = req.method === 'POST' ? req.body : req.query;

    // Default to last 30 days if not specified
    const end = endDate ? new Date(endDate) : new Date();
    const start = startDate ? new Date(startDate) : new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);

    console.log('Date range:', start.toISOString(), 'to', end.toISOString());

    // Example: Get orders
    // In production, you would use the appropriate SP-API endpoint based on reportType
    const ordersEndpoint = `/orders/v0/orders?MarketplaceIds=${marketplaceId}&CreatedAfter=${start.toISOString()}`;
    
    console.log('Calling SP-API:', ordersEndpoint);
    const result = await callSpApi(
      ordersEndpoint,
      accessToken,
      { accessKeyId, secretAccessKey, sessionToken },
      { host: spApiHost, region: spApiRegion }
    );

    console.log('SP-API response status:', result.statusCode);

    if (result.statusCode >= 200 && result.statusCode < 300) {
      return res.status(200).json({
        success: true,
        data: result.data,
        metadata: {
          startDate: start.toISOString(),
          endDate: end.toISOString(),
          marketplaceId,
        },
      });
    } else {
      console.error('SP-API error:', JSON.stringify(result.data));
      return res.status(result.statusCode).json({
        success: false,
        error: 'SP-API request failed',
        details: result.data,
      });
    }
  } catch (err) {
    console.error('Error in amazonSalesData:', err);
    return res.status(500).json({
      success: false,
      error: 'Internal server error',
      message: err.message,
      stack: process.env.NODE_ENV === 'development' ? err.stack : undefined,
    });
  }
};
