import { BigQuery } from '@google-cloud/bigquery';

// Initialize BQ from Dashboard side
// Ensure you have GOOGLE_APPLICATION_CREDENTIALS or raw JSON credentials in Vercel env
const bigquery = new BigQuery({
  projectId: process.env.GCP_PROJECT_ID,
  credentials: JSON.parse(process.env.GCP_SERVICE_ACCOUNT_KEY)
});

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ message: 'Method not allowed' });
  }

  try {
    // Query to get the most recent 50 optimization actions
    const query = `
      SELECT 
        timestamp,
        campaign_name,
        keyword_text,
        old_bid,
        new_bid,
        acos,
        action_taken
      FROM \`amazon-ppc.optimization_log\`
      ORDER BY timestamp DESC
      LIMIT 50
    `;

    const options = {
      query: query,
      location: 'US', // Must match dataset location
    };

    const [rows] = await bigquery.query(options);

    res.status(200).json({ 
      success: true, 
      data: rows 
    });

  } catch (error) {
    console.error('BigQuery Fetch Error:', error);
    res.status(500).json({ 
      success: false, 
      error: error.message 
    });
  }
}
