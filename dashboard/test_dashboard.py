"""
Test suite for Amazon PPC BigQuery Dashboard
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app


class TestDashboardEndpoints(unittest.TestCase):
    """Test all dashboard API endpoints"""
    
    def setUp(self):
        """Set up test client"""
        app.app.config['TESTING'] = True
        self.client = app.app.test_client()
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('timestamp', data)
    
    def test_index_page(self):
        """Test main dashboard page loads"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Amazon PPC BigQuery Dashboard', response.data)
        self.assertIn(b'summary-cards', response.data)
    
    @patch('app.get_bigquery_client')
    def test_list_tables_success(self, mock_client):
        """Test listing BigQuery tables"""
        # Mock BigQuery client and tables
        mock_bq = MagicMock()
        mock_client.return_value = (mock_bq, None)
        
        # Mock table list
        mock_table = MagicMock()
        mock_table.table_id = 'optimization_results'
        
        mock_table_info = MagicMock()
        mock_table_info.num_rows = 100
        mock_table_info.num_bytes = 1024
        mock_table_info.created = None
        mock_table_info.modified = None
        
        mock_bq.list_tables.return_value = [mock_table]
        mock_bq.get_table.return_value = mock_table_info
        
        response = self.client.get('/api/tables')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('tables', data)
        self.assertEqual(len(data['tables']), 1)
        self.assertEqual(data['tables'][0]['table_id'], 'optimization_results')
    
    @patch('app.get_bigquery_client')
    def test_list_tables_no_client(self, mock_client):
        """Test listing tables when client fails"""
        mock_client.return_value = (None, "Could not load Google Cloud credentials for BigQuery. Please ensure GCP_SERVICE_ACCOUNT_KEY or GOOGLE_APPLICATION_CREDENTIALS is set.")
        
        response = self.client.get('/api/tables')
        self.assertEqual(response.status_code, 500)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('Could not load Google Cloud credentials', data['error'])
    
    @patch('app.get_bigquery_client')
    def test_get_table_data(self, mock_client):
        """Test getting table data"""
        mock_bq = MagicMock()
        mock_client.return_value = (mock_bq, None)
        
        # Mock query results
        mock_row = {'timestamp': '2024-01-01', 'run_id': 'test123', 'status': 'success'}
        mock_result = [mock_row]
        
        # Mock count query result
        mock_count_row = {'total': 1}
        mock_count_result = [mock_count_row]
        
        mock_query_job = MagicMock()
        # First call returns data rows, second call returns count
        mock_query_job.result.side_effect = [mock_result, mock_count_result]
        mock_bq.query.return_value = mock_query_job
        
        response = self.client.get('/api/table/optimization_results?limit=10&days=30')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['table_name'], 'optimization_results')
        self.assertIn('rows', data)
        self.assertIn('total_count', data)
    
    @patch('app.get_bigquery_client')
    def test_get_table_schema(self, mock_client):
        """Test getting table schema"""
        mock_bq = MagicMock()
        mock_client.return_value = (mock_bq, None)
        
        # Mock table with schema
        mock_field = MagicMock()
        mock_field.name = 'timestamp'
        mock_field.field_type = 'TIMESTAMP'
        mock_field.mode = 'REQUIRED'
        mock_field.description = None
        
        mock_table = MagicMock()
        mock_table.schema = [mock_field]
        mock_table.num_rows = 100
        mock_table.num_bytes = 1024
        
        mock_bq.get_table.return_value = mock_table
        
        response = self.client.get('/api/table/optimization_results/schema')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['table_name'], 'optimization_results')
        self.assertIn('schema', data)
        self.assertEqual(len(data['schema']), 1)
    
    @patch('app.get_bigquery_client')
    def test_get_summary(self, mock_client):
        """Test getting summary statistics"""
        mock_bq = MagicMock()
        mock_client.return_value = (mock_bq, None)
        
        # Mock summary query result
        mock_result = [{
            'total_runs': 10,
            'total_keywords_optimized': 500,
            'total_campaigns_analyzed': 20,
            'avg_acos': 0.25,
            'total_spend': 1000.0,
            'total_sales': 5000.0,
            'last_run': None
        }]
        
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = mock_result
        mock_bq.query.return_value = mock_query_job
        
        response = self.client.get('/api/summary')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('summary', data)
        self.assertEqual(data['summary']['total_runs'], 10)
    
    @patch('app.get_bigquery_client')
    def test_get_chart_data_daily_performance(self, mock_client):
        """Test getting daily performance chart data"""
        mock_bq = MagicMock()
        mock_client.return_value = (mock_bq, None)
        
        # Mock chart data
        mock_result = [
            {
                'date': '2024-01-01',
                'runs': 5,
                'keywords_optimized': 100,
                'avg_acos': 0.25,
                'total_spend': 500.0,
                'total_sales': 2000.0
            }
        ]
        
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = mock_result
        mock_bq.query.return_value = mock_query_job
        
        response = self.client.get('/api/chart-data/daily_performance?days=30')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['chart_type'], 'daily_performance')
        self.assertIn('data', data)
    
    @patch('app.get_bigquery_client')
    def test_get_chart_data_invalid_type(self, mock_client):
        """Test getting chart data with invalid type"""
        mock_bq = MagicMock()
        mock_client.return_value = (mock_bq, None)
        
        response = self.client.get('/api/chart-data/invalid_chart')
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('error', data)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""
    
    @patch('app.load_credentials')
    def test_get_bigquery_client_with_credentials(self, mock_load):
        """Test BigQuery client initialization with credentials"""
        mock_creds = MagicMock()
        mock_load.return_value = mock_creds
        
        with patch('app.bigquery.Client') as mock_bq_client:
            client, error = app.get_bigquery_client()
            self.assertIsNotNone(client)
            self.assertIsNone(error)
            mock_bq_client.assert_called_once()
    
    @patch('app.load_credentials')
    def test_get_bigquery_client_without_credentials(self, mock_load):
        """Test BigQuery client initialization without credentials"""
        mock_load.return_value = None
        
        with patch('app.bigquery.Client') as mock_bq_client:
            client, error = app.get_bigquery_client()
            self.assertIsNotNone(client)
            self.assertIsNone(error)
            mock_bq_client.assert_called_once()
    
    @patch('app.load_credentials')
    def test_get_bigquery_client_error_handling(self, mock_load):
        """Test BigQuery client initialization with error"""
        mock_load.side_effect = Exception("Credential loading failed")
        
        client, error = app.get_bigquery_client()
        self.assertIsNone(client)
        self.assertIsNotNone(error)
        self.assertIn("Could not load Google Cloud credentials for BigQuery", error)
        self.assertIn("Credential loading failed", error)


if __name__ == '__main__':
    unittest.main()
