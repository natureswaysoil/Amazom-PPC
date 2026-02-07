import { GoogleAuth } from 'google-auth-library';
import { getFirstSetEnv, PROJECT_ID_ENV_NAMES } from './credentials';

type ApiKeyResolution = {
  apiKey: string | null;
  source: 'env' | 'secret-manager' | 'unset';
};

let cached: ApiKeyResolution | null = null;

function normalizeSecretResource(resourceOrName: string): string {
  const trimmed = resourceOrName.trim();
  if (!trimmed) return '';
  // Accept full resource name: projects/<p>/secrets/<s>/versions/<v>
  if (trimmed.startsWith('projects/')) return trimmed;
  return trimmed;
}

async function getProjectIdViaADC(): Promise<string | null> {
  try {
    const auth = new GoogleAuth({
      scopes: ['https://www.googleapis.com/auth/cloud-platform'],
    });
    const projectId = await auth.getProjectId().catch(() => undefined);
    return projectId?.trim() ? projectId.trim() : null;
  } catch {
    return null;
  }
}

async function accessSecretVersion(resourceName: string): Promise<string> {
  const auth = new GoogleAuth({
    scopes: ['https://www.googleapis.com/auth/cloud-platform'],
  });

  const client: any = await auth.getClient();
  const url = `https://secretmanager.googleapis.com/v1/${resourceName}:access`;
  const resp = await client.request({ url, method: 'GET' });

  const b64 = resp?.data?.payload?.data;
  if (!b64 || typeof b64 !== 'string') {
    throw new Error('Secret Manager response missing payload.data');
  }

  const value = Buffer.from(b64, 'base64').toString('utf8');
  return value;
}

/**
 * Resolves the dashboard API key.
 * Priority:
 * 1) DASHBOARD_API_KEY env var
 * 2) Secret Manager via ADC using:
 *    - DASHBOARD_API_SECRET_RESOURCE (full resource name) OR
 *    - DASHBOARD_API_SECRET_NAME (+ optional DASHBOARD_API_SECRET_VERSION)
 */
export async function resolveDashboardApiKey(options?: {
  required?: boolean;
  forceRefresh?: boolean;
}): Promise<ApiKeyResolution> {
  if (!options?.forceRefresh && cached) return cached;

  const fromEnv = (process.env.DASHBOARD_API_KEY || '').trim();
  if (fromEnv) {
    cached = { apiKey: fromEnv, source: 'env' };
    return cached;
  }

  const secretResource = normalizeSecretResource(
    process.env.DASHBOARD_API_SECRET_RESOURCE || '',
  );
  const secretName = (process.env.DASHBOARD_API_SECRET_NAME || '').trim();
  const secretVersion = (process.env.DASHBOARD_API_SECRET_VERSION || 'latest').trim();

  const hasSecretConfig = !!(secretResource || secretName);
  if (hasSecretConfig) {
    let resourceName = secretResource;

    if (!resourceName) {
      const projectId =
        getFirstSetEnv(PROJECT_ID_ENV_NAMES) || (await getProjectIdViaADC());
      if (!projectId) {
        throw new Error(
          'Cannot resolve project ID for Secret Manager. Set GOOGLE_CLOUD_PROJECT (or GCP_PROJECT) or provide DASHBOARD_API_SECRET_RESOURCE.',
        );
      }

      resourceName = `projects/${projectId}/secrets/${secretName}/versions/${secretVersion}`;
    }

    const value = (await accessSecretVersion(resourceName)).trim();
    if (!value) {
      throw new Error(`Secret Manager returned empty value for ${resourceName}`);
    }

    cached = { apiKey: value, source: 'secret-manager' };
    return cached;
  }

  cached = { apiKey: null, source: 'unset' };
  if (options?.required) {
    throw new Error(
      'DASHBOARD_API_KEY is not configured. Set DASHBOARD_API_KEY or configure Secret Manager via DASHBOARD_API_SECRET_NAME / DASHBOARD_API_SECRET_RESOURCE.',
    );
  }

  return cached;
}
