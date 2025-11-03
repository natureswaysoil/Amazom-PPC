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
    
    // Log the status update
    console.log('Optimization status update:', body);
    
    // TODO: Store in your database
    // Example fields in body:
    // - run_id: unique identifier for this run
    // - status: 'started' | 'running' | 'completed'
    // - profile_id: Amazon profile ID
    // - timestamp: ISO timestamp
    // - message: optional progress message
    // - percent_complete: optional progress percentage
    
    return NextResponse.json({ 
      success: true,
      received: true 
    }, { status: 200 });
    
  } catch (error) {
    console.error('Error processing status update:', error);
    return NextResponse.json({ 
      error: 'Internal server error' 
    }, { status: 500 });
  }
}
