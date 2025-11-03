import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    // Verify API key
    const authHeader = request.headers.get('authorization');
    const apiKey = process.env.DASHBOARD_API_KEY;
    
    if (!authHeader || !authHeader.startsWith('Bearer ') || authHeader.slice(7) !== apiKey) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    
    // Log the results
    console.log('Optimization results received:', {
      run_id: body.run_id,
      status: body.status,
      duration: body.duration_seconds,
      summary: body.summary
    });
    
    // TODO: Store in your database
    // Example fields in body:
    // - run_id: unique identifier
    // - status: 'success' | 'error'
    // - profile_id: Amazon profile ID
    // - timestamp: ISO timestamp
    // - duration_seconds: how long it took
    // - dry_run: boolean
    // - summary: { campaigns_analyzed, keywords_optimized, bids_increased, etc. }
    // - features: { bid_optimization: {...}, dayparting: {...}, etc. }
    // - campaigns: array of campaign data
    // - top_performers: array of best performing keywords
    // - config_snapshot: configuration used for this run
    
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
