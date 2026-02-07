#!/usr/bin/env python3
"""
Bridge script to invoke the optimizer from Node.js server.
Reads request data from stdin and invokes the optimizer.
"""
import sys
import json
import os

# Add current directory to path for Cloud Run
sys.path.insert(0, '/workspace')
sys.path.insert(0, '/app')
sys.path.insert(0, os.getcwd())

try:
    from main import run_optimizer
    
    class MockRequest:
        """Mock request object that mimics Flask/Cloud Functions request."""
        def __init__(self, json_data, query_params, method='POST', headers=None):
            self.args = {}
            for param in query_params:
                if '=' in param:
                    key, val = param.split('=', 1)
                    self.args[key] = val
            self._json = json_data
            self.method = method
            # Flask request.headers supports .get()
            self.headers = headers or {}
        
        def get_json(self, silent=True):
            """Return the JSON data from the request."""
            return self._json
    
    # Read request data from stdin
    input_data = json.load(sys.stdin)
    request_data = input_data.get('request_data', {})
    query_params = input_data.get('query_params', [])
    method = input_data.get('method', 'POST')
    headers = input_data.get('headers', {})
    
    # Create mock request and invoke optimizer
    request = MockRequest(request_data, query_params, method=method, headers=headers)
    resp = run_optimizer(request)

    # main.run_optimizer can return either:
    # - (dict, status)
    # - (json_string, status, headers)
    if isinstance(resp, tuple) and len(resp) == 3:
        body, status, _headers = resp
        if isinstance(body, (str, bytes)):
            try:
                result = json.loads(body)
            except Exception:
                result = {'raw': body.decode('utf-8') if isinstance(body, bytes) else body}
        else:
            result = body
    elif isinstance(resp, tuple) and len(resp) == 2:
        result, status = resp
    else:
        # Fallback: treat as body with 200
        result, status = resp, 200
    
    # Output result as JSON with special marker for easy parsing
    output = {
        '__OPTIMIZER_RESULT__': True,
        'result': result,
        'status': status
    }
    print(json.dumps(output))
    sys.exit(0)
    
except Exception as e:
    import traceback
    error_details = traceback.format_exc()
    error_output = {
        '__OPTIMIZER_ERROR__': True,
        'error': str(e),
        'details': error_details,
        'status': 500
    }
    # Write error to stderr
    print(json.dumps(error_output), file=sys.stderr)
    sys.exit(1)
