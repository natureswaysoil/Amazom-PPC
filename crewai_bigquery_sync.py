"""
CrewAI BigQuery to Dashboard Sync Module
==========================================

Uses CrewAI agents to orchestrate data synchronization from BigQuery
to the dashboard at https://amazonppcdashboard-db7ltsqjn-james-projects-5e9a58a0.vercel.app/

This module creates specialized AI agents that:
- Query BigQuery for optimization data
- Transform and prepare data for dashboard consumption
- Send data to the dashboard via API
- Monitor and verify data delivery

Author: Nature's Way Soil
Version: 1.0.0
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests

try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    logging.warning("google-cloud-bigquery not available. Install with: pip install google-cloud-bigquery")

try:
    from crewai import Agent, Task, Crew, Process
    from crewai.tools import tool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    logging.warning("crewAI not available. Install with: pip install crewai crewai-tools")

logger = logging.getLogger(__name__)


# Define tools for agents to use
@tool("Query BigQuery for optimization data")
def query_bigquery_data(project_id: str, dataset_id: str, limit: int = 100) -> str:
    """
    Query BigQuery for recent optimization results.
    
    Args:
        project_id: Google Cloud project ID
        dataset_id: BigQuery dataset ID
        limit: Maximum number of records to return
        
    Returns:
        JSON string with query results
    """
    if not BIGQUERY_AVAILABLE:
        return json.dumps({'success': False, 'error': 'BigQuery client not available'})
    
    try:
        client = bigquery.Client(project=project_id)
        
        query = f"""
        SELECT 
            timestamp,
            run_id,
            status,
            profile_id,
            campaigns_analyzed,
            keywords_optimized,
            bids_increased,
            bids_decreased,
            negative_keywords_added,
            budget_changes,
            total_spend,
            total_sales,
            average_acos,
            target_acos,
            dry_run,
            duration_seconds
        FROM `{project_id}.{dataset_id}.optimization_results`
        WHERE DATE(timestamp) >= CURRENT_DATE() - 7
        ORDER BY timestamp DESC
        LIMIT {limit}
        """
        
        query_job = client.query(query)
        results = query_job.result()
        
        data = []
        for row in results:
            data.append({
                'timestamp': row.timestamp.isoformat() if row.timestamp else None,
                'run_id': row.run_id,
                'status': row.status,
                'profile_id': row.profile_id,
                'campaigns_analyzed': row.campaigns_analyzed,
                'keywords_optimized': row.keywords_optimized,
                'bids_increased': row.bids_increased,
                'bids_decreased': row.bids_decreased,
                'negative_keywords_added': row.negative_keywords_added,
                'budget_changes': row.budget_changes,
                'total_spend': float(row.total_spend) if row.total_spend else 0.0,
                'total_sales': float(row.total_sales) if row.total_sales else 0.0,
                'average_acos': float(row.average_acos) if row.average_acos else 0.0,
                'target_acos': float(row.target_acos) if row.target_acos else 0.0,
                'dry_run': row.dry_run,
                'duration_seconds': float(row.duration_seconds) if row.duration_seconds else 0.0
            })
        
        logger.info(f"Retrieved {len(data)} records from BigQuery")
        return json.dumps({'success': True, 'data': data, 'count': len(data)})
        
    except Exception as e:
        logger.error(f"Error querying BigQuery: {str(e)}")
        return json.dumps({'success': False, 'error': str(e)})


@tool("Query campaign details from BigQuery")
def query_campaign_details(project_id: str, dataset_id: str, limit: int = 100) -> str:
    """
    Query BigQuery for campaign-level details.
    
    Args:
        project_id: Google Cloud project ID
        dataset_id: BigQuery dataset ID
        limit: Maximum number of records to return
        
    Returns:
        JSON string with campaign data
    """
    if not BIGQUERY_AVAILABLE:
        return json.dumps({'success': False, 'error': 'BigQuery client not available'})
    
    try:
        client = bigquery.Client(project=project_id)
        
        query = f"""
        SELECT 
            timestamp,
            run_id,
            campaign_id,
            campaign_name,
            spend,
            sales,
            acos,
            impressions,
            clicks,
            conversions,
            budget,
            status
        FROM `{project_id}.{dataset_id}.campaign_details`
        WHERE DATE(timestamp) >= CURRENT_DATE() - 7
        ORDER BY timestamp DESC, spend DESC
        LIMIT {limit}
        """
        
        query_job = client.query(query)
        results = query_job.result()
        
        data = []
        for row in results:
            data.append({
                'timestamp': row.timestamp.isoformat() if row.timestamp else None,
                'run_id': row.run_id,
                'campaign_id': row.campaign_id,
                'campaign_name': row.campaign_name,
                'spend': float(row.spend) if row.spend else 0.0,
                'sales': float(row.sales) if row.sales else 0.0,
                'acos': float(row.acos) if row.acos else 0.0,
                'impressions': row.impressions,
                'clicks': row.clicks,
                'conversions': row.conversions,
                'budget': float(row.budget) if row.budget else 0.0,
                'status': row.status
            })
        
        logger.info(f"Retrieved {len(data)} campaign records from BigQuery")
        return json.dumps({'success': True, 'data': data, 'count': len(data)})
        
    except Exception as e:
        logger.error(f"Error querying campaign details: {str(e)}")
        return json.dumps({'success': False, 'error': str(e)})


@tool("Send data to dashboard")
def send_to_dashboard(dashboard_url: str, api_key: str, data: str) -> str:
    """
    Send data to the dashboard API.
    
    Args:
        dashboard_url: Dashboard base URL
        api_key: API key for authentication
        data: JSON string with data to send
        
    Returns:
        JSON string with response status
    """
    try:
        # Parse the data string
        payload = json.loads(data)
        
        # Send to dashboard
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'NWS-PPC-Optimizer-CrewAI/1.0'
        }
        
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        endpoint = f"{dashboard_url}/api/optimization-data"
        
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        logger.info(f"Dashboard response: HTTP {response.status_code}")
        
        if response.status_code == 200:
            return json.dumps({
                'success': True,
                'message': 'Data sent successfully',
                'status_code': response.status_code
            })
        else:
            return json.dumps({
                'success': False,
                'message': f'Dashboard returned status {response.status_code}',
                'status_code': response.status_code,
                'response': response.text
            })
            
    except Exception as e:
        logger.error(f"Error sending to dashboard: {str(e)}")
        return json.dumps({'success': False, 'error': str(e)})


@tool("Verify dashboard connectivity")
def verify_dashboard_connection(dashboard_url: str) -> str:
    """
    Verify that the dashboard is reachable.
    
    Args:
        dashboard_url: Dashboard base URL
        
    Returns:
        JSON string with connectivity status
    """
    try:
        # Try to connect to the dashboard
        response = requests.get(
            dashboard_url,
            timeout=10
        )
        
        return json.dumps({
            'success': True,
            'reachable': True,
            'status_code': response.status_code
        })
        
    except Exception as e:
        logger.error(f"Dashboard connectivity check failed: {str(e)}")
        return json.dumps({
            'success': False,
            'reachable': False,
            'error': str(e)
        })


class BigQueryDashboardSync:
    """
    CrewAI-based orchestrator for syncing BigQuery data to dashboard
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the sync orchestrator
        
        Args:
            config: Configuration dictionary
        """
        if not CREWAI_AVAILABLE:
            raise ImportError("crewAI is not available. Install with: pip install crewai crewai-tools")
        
        self.config = config
        self.bigquery_config = config.get('bigquery', {})
        self.dashboard_config = config.get('dashboard', {})
        
        # Extract configuration
        self.project_id = self.bigquery_config.get('project_id') or os.getenv('GCP_PROJECT') or os.getenv('GOOGLE_CLOUD_PROJECT')
        self.dataset_id = self.bigquery_config.get('dataset_id', 'amazon_ppc')
        self.dashboard_url = self.dashboard_config.get('url', '')
        self.api_key = self.dashboard_config.get('api_key', '')
        
        if not self.project_id:
            raise ValueError("BigQuery project_id not configured")
        
        if not self.dashboard_url:
            raise ValueError("Dashboard URL not configured")
        
        # Create agents
        self._create_agents()
    
    def _create_agents(self):
        """Create specialized AI agents for the sync process"""
        
        # Data Analyst Agent - queries and analyzes BigQuery data
        self.data_analyst = Agent(
            role='Data Analyst',
            goal='Query and analyze optimization data from BigQuery',
            backstory="""You are an expert data analyst specializing in Amazon PPC 
            optimization data. You understand BigQuery schemas and can efficiently 
            query and prepare data for dashboard visualization.""",
            tools=[query_bigquery_data, query_campaign_details],
            verbose=True
        )
        
        # Data Engineer Agent - transforms and prepares data
        self.data_engineer = Agent(
            role='Data Engineer',
            goal='Transform and prepare data for dashboard consumption',
            backstory="""You are a skilled data engineer who specializes in ETL 
            processes. You ensure data is properly formatted, validated, and 
            optimized for dashboard APIs.""",
            verbose=True
        )
        
        # Integration Specialist Agent - sends data to dashboard
        self.integration_specialist = Agent(
            role='Integration Specialist',
            goal='Reliably send data to the dashboard and verify delivery',
            backstory="""You are an integration specialist focused on reliable 
            data delivery. You ensure data reaches the dashboard successfully 
            and can troubleshoot connectivity issues.""",
            tools=[send_to_dashboard, verify_dashboard_connection],
            verbose=True
        )
    
    def sync_data(self) -> Dict[str, Any]:
        """
        Execute the data synchronization process using CrewAI
        
        Returns:
            Dictionary with sync results
        """
        logger.info("Starting BigQuery to Dashboard sync with CrewAI")
        
        try:
            # Task 1: Query BigQuery data
            task_query = Task(
                description=f"""Query BigQuery for the last 7 days of optimization 
                results from project '{self.project_id}' and dataset '{self.dataset_id}'. 
                Retrieve up to 100 records with all relevant metrics including 
                campaigns analyzed, keywords optimized, spend, sales, and ACOS.""",
                agent=self.data_analyst,
                expected_output="JSON data with optimization results from BigQuery"
            )
            
            # Task 2: Query campaign details
            task_campaigns = Task(
                description=f"""Query BigQuery for campaign-level details from 
                project '{self.project_id}' and dataset '{self.dataset_id}'. 
                Get the top 100 campaigns by spend from the last 7 days.""",
                agent=self.data_analyst,
                expected_output="JSON data with campaign details from BigQuery"
            )
            
            # Task 3: Prepare data for dashboard
            task_prepare = Task(
                description="""Transform the queried data into the format expected 
                by the dashboard API. Combine optimization results and campaign details 
                into a cohesive payload. Validate all data types and handle null values.""",
                agent=self.data_engineer,
                expected_output="Formatted JSON payload ready for dashboard API"
            )
            
            # Task 4: Verify dashboard connectivity
            task_verify = Task(
                description=f"""Verify that the dashboard at {self.dashboard_url} 
                is reachable and responsive before sending data.""",
                agent=self.integration_specialist,
                expected_output="Dashboard connectivity status"
            )
            
            # Task 5: Send data to dashboard
            task_send = Task(
                description=f"""Send the prepared data to the dashboard at 
                {self.dashboard_url}. Use the API key for authentication and 
                ensure successful delivery. Handle any errors gracefully.""",
                agent=self.integration_specialist,
                expected_output="Confirmation of successful data delivery to dashboard"
            )
            
            # Create crew
            crew = Crew(
                agents=[self.data_analyst, self.data_engineer, self.integration_specialist],
                tasks=[task_query, task_campaigns, task_prepare, task_verify, task_send],
                process=Process.sequential,
                verbose=True
            )
            
            # Execute the crew
            result = crew.kickoff()
            
            logger.info("CrewAI sync completed successfully")
            
            return {
                'success': True,
                'message': 'Data synced successfully from BigQuery to dashboard',
                'timestamp': datetime.now().isoformat(),
                'result': str(result)
            }
            
        except Exception as e:
            logger.error(f"CrewAI sync failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def sync_latest_run(self, run_id: str) -> Dict[str, Any]:
        """
        Sync data for a specific optimization run
        
        Args:
            run_id: Unique run identifier
            
        Returns:
            Dictionary with sync results
        """
        logger.info(f"Syncing specific run {run_id} to dashboard")
        
        if not BIGQUERY_AVAILABLE:
            return {
                'success': False,
                'error': 'BigQuery client not available'
            }
        
        try:
            # Query data for specific run
            client = bigquery.Client(project=self.project_id)
            
            query = f"""
            SELECT *
            FROM `{self.project_id}.{self.dataset_id}.optimization_results`
            WHERE run_id = @run_id
            LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("run_id", "STRING", run_id)
                ]
            )
            
            query_job = client.query(query, job_config=job_config)
            results = query_job.result()
            
            data = None
            for row in results:
                data = dict(row)
                # Convert timestamps and decimals to JSON-serializable types
                for key, value in data.items():
                    if hasattr(value, 'isoformat'):
                        data[key] = value.isoformat()
                    elif isinstance(value, (float, int)):
                        data[key] = value
            
            if not data:
                return {
                    'success': False,
                    'error': f'No data found for run_id {run_id}'
                }
            
            # Send to dashboard
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'NWS-PPC-Optimizer-CrewAI/1.0'
            }
            
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            response = requests.post(
                f"{self.dashboard_url}/api/optimization-data",
                json={'data': [data], 'run_id': run_id},
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully synced run {run_id} to dashboard")
                return {
                    'success': True,
                    'message': f'Run {run_id} synced successfully',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.warning(f"Dashboard returned status {response.status_code}")
                return {
                    'success': False,
                    'error': f'Dashboard returned status {response.status_code}',
                    'response': response.text
                }
                
        except Exception as e:
            logger.error(f"Failed to sync run {run_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
