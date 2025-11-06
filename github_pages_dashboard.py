#!/usr/bin/env python3
"""
GitHub Pages Dashboard Integration
====================================

Integration module for sending PPC optimization data to GitHub Pages dashboard
at https://natureswaysoil.github.io/best/

Features:
- Data transformation for GitHub Pages format
- JSON file generation for static hosting
- Automatic data updates via GitHub API
- Historical data tracking
- Real-time metrics display

Author: Nature's Way Soil
Version: 1.0.0
"""

import logging
import json
import base64
from datetime import datetime
from typing import Dict, List, Optional, Any
import requests

logger = logging.getLogger(__name__)


class GitHubPagesDashboard:
    """
    Client for updating GitHub Pages dashboard with PPC optimization data
    
    Features:
    - Updates dashboard data via GitHub API
    - Maintains historical data
    - Formats data for static site consumption
    - Handles authentication with GitHub
    """
    
    def __init__(self, config: Dict):
        """
        Initialize GitHub Pages dashboard client
        
        Args:
            config: Configuration dictionary with GitHub settings
        """
        github_config = config.get('github_pages_dashboard', {})
        
        self.enabled = github_config.get('enabled', False)
        self.repo_owner = github_config.get('repo_owner', 'natureswaysoil')
        self.repo_name = github_config.get('repo_name', 'best')
        self.branch = github_config.get('branch', 'main')
        self.data_path = github_config.get('data_path', 'data/ppc-data.json')
        self.github_token = github_config.get('github_token', '')
        
        # GitHub API base URL
        self.api_base = 'https://api.github.com'
        
        # Dashboard URL
        self.dashboard_url = github_config.get('dashboard_url', 
                                               'https://natureswaysoil.github.io/best/')
        
        if not self.enabled:
            logger.info("GitHub Pages dashboard integration is disabled")
        elif not self.github_token:
            logger.warning("GitHub token not configured - dashboard updates will fail")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests"""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
        
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        return headers
    
    def _get_file_sha(self) -> Optional[str]:
        """
        Get the SHA of the current data file
        
        Returns:
            File SHA if exists, None otherwise
        """
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{self.data_path}"
        params = {'ref': self.branch}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('sha')
            elif response.status_code == 404:
                logger.info(f"Data file {self.data_path} does not exist yet")
                return None
            else:
                logger.warning(f"Failed to get file SHA: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting file SHA: {e}")
            return None
    
    def _get_current_data(self) -> Dict:
        """
        Get current data from GitHub Pages dashboard
        
        Returns:
            Current dashboard data or empty dict
        """
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{self.data_path}"
        params = {'ref': self.branch}
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data['content']).decode('utf-8')
                return json.loads(content)
            else:
                logger.info("No existing data file, starting fresh")
                return {}
                
        except Exception as e:
            logger.warning(f"Error reading current data: {e}")
            return {}
    
    def update_dashboard(self, optimization_results: Dict) -> bool:
        """
        Update GitHub Pages dashboard with new optimization results
        
        Args:
            optimization_results: Complete optimization results
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug("GitHub Pages dashboard updates disabled")
            return False
        
        try:
            logger.info(f"Updating GitHub Pages dashboard at {self.dashboard_url}")
            
            # Get current data to maintain history
            current_data = self._get_current_data()
            
            # Format new data
            new_entry = self._format_optimization_data(optimization_results)
            
            # Update historical runs
            if 'runs' not in current_data:
                current_data['runs'] = []
            
            current_data['runs'].insert(0, new_entry)
            
            # Keep last 30 runs
            current_data['runs'] = current_data['runs'][:30]
            
            # Update summary with latest data
            current_data['latest'] = new_entry
            current_data['updated_at'] = datetime.now().isoformat()
            
            # Calculate aggregated statistics
            current_data['statistics'] = self._calculate_statistics(current_data['runs'])
            
            # Upload to GitHub
            success = self._upload_to_github(current_data)
            
            if success:
                logger.info(f"✓ Successfully updated dashboard: {self.dashboard_url}")
            else:
                logger.error("✗ Failed to update dashboard")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating GitHub Pages dashboard: {e}")
            return False
    
    def _format_optimization_data(self, results: Dict) -> Dict:
        """
        Format optimization results for dashboard consumption
        
        Args:
            results: Raw optimization results
            
        Returns:
            Formatted data for dashboard
        """
        summary = results.get('summary', {})
        
        formatted = {
            'timestamp': results.get('timestamp', datetime.now().isoformat()),
            'run_id': results.get('run_id', 'unknown'),
            'status': results.get('status', 'unknown'),
            'dry_run': results.get('dry_run', False),
            'duration_seconds': results.get('duration_seconds', 0),
            
            # Key metrics
            'metrics': {
                'campaigns_analyzed': summary.get('campaigns_analyzed', 0),
                'keywords_optimized': summary.get('keywords_optimized', 0),
                'bids_increased': summary.get('bids_increased', 0),
                'bids_decreased': summary.get('bids_decreased', 0),
                'negative_keywords_added': summary.get('negative_keywords_added', 0),
                'budget_changes': summary.get('budget_changes', 0),
                'total_spend': round(summary.get('total_spend', 0.0), 2),
                'total_sales': round(summary.get('total_sales', 0.0), 2),
                'average_acos': round(summary.get('average_acos', 0.0), 4)
            },
            
            # Feature-specific results
            'features': {}
        }
        
        # Extract feature results
        feature_keys = ['bid_optimization', 'campaign_management', 'keyword_discovery', 
                       'negative_keywords', 'dayparting']
        
        for feature in feature_keys:
            if feature in results.get('features', {}):
                formatted['features'][feature] = results['features'][feature]
        
        return formatted
    
    def _calculate_statistics(self, runs: List[Dict]) -> Dict:
        """
        Calculate aggregated statistics from historical runs
        
        Args:
            runs: List of historical run data
            
        Returns:
            Aggregated statistics
        """
        if not runs:
            return {}
        
        total_campaigns = 0
        total_keywords = 0
        total_spend = 0.0
        total_sales = 0.0
        successful_runs = 0
        
        for run in runs:
            if run.get('status') == 'success':
                successful_runs += 1
                metrics = run.get('metrics', {})
                total_campaigns += metrics.get('campaigns_analyzed', 0)
                total_keywords += metrics.get('keywords_optimized', 0)
                total_spend += metrics.get('total_spend', 0.0)
                total_sales += metrics.get('total_sales', 0.0)
        
        # Calculate average ACOS (Advertising Cost of Sales = Spend / Sales)
        avg_acos = (total_spend / total_sales) if total_sales > 0 else 0.0
        
        return {
            'total_runs': len(runs),
            'successful_runs': successful_runs,
            'total_campaigns_analyzed': total_campaigns,
            'total_keywords_optimized': total_keywords,
            'total_spend': round(total_spend, 2),
            'total_sales': round(total_sales, 2),
            'average_acos': round(avg_acos, 4),
            'last_30_days': {
                'runs': len(runs),
                'avg_campaigns_per_run': round(total_campaigns / len(runs), 1) if runs else 0,
                'avg_keywords_per_run': round(total_keywords / len(runs), 1) if runs else 0
            }
        }
    
    def _upload_to_github(self, data: Dict) -> bool:
        """
        Upload data to GitHub repository
        
        Args:
            data: Data to upload
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{self.data_path}"
        
        try:
            # Convert data to JSON string
            json_content = json.dumps(data, indent=2, ensure_ascii=False)
            
            # Encode content
            encoded_content = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')
            
            # Get current file SHA (required for updates)
            current_sha = self._get_file_sha()
            
            # Prepare commit message
            commit_message = f"Update PPC optimization data - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Build payload
            payload = {
                'message': commit_message,
                'content': encoded_content,
                'branch': self.branch
            }
            
            if current_sha:
                payload['sha'] = current_sha
            
            # Make request
            response = requests.put(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully uploaded data to {self.repo_owner}/{self.repo_name}")
                return True
            else:
                logger.error(f"GitHub API error: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error uploading to GitHub: {e}")
            return False
    
    def send_verification_status(self, verification_results: Dict) -> bool:
        """
        Send verification results to dashboard
        
        Args:
            verification_results: Verification results from VerificationSystem
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # Get current data
            current_data = self._get_current_data()
            
            # Add verification results
            current_data['last_verification'] = {
                'timestamp': datetime.now().isoformat(),
                'results': verification_results,
                'summary': verification_results.get('summary', {})
            }
            
            # Upload
            return self._upload_to_github(current_data)
            
        except Exception as e:
            logger.error(f"Error sending verification status: {e}")
            return False
    
    def get_dashboard_url(self) -> str:
        """Get the dashboard URL"""
        return self.dashboard_url
