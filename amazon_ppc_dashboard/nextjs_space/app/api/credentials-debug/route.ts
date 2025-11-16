import { NextRequest, NextResponse } from 'next/server';
import { Buffer } from 'buffer';

/**
 * Debug endpoint for GCP credentials troubleshooting
 * Returns non-sensitive diagnostic information about credential configuration
 * 
 * SECURITY: Never expose actual credential values, only diagnostic info
 */
export async function GET(request: NextRequest) {
  const debug = {
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'unknown',
    platform: process.env.VERCEL ? 'vercel' : 'other',
    diagnostics: [] as string[],
    credential_sources: [] as any[],
  };

  // Check all possible credential environment variables
  const credentialEnvVars = [
    'GCP_SERVICE_ACCOUNT_KEY',
    'GCP_SA_KEY',
    'GCP_SERVICE_ACCOUNT_JSON',
    'GOOGLE_APPLICATION_CREDENTIALS',
    'GCP_SERVICE_ACCOUNT',
    'GCP_CREDENTIALS',
  ];

  for (const envVar of credentialEnvVars) {
    const value = process.env[envVar];
    if (!value || !value.trim()) {
      continue;
    }

    const analysis: any = {
      name: envVar,
      set: true,
      length: value.length,
      starts_with: value.substring(0, 20),
      ends_with: value.substring(value.length - 20),
    };

    // Detect format
    const trimmed = value.trim();
    if (trimmed.startsWith('{')) {
      analysis.format = 'raw_json';
      analysis.appears_valid_json = (() => {
        try {
          JSON.parse(trimmed);
          return true;
        } catch {
          return false;
        }
      })();
      
      if (analysis.appears_valid_json) {
        try {
          const parsed = JSON.parse(trimmed);
          analysis.has_type = 'type' in parsed;
          analysis.type_value = parsed.type;
          analysis.has_project_id = 'project_id' in parsed;
          analysis.has_private_key = 'private_key' in parsed;
          analysis.has_client_email = 'client_email' in parsed;
          analysis.project_id_preview = parsed.project_id?.substring(0, 10) + '...';
          analysis.client_email_domain = parsed.client_email?.split('@')[1];
        } catch (e) {
          // Silently continue
        }
      }
    } else if (trimmed.startsWith('/')) {
      analysis.format = 'file_path';
      analysis.warning = 'File paths do not work in serverless environments like Vercel';
    } else {
      // Might be base64
      analysis.format = 'possibly_base64';
      const base64Pattern = /^[A-Za-z0-9+/]*={0,2}$/;
      analysis.matches_base64_pattern = base64Pattern.test(trimmed);
      
      if (analysis.matches_base64_pattern) {
        try {
          const decoded = Buffer.from(trimmed, 'base64').toString('utf8');
          analysis.base64_decode_success = true;
          analysis.decoded_length = decoded.length;
          analysis.decoded_starts_with = decoded.substring(0, 20);
          
          // Check if decoded content is JSON
          try {
            const parsed = JSON.parse(decoded);
            analysis.decoded_is_valid_json = true;
            analysis.decoded_has_type = 'type' in parsed;
            analysis.decoded_type_value = parsed.type;
            analysis.decoded_has_project_id = 'project_id' in parsed;
            analysis.decoded_has_private_key = 'private_key' in parsed;
            analysis.decoded_has_client_email = 'client_email' in parsed;
            analysis.decoded_project_id_preview = parsed.project_id?.substring(0, 10) + '...';
            analysis.decoded_client_email_domain = parsed.client_email?.split('@')[1];
          } catch (jsonError: any) {
            analysis.decoded_is_valid_json = false;
            analysis.decoded_json_error = jsonError.message;
            analysis.decoded_preview = decoded.substring(0, 100);
          }
        } catch (b64Error: any) {
          analysis.base64_decode_success = false;
          analysis.base64_decode_error = b64Error.message;
        }
      }
    }

    debug.credential_sources.push(analysis);
  }

  // Generate diagnostics
  if (debug.credential_sources.length === 0) {
    debug.diagnostics.push('❌ No GCP credential environment variables found');
    debug.diagnostics.push('Set GCP_SERVICE_ACCOUNT_KEY with your service account JSON');
  } else {
    for (const source of debug.credential_sources) {
      if (source.format === 'raw_json' && source.appears_valid_json) {
        if (source.type_value === 'service_account' && source.has_project_id && source.has_private_key && source.has_client_email) {
          debug.diagnostics.push(`✅ ${source.name}: Valid service account JSON detected`);
        } else if (source.type_value !== 'service_account') {
          debug.diagnostics.push(`⚠️ ${source.name}: JSON detected but type is '${source.type_value}' (expected 'service_account')`);
        } else {
          const missing = [];
          if (!source.has_project_id) missing.push('project_id');
          if (!source.has_private_key) missing.push('private_key');
          if (!source.has_client_email) missing.push('client_email');
          debug.diagnostics.push(`⚠️ ${source.name}: JSON detected but missing fields: ${missing.join(', ')}`);
        }
      } else if (source.format === 'raw_json' && !source.appears_valid_json) {
        debug.diagnostics.push(`❌ ${source.name}: Appears to be JSON but parsing failed`);
      } else if (source.format === 'file_path') {
        debug.diagnostics.push(`⚠️ ${source.name}: File path detected (won't work in serverless environments)`);
      } else if (source.format === 'possibly_base64') {
        if (source.matches_base64_pattern && source.base64_decode_success) {
          if (source.decoded_is_valid_json) {
            if (source.decoded_type_value === 'service_account' && source.decoded_has_project_id && source.decoded_has_private_key && source.decoded_has_client_email) {
              debug.diagnostics.push(`✅ ${source.name}: Valid base64-encoded service account JSON detected`);
            } else {
              const missing = [];
              if (!source.decoded_has_project_id) missing.push('project_id');
              if (!source.decoded_has_private_key) missing.push('private_key');
              if (!source.decoded_has_client_email) missing.push('client_email');
              debug.diagnostics.push(`⚠️ ${source.name}: Base64-encoded but missing fields: ${missing.join(', ')}`);
            }
          } else {
            debug.diagnostics.push(`❌ ${source.name}: Base64 decodes but result is not valid JSON`);
            debug.diagnostics.push(`   Decoded content starts with: ${source.decoded_starts_with}`);
            debug.diagnostics.push(`   JSON parse error: ${source.decoded_json_error}`);
          }
        } else if (source.matches_base64_pattern && !source.base64_decode_success) {
          debug.diagnostics.push(`❌ ${source.name}: Looks like base64 but decode failed`);
        } else {
          debug.diagnostics.push(`⚠️ ${source.name}: Unknown format (not JSON, not file path, not base64)`);
        }
      }
    }
  }

  // Check component credentials
  const componentEnvVars = {
    client_email: ['GCP_CLIENT_EMAIL', 'GCP_SERVICE_ACCOUNT_EMAIL', 'GOOGLE_CLIENT_EMAIL'],
    private_key: ['GCP_PRIVATE_KEY', 'GOOGLE_PRIVATE_KEY'],
    project_id: ['GCP_PROJECT', 'GOOGLE_CLOUD_PROJECT', 'GCP_PROJECT_ID'],
  };

  const componentStatus: any = {};
  for (const [component, envVars] of Object.entries(componentEnvVars)) {
    const found = envVars.find(name => process.env[name]?.trim());
    componentStatus[component] = {
      set: !!found,
      source: found || null,
    };
    
    if (component === 'private_key' && found) {
      const key = process.env[found];
      componentStatus[component].has_escaped_newlines = key?.includes('\\n') || false;
      componentStatus[component].has_actual_newlines = key?.includes('\n') || false;
      componentStatus[component].length = key?.length || 0;
    }
  }

  if (componentStatus.client_email.set && componentStatus.private_key.set) {
    if (componentStatus.private_key.has_actual_newlines) {
      debug.diagnostics.push('✅ Component credentials detected (client_email + private_key with proper newlines)');
    } else if (componentStatus.private_key.has_escaped_newlines) {
      debug.diagnostics.push('⚠️ Component credentials detected but private_key may have escaped newlines (\\n instead of actual newlines)');
    } else {
      debug.diagnostics.push('⚠️ Component credentials detected but private_key format may be incorrect');
    }
  }

  const hasValidCredentials = debug.diagnostics.some(d => d.startsWith('✅'));
  const hasErrors = debug.diagnostics.some(d => d.startsWith('❌'));

  return NextResponse.json({
    status: hasValidCredentials ? 'ok' : (hasErrors ? 'error' : 'warning'),
    message: hasValidCredentials 
      ? 'Valid GCP credentials detected' 
      : 'No valid GCP credentials found or credentials have issues',
    debug,
    recommendations: hasValidCredentials 
      ? [
          'Credentials appear valid',
          'Test BigQuery connection at /api/bigquery-data',
          'Test full config at /api/config-check',
        ]
      : [
          'Set GCP_SERVICE_ACCOUNT_KEY to your service account JSON (raw or base64)',
          'Ensure the JSON file is valid: cat service-account.json | jq .',
          'For base64 encoding: cat service-account.json | base64 | tr -d "\\n"',
          'After setting, redeploy the application',
          'Visit /api/config-check for full configuration validation',
        ],
  }, {
    status: hasValidCredentials ? 200 : 500,
    headers: {
      'Cache-Control': 'no-cache, no-store, must-revalidate',
    },
  });
}
