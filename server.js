const http = require('http');
const { syncAmazonData } = require('./index');

const PORT = process.env.PORT || 8080;

const server = http.createServer(async (req, res) => {
  if (req.url === '/health' || req.url === '/') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'healthy', service: 'amazon-ppc-sync' }));
    return;
  }

  if (req.url === '/sync' && req.method === 'POST') {
    try {
      console.log('Starting Amazon PPC data sync...');
      const data = await syncAmazonData();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        success: true,
        campaigns: data.length,
        timestamp: new Date().toISOString()
      }));
    } catch (error) {
      console.error('Sync failed:', error);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        error: error.message,
        timestamp: new Date().toISOString()
      }));
    }
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, () => {
  console.log(`Amazon PPC Sync service listening on port ${PORT}`);
});
