import { NextRequest, NextResponse } from 'next/server';

/**
 * Configuration check endpoint
 * Helps diagnose BigQuery and dashboard configuration issues
 * Returns non-sensitive information about what's configured
 */
export async function GET(request: NextRequest) {
  // Default project ID from config.json (same as bigquery-data route)
  const DEFAULT_PROJECT_ID = 'amazon-ppc-474902';
  
  const checks = {
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'unknown',
    configuration: {
      gcp_project: {
        set: !!(process.env.GCP_PROJECT || process.env.GOOGLE_CLOUD_PROJECT),
        source: process.env.GCP_PROJECT ? 'GCP_PROJECT' : process.env.GOOGLE_CLOUD_PROJECT ? 'GOOGLE_CLOUD_PROJECT' : 'default fallback',
        value: process.env.GCP_PROJECT || process.env.GOOGLE_CLOUD_PROJECT || DEFAULT_PROJECT_ID,
        using_default: !(process.env.GCP_PROJECT || process.env.GOOGLE_CLOUD_PROJECT),
      },
      bq_dataset_id: {
        set: !!process.env.BQ_DATASET_ID,
        value: process.env.BQ_DATASET_ID || 'amazon_ppc (default)',
      },
      bq_location: {
        set: !!process.env.BQ_LOCATION,
        value: process.env.BQ_LOCATION || 'us-east4 (default)',
      },
      credentials: {
        gcp_service_account_key: {
          set: !!process.env.GCP_SERVICE_ACCOUNT_KEY,
          valid_json: process.env.GCP_SERVICE_ACCOUNT_KEY ? (() => {
            try {
              JSON.parse(process.env.GCP_SERVICE_ACCOUNT_KEY);
              return true;
            } catch {
              return false;
            }
          })() : null,
          has_required_fields: process.env.GCP_SERVICE_ACCOUNT_KEY ? (() => {
            try {
              const creds = JSON.parse(process.env.GCP_SERVICE_ACCOUNT_KEY);
              return !!(creds.project_id && creds.private_key && creds.client_email);
            } catch {
              return false;
            }
          })() : null,
        },
        google_application_credentials: {
          set: !!process.env.GOOGLE_APPLICATION_CREDENTIALS,
          appears_to_be_json: process.env.GOOGLE_APPLICATION_CREDENTIALS?.startsWith('{') || false,
          appears_to_be_path: process.env.GOOGLE_APPLICATION_CREDENTIALS?.includes('/') || false,
        },
        split_env: (() => {
          const emailEnv = ['GCP_SERVICE_ACCOUNT_EMAIL', 'GCP_CLIENT_EMAIL', 'GOOGLE_CLIENT_EMAIL', 'BIGQUERY_CLIENT_EMAIL', 'BQ_CLIENT_EMAIL'];
          const keyEnv = ['GCP_SERVICE_ACCOUNT_KEY_RAW', 'GCP_PRIVATE_KEY', 'GOOGLE_PRIVATE_KEY', 'BIGQUERY_PRIVATE_KEY', 'BQ_PRIVATE_KEY'];
          const projectEnv = ['GCP_PROJECT', 'GOOGLE_CLOUD_PROJECT', 'GOOGLE_PROJECT_ID', 'GCP_PROJECT_ID', 'BIGQUERY_PROJECT_ID', 'BQ_PROJECT_ID'];

          const resolvedEmail = emailEnv.find((name) => !!(process.env[name]?.trim()));
          const resolvedKey = keyEnv.find((name) => !!(process.env[name]?.trim()));
          const resolvedProject = projectEnv.find((name) => !!(process.env[name]?.trim()));

          return {
            email_env: resolvedEmail || null,
            private_key_env: resolvedKey || null,
            project_id_env: resolvedProject || null,
            private_key_contains_newlines: resolvedKey ? /\n/.test(process.env[resolvedKey] || '') : null,
            ready: Boolean(resolvedEmail && resolvedKey),
          };
        })(),
      },
      dashboard_api_key: {
        set: !!process.env.DASHBOARD_API_KEY,
      },
    },
    diagnosis: [] as string[],
    recommendations: [] as string[],
  };

  // Run diagnostics
  if (!checks.configuration.gcp_project.set) {
    checks.diagnosis.push('⚠️  GCP_PROJECT or GOOGLE_CLOUD_PROJECT is not set - using default fallback');
    checks.recommendations.push('For production, set GCP_PROJECT and GOOGLE_CLOUD_PROJECT environment variables to your Google Cloud project ID');
  } else {
    checks.diagnosis.push('✅ GCP project ID is configured');
  }

  const splitCredentialConfig = checks.configuration.credentials.split_env;

  if (!checks.configuration.credentials.gcp_service_account_key.set &&
      !checks.configuration.credentials.google_application_credentials.set &&
      !splitCredentialConfig.ready) {
    checks.diagnosis.push('⚠️  No Google Cloud credentials found (GCP_SERVICE_ACCOUNT_KEY, GOOGLE_APPLICATION_CREDENTIALS, or credential parts)');
    checks.recommendations.push('Add GCP_SERVICE_ACCOUNT_KEY with your service account JSON credentials as a string');
    checks.recommendations.push('Or add GOOGLE_APPLICATION_CREDENTIALS with the service account JSON');
    checks.recommendations.push('Alternatively, provide credential parts using variables like GCP_CLIENT_EMAIL and GCP_PRIVATE_KEY (escape newlines as \\n)');
  } else if (checks.configuration.credentials.gcp_service_account_key.set) {
    if (checks.configuration.credentials.gcp_service_account_key.valid_json) {
      if (checks.configuration.credentials.gcp_service_account_key.has_required_fields) {
        checks.diagnosis.push('✅ GCP_SERVICE_ACCOUNT_KEY is valid and contains required fields');
      } else {
        checks.diagnosis.push('⚠️  GCP_SERVICE_ACCOUNT_KEY is valid JSON but missing required fields (project_id, private_key, client_email)');
        checks.recommendations.push('Ensure your service account key JSON includes project_id, private_key, and client_email');
      }
    } else {
      checks.diagnosis.push('❌ GCP_SERVICE_ACCOUNT_KEY is set but not valid JSON');
      checks.recommendations.push('Check that GCP_SERVICE_ACCOUNT_KEY contains a valid JSON string from your service account key file');
    }
  } else if (checks.configuration.credentials.google_application_credentials.set) {
    if (checks.configuration.credentials.google_application_credentials.appears_to_be_json) {
      checks.diagnosis.push('✅ GOOGLE_APPLICATION_CREDENTIALS appears to be JSON credentials');
    } else if (checks.configuration.credentials.google_application_credentials.appears_to_be_path) {
      checks.diagnosis.push('⚠️  GOOGLE_APPLICATION_CREDENTIALS appears to be a file path (this works locally but not on Vercel)');
      checks.recommendations.push('For Vercel deployment, use GCP_SERVICE_ACCOUNT_KEY with the JSON content instead of a file path');
    }
  } else if (splitCredentialConfig.ready) {
    checks.diagnosis.push('✅ Google Cloud credential parts detected (client email and private key)');
    if (!splitCredentialConfig.private_key_contains_newlines) {
      checks.recommendations.push('Ensure your private key uses escaped newlines (\\n) so it loads correctly at runtime');
    }
  }

  if (!checks.configuration.dashboard_api_key.set) {
    checks.diagnosis.push('⚠️  DASHBOARD_API_KEY is not set (required for optimizer integration)');
    checks.recommendations.push('Set DASHBOARD_API_KEY to match the key in your Cloud Function Secret Manager');
  }

  const allChecksPassed = checks.diagnosis.filter(d => d.startsWith('❌')).length === 0;
  const warningsExist = checks.diagnosis.filter(d => d.startsWith('⚠️')).length > 0;

  return NextResponse.json({
    status: allChecksPassed ? (warningsExist ? 'warning' : 'ok') : 'error',
    message: allChecksPassed 
      ? 'Configuration appears correct' 
      : 'Configuration issues detected - see diagnosis and recommendations',
    checks,
    next_steps: allChecksPassed && !warningsExist
      ? [
          'Test BigQuery connection: GET /api/bigquery-data?table=optimization_results&limit=1',
          'Check if data exists in BigQuery tables',
          'Verify optimizer is writing to BigQuery',
        ]
      : checks.recommendations,
  }, { 
    status: allChecksPassed ? 200 : 500,
    headers: {
      'Cache-Control': 'no-cache, no-store, must-revalidate',
    }
  });
}
