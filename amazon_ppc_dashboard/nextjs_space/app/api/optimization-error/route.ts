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
    
    // Log the error
    console.error('Optimization error received:', body);
    
    // TODO: Store in your database and/or send alerts
    // Example fields in body:
    // - run_id: unique identifier
    // - status: 'error'
    // - profile_id: Amazon profile ID
    // - timestamp: ISO timestamp
    // - error: error message
    // - error_type: error classification
    
    return NextResponse.json({ 
      success: true,
      received: true 
    }, { status: 200 });
    
  } catch (error) {
    console.error('Error processing error report:', error);
    return NextResponse.json({ 
      error: 'Internal server error' 
    }, { status: 500 });
  }
}
