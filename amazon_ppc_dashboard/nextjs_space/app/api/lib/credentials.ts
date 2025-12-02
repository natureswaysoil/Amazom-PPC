cat > app/api/lib/credentials.ts << 'EOF'
import { GoogleAuth } from 'google-auth-library';

export const SERVICE_ACCOUNT_ENV_NAMES = [
  'GCP_SERVICE_ACCOUNT_KEY',
  'GCP_SA_KEY',
  'GCP_SERVICE_ACCOUNT_KEY_JSON',
];

export const PROJECT_ID_ENV_NAMES = [
  'GOOGLE_CLOUD_PROJECT',
  'GCP_PROJECT',
  'GCP_PROJECT_ID',
  'GCLOUD_PROJECT',
];

export type CredentialResolutionResult = {
  success: boolean;
  credentials?: any;
  projectId?: string;
  source?: string;
  error?: Error;
};

export function getFirstSetEnv(names: string[]): string | undefined {
  for (const name of names) {
    const value = process.env[name];
    if (value && value.trim().length > 0) {
      return value.trim();
    }
  }
  return undefined;
}

function looksLikeBase64(value: string): boolean {
  const cleaned = value.trim();
  if (!cleaned) return false;
  if (cleaned.startsWith('{') || cleaned.startsWith('[')) return false;
  if (!/^[A-Za-z0-9+/=]+$/.test(cleaned)) return false;
  // typical base64 length multiple-of-4
  return cleaned.length >= 16 && cleaned.length % 4 === 0;
}

function parseServiceAccountFromEnv(
  raw: string,
  source: string,
): { credentials: any; projectId?: string } {
  // 1) Try raw JSON
  try {
    const parsed = JSON.parse(raw);
    console.log(`[Credentials] Parsed ${source} as raw JSON`);
    return { credentials: parsed, projectId: parsed.project_id };
  } catch {
    console.log(`[Credentials] ${source} is not valid raw JSON, trying base64`);
  }

  // 2) Try base64 → JSON
  if (looksLikeBase64(raw)) {
    try {
      const decoded = Buffer.from(raw.trim(), 'base64').toString('utf8');
      const parsed = JSON.parse(decoded);
      console.log(`[Credentials] Parsed ${source} as base64-encoded JSON`);
      return { credentials: parsed, projectId: parsed.project_id };
    } catch (err) {
      console.warn(
        `[Credentials] Failed to parse ${source} as base64-encoded JSON:`,
        (err as Error).message,
      );
    }
  } else {
    console.log(
      `[Credentials] Base64 likelihood for ${source} is low; skipping base64 parse`,
    );
  }

  throw new Error(
    `${source} is not valid JSON or base64-encoded JSON. Make sure it is either:\n` +
      '- Raw JSON of your service account, in a single line, or\n' +
      '- Base64 of the JSON file (no extra quotes or prefixes).',
  );
}

/**
 * Resolve GCP credentials for use with @google-cloud/bigquery
 * - Prefers env-based service account (GCP_SERVICE_ACCOUNT_KEY, GCP_SA_KEY, GCP_SERVICE_ACCOUNT_KEY_JSON)
 * - Falls back to Application Default Credentials (ADC)
 */
export async function resolveGCPCredentials(): Promise<CredentialResolutionResult> {
  console.log('[Credentials] Starting credential resolution...');

  const rawKey = getFirstSetEnv(SERVICE_ACCOUNT_ENV_NAMES);

  if (rawKey) {
    const source =
      SERVICE_ACCOUNT_ENV_NAMES.find(
        (n) => process.env[n] && process.env[n]!.trim().length > 0,
      ) ?? 'GCP_SERVICE_ACCOUNT_KEY';

    console.log(`[Credentials] Found credentials in ${source}`);

    try {
      const { credentials, projectId } = parseServiceAccountFromEnv(rawKey, source);
      return {
        success: true,
        credentials,
        projectId,
        source,
      };
    } catch (error) {
      console.warn('[Credentials] Failed to resolve explicit credentials from env');
      console.warn('Credential error:', (error as Error).message);
      return {
        success: false,
        error: error as Error,
      };
    }
  }

  // No explicit service account → use ADC
  try {
    console.log(
      '[Credentials] No explicit service account env found. Falling back to Application Default Credentials (ADC)',
    );

    const auth = new GoogleAuth({
      scopes: ['https://www.googleapis.com/auth/cloud-platform'],
    });

    const client = await auth.getClient(); // eslint-disable-line @typescript-eslint/no-unused-vars
    const projectId = await auth.getProjectId().catch(() => undefined);

    return {
      success: true,
      credentials: undefined,
      projectId,
      source: 'adc',
    };
  } catch (error) {
    console.error('[Credentials] Failed to initialize ADC:', error);
    return {
      success: false,
      error: error as Error,
    };
  }
}
EOF
