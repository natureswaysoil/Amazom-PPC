import { NextRequest, NextResponse } from 'next/server';
import { BigQuery } from '@google-cloud/bigquery';

export async function GET(request: NextRequest) {
  try {
    // Get configuration from environment variables
    const projectId = process.env.GCP_PROJECT || process.env.GOOGLE_CLOUD_PROJECT || 'amazon-ppc-474902';
    const datasetId = process.env.BQ_DATASET_ID || 'amazon_ppc';
    const location = process.env.BQ_LOCATION || 'us-east4';
    
    // Initialize BigQuery client
    const bigquery = new BigQuery({
      projectId: projectId,
    });
    
    // Get query parameters
    const searchParams = request.nextUrl.searchParams;
    const table = searchParams.get('table') || 'optimization_results';
    const limit = parseInt(searchParams.get('limit') || '10');
    const days = parseInt(searchParams.get('days') || '7');
    
    // Build query based on table
    let query = '';
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
          FROM \`${projectId}.${datasetId}.optimization_results\`
          WHERE DATE(timestamp) >= CURRENT_DATE() - ${days}
          ORDER BY timestamp DESC
          LIMIT ${limit}
        `;
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
          FROM \`${projectId}.${datasetId}.campaign_details\`
          WHERE DATE(timestamp) >= CURRENT_DATE() - ${days}
          ORDER BY timestamp DESC
          LIMIT ${limit}
        `;
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
          FROM \`${projectId}.${datasetId}.optimization_results\`
          WHERE DATE(timestamp) >= CURRENT_DATE() - ${days}
          GROUP BY DATE(timestamp)
          ORDER BY date DESC
        `;
        break;
        
      default:
        return NextResponse.json({ 
          error: 'Invalid table parameter' 
        }, { status: 400 });
    }
    
    // Execute query
    const [rows] = await bigquery.query({
      query: query,
      location: location,
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
