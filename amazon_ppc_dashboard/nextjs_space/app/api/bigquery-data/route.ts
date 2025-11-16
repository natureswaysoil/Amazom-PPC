import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';
import { resolveGCPCredentials, getFirstSetEnv, PROJECT_ID_ENV_NAMES } from '../lib/credentials';

export async function GET(request: NextRequest) {
  try {
    // Get configuration from environment variables with fallback to default
    const datasetId = process.env.BQ_DATASET_ID || 'amazon_ppc';
    const location = process.env.BQ_LOCATION || 'us-east4';
    const DEFAULT_PROJECT_ID = 'amazon-ppc-474902';
    
    // Resolve credentials using the new shared utility
    const credentialResult = resolveGCPCredentials();
    
    let credentials: any = undefined;
    let projectId = getFirstSetEnv(PROJECT_ID_ENV_NAMES);

    // Handle credential resolution errors
    if (!credentialResult.success) {
      const runningOnVercel = process.env.VERCEL === '1';
      
      // Only require credentials in production/Vercel environment
      if (runningOnVercel) {
        return NextResponse.json({
          error: credentialResult.error!.type === 'missing' ? 'Missing Google Cloud credentials' : 'Configuration error',
          message: credentialResult.error!.message,
          details: credentialResult.error!.details,
          troubleshooting: credentialResult.error!.troubleshooting,
          documentation: 'See README.md for detailed setup instructions.',
        }, { status: 500 });
      }
      
      // In development, allow using default credentials if available
      console.warn('Failed to resolve credentials from environment, will attempt to use Application Default Credentials');
      console.warn(`Credential error: ${credentialResult.error!.message}`);
    } else {
      // Successfully resolved credentials
      credentials = credentialResult.credentials;
      
      // Use project ID from credentials if not explicitly set
      if (!projectId && credentialResult.projectId) {
        projectId = credentialResult.projectId;
        console.log(`Using project ID from credentials (${credentialResult.source}):`, projectId);
      }
    }

    // Use default project ID if none found
    if (!projectId) {
      projectId = DEFAULT_PROJECT_ID;
      console.log('Using default project ID:', projectId);
    }
    
    // Validate that we have a project ID
    if (!projectId) {
      return NextResponse.json({ 
        error: 'Configuration error',
        message: 'Project ID not found',
        details: 'Set GCP_PROJECT/GOOGLE_CLOUD_PROJECT or provide service account credentials with project_id',
        troubleshooting: [
          'Option 1: Set GCP_SERVICE_ACCOUNT_KEY with service account JSON (includes project_id)',
          'Option 2: Set GCP_PROJECT or GOOGLE_CLOUD_PROJECT to your project ID',
          'Redeploy the application after setting environment variables',
        ],
      }, { status: 500 });
    }

    // Initialize BigQuery client with explicit credentials if provided
    const bigquery = new BigQuery({
      projectId: projectId,
      ...(credentials && { credentials }),
    });
    
    // Get query parameters with validation
    const searchParams = request.nextUrl.searchParams;
    const table = searchParams.get('table') || 'optimization_results';
    
    // Validate and sanitize limit parameter (max 100)
    let limit = parseInt(searchParams.get('limit') || '10');
    if (isNaN(limit) || limit < 1) {
      limit = 10;
    } else if (limit > 100) {
      limit = 100;
    }
    
    // Validate and sanitize days parameter (max 365)
    let days = parseInt(searchParams.get('days') || '7');
    if (isNaN(days) || days < 1) {
      days = 7;
    } else if (days > 365) {
      days = 365;
    }
    
    // Validate table parameter (whitelist approach)
    const validTables = ['optimization_results', 'campaign_details', 'summary'];
    if (!validTables.includes(table)) {
      return NextResponse.json({ 
        error: 'Invalid table parameter',
        message: `Table must be one of: ${validTables.join(', ')}`
      }, { status: 400 });
    }
    
    // Build fully qualified table name (safely)
    const fullTableName = `\`${projectId}.${datasetId}.optimization_results\``;
    const campaignTableName = `\`${projectId}.${datasetId}.campaign_details\``;
    
    // Build query based on table with parameterized values
    let query = '';
    let queryParams: any[] = [];
    
    switch (table) {
      case 'optimization_results':
        query = `
          SELECT 
            timestamp,
            run_id,
            status,
            profile_id,
            dry_run,
            duration_seconds,
            campaigns_analyzed,
            keywords_optimized,
            bids_increased,
            bids_decreased,
            negative_keywords_added,
            budget_changes,
            average_acos,
            total_spend,
            total_sales,
            target_acos,
            lookback_days,
            enabled_features,
            errors,
            warnings,
            campaigns,
            top_performers,
            features,
            config_snapshot
          FROM ${fullTableName}
          WHERE DATE(timestamp) >= CURRENT_DATE() - @days
          ORDER BY timestamp DESC
          LIMIT @limit
        `;
        queryParams = [
          { name: 'days', value: days },
          { name: 'limit', value: limit }
        ];
        break;
        
      case 'campaign_details':
        query = `
          SELECT 
            timestamp,
            run_id,
            campaign_id,
            campaign_name,
            spend,
            sales,
            acos,
            impressions,
            clicks,
            conversions,
            budget,
            status
          FROM ${campaignTableName}
          WHERE DATE(timestamp) >= CURRENT_DATE() - @days
          ORDER BY timestamp DESC
          LIMIT @limit
        `;
        queryParams = [
          { name: 'days', value: days },
          { name: 'limit', value: limit }
        ];
        break;
        
      case 'summary':
        query = `
          SELECT 
            DATE(timestamp) as date,
            COUNT(*) as optimization_runs,
            SUM(keywords_optimized) as total_keywords_optimized,
            SUM(bids_increased) as total_bids_increased,
            SUM(bids_decreased) as total_bids_decreased,
            AVG(average_acos) as avg_acos,
            SUM(total_spend) as total_spend,
            SUM(total_sales) as total_sales
          FROM ${fullTableName}
          WHERE DATE(timestamp) >= CURRENT_DATE() - @days
          GROUP BY DATE(timestamp)
          ORDER BY date DESC
        `;
        queryParams = [
          { name: 'days', value: days }
        ];
        break;
    }
    
    // Execute query with parameters
    const [rows] = await bigquery.query({
      query: query,
      location: location,
      params: queryParams,
    });
    
    // Post-process rows to parse JSON fields for optimization_results
    let processedRows = rows;
    if (table === 'optimization_results') {
      processedRows = rows.map((row: any) => {
        const processed = { ...row };
        
        // Parse JSON fields if they exist and are strings
        const jsonFields = ['campaigns', 'top_performers', 'features', 'config_snapshot'];
        jsonFields.forEach(field => {
          if (processed[field]) {
            try {
              // If it's a string, parse it as JSON
              if (typeof processed[field] === 'string') {
                processed[field] = JSON.parse(processed[field]);
              }
              // Otherwise it's already an object from BigQuery JSON type
            } catch (e) {
              console.warn(`Failed to parse ${field} for row ${processed.run_id}:`, e);
              processed[field] = field === 'campaigns' || field === 'top_performers' ? [] : {};
            }
          } else {
            // Set default values for missing fields
            processed[field] = field === 'campaigns' || field === 'top_performers' ? [] : {};
          }
        });
        
        return processed;
      });
      
      // Log warnings if data is incomplete
      const incompleteRows = processedRows.filter((row: any) => 
        !row.campaigns || 
        (Array.isArray(row.campaigns) && row.campaigns.length === 0) ||
        !row.top_performers ||
        (Array.isArray(row.top_performers) && row.top_performers.length === 0)
      );
      
      if (incompleteRows.length > 0) {
        console.warn(`⚠️ ${incompleteRows.length} of ${processedRows.length} results have incomplete data (missing campaigns or top_performers)`);
      }
    }
    
    return NextResponse.json({
      success: true,
      data: processedRows,
      metadata: {
        projectId,
        datasetId,
        table,
        rowCount: processedRows.length
      }
    }, { status: 200 });
    
  } catch (error: any) {
    console.error('BigQuery query error:', error);
    
    // Check if it's a "not found" error
    if (error.message && error.message.includes('Not found')) {
      return NextResponse.json({
        error: 'Dataset or table not found',
        message: 'Please run setup-bigquery.sh to create the BigQuery dataset and tables',
        details: error.message
      }, { status: 404 });
    }

    // Check for BigQuery permission errors
    if (error.message && (
      error.message.includes('bigquery.jobs.create') ||
      error.message.includes('bigquery.tables.get') ||
      error.message.includes('Access Denied') ||
      error.message.includes('does not have bigquery') ||
      (error.code === 403 || error.code === 7) // 403 Forbidden or gRPC PERMISSION_DENIED
    )) {
      const projectId = getFirstSetEnv(PROJECT_ID_ENV_NAMES) || 'amazon-ppc-474902';
      
      return NextResponse.json({
        error: 'Access Denied',
        message: 'The service account does not have sufficient BigQuery permissions',
        details: error.message,
        troubleshooting: [
          'The service account needs these BigQuery IAM roles:',
          '  • roles/bigquery.dataViewer (or roles/bigquery.dataEditor) - to read/write data',
          '  • roles/bigquery.jobUser - to create and run query jobs',
          '',
          'To grant the required permissions, run these commands in Google Cloud Shell:',
          '',
          `# Get the service account email from your credentials`,
          `SERVICE_ACCOUNT_EMAIL=$(echo "$GCP_SERVICE_ACCOUNT_KEY" | jq -r .client_email)`,
          '',
          `# Grant BigQuery Data Viewer role`,
          `gcloud projects add-iam-policy-binding ${projectId} \\`,
          `  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \\`,
          `  --role="roles/bigquery.dataViewer"`,
          '',
          `# Grant BigQuery Job User role (required to run queries)`,
          `gcloud projects add-iam-policy-binding ${projectId} \\`,
          `  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \\`,
          `  --role="roles/bigquery.jobUser"`,
          '',
          'Alternatively, you can grant these roles in the Google Cloud Console:',
          `  1. Go to https://console.cloud.google.com/iam-admin/iam?project=${projectId}`,
          '  2. Find your service account in the list',
          '  3. Click "Edit principal" (pencil icon)',
          '  4. Add the roles: BigQuery Data Viewer + BigQuery Job User',
          '  5. Click "Save"',
          '',
          'After granting permissions, refresh this page to try again.',
        ],
        documentation: 'See BIGQUERY_DATASET_FIX.md and ACCESS_GUIDE.md for more details.',
      }, { status: 403 });
    }

    if (error.message && error.message.includes('Could not load the default credentials')) {
      return NextResponse.json({
        error: 'Missing Google Cloud credentials',
        message: 'Could not load Google Cloud credentials for BigQuery.',
        details: 'Provide service account credentials via the GCP_SERVICE_ACCOUNT_KEY environment variable (preferred) or GOOGLE_APPLICATION_CREDENTIALS as a JSON string.',
        documentation: 'See amazon_ppc_dashboard/nextjs_space/README_BIGQUERY.md for deployment steps.',
        next_steps: [
          'Add the service account JSON to GCP_SERVICE_ACCOUNT_KEY in your deployment environment.',
          'If using GOOGLE_APPLICATION_CREDENTIALS, paste the JSON contents directly instead of a file path.',
          'Redeploy the dashboard after saving the variables.',
          'Re-run /api/config-check to verify configuration.'
        ],
      }, { status: 500 });
    }

    return NextResponse.json({
      error: 'Failed to query BigQuery',
      message: error.message || 'Unknown error',
      details: error.stack || 'No additional details available'
    }, { status: 500 });
  }
}
