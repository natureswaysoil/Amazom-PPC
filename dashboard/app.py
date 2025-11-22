"""
Amazon PPC BigQuery Dashboard
==============================

A fresh dashboard application to display all BigQuery Amazon PPC data tables.
Built with Flask backend and modern frontend.

Tables displayed:
- optimization_results
- campaign_details
- optimization_progress
- optimization_errors
- optimizer_run_events
"""

import os
import json
import logging
import traceback
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from google.cloud import bigquery
from google.oauth2 import service_account

# Import centralized credential loading
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gcp_credentials import load_credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Error message constant
BIGQUERY_CREDENTIAL_ERROR = "Could not load Google Cloud credentials for BigQuery. Please ensure GCP_SERVICE_ACCOUNT_KEY or GOOGLE_APPLICATION_CREDENTIALS is set."

app = Flask(__name__)
CORS(app)

# Configuration
# Project ID should be set via GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable
# or configured in config.json
PROJECT_ID = os.getenv('GCP_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT', 'amazon-ppc-474902')
DATASET_ID = os.getenv('BIGQUERY_DATASET', 'amazon_ppc')

def get_bigquery_client():
    """Initialize BigQuery client with credentials"""
    try:
        credentials = load_credentials()
        if credentials:
            logger.info("Using service account credentials for BigQuery")
            client = bigquery.Client(project=PROJECT_ID, credentials=credentials)
            logger.info(f"✓ BigQuery client initialized successfully for project {PROJECT_ID}")
            return client
        else:
            logger.info("Using Application Default Credentials for BigQuery")
            client = bigquery.Client(project=PROJECT_ID)
            logger.info(f"✓ BigQuery client initialized with ADC for project {PROJECT_ID}")
            return client
    except Exception as e:
        logger.error(f"Failed to initialize BigQuery client: {e}")
        logger.error(BIGQUERY_CREDENTIAL_ERROR)
        logger.error(traceback.format_exc())
        return None

@app.route('/')
def index():
    """Render main dashboard page"""
    return render_template('index.html')

@app.route('/api/tables')
def list_tables():
    """List all available BigQuery tables"""
    try:
        client = get_bigquery_client()
        if not client:
            return jsonify({'error': 'Failed to initialize BigQuery client'}), 500
        
        dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
        tables = client.list_tables(dataset_ref)
        
        table_list = []
        for table in tables:
            table_info = client.get_table(table.reference)
            table_list.append({
                'table_id': table.table_id,
                'num_rows': table_info.num_rows,
                'size_bytes': table_info.num_bytes,
                'created': table_info.created.isoformat() if table_info.created else None,
                'modified': table_info.modified.isoformat() if table_info.modified else None
            })
        
        return jsonify({'tables': table_list})
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/table/<table_name>')
def get_table_data(table_name):
    """Get data from a specific BigQuery table"""
    try:
        client = get_bigquery_client()
        if not client:
            return jsonify({'error': 'Failed to initialize BigQuery client'}), 500
        
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        days = request.args.get('days', 30, type=int)
        order_by = request.args.get('order_by', 'timestamp DESC')
        
        # Build query with filters
        table_ref = f"`{PROJECT_ID}.{DATASET_ID}.{table_name}`"
        
        query = f"""
        SELECT *
        FROM {table_ref}
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        ORDER BY {order_by}
        LIMIT {limit}
        OFFSET {offset}
        """
        
        query_job = client.query(query)
        results = query_job.result()
        
        # Convert results to list of dicts
        rows = []
        for row in results:
            row_dict = dict(row)
            # Convert datetime objects to ISO format strings
            for key, value in row_dict.items():
                if isinstance(value, datetime):
                    row_dict[key] = value.isoformat()
            rows.append(row_dict)
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total
        FROM {table_ref}
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        """
        count_job = client.query(count_query)
        count_result = list(count_job.result())
        total_count = count_result[0]['total'] if count_result else 0
        
        return jsonify({
            'table_name': table_name,
            'rows': rows,
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        logger.error(f"Error fetching table data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/table/<table_name>/schema')
def get_table_schema(table_name):
    """Get schema information for a specific table"""
    try:
        client = get_bigquery_client()
        if not client:
            return jsonify({'error': 'Failed to initialize BigQuery client'}), 500
        
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
        table = client.get_table(table_ref)
        
        schema = []
        for field in table.schema:
            schema.append({
                'name': field.name,
                'field_type': field.field_type,
                'mode': field.mode,
                'description': field.description
            })
        
        return jsonify({
            'table_name': table_name,
            'schema': schema,
            'num_rows': table.num_rows,
            'size_bytes': table.num_bytes
        })
    except Exception as e:
        logger.error(f"Error fetching table schema: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/summary')
def get_summary():
    """Get summary statistics across all tables"""
    try:
        client = get_bigquery_client()
        if not client:
            return jsonify({'error': 'Failed to initialize BigQuery client'}), 500
        
        # Get optimization results summary
        query = f"""
        SELECT
            COUNT(*) as total_runs,
            SUM(keywords_optimized) as total_keywords_optimized,
            SUM(campaigns_analyzed) as total_campaigns_analyzed,
            AVG(average_acos) as avg_acos,
            SUM(total_spend) as total_spend,
            SUM(total_sales) as total_sales,
            MAX(timestamp) as last_run
        FROM `{PROJECT_ID}.{DATASET_ID}.optimization_results`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        """
        
        query_job = client.query(query)
        results = list(query_job.result())
        
        if results:
            row = dict(results[0])
            # Convert datetime to ISO format
            if row.get('last_run'):
                row['last_run'] = row['last_run'].isoformat()
            
            return jsonify({'summary': row})
        
        return jsonify({'summary': {}})
    except Exception as e:
        logger.error(f"Error fetching summary: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chart-data/<chart_type>')
def get_chart_data(chart_type):
    """Get data for various charts"""
    try:
        client = get_bigquery_client()
        if not client:
            return jsonify({'error': 'Failed to initialize BigQuery client'}), 500
        
        days = request.args.get('days', 30, type=int)
        
        if chart_type == 'daily_performance':
            query = f"""
            SELECT
                DATE(timestamp) as date,
                COUNT(*) as runs,
                SUM(keywords_optimized) as keywords_optimized,
                AVG(average_acos) as avg_acos,
                SUM(total_spend) as total_spend,
                SUM(total_sales) as total_sales
            FROM `{PROJECT_ID}.{DATASET_ID}.optimization_results`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            GROUP BY date
            ORDER BY date DESC
            """
        elif chart_type == 'campaign_performance':
            query = f"""
            SELECT
                campaign_name,
                AVG(acos) as avg_acos,
                SUM(spend) as total_spend,
                SUM(sales) as total_sales,
                SUM(clicks) as total_clicks,
                SUM(conversions) as total_conversions
            FROM `{PROJECT_ID}.{DATASET_ID}.campaign_details`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            GROUP BY campaign_name
            ORDER BY total_spend DESC
            LIMIT 20
            """
        elif chart_type == 'error_distribution':
            query = f"""
            SELECT
                status,
                COUNT(*) as count
            FROM `{PROJECT_ID}.{DATASET_ID}.optimization_results`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            GROUP BY status
            """
        else:
            return jsonify({'error': 'Invalid chart type'}), 400
        
        query_job = client.query(query)
        results = query_job.result()
        
        rows = []
        for row in results:
            row_dict = dict(row)
            # Convert date/datetime objects to ISO format strings
            for key, value in row_dict.items():
                if isinstance(value, (datetime, type(row_dict.get('date')))):
                    row_dict[key] = str(value)
            rows.append(row_dict)
        
        return jsonify({'chart_type': chart_type, 'data': rows})
    except Exception as e:
        logger.error(f"Error fetching chart data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/bigquery-health')
def bigquery_health():
    """Check BigQuery connectivity and credentials"""
    try:
        # Test credential loading
        from gcp_credentials import validate_credentials_early
        creds_valid, creds_error = validate_credentials_early()
        
        # Test BigQuery client initialization
        client = get_bigquery_client()
        client_ok = client is not None
        
        # Test dataset access if client initialized
        dataset_accessible = False
        dataset_error = None
        row_count = 0
        
        if client:
            try:
                dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
                dataset = client.get_dataset(dataset_ref)
                dataset_accessible = True
                
                # Try to count rows in optimization_results table
                query = f"""
                    SELECT COUNT(*) as total 
                    FROM `{PROJECT_ID}.{DATASET_ID}.optimization_results`
                """
                result = client.query(query).result()
                for row in result:
                    row_count = row['total']
                    break
                    
            except Exception as dataset_err:
                dataset_error = str(dataset_err)
                logger.warning(f"Dataset access check failed: {dataset_err}")
        
        response = {
            'status': 'healthy' if (client_ok and dataset_accessible) else 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'credentials': {
                'valid': creds_valid,
                'error': creds_error
            },
            'bigquery': {
                'project_id': PROJECT_ID,
                'dataset_id': DATASET_ID,
                'client_initialized': client_ok,
                'dataset_accessible': dataset_accessible,
                'dataset_error': dataset_error,
                'optimization_results_count': row_count
            }
        }
        
        return jsonify(response), 200 if response['status'] == 'healthy' else 500
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
