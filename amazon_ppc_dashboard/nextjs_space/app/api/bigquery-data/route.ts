import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';
import * as fs from 'fs';

export async function GET(request: NextRequest) {
  try {
    // Get configuration from environment variables
    let projectId = process.env.GCP_PROJECT || process.env.GOOGLE_CLOUD_PROJECT;
    const datasetId = process.env.BQ_DATASET_ID || 'amazon_ppc';
    const location = process.env.BQ_LOCATION || 'us-east4';
    
    // Handle Google Cloud credentials
    // In Vercel, credentials can be provided as:
    // 1. GCP_SERVICE_ACCOUNT_KEY (JSON string of service account key)
    // 2. GOOGLE_APPLICATION_CREDENTIALS (JSON string, though typically a file path locally)
    // 3. Default application credentials (if running in GCP)
    let credentials: any = undefined;
    
    if (process.env.GCP_SERVICE_ACCOUNT_KEY) {
      try {
        credentials = JSON.parse(process.env.GCP_SERVICE_ACCOUNT_KEY);
        // Extract project ID from service account credentials if not already set
        // Type-safe check for project_id property
        if (!projectId && credentials && typeof credentials === 'object' && credentials.project_id) {
          projectId = credentials.project_id;
          console.log('Using project ID from GCP_SERVICE_ACCOUNT_KEY');
        }
      } catch (e) {
        return NextResponse.json({ 
          error: 'Configuration error',
          message: 'GCP_SERVICE_ACCOUNT_KEY is not valid JSON',
          details: 'The GCP_SERVICE_ACCOUNT_KEY environment variable must contain a valid JSON string. Please check the format and redeploy.',
        }, { status: 500 });
      }
    } else if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
      // Try to parse as JSON string (Vercel pattern)
      try {
        credentials = JSON.parse(process.env.GOOGLE_APPLICATION_CREDENTIALS);
        // Extract project ID from service account credentials if not already set
        // Type-safe check for project_id property
        if (!projectId && credentials && typeof credentials === 'object' && credentials.project_id) {
          projectId = credentials.project_id;
          console.log('Using project ID from GOOGLE_APPLICATION_CREDENTIALS JSON');
        }
      } catch (e) {
        // If not JSON, assume it's a file path (local development)
        // Try to read the file and extract project_id
        try {
          const credPath = process.env.GOOGLE_APPLICATION_CREDENTIALS;
          if (credPath && fs.existsSync(credPath)) {
            const fileContent = fs.readFileSync(credPath, 'utf8');
            const fileCreds = JSON.parse(fileContent);
            if (!projectId && fileCreds && typeof fileCreds === 'object' && fileCreds.project_id) {
              projectId = fileCreds.project_id;
              console.log('Using project ID from GOOGLE_APPLICATION_CREDENTIALS file');
            }
            // Don't set credentials here - let BigQuery client handle file path
            credentials = undefined;
          }
        } catch (fileErr) {
          console.warn('Could not read GOOGLE_APPLICATION_CREDENTIALS file:', fileErr);
          credentials = undefined;
        }
      }
    }
    
    // Validate required configuration after attempting to extract from credentials
    if (!projectId) {
      // Build helpful error message based on what's configured
      const configStatus = {
        GCP_PROJECT: !!process.env.GCP_PROJECT,
        GOOGLE_CLOUD_PROJECT: !!process.env.GOOGLE_CLOUD_PROJECT,
        GCP_SERVICE_ACCOUNT_KEY: !!process.env.GCP_SERVICE_ACCOUNT_KEY,
        GOOGLE_APPLICATION_CREDENTIALS: !!process.env.GOOGLE_APPLICATION_CREDENTIALS
      };
      
      return NextResponse.json({ 
        error: 'Configuration error',
        message: 'Project ID not found: Set GCP_PROJECT/GOOGLE_CLOUD_PROJECT or provide service account credentials',
        details: 'To fix this error, choose ONE of these options:\n\n' +
                 'Option 1 (Recommended for Vercel/Cloud deployments):\n' +
                 '  • Set GCP_SERVICE_ACCOUNT_KEY environment variable to your service account JSON\n' +
                 '  • The JSON must include "project_id" field (e.g., {"type":"service_account","project_id":"amazon-ppc-474902",...})\n\n' +
                 'Option 2 (Simple approach):\n' +
                 '  • Set GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variable to your project ID\n' +
                 '  • Example: GCP_PROJECT=amazon-ppc-474902\n\n' +
                 'Option 3 (Local development):\n' +
                 '  • Set GOOGLE_APPLICATION_CREDENTIALS to point to your service account JSON file\n' +
                 '  • Example: GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json\n\n' +
                 'After setting environment variables, redeploy the application.',
        configStatus,
        documentation: 'See .env.example file for configuration templates. Visit https://vercel.com/docs/concepts/projects/environment-variables for Vercel setup.',
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
            average_acos,
            total_spend,
            total_sales
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
    
    return NextResponse.json({ 
      success: true,
      data: rows,
      metadata: {
        projectId,
        datasetId,
        table,
        rowCount: rows.length
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
    
    return NextResponse.json({ 
      error: 'Failed to query BigQuery',
      message: error.message || 'Unknown error'
    }, { status: 500 });
  }
}
