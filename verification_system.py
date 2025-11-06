#!/usr/bin/env python3
"""
Verification System Module
===========================

Comprehensive verification system for Amazon PPC Optimizer that:
- Validates critical operations and data transformations
- Verifies API connections and responses
- Ensures data integrity throughout the pipeline
- Provides health checks for all integrations
- Logs verification results to audit trail

Author: Nature's Way Soil
Version: 1.0.0
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of a verification check"""
    check_name: str
    status: str  # 'passed', 'failed', 'warning'
    message: str
    timestamp: str
    details: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        result = {
            'check_name': self.check_name,
            'status': self.status,
            'message': self.message,
            'timestamp': self.timestamp
        }
        if self.details:
            result['details'] = self.details
        return result


class VerificationSystem:
    """
    Comprehensive verification system for the PPC Optimizer
    
    Features:
    - API connection verification
    - Data integrity checks
    - Calculation verification
    - Integration health checks
    - Audit trail integration
    """
    
    def __init__(self, audit_logger=None, config: Dict = None):
        """
        Initialize verification system
        
        Args:
            audit_logger: AuditLogger instance for recording verifications
            config: Configuration dictionary
        """
        self.audit_logger = audit_logger
        self.config = config or {}
        self.verification_results: List[VerificationResult] = []
    
    def verify_api_connection(self, api_client) -> VerificationResult:
        """
        Verify Amazon Ads API connection
        
        Args:
            api_client: AmazonAdsAPI instance
            
        Returns:
            VerificationResult with connection status
        """
        logger.info("Verifying Amazon Ads API connection...")
        start_time = time.time()
        
        try:
            # Test connection by fetching a small sample of campaigns
            result = api_client.verify_connection(sample_size=3)
            elapsed = time.time() - start_time
            
            if result.get('success'):
                verification = VerificationResult(
                    check_name='api_connection',
                    status='passed',
                    message=f'Successfully connected to Amazon Ads API ({elapsed:.2f}s)',
                    timestamp=datetime.now().isoformat(),
                    details={
                        'campaign_count': result.get('campaign_count', 0),
                        'sample_size': len(result.get('sample', [])),
                        'response_time_seconds': round(elapsed, 2)
                    }
                )
                logger.info(f"✓ API connection verified: {result.get('campaign_count', 0)} campaigns found")
            else:
                verification = VerificationResult(
                    check_name='api_connection',
                    status='failed',
                    message=f"API connection failed: {result.get('error', 'Unknown error')}",
                    timestamp=datetime.now().isoformat(),
                    details={'error': result.get('error')}
                )
                logger.error(f"✗ API connection failed: {result.get('error')}")
            
            self.verification_results.append(verification)
            
            if self.audit_logger:
                self.audit_logger.log(
                    'VERIFICATION_CHECK',
                    'API_CONNECTION',
                    'amazon_ads_api',
                    '',
                    verification.status,
                    verification.message,
                    dry_run=False
                )
            
            return verification
            
        except Exception as e:
            elapsed = time.time() - start_time
            verification = VerificationResult(
                check_name='api_connection',
                status='failed',
                message=f'API connection verification error: {str(e)}',
                timestamp=datetime.now().isoformat(),
                details={'error': str(e), 'elapsed_seconds': round(elapsed, 2)}
            )
            logger.error(f"✗ API connection verification failed: {e}")
            self.verification_results.append(verification)
            return verification
    
    def verify_bid_calculation(self, old_bid: float, new_bid: float, 
                               metrics: Dict, config: Dict) -> VerificationResult:
        """
        Verify bid calculation is within expected ranges
        
        Args:
            old_bid: Original bid amount
            new_bid: Calculated new bid amount
            metrics: Performance metrics used in calculation
            config: Bid optimization configuration
            
        Returns:
            VerificationResult with validation status
        """
        logger.debug(f"Verifying bid calculation: ${old_bid:.2f} -> ${new_bid:.2f}")
        
        min_bid = config.get('min_bid', 0.25)
        max_bid = config.get('max_bid', 5.0)
        max_change_pct = config.get('max_change_pct', 0.50)  # 50% max change
        
        issues = []
        
        # Check bid is within bounds
        if new_bid < min_bid:
            issues.append(f"New bid ${new_bid:.2f} below minimum ${min_bid:.2f}")
        if new_bid > max_bid:
            issues.append(f"New bid ${new_bid:.2f} above maximum ${max_bid:.2f}")
        
        # Check change percentage is reasonable
        if old_bid > 0:
            change_pct = abs((new_bid - old_bid) / old_bid)
            if change_pct > max_change_pct:
                issues.append(f"Bid change {change_pct:.1%} exceeds maximum {max_change_pct:.1%}")
        
        # Check for extreme values
        if new_bid <= 0:
            issues.append(f"Invalid bid amount: ${new_bid:.2f}")
        
        if issues:
            status = 'warning' if new_bid >= min_bid and new_bid <= max_bid else 'failed'
            verification = VerificationResult(
                check_name='bid_calculation',
                status=status,
                message=f"Bid calculation issues: {', '.join(issues)}",
                timestamp=datetime.now().isoformat(),
                details={
                    'old_bid': old_bid,
                    'new_bid': new_bid,
                    'metrics': metrics,
                    'issues': issues
                }
            )
        else:
            verification = VerificationResult(
                check_name='bid_calculation',
                status='passed',
                message=f"Bid calculation valid: ${old_bid:.2f} -> ${new_bid:.2f}",
                timestamp=datetime.now().isoformat(),
                details={
                    'old_bid': old_bid,
                    'new_bid': new_bid,
                    'change_pct': abs((new_bid - old_bid) / old_bid) if old_bid > 0 else 0
                }
            )
        
        self.verification_results.append(verification)
        return verification
    
    def verify_data_integrity(self, data: Dict, required_fields: List[str],
                             data_type: str = 'generic') -> VerificationResult:
        """
        Verify data has required fields and valid values
        
        Args:
            data: Data dictionary to verify
            required_fields: List of required field names
            data_type: Type of data being verified (for logging)
            
        Returns:
            VerificationResult with validation status
        """
        logger.debug(f"Verifying data integrity for {data_type}")
        
        missing_fields = []
        invalid_values = []
        
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
            elif data[field] is None:
                invalid_values.append(f"{field} is None")
        
        if missing_fields or invalid_values:
            issues = []
            if missing_fields:
                issues.append(f"Missing fields: {', '.join(missing_fields)}")
            if invalid_values:
                issues.append(f"Invalid values: {', '.join(invalid_values)}")
            
            verification = VerificationResult(
                check_name='data_integrity',
                status='failed',
                message=f"Data integrity issues for {data_type}: {'; '.join(issues)}",
                timestamp=datetime.now().isoformat(),
                details={
                    'data_type': data_type,
                    'missing_fields': missing_fields,
                    'invalid_values': invalid_values
                }
            )
            logger.warning(f"⚠ Data integrity issues for {data_type}: {'; '.join(issues)}")
        else:
            verification = VerificationResult(
                check_name='data_integrity',
                status='passed',
                message=f"Data integrity verified for {data_type}",
                timestamp=datetime.now().isoformat(),
                details={
                    'data_type': data_type,
                    'field_count': len(required_fields)
                }
            )
            logger.debug(f"✓ Data integrity verified for {data_type}")
        
        self.verification_results.append(verification)
        return verification
    
    def verify_bigquery_connection(self, bigquery_client) -> VerificationResult:
        """
        Verify BigQuery connection and dataset access
        
        Args:
            bigquery_client: BigQueryClient instance
            
        Returns:
            VerificationResult with connection status
        """
        logger.info("Verifying BigQuery connection...")
        
        try:
            # Try to get dataset to verify connection
            dataset_ref = f"{bigquery_client.project_id}.{bigquery_client.dataset_id}"
            dataset = bigquery_client.client.get_dataset(dataset_ref)
            
            verification = VerificationResult(
                check_name='bigquery_connection',
                status='passed',
                message=f'BigQuery connection verified: {dataset_ref}',
                timestamp=datetime.now().isoformat(),
                details={
                    'project_id': bigquery_client.project_id,
                    'dataset_id': bigquery_client.dataset_id,
                    'location': bigquery_client.location
                }
            )
            logger.info(f"✓ BigQuery connection verified: {dataset_ref}")
            
            self.verification_results.append(verification)
            
            if self.audit_logger:
                self.audit_logger.log(
                    'VERIFICATION_CHECK',
                    'BIGQUERY_CONNECTION',
                    dataset_ref,
                    '',
                    'passed',
                    'BigQuery connection verified',
                    dry_run=False
                )
            
            return verification
            
        except Exception as e:
            verification = VerificationResult(
                check_name='bigquery_connection',
                status='failed',
                message=f'BigQuery connection failed: {str(e)}',
                timestamp=datetime.now().isoformat(),
                details={'error': str(e)}
            )
            logger.error(f"✗ BigQuery connection failed: {e}")
            self.verification_results.append(verification)
            return verification
    
    def verify_dashboard_connection(self, dashboard_client) -> VerificationResult:
        """
        Verify dashboard API connection
        
        Args:
            dashboard_client: DashboardClient instance
            
        Returns:
            VerificationResult with connection status
        """
        logger.info("Verifying dashboard connection...")
        
        try:
            if not dashboard_client.enabled:
                verification = VerificationResult(
                    check_name='dashboard_connection',
                    status='warning',
                    message='Dashboard integration is disabled',
                    timestamp=datetime.now().isoformat(),
                    details={'enabled': False}
                )
                logger.warning("⚠ Dashboard integration is disabled")
                self.verification_results.append(verification)
                return verification
            
            # Test health check endpoint
            is_healthy = dashboard_client.health_check()
            
            if is_healthy:
                verification = VerificationResult(
                    check_name='dashboard_connection',
                    status='passed',
                    message=f'Dashboard connection verified: {dashboard_client.url}',
                    timestamp=datetime.now().isoformat(),
                    details={
                        'url': dashboard_client.url,
                        'enabled': True
                    }
                )
                logger.info(f"✓ Dashboard connection verified: {dashboard_client.url}")
            else:
                verification = VerificationResult(
                    check_name='dashboard_connection',
                    status='failed',
                    message=f'Dashboard health check failed: {dashboard_client.url}',
                    timestamp=datetime.now().isoformat(),
                    details={
                        'url': dashboard_client.url,
                        'enabled': True
                    }
                )
                logger.error(f"✗ Dashboard health check failed: {dashboard_client.url}")
            
            self.verification_results.append(verification)
            
            if self.audit_logger:
                self.audit_logger.log(
                    'VERIFICATION_CHECK',
                    'DASHBOARD_CONNECTION',
                    dashboard_client.url,
                    '',
                    verification.status,
                    verification.message,
                    dry_run=False
                )
            
            return verification
            
        except Exception as e:
            verification = VerificationResult(
                check_name='dashboard_connection',
                status='failed',
                message=f'Dashboard verification error: {str(e)}',
                timestamp=datetime.now().isoformat(),
                details={'error': str(e)}
            )
            logger.error(f"✗ Dashboard verification failed: {e}")
            self.verification_results.append(verification)
            return verification
    
    def run_all_verifications(self, api_client=None, bigquery_client=None,
                             dashboard_client=None) -> Dict[str, Any]:
        """
        Run all verification checks
        
        Args:
            api_client: Optional AmazonAdsAPI instance
            bigquery_client: Optional BigQueryClient instance
            dashboard_client: Optional DashboardClient instance
            
        Returns:
            Summary of all verification results
        """
        logger.info("=" * 80)
        logger.info("RUNNING COMPREHENSIVE VERIFICATION CHECKS")
        logger.info("=" * 80)
        
        start_time = time.time()
        results = {
            'timestamp': datetime.now().isoformat(),
            'checks': [],
            'summary': {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        }
        
        # Run API verification
        if api_client:
            result = self.verify_api_connection(api_client)
            results['checks'].append(result.to_dict())
        
        # Run BigQuery verification
        if bigquery_client:
            result = self.verify_bigquery_connection(bigquery_client)
            results['checks'].append(result.to_dict())
        
        # Run Dashboard verification
        if dashboard_client:
            result = self.verify_dashboard_connection(dashboard_client)
            results['checks'].append(result.to_dict())
        
        # Calculate summary
        for check in results['checks']:
            results['summary']['total'] += 1
            if check['status'] == 'passed':
                results['summary']['passed'] += 1
            elif check['status'] == 'failed':
                results['summary']['failed'] += 1
            elif check['status'] == 'warning':
                results['summary']['warnings'] += 1
        
        elapsed = time.time() - start_time
        results['duration_seconds'] = round(elapsed, 2)
        
        # Log summary
        logger.info("=" * 80)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Checks: {results['summary']['total']}")
        logger.info(f"✓ Passed: {results['summary']['passed']}")
        logger.info(f"✗ Failed: {results['summary']['failed']}")
        logger.info(f"⚠ Warnings: {results['summary']['warnings']}")
        logger.info(f"Duration: {elapsed:.2f}s")
        logger.info("=" * 80)
        
        return results
    
    def get_verification_report(self) -> str:
        """
        Generate human-readable verification report
        
        Returns:
            Formatted verification report
        """
        report_lines = [
            "=" * 80,
            "VERIFICATION REPORT",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Total Checks: {len(self.verification_results)}",
            ""
        ]
        
        for result in self.verification_results:
            status_symbol = {
                'passed': '✓',
                'failed': '✗',
                'warning': '⚠'
            }.get(result.status, '?')
            
            report_lines.append(f"{status_symbol} {result.check_name}: {result.message}")
            if result.details:
                for key, value in result.details.items():
                    report_lines.append(f"    {key}: {value}")
            report_lines.append("")
        
        report_lines.extend([
            "=" * 80,
            ""
        ])
        
        return '\n'.join(report_lines)
