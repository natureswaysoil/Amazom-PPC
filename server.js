const http = require('http');
const { spawn } = require('child_process');
const { syncAmazonData } = require('./index');

const PORT = process.env.PORT || 8080;

/**
 * Run the Python optimizer and return results
 */
function runPythonOptimizer(requestData) {
  return new Promise((resolve, reject) => {
    // Check if Python is available
    const pythonCommand = process.env.PYTHON_PATH || 'python3';
    
    // Build query parameters from request
    const queryParams = [];
    if (requestData.dry_run) queryParams.push('dry_run=true');
    if (requestData.force) queryParams.push('force=true');
    if (requestData.health) queryParams.push('health=true');
    if (requestData.verify_connection) queryParams.push('verify_connection=true');
    if (requestData.list_profiles) queryParams.push('list_profiles=true');
    if (requestData.permission_health) queryParams.push('permission_health=true');
    
    // Set environment variables
    const env = { ...process.env };
    
    // Invoke the bridge script
    const python = spawn(pythonCommand, ['run_optimizer_bridge.py'], { 
      env,
      stdio: ['pipe', 'pipe', 'pipe']
    });
    
    // Send request data via stdin
    python.stdin.write(JSON.stringify({
      request_data: requestData,
      query_params: queryParams
    }));
    python.stdin.end();
    
    let stdout = '';
    let stderr = '';
    
    python.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    python.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    python.on('error', (error) => {
      reject(new Error(`Failed to spawn Python process: ${error.message}`));
    });
    
    python.on('close', (code) => {
      if (code !== 0) {
        // Try to parse error from stderr - look for our error marker
        try {
          // Parse each line to find the error marker
          const stderrLines = stderr.trim().split('\n');
          for (const line of stderrLines) {
            try {
              const parsed = JSON.parse(line);
              if (parsed.__OPTIMIZER_ERROR__) {
                reject({ status: parsed.status || 500, data: parsed });
                return;
              }
            } catch (e) {
              // Not JSON, skip this line
            }
          }
          // No error marker found, use generic error
          reject({ 
            status: 500, 
            data: { 
              status: 'error', 
              error: 'Optimizer initialization failed. Check logs for details.',
              details: stderr.slice(0, 1000),
              stdout: stdout.slice(0, 500)
            } 
          });
        } catch (e) {
          reject({ 
            status: 500, 
            data: { 
              status: 'error', 
              error: 'Optimizer initialization failed. Check logs for details.',
              details: stderr.slice(0, 1000),
              stdout: stdout.slice(0, 500)
            } 
          });
        }
        return;
      }
      
      try {
        // Parse successful response - look for our result marker
        const stdoutLines = stdout.trim().split('\n');
        for (const line of stdoutLines) {
          try {
            const parsed = JSON.parse(line);
            if (parsed.__OPTIMIZER_RESULT__) {
              resolve({ status: parsed.status || 200, data: parsed.result });
              return;
            }
          } catch (e) {
            // Not JSON, skip this line
          }
        }
        // No result marker found, try parsing the last line as fallback
        const lastLine = stdoutLines[stdoutLines.length - 1];
        const result = JSON.parse(lastLine);
        resolve({ status: result.status || 200, data: result.result || result });
      } catch (error) {
        reject({ 
          status: 500, 
          data: { 
            status: 'error', 
            error: 'Failed to parse optimizer response',
            output: stdout.slice(0, 1000)
          } 
        });
      }
    });
  });
}

const server = http.createServer(async (req, res) => {
  // Handle GET requests to health  
  if (req.url === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'healthy', service: 'amazon-ppc-optimizer' }));
    return;
  }
  
  // Handle GET requests to root - return service info
  if (req.url === '/' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ 
      status: 'healthy', 
      service: 'amazon-ppc-optimizer',
      endpoints: {
        'POST /': 'Run optimizer (accepts dry_run, force flags)',
        'POST /sync': 'Sync Amazon data',
        'GET /health': 'Health check'
      }
    }));
    return;
  }
  
  // Handle POST requests to root - run Python optimizer
  if (req.url === '/' && req.method === 'POST') {
    let body = '';
    
    req.on('data', chunk => {
      body += chunk.toString();
    });
    
    req.on('end', async () => {
      try {
        let requestData = {};
        if (body) {
          try {
            requestData = JSON.parse(body);
          } catch (e) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ 
              status: 'error', 
              error: 'Invalid JSON in request body' 
            }));
            return;
          }
        }
        
        console.log('Invoking Python optimizer with request:', JSON.stringify(requestData));
        
        const result = await runPythonOptimizer(requestData);
        res.writeHead(result.status, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result.data));
        
      } catch (error) {
        console.error('Optimizer failed:', error);
        const status = error.status || 500;
        const data = error.data || { 
          status: 'error', 
          error: error.message || 'Optimizer initialization failed. Check logs for details.' 
        };
        res.writeHead(status, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(data));
      }
    });
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
  res.end(JSON.stringify({ 
    status: 'error',
    error: 'Not found',
    available_endpoints: {
      'POST /': 'Run optimizer',
      'POST /sync': 'Sync Amazon data',
      'GET /health': 'Health check'
    }
  }));
});

server.listen(PORT, () => {
  console.log(`Amazon PPC Sync service listening on port ${PORT}`);
});
