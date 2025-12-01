cd /workspaces/Amazom-PPC/amazon_ppc_dashboard/nextjs_space

cat > app/api/lib/credentials.ts << 'EOF'
import { GoogleAuth, GoogleAuthOptions } from 'google-auth-library';

export const PROJECT_ID_ENV_NAMES = [
  'GCP_PROJECT',
  'GOOGLE_CLOUD_PROJECT',
  'GCP_PROJECT_ID',
];

export function getFirstSetEnv(names: string[]): string | undefined {
  for (const name of names) {
    const value = process.env[name];
    if (value && value.trim() !== '') {
      return value.trim();
    }
  }
  return undefined;
}

/**
 * Try to parse a service account JSON from an env var that may be:
 * - raw JSON
 * - base64-encoded JSON
 */
function parseServiceAccountEnv(raw: string): any {
  const trimmed = raw.trim();

  // Try raw JSON first
  try {
    return JSON.parse(trimmed);
  } catch {
    // fall through
  }

  // Try base64 → JSON
  try {
    const decoded = Buffer.from(trimmed, 'base64').toString('utf8');
    return JSON.parse(decoded);
  } catch {
    // If both fail, rethrow a helpful error
    throw new Error(
      'GCP_SERVICE_ACCOUNT_KEY is set but is not valid JSON or base64-encoded JSON.'
    );
  }
}

/**
 * Resolve Google Cloud credentials for server-side use (Node only).
 * This is used by the dashboard API routes to talk to BigQuery.
 */
export async function resolveGCPCredentials(): Promise<
  | { success: true; auth: GoogleAuth; projectId?: string }
  | { success: false; error: Error }
> {
  try {
    const envProject = getFirstSetEnv(PROJECT_ID_ENV_NAMES);
    const saJson =
      process.env.GCP_SERVICE_ACCOUNT_KEY || process.env.GCP_SA_KEY || null;

    let options: GoogleAuthOptions = {
      scopes: ['https://www.googleapis.com/auth/cloud-platform'],
    };

    if (saJson) {
      const creds = parseServiceAccountEnv(saJson);
      options = {
        ...options,
        credentials: creds,
        projectId: creds.project_id || envProject,
      };
    } else if (envProject) {
      options = {
        ...options,
        projectId: envProject,
      };
    }

    const auth = new GoogleAuth(options);
    const projectId = (await auth.getProjectId().catch(() => envProject)) || envProject;

    return {
      success: true as const,
      auth,
      projectId,
    };
  } catch (err: any) {
    return {
      success: false as const,
      error: err instanceof Error ? err : new Error(String(err)),
    };
  }
}
EOF
