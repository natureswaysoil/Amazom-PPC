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
    
    // Create a Python script that invokes the optimizer
    // We'll pass the request data via stdin to avoid escaping issues
    const pythonScript = `
import sys
import json
import os

# Add current directory to path
sys.path.insert(0, '/workspace')
sys.path.insert(0, '/app')
sys.path.insert(0, os.getcwd())

try:
    from main import run_optimizer
    
    class MockRequest:
        def __init__(self, json_data, query_params):
            self.args = {}
            for param in query_params:
                if '=' in param:
                    key, val = param.split('=', 1)
                    self.args[key] = val
            self._json = json_data
        
        def get_json(self, silent=True):
            return self._json
    
    # Read request data from stdin
    input_data = json.load(sys.stdin)
    request_data = input_data.get('request_data', {})
    query_params = input_data.get('query_params', [])
    
    request = MockRequest(request_data, query_params)
    result, status = run_optimizer(request)
    
    print(json.dumps({'result': result, 'status': status}))
    sys.exit(0)
    
except Exception as e:
    import traceback
    error_details = traceback.format_exc()
    error_msg = {'error': str(e), 'details': error_details, 'status': 500}
    print(json.dumps(error_msg), file=sys.stderr)
    sys.exit(1)
`;

    const python = spawn(pythonCommand, ['-c', pythonScript], { 
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
        // Try to parse error from stderr
        try {
          const errorData = JSON.parse(stderr);
          reject({ status: errorData.status || 500, data: errorData });
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
        // Parse successful response
        const lines = stdout.trim().split('\n');
        const lastLine = lines[lines.length - 1];
        const result = JSON.parse(lastLine);
        resolve({ status: result.status || 200, data: result.result });
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
