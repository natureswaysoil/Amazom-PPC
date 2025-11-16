import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';
import { resolveGCPCredentials, getFirstSetEnv, PROJECT_ID_ENV_NAMES } from '../lib/credentials';

// Get BigQuery client with proper credential handling
function getBigQueryClient() {
  const DEFAULT_PROJECT_ID = 'amazon-ppc-474902';
  
  // Resolve credentials
  const credentialResult = resolveGCPCredentials();
  
  let credentials: any = undefined;
  let projectId = getFirstSetEnv(PROJECT_ID_ENV_NAMES);
  
  if (credentialResult.success) {
    credentials = credentialResult.credentials;
    if (!projectId && credentialResult.projectId) {
      projectId = credentialResult.projectId;
    }
  } else {
    // Log warning but continue with Application Default Credentials
    console.warn(`Failed to resolve credentials: ${credentialResult.error!.message}`);
  }
  
  if (!projectId) {
    projectId = DEFAULT_PROJECT_ID;
  }
  
  return new BigQuery({
    projectId,
    ...(credentials && { credentials }),
  });
}

export async function POST(request: NextRequest) {
  try {
    // Verify API key
    const apiKey = process.env.DASHBOARD_API_KEY;
    const authHeader = request.headers.get('authorization');
    const bearerToken = authHeader?.startsWith('Bearer ')
      ? authHeader.slice(7)
      : authHeader || undefined;
    const headerApiKey = request.headers.get('x-api-key') ?? undefined;

    if (apiKey) {
      if (bearerToken !== apiKey && headerApiKey !== apiKey) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
      }
    } else {
      console.warn('DASHBOARD_API_KEY is not set. Skipping authentication.');
    }

    const body = await request.json();
    
    // Log the results
    console.log('Optimization results received:', {
      run_id: body.run_id,
      status: body.status,
      duration: body.duration_seconds,
      summary: body.summary
    });
    
    // Validate required fields from enhanced schema
    const requiredFields = ['run_id', 'status', 'timestamp'];
    const missingFields = requiredFields.filter(field => !body[field]);
    
    if (missingFields.length > 0) {
      console.error('Missing required fields in results payload:', missingFields);
      return NextResponse.json({
        error: 'Invalid payload',
        message: `Missing required fields: ${missingFields.join(', ')}`,
      }, { status: 400 });
    }
    
    // Check for expected enhanced fields and log warnings
    const expectedFields = ['summary', 'features', 'campaigns', 'top_performers', 'config_snapshot'];
    const missingEnhancedFields = expectedFields.filter(field => !body[field]);
    
    if (missingEnhancedFields.length > 0) {
      console.warn('⚠️ Missing enhanced fields in payload:', missingEnhancedFields);
      console.warn('This may indicate the optimizer is not sending the complete enhanced payload.');
    }
    
    // Store in BigQuery
    try {
      const bigquery = getBigQueryClient();
      const datasetId = process.env.BQ_DATASET_ID || 'amazon_ppc';
      const projectId = process.env.GCP_PROJECT || process.env.GOOGLE_CLOUD_PROJECT || 'amazon-ppc-474902';
      const tableRef = `${projectId}.${datasetId}.optimization_results`;
      
      // Build row matching the schema in bigquery_client.py
      const summary = body.summary || {};
      const config = body.config_snapshot || {};
      const enabledFeatures = Array.isArray(config.enabled_features) ? config.enabled_features : [];
      const errors = Array.isArray(body.errors) ? body.errors.map((e: any) => String(e)) : [];
      const warnings = Array.isArray(body.warnings) ? body.warnings.map((w: any) => String(w)) : [];
      
      const row = {
        timestamp: body.timestamp || new Date().toISOString(),
        run_id: body.run_id,
        status: body.status || 'success',
        profile_id: body.profile_id || '',
        dry_run: body.dry_run || false,
        duration_seconds: body.duration_seconds || 0,
        campaigns_analyzed: summary.campaigns_analyzed || 0,
        keywords_optimized: summary.keywords_optimized || 0,
        bids_increased: summary.bids_increased || 0,
        bids_decreased: summary.bids_decreased || 0,
        negative_keywords_added: summary.negative_keywords_added || 0,
        budget_changes: summary.budget_changes || 0,
        total_spend: summary.total_spend || 0.0,
        total_sales: summary.total_sales || 0.0,
        average_acos: summary.average_acos || 0.0,
        target_acos: config.target_acos || null,
        lookback_days: config.lookback_days || null,
        enabled_features: enabledFeatures,
        errors: errors,
        warnings: warnings,
        // Enhanced fields stored as JSON
        campaigns: JSON.stringify(body.campaigns || []),
        top_performers: JSON.stringify(body.top_performers || []),
        features: JSON.stringify(body.features || {}),
        config_snapshot: JSON.stringify(body.config_snapshot || {}),
      };
      
      const insertErrors = await bigquery.dataset(datasetId).table('optimization_results').insert([row]);
      
      if (insertErrors && insertErrors.length > 0) {
        console.error('BigQuery insert errors:', insertErrors);
        // Don't fail the request, just log the error
      } else {
        console.log('✅ Successfully stored optimization results in BigQuery');
      }
    } catch (bqError: any) {
      console.error('Failed to store results in BigQuery:', bqError.message);
      // Don't fail the request if BigQuery storage fails
    }
    
    return NextResponse.json({ 
      success: true,
      received: true,
      run_id: body.run_id
    }, { status: 200 });
    
  } catch (error) {
    console.error('Error processing results:', error);
    return NextResponse.json({ 
      error: 'Internal server error' 
    }, { status: 500 });
  }
}
