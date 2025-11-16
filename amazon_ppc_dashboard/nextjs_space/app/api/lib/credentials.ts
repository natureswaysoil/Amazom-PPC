/**
 * Shared utilities for parsing and validating GCP service account credentials
 * across dashboard API routes.
 */

import { Buffer } from 'buffer';

export interface CredentialParseResult {
  success: boolean;
  credentials?: any;
  projectId?: string;
  error?: {
    type: 'missing' | 'invalid_json' | 'invalid_base64' | 'invalid_structure' | 'missing_fields';
    message: string;
    details: string;
    troubleshooting: string[];
  };
  source?: string;
}

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

export const PROJECT_ID_ENV_NAMES = [
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

export function getFirstSetEnv(names: string[]): string | undefined {
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

function buildCredentialsFromEnvironmentParts(): any | undefined {
  const clientEmail = getFirstSetEnv(SERVICE_ACCOUNT_EMAIL_ENV_NAMES);
  const privateKey = normalisePrivateKey(getFirstSetEnv(SERVICE_ACCOUNT_KEY_ENV_NAMES));
  const projectId = getFirstSetEnv(PROJECT_ID_ENV_NAMES);

  if (clientEmail && privateKey) {
    const credentials: any = {
      client_email: clientEmail,
      private_key: privateKey,
      type: 'service_account',
    };

    if (projectId) {
      credentials.project_id = projectId;
    }

    return credentials;
  }

  return undefined;
}

/**
 * Smart detection to identify if a string might be base64 encoded.
 * Returns a confidence score from 0 to 1.
 */
function detectBase64Likelihood(value: string): number {
  // Remove whitespace for analysis
  const cleaned = value.trim().replace(/\s+/g, '');
  
  // Check if it starts with { or [ (likely raw JSON)
  if (cleaned.startsWith('{') || cleaned.startsWith('[')) {
    return 0.0;
  }
  
  // Check character composition
  const base64Pattern = /^[A-Za-z0-9+/]+=*$/;
  if (!base64Pattern.test(cleaned)) {
    return 0.0;
  }
  
  // Base64 strings are typically much longer and have specific length characteristics
  if (cleaned.length < 100) {
    return 0.3; // Might be base64 but suspicious
  }
  
  // Check for typical base64 padding
  const paddingMatch = cleaned.match(/=*$/);
  const padding = paddingMatch ? paddingMatch[0].length : 0;
  if (padding > 2) {
    return 0.2; // Invalid base64 padding
  }
  
  // Strong indicator: Length is a multiple of 4 (or close to it)
  const remainder = cleaned.length % 4;
  if (remainder === 0) {
    return 0.9;
  } else if (remainder <= 2) {
    return 0.7;
  }
  
  return 0.5;
}

/**
 * Parse service account credentials from a string value with smart format detection.
 * Handles raw JSON, base64-encoded JSON, URL-encoded JSON, and malformed variants.
 */
function parseServiceAccountValue(value: string | undefined, source: string): CredentialParseResult {
  if (!value || !value.trim()) {
    return {
      success: false,
      error: {
        type: 'missing',
        message: `${source} is not set or is empty`,
        details: `The environment variable ${source} must be set to your service account credentials.`,
        troubleshooting: [
          `Set ${source} to the contents of your service account key JSON file (raw JSON)`,
          `Or, set ${source} to base64-encoded JSON: run 'cat service-account.json | base64'`,
          'After setting the variable, redeploy the application',
        ],
      },
    };
  }

  // Clean up common issues: extra whitespace, newlines within the value
  let cleanedValue = value.trim();
  
  // Remove line breaks that might have been added during copy/paste
  if (cleanedValue.includes('\n') && !cleanedValue.startsWith('{')) {
    cleanedValue = cleanedValue.replace(/\n/g, '');
    console.log(`[Credentials] Removed embedded newlines from ${source}`);
  }
  
  // Try URL decoding if it looks URL encoded
  if (cleanedValue.includes('%22') || cleanedValue.includes('%7B') || cleanedValue.includes('%7D')) {
    try {
      const urlDecoded = decodeURIComponent(cleanedValue);
      console.log(`[Credentials] ${source} appears to be URL-encoded, attempting to decode...`);
      cleanedValue = urlDecoded;
    } catch (urlErr) {
      console.log(`[Credentials] URL decode failed, continuing with original value`);
    }
  }

  // Try parsing as raw JSON first
  try {
    console.log(`[Credentials] Attempting to parse ${source} as raw JSON...`);
    const parsed = JSON.parse(cleanedValue);
    console.log(`[Credentials] ✓ Successfully parsed ${source} as raw JSON`);
    return {
      success: true,
      credentials: parsed,
      projectId: parsed.project_id,
      source: `${source} (raw JSON)`,
    };
  } catch (jsonError: any) {
    console.log(`[Credentials] ${source} is not valid raw JSON: ${jsonError.message}`);
  }

  // Smart detection: Should we try base64 decoding?
  const base64Confidence = detectBase64Likelihood(cleanedValue);
  console.log(`[Credentials] Base64 likelihood for ${source}: ${(base64Confidence * 100).toFixed(0)}%`);

  if (base64Confidence > 0.3) {
    // Try decoding as base64
    console.log(`[Credentials] Attempting to decode ${source} as base64...`);
    try {
      const decoded = Buffer.from(cleanedValue, 'base64').toString('utf8');
      console.log(`[Credentials] Successfully decoded ${source} from base64`);
      console.log(`[Credentials] Decoded length: ${decoded.length} characters`);
      console.log(`[Credentials] Decoded preview (first 100 chars): ${decoded.substring(0, 100)}`);
      
      try {
        const parsed = JSON.parse(decoded);
        console.log(`[Credentials] ✓ Successfully parsed decoded ${source} as JSON`);
        return {
          success: true,
          credentials: parsed,
          projectId: parsed.project_id,
          source: `${source} (base64-encoded JSON)`,
        };
      } catch (decodedJsonError: any) {
        console.error(`[Credentials] Decoded ${source} is not valid JSON: ${decodedJsonError.message}`);
        console.error(`[Credentials] Decoded content (first 500 chars): ${decoded.substring(0, 500)}`);
        
        // Check if the decoded content looks like it might be double-encoded or has other issues
        let additionalGuidance: string[] = [];
        if (decoded.startsWith('data:') || decoded.includes('base64,')) {
          additionalGuidance.push('The decoded content appears to contain a data URL. Use only the service account JSON, not a data URL.');
        } else if (decoded.includes('\\n') && !decoded.includes('\n')) {
          additionalGuidance.push('The decoded content contains escaped newlines (\\n). These should be actual newlines in the JSON.');
        } else if (decoded.trim().length === 0) {
          additionalGuidance.push('The decoded content is empty. The base64 string may be invalid or incomplete.');
        }
        
        return {
          success: false,
          error: {
            type: 'invalid_json',
            message: `${source} was successfully base64 decoded but does not contain valid JSON`,
            details: `The base64-decoded content could not be parsed as JSON. JSON error: ${decodedJsonError.message}. Decoded length: ${decoded.length} characters.`,
            troubleshooting: [
              'Ensure you are encoding valid JSON content when creating the base64 value',
              `Example: 'cat service-account.json | base64 | tr -d "\\n"' should produce valid base64 encoding`,
              `Verify your service-account.json file is valid JSON before encoding: 'cat service-account.json | jq .'`,
              `Test the encoding/decoding locally: 'echo "$GCP_SERVICE_ACCOUNT_KEY" | base64 -d | jq .'`,
              ...additionalGuidance,
              `After correcting the value, redeploy the application`,
            ],
          },
        };
      }
    } catch (base64Error: any) {
      console.error(`[Credentials] ${source} base64 decode failed: ${base64Error.message}`);
      // Don't return error yet, we'll try other formats
    }
  }

  // If we get here, neither raw JSON nor base64 worked
  // Provide helpful error message based on what we detected
  let errorType: 'invalid_base64' | 'invalid_json' = 'invalid_base64';
  let details = `Could not parse ${source} as JSON or base64-encoded JSON.`;
  let troubleshooting = [
    `Option 1 (Raw JSON - Recommended): Set ${source} to the entire contents of your service account key file`,
    `Option 2 (Base64): Run 'cat service-account.json | base64 | tr -d "\\n"' and set ${source} to the output`,
    `Ensure there are no extra spaces, line breaks, or special characters in the environment variable`,
    `Verify the JSON is valid before encoding: 'cat service-account.json | jq .'`,
    `After correcting the value, redeploy the application`,
  ];

  if (cleanedValue.startsWith('{') || cleanedValue.startsWith('[')) {
    errorType = 'invalid_json';
    details = `${source} appears to be JSON but contains syntax errors.`;
    troubleshooting = [
      'The value looks like JSON but has syntax errors',
      'Ensure the entire JSON is copied, including opening { and closing }',
      'Check for missing commas, quotes, or brackets',
      `Validate your JSON: 'cat service-account.json | jq .'`,
      'Ensure no characters were corrupted during copy/paste',
      'After correcting the value, redeploy the application',
    ];
  }

  return {
    success: false,
    error: {
      type: errorType,
      message: `${source} is not valid JSON or base64 encoded JSON`,
      details,
      troubleshooting,
    },
  };
}

/**
 * Validate service account credential structure.
 */
function validateServiceAccountStructure(credentials: any, source: string): CredentialParseResult {
  if (!credentials || typeof credentials !== 'object') {
    return {
      success: false,
      error: {
        type: 'invalid_structure',
        message: `${source} does not contain a valid object`,
        details: 'The parsed JSON is not an object structure',
        troubleshooting: [
          'Ensure you are using the service account key JSON file from Google Cloud Console',
          'The file should be a JSON object with fields like type, project_id, private_key, etc.',
          'Download a fresh service account key from Google Cloud Console if needed',
        ],
      },
    };
  }

  // Check for service account type
  if (credentials.type !== 'service_account') {
    return {
      success: false,
      error: {
        type: 'invalid_structure',
        message: `${source} does not contain a service account credential`,
        details: `Expected "type": "service_account" but got "type": "${credentials.type || 'missing'}"`,
        troubleshooting: [
          'Ensure you are using a service account key JSON (not other credential types)',
          'Download the key from: Google Cloud Console > IAM & Admin > Service Accounts > Keys',
          'Create a new key if needed (JSON format)',
        ],
      },
    };
  }

  // Check for required fields
  const requiredFields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email'];
  const missingFields = requiredFields.filter((field) => !(field in credentials));

  if (missingFields.length > 0) {
    return {
      success: false,
      error: {
        type: 'missing_fields',
        message: `${source} is missing required service account fields`,
        details: `Missing fields: ${missingFields.join(', ')}`,
        troubleshooting: [
          'Ensure you are using the complete service account key JSON file',
          'The file should contain: type, project_id, private_key_id, private_key, client_email',
          'Download a fresh service account key from Google Cloud Console if the file is incomplete',
        ],
      },
    };
  }

  console.log(`[Credentials] Successfully validated service account structure from ${source}`);
  return {
    success: true,
    credentials,
    projectId: credentials.project_id,
    source,
  };
}

/**
 * Resolve GCP service account credentials from environment variables.
 * Returns parsed credentials, project ID, and detailed error information if parsing fails.
 */
export function resolveGCPCredentials(): CredentialParseResult {
  console.log('[Credentials] Starting credential resolution...');

  // Try to get credentials from JSON environment variable
  const serviceAccountKeyResult = getFirstSetEnvWithName(SERVICE_ACCOUNT_JSON_ENV_NAMES);
  if (serviceAccountKeyResult) {
    console.log(`[Credentials] Found credentials in ${serviceAccountKeyResult.name}`);
    const parseResult = parseServiceAccountValue(serviceAccountKeyResult.value, serviceAccountKeyResult.name);
    
    if (parseResult.success && parseResult.credentials) {
      const validationResult = validateServiceAccountStructure(parseResult.credentials, parseResult.source!);
      if (validationResult.success) {
        return validationResult;
      }
      return validationResult;
    }
    
    // If parsing failed, return the error
    return parseResult;
  }

  // Try GOOGLE_APPLICATION_CREDENTIALS
  const googleCredentialsResult = getFirstSetEnvWithName(['GOOGLE_APPLICATION_CREDENTIALS']);
  if (googleCredentialsResult) {
    console.log(`[Credentials] Found credentials in ${googleCredentialsResult.name}`);
    const parseResult = parseServiceAccountValue(googleCredentialsResult.value, googleCredentialsResult.name);
    
    if (parseResult.success && parseResult.credentials) {
      const validationResult = validateServiceAccountStructure(parseResult.credentials, parseResult.source!);
      if (validationResult.success) {
        return validationResult;
      }
      return validationResult;
    }
    
    // If parsing failed, continue to try building from parts
    console.log('[Credentials] Failed to parse GOOGLE_APPLICATION_CREDENTIALS, trying credential parts...');
  }

  // Try building from individual environment variable parts
  console.log('[Credentials] Attempting to build credentials from individual environment variables...');
  const credentialsFromParts = buildCredentialsFromEnvironmentParts();
  if (credentialsFromParts) {
    console.log('[Credentials] Successfully built credentials from individual environment variables');
    const validationResult = validateServiceAccountStructure(credentialsFromParts, 'credential parts (GCP_CLIENT_EMAIL + GCP_PRIVATE_KEY)');
    if (validationResult.success) {
      return validationResult;
    }
    return validationResult;
  }

  // No credentials found
  console.error('[Credentials] No service account credentials found in environment variables');
  return {
    success: false,
    error: {
      type: 'missing',
      message: 'No Google Cloud service account credentials configured',
      details: 'No supported credential environment variables found',
      troubleshooting: [
        'Option 1: Set GCP_SERVICE_ACCOUNT_KEY with your service account JSON (raw or base64 encoded)',
        'Option 2: Set GOOGLE_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS with your service account JSON',
        'Option 3: Set individual variables: GCP_CLIENT_EMAIL + GCP_PRIVATE_KEY (with \\n for newlines)',
        'After setting credentials, redeploy the application',
        'Verify configuration at: /api/config-check',
      ],
    },
  };
}
