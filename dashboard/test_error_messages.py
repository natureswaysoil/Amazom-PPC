"""
Test suite for verifying error message handling in the dashboard
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app


class TestErrorMessages(unittest.TestCase):
    """Test error message propagation to frontend"""
    
    def setUp(self):
        """Set up test client"""
        app.app.config['TESTING'] = True
        self.client = app.app.test_client()
    
    @patch('app.load_credentials')
    def test_credential_error_message_in_api_response(self, mock_load):
        """
        Test that credential errors return helpful error messages
        
        This test verifies the fix for the issue:
        "Failed to fetch optimization results: Could not load Google Cloud credentials for BigQuery."
        """
        # Simulate credential loading failure
        mock_load.side_effect = Exception("Credentials file not found")
        
        # Test /api/tables endpoint
        response = self.client.get('/api/tables')
        self.assertEqual(response.status_code, 500)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
        
        # Verify the error message includes the helpful constant
        error_message = data['error']
        self.assertIn('Could not load Google Cloud credentials for BigQuery', error_message)
        self.assertIn('GCP_SERVICE_ACCOUNT_KEY', error_message)
        self.assertIn('GOOGLE_APPLICATION_CREDENTIALS', error_message)
        
        # Verify the error includes the specific exception details
        self.assertIn('Credentials file not found', error_message)
    
    @patch('app.load_credentials')
    def test_multiple_endpoints_return_same_error(self, mock_load):
        """Test that all endpoints return consistent error messages"""
        mock_load.side_effect = Exception("Invalid credentials format")
        
        endpoints = [
            '/api/tables',
            '/api/table/optimization_results',
            '/api/table/optimization_results/schema',
            '/api/summary',
            '/api/chart-data/daily_performance'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 500)
                
                data = json.loads(response.data)
                self.assertIn('error', data)
                
                error_message = data['error']
                self.assertIn('Could not load Google Cloud credentials', error_message)
                self.assertIn('Invalid credentials format', error_message)
    
    @patch('app.load_credentials')
    @patch('gcp_credentials.validate_credentials_early')
    def test_bigquery_health_endpoint_detailed_error(self, mock_validate, mock_load):
        """Test that the health check endpoint provides detailed error information"""
        mock_load.side_effect = Exception("Service account key is malformed")
        mock_validate.return_value = (False, "Credential validation failed")
        
        response = self.client.get('/api/bigquery-health')
        
        # Health check returns 500 when unhealthy
        self.assertEqual(response.status_code, 500)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'unhealthy')
        
        # Check that error details are included
        self.assertIn('bigquery', data)
        self.assertFalse(data['bigquery']['client_initialized'])
        
        # Verify client_error field is present and contains helpful information
        self.assertIn('client_error', data['bigquery'])
        client_error = data['bigquery']['client_error']
        self.assertIsNotNone(client_error)
        self.assertIn('Could not load Google Cloud credentials', client_error)
        self.assertIn('Service account key is malformed', client_error)
    
    @patch('app.load_credentials')
    def test_successful_response_has_no_error(self, mock_load):
        """Test that successful responses don't have error messages"""
        mock_creds = MagicMock()
        mock_load.return_value = mock_creds
        
        with patch('app.bigquery.Client') as mock_bq_client:
            mock_bq = MagicMock()
            mock_bq_client.return_value = mock_bq
            
            # Mock successful table list
            mock_table = MagicMock()
            mock_table.table_id = 'test_table'
            mock_table_info = MagicMock()
            mock_table_info.num_rows = 0
            mock_table_info.num_bytes = 0
            mock_table_info.created = None
            mock_table_info.modified = None
            
            mock_bq.list_tables.return_value = [mock_table]
            mock_bq.get_table.return_value = mock_table_info
            
            response = self.client.get('/api/tables')
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertNotIn('error', data)
            self.assertIn('tables', data)


if __name__ == '__main__':
    unittest.main()
