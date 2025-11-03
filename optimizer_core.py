#!/usr/bin/env python3
"""
Amazon PPC Automation Suite
===========================

Comprehensive Amazon Advertising API automation script that includes:
- Bid optimization based on performance metrics
- Dayparting (time-based bid adjustments)
- Campaign management (activate/deactivate based on ACOS)
- Keyword discovery and automatic addition
- New campaign creation for products without campaigns
- Negative keyword management
- Budget optimization
- Match type progression
- Placement bid adjustments

Author: Nature's Way Soil
Version: 2.0.0
License: MIT

Setup:
    export AMAZON_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
    export AMAZON_CLIENT_SECRET="xxxxxxxx"
    export AMAZON_REFRESH_TOKEN="Atzr|IwEBxxxxxxxx"
    
Usage:
    python optimizer_core.py --config ppc_config.yaml --profile-id 1780498399290938
    python optimizer_core.py --config ppc_config.yaml --profile-id 1780498399290938 --dry-run
    python optimizer_core.py --config ppc_config.yaml --profile-id 1780498399290938 \
        --features bid_optimization dayparting
    python optimizer_core.py --config ppc_config.yaml --verify-connection --verify-sample-size 10
"""

import argparse
import csv
import io
import json
import logging
import os
import sys
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import traceback

import requests

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(1)

try:
    import pytz
except ImportError:
    print("WARNING: pytz is not installed. Dayparting will use server timezone (UTC).")
    print("Install with: pip install pytz")
    pytz = None

# ============================================================================
# CONSTANTS
# ============================================================================

ENDPOINTS = {
    "NA": "https://advertising-api.amazon.com",
    "EU": "https://advertising-api-eu.amazon.com",
    "FE": "https://advertising-api-fe.amazon.com",
}

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
USER_AGENT = "NWS-PPC-Automation/2.0"

# Rate limiting - Amazon Advertising API supports 10 requests/second
MAX_REQUESTS_PER_SECOND = 10
REQUEST_INTERVAL = 1.0 / MAX_REQUESTS_PER_SECOND

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'ppc_automation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Auth:
    """Authentication credentials"""
    access_token: str
    token_type: str
    expires_at: float

    def is_expired(self) -> bool:
        return time.time() > self.expires_at - 60


@dataclass
class Campaign:
    """Campaign data structure"""
    campaign_id: str
    name: str
    state: str
    daily_budget: float
    targeting_type: str
    campaign_type: str = "sponsoredProducts"
    
    
@dataclass
class AdGroup:
    """Ad Group data structure"""
    ad_group_id: str
    campaign_id: str
    name: str
    state: str
    default_bid: float


@dataclass
class Keyword:
    """Keyword data structure"""
    keyword_id: str
    ad_group_id: str
    campaign_id: str
    keyword_text: str
    match_type: str
    state: str
    bid: float


@dataclass
class PerformanceMetrics:
    """Performance metrics for keywords/campaigns"""
    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0
    sales: float = 0.0
    orders: int = 0
    
    @property
    def ctr(self) -> float:
        return (self.clicks / self.impressions) if self.impressions > 0 else 0.0
    
    @property
    def acos(self) -> float:
        return (self.cost / self.sales) if self.sales > 0 else float('inf')
    
    @property
    def roas(self) -> float:
        return (self.sales / self.cost) if self.cost > 0 else 0.0
    
    @property
    def cpc(self) -> float:
        return (self.cost / self.clicks) if self.clicks > 0 else 0.0


@dataclass
class AuditEntry:
    """Audit trail entry"""
    timestamp: str
    action_type: str
    entity_type: str
    entity_id: str
    old_value: str
    new_value: str
    reason: str
    dry_run: bool


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Rate limiter for API calls with burst support"""
    
    def __init__(self, max_per_second: int = MAX_REQUESTS_PER_SECOND, burst_size: int = 3):
        self.max_per_second = max_per_second
        self.interval = 1.0 / max_per_second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_update_time = time.time()
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits with token bucket algorithm"""
        current_time = time.time()
        time_elapsed = current_time - self.last_update_time
        
        # Refill tokens based on time elapsed
        self.tokens = min(self.burst_size, self.tokens + time_elapsed * self.max_per_second)
        self.last_update_time = current_time
        
        # If no tokens available, wait
        if self.tokens < 1:
            sleep_time = (1 - self.tokens) / self.max_per_second
            time.sleep(sleep_time)
            self.tokens = 1
        
        # Consume one token
        self.tokens -= 1


# ============================================================================
# PERFORMANCE TIMING DECORATOR
# ============================================================================

def timing_logger(operation_name: str = None):
    """Decorator to log execution time of operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()
            logger.info(f"Starting {op_name}...")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"✓ {op_name} completed in {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"✗ {op_name} failed after {elapsed:.2f}s: {e}")
                raise
        return wrapper
    return decorator


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================

class Config:
    """Configuration manager"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.data = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    
    def get(self, key: str, default=None):
        """Get configuration value with dot notation support"""
        keys = key.split('.')
        value = self.data
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default


# ============================================================================
# AUDIT LOGGER
# ============================================================================

class AuditLogger:
    """CSV-based audit trail logger"""

    def __init__(self, output_dir: str = "."):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.filename = os.path.join(
            output_dir,
            f"ppc_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        self.entries: List[AuditEntry] = []
    
    def log(self, action_type: str, entity_type: str, entity_id: str,
            old_value: str, new_value: str, reason: str, dry_run: bool = False):
        """Log an audit entry"""
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            dry_run=dry_run
        )
        self.entries.append(entry)
    
    def save(self):
        """Save audit trail to CSV"""
        if not self.entries:
            logger.info("No audit entries to save")
            return
        
        try:
            with open(self.filename, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['timestamp', 'action_type', 'entity_type', 'entity_id',
                             'old_value', 'new_value', 'reason', 'dry_run']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for entry in self.entries:
                    writer.writerow({
                        'timestamp': entry.timestamp,
                        'action_type': entry.action_type,
                        'entity_type': entry.entity_type,
                        'entity_id': entry.entity_id,
                        'old_value': entry.old_value,
                        'new_value': entry.new_value,
                        'reason': entry.reason,
                        'dry_run': entry.dry_run
                    })
            
            logger.info(f"Audit trail saved to {self.filename} ({len(self.entries)} entries)")
        except Exception as e:
            logger.error(f"Failed to save audit trail: {e}")


# ============================================================================
# AMAZON ADS API CLIENT
# ============================================================================

class AmazonAdsAPI:
    """Amazon Advertising API client with retry logic and rate limiting"""
    
    def __init__(self, profile_id: str, region: str = "NA", max_requests_per_second: int = None, 
                 session: requests.Session = None):
        self.profile_id = profile_id
        self.region = region.upper()
        self.base_url = ENDPOINTS.get(self.region, ENDPOINTS["NA"])
        self.auth = self._authenticate()
        self.rate_limiter = RateLimiter(max_requests_per_second or MAX_REQUESTS_PER_SECOND)
        self.session = session or requests.Session()
        # Cache for campaigns and ad groups (lifetime of API instance)
        self._campaigns_cache = None
        self._ad_groups_cache = None
    
    def _authenticate(self) -> Auth:
        """Authenticate and get access token"""
        client_id = os.getenv("AMAZON_CLIENT_ID")
        client_secret = os.getenv("AMAZON_CLIENT_SECRET")
        refresh_token = os.getenv("AMAZON_REFRESH_TOKEN")
        
        if not all([client_id, client_secret, refresh_token]):
            logger.error("Missing required environment variables")
            sys.exit(1)
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        
        try:
            response = requests.post(TOKEN_URL, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            auth = Auth(
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_at=time.time() + int(data.get("expires_in", 3600))
            )
            logger.info("Successfully authenticated with Amazon Ads API")
            return auth
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            sys.exit(1)
    
    def _refresh_auth_if_needed(self):
        """Refresh authentication if token expired"""
        if self.auth.is_expired():
            logger.info("Access token expired, refreshing...")
            self.auth = self._authenticate()

    def _headers(self) -> Dict[str, str]:
        """Get API request headers"""
        self._refresh_auth_if_needed()

        return {
            "Authorization": f"{self.auth.token_type} {self.auth.access_token}",
            "Content-Type": "application/json",
            "Amazon-Advertising-API-ClientId": self.client_id,
            "Amazon-Advertising-API-Scope": self.profile_id,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make API request with retry logic and rate limiting using connection pooling"""
        self.rate_limiter.wait_if_needed()
        
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=self._headers(),
                    timeout=30,
                    **kwargs
                )
                
                if response.status_code == 429:  # Rate limit
                    retry_after = int(response.headers.get('Retry-After', retry_delay * (attempt + 1)))
                    logger.warning(f"Rate limit hit, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.HTTPError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay * (attempt + 1))
        
        raise Exception("Max retries exceeded")

    def verify_connection(self, sample_size: int = 5) -> Dict[str, Any]:
        """Verify API connectivity by retrieving a small campaign sample"""

        try:
            response = self._request(
                "GET",
                "/v2/sp/campaigns",
                params={"startIndex": 0, "count": max(sample_size, 1)}
            )
            campaigns = response.json() or []

            sample = []
            for entry in campaigns[:sample_size]:
                sample.append(
                    {
                        "campaignId": entry.get("campaignId"),
                        "name": entry.get("name"),
                        "state": entry.get("state"),
                        "dailyBudget": entry.get("dailyBudget"),
                    }
                )

            result = {
                "success": True,
                "campaign_count": len(campaigns),
                "sample": sample,
            }
            logger.info(
                "Amazon Ads API connectivity verified. Retrieved %d campaigns.",
                result["campaign_count"],
            )
            return result
        except Exception as exc:
            logger.error(f"Amazon Ads API verification failed: {exc}")
            return {
                "success": False,
                "error": str(exc),
            }
    
    # ========================================================================
    # CAMPAIGNS
    # ========================================================================
    
    def get_campaigns(self, state_filter: str = None, use_cache: bool = True) -> List[Campaign]:
        """Get all campaigns with caching support"""
        # Use cache if available and no state filter
        if use_cache and self._campaigns_cache is not None and state_filter is None:
            logger.debug(f"Using cached campaigns ({len(self._campaigns_cache)} items)")
            return self._campaigns_cache
        
        try:
            params = {}
            if state_filter:
                params['stateFilter'] = state_filter
            
            response = self._request('GET', '/v2/sp/campaigns', params=params)
            campaigns_data = response.json()
            
            campaigns = []
            for c in campaigns_data:
                campaign = Campaign(
                    campaign_id=str(c.get('campaignId')),
                    name=c.get('name', ''),
                    state=c.get('state', ''),
                    daily_budget=float(c.get('dailyBudget', 0)),
                    targeting_type=c.get('targetingType', ''),
                    campaign_type='sponsoredProducts'
                )
                campaigns.append(campaign)
            
            logger.info(f"Retrieved {len(campaigns)} campaigns")
            
            # Cache if no state filter
            if state_filter is None:
                self._campaigns_cache = campaigns
            
            return campaigns
        except Exception as e:
            logger.error(f"Failed to get campaigns: {e}")
            return []
    
    def invalidate_campaigns_cache(self):
        """Invalidate campaigns cache after updates"""
        self._campaigns_cache = None
    
    def update_campaign(self, campaign_id: str, updates: Dict) -> bool:
        """Update campaign settings"""
        try:
            response = self._request(
                'PUT',
                f'/v2/sp/campaigns/{campaign_id}',
                json=updates
            )
            logger.info(f"Updated campaign {campaign_id}")
            self.invalidate_campaigns_cache()  # Invalidate cache after update
            return True
        except Exception as e:
            logger.error(f"Failed to update campaign {campaign_id}: {e}")
            return False
    
    def create_campaign(self, campaign_data: Dict) -> Optional[str]:
        """Create new campaign"""
        try:
            response = self._request('POST', '/v2/sp/campaigns', json=[campaign_data])
            result = response.json()
            
            if result and len(result) > 0:
                campaign_id = result[0].get('campaignId')
                logger.info(f"Created campaign: {campaign_id}")
                return str(campaign_id)
            return None
        except Exception as e:
            logger.error(f"Failed to create campaign: {e}")
            return None
    
    # ========================================================================
    # AD GROUPS
    # ========================================================================
    
    def get_ad_groups(self, campaign_id: str = None, use_cache: bool = True) -> List[AdGroup]:
        """Get ad groups with caching support"""
        # Use cache if available and no campaign_id filter
        if use_cache and self._ad_groups_cache is not None and campaign_id is None:
            logger.debug(f"Using cached ad groups ({len(self._ad_groups_cache)} items)")
            return self._ad_groups_cache
        
        try:
            params = {}
            if campaign_id:
                params['campaignIdFilter'] = campaign_id
            
            response = self._request('GET', '/v2/sp/adGroups', params=params)
            ad_groups_data = response.json()
            
            ad_groups = []
            for ag in ad_groups_data:
                ad_group = AdGroup(
                    ad_group_id=str(ag.get('adGroupId')),
                    campaign_id=str(ag.get('campaignId')),
                    name=ag.get('name', ''),
                    state=ag.get('state', ''),
                    default_bid=float(ag.get('defaultBid', 0))
                )
                ad_groups.append(ad_group)
            
            logger.info(f"Retrieved {len(ad_groups)} ad groups")
            
            # Cache if no campaign_id filter
            if campaign_id is None:
                self._ad_groups_cache = ad_groups
            
            return ad_groups
        except Exception as e:
            logger.error(f"Failed to get ad groups: {e}")
            return []
    
    def invalidate_ad_groups_cache(self):
        """Invalidate ad groups cache after updates"""
        self._ad_groups_cache = None
    
    def create_ad_group(self, ad_group_data: Dict) -> Optional[str]:
        """Create new ad group"""
        try:
            response = self._request('POST', '/v2/sp/adGroups', json=[ad_group_data])
            result = response.json()
            
            if result and len(result) > 0:
                ad_group_id = result[0].get('adGroupId')
                logger.info(f"Created ad group: {ad_group_id}")
                return str(ad_group_id)
            return None
        except Exception as e:
            logger.error(f"Failed to create ad group: {e}")
            return None
    
    # ========================================================================
    # KEYWORDS
    # ========================================================================
    
    def get_keywords(self, campaign_id: str = None, ad_group_id: str = None) -> List[Keyword]:
        """Get keywords"""
        try:
            params = {}
            if campaign_id:
                params['campaignIdFilter'] = campaign_id
            if ad_group_id:
                params['adGroupIdFilter'] = ad_group_id
            
            response = self._request('GET', '/v2/sp/keywords', params=params)
            keywords_data = response.json()
            
            keywords = []
            for kw in keywords_data:
                keyword = Keyword(
                    keyword_id=str(kw.get('keywordId')),
                    ad_group_id=str(kw.get('adGroupId')),
                    campaign_id=str(kw.get('campaignId')),
                    keyword_text=kw.get('keywordText', ''),
                    match_type=kw.get('matchType', ''),
                    state=kw.get('state', ''),
                    bid=float(kw.get('bid', 0))
                )
                keywords.append(keyword)
            
            logger.info(f"Retrieved {len(keywords)} keywords")
            return keywords
        except Exception as e:
            logger.error(f"Failed to get keywords: {e}")
            return []
    
    def update_keyword_bid(self, keyword_id: str, bid: float, state: str = None) -> bool:
        """Update keyword bid (single keyword - consider using batch_update_keywords for multiple updates)"""
        try:
            updates = {'keywordId': int(keyword_id), 'bid': round(bid, 2)}
            if state:
                updates['state'] = state
            
            response = self._request('PUT', '/v2/sp/keywords', json=[updates])
            logger.debug(f"Updated keyword {keyword_id} bid to ${bid:.2f}")
            return True
        except Exception as e:
            logger.error(f"Failed to update keyword {keyword_id}: {e}")
            return False
    
    def batch_update_keywords(self, updates: List[Dict]) -> Dict:
        """Batch update keywords (up to 100 at a time)"""
        results = {
            'total': len(updates),
            'success': 0,
            'failed': 0
        }
        
        batch_size = 100
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            try:
                response = self._request('PUT', '/v2/sp/keywords', json=batch)
                result = response.json()
                
                for r in result:
                    if r.get('code') == 'SUCCESS':
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                        logger.warning(f"Failed to update keyword {r.get('keywordId')}: {r.get('details')}")
                
                logger.info(f"Batch updated {len(batch)} keywords (batch {i//batch_size + 1})")
            except Exception as e:
                logger.error(f"Failed to batch update keywords: {e}")
                results['failed'] += len(batch)
        
        logger.info(f"Batch update complete: {results['success']}/{results['total']} successful")
        return results
    
    def create_keywords(self, keywords_data: List[Dict]) -> List[str]:
        """Create new keywords"""
        try:
            response = self._request('POST', '/v2/sp/keywords', json=keywords_data)
            result = response.json()
            
            created_ids = []
            for r in result:
                if r.get('code') == 'SUCCESS':
                    created_ids.append(str(r.get('keywordId')))
            
            logger.info(f"Created {len(created_ids)} keywords")
            return created_ids
        except Exception as e:
            logger.error(f"Failed to create keywords: {e}")
            return []
    
    # ========================================================================
    # NEGATIVE KEYWORDS
    # ========================================================================
    
    def get_negative_keywords(self, campaign_id: str = None) -> List[Dict]:
        """Get negative keywords"""
        try:
            params = {}
            if campaign_id:
                params['campaignIdFilter'] = campaign_id
            
            response = self._request('GET', '/v2/sp/negativeKeywords', params=params)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get negative keywords: {e}")
            return []
    
    def create_negative_keywords(self, negative_keywords_data: List[Dict]) -> List[str]:
        """Create negative keywords"""
        try:
            response = self._request('POST', '/v2/sp/negativeKeywords', json=negative_keywords_data)
            result = response.json()
            
            created_ids = []
            for r in result:
                if r.get('code') == 'SUCCESS':
                    created_ids.append(str(r.get('keywordId')))
            
            logger.info(f"Created {len(created_ids)} negative keywords")
            return created_ids
        except Exception as e:
            logger.error(f"Failed to create negative keywords: {e}")
            return []
    
    # ========================================================================
    # REPORTS
    # ========================================================================
    
    def create_report(self, report_type: str, metrics: List[str], 
                     report_date: str = None, segment: str = None) -> Optional[str]:
        """Create performance report"""
        try:
            if report_date is None:
                report_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
            
            payload = {
                'reportDate': report_date,
                'metrics': ','.join(metrics)
            }
            
            if segment:
                payload['segment'] = segment
            
            endpoint = f'/v2/sp/{report_type}/report'
            response = self._request('POST', endpoint, json=payload)
            report_id = response.json().get('reportId')
            
            logger.info(f"Created report {report_id} (type: {report_type})")
            return report_id
        except Exception as e:
            logger.error(f"Failed to create report: {e}")
            return None
    
    def get_report_status(self, report_id: str) -> Dict:
        """Get report status"""
        try:
            response = self._request('GET', f'/v2/reports/{report_id}')
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get report status: {e}")
            return {}
    
    def download_report(self, report_url: str) -> List[Dict]:
        """Download and parse report"""
        try:
            response = requests.get(report_url, timeout=60)
            response.raise_for_status()
            
            # Try to decompress as gzip or zip
            content = response.content
            
            try:
                # Try ZIP format first
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    names = z.namelist()
                    with z.open(names[0]) as f:
                        text = io.TextIOWrapper(f, encoding='utf-8', newline='')
                        return list(csv.DictReader(text))
            except zipfile.BadZipFile:
                # Try GZIP format
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                        text = io.TextIOWrapper(gz, encoding='utf-8', newline='')
                        return list(csv.DictReader(text))
                except Exception:
                    # Try as plain text
                    text = io.StringIO(content.decode('utf-8'))
                    return list(csv.DictReader(text))
        except Exception as e:
            logger.error(f"Failed to download report: {e}")
            return []
    
    def wait_for_report(self, report_id: str, timeout: int = 300) -> Optional[str]:
        """Wait for report to be ready with adaptive polling (exponential backoff)"""
        start_time = time.time()
        poll_interval = 2  # Start with 2 seconds
        max_poll_interval = 10  # Cap at 10 seconds
        
        while time.time() - start_time < timeout:
            status_data = self.get_report_status(report_id)
            status = status_data.get('status')
            
            if status == 'SUCCESS':
                elapsed = time.time() - start_time
                logger.info(f"Report {report_id} ready in {elapsed:.1f}s")
                return status_data.get('location')
            elif status in ['FAILURE', 'CANCELLED']:
                logger.error(f"Report {report_id} failed: {status}")
                return None
            
            # Adaptive polling: gradually increase wait time
            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, max_poll_interval)
        
        logger.error(f"Report {report_id} timeout after {timeout}s")
        return None
    
    def create_and_download_reports_parallel(self, report_configs: List[Dict], 
                                            max_workers: int = 3) -> Dict[str, List[Dict]]:
        """
        Create multiple reports and download them in parallel for faster processing.
        
        Args:
            report_configs: List of dicts with 'name', 'report_type', 'metrics', etc.
            max_workers: Number of parallel workers (default 3 to avoid rate limits)
            
        Returns:
            Dict mapping report names to their downloaded data
        """
        start_time = time.time()
        logger.info(f"Creating {len(report_configs)} reports in parallel...")
        
        # Step 1: Create all reports
        report_ids = {}
        for config in report_configs:
            name = config.get('name', 'unnamed')
            report_id = self.create_report(
                report_type=config['report_type'],
                metrics=config['metrics'],
                report_date=config.get('report_date'),
                segment=config.get('segment')
            )
            if report_id:
                report_ids[name] = report_id
                logger.info(f"Created report '{name}': {report_id}")
        
        if not report_ids:
            logger.error("No reports were created successfully")
            return {}
        
        # Step 2: Wait for all reports in parallel using ThreadPoolExecutor
        logger.info(f"Waiting for {len(report_ids)} reports in parallel...")
        report_urls = {}
        
        def wait_for_single_report(name_and_id):
            name, report_id = name_and_id
            url = self.wait_for_report(report_id)
            return name, url
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(wait_for_single_report, (name, rid)): name 
                for name, rid in report_ids.items()
            }
            
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result_name, url = future.result()
                    if url:
                        report_urls[result_name] = url
                        logger.info(f"Report '{result_name}' ready for download")
                except Exception as e:
                    logger.error(f"Error waiting for report '{name}': {e}")
        
        # Step 3: Download all reports in parallel
        logger.info(f"Downloading {len(report_urls)} reports in parallel...")
        results = {}
        
        def download_single_report(name_and_url):
            name, url = name_and_url
            data = self.download_report(url)
            return name, data
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(download_single_report, (name, url)): name 
                for name, url in report_urls.items()
            }
            
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result_name, data = future.result()
                    results[result_name] = data
                    logger.info(f"Downloaded report '{result_name}': {len(data)} records")
                except Exception as e:
                    logger.error(f"Error downloading report '{name}': {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"Parallel report processing complete in {elapsed:.1f}s (saved ~{len(report_configs)*5-elapsed:.1f}s)")
        
        return results
    
    # ========================================================================
    # KEYWORD SUGGESTIONS
    # ========================================================================
    
    def get_keyword_suggestions(self, asin: str, max_suggestions: int = 100) -> List[Dict]:
        """Get keyword suggestions for ASIN"""
        try:
            # Use keyword recommendations endpoint
            payload = {
                'asins': [asin],
                'maxRecommendations': max_suggestions
            }
            
            response = self._request('POST', '/v2/sp/targets/keywords/recommendations', json=payload)
            recommendations = response.json()
            
            suggested_keywords = []
            if 'recommendations' in recommendations:
                for rec in recommendations['recommendations']:
                    suggested_keywords.append({
                        'keyword': rec.get('keyword', ''),
                        'match_type': rec.get('matchType', 'broad'),
                        'suggested_bid': rec.get('bid', 0.5)
                    })
            
            logger.info(f"Retrieved {len(suggested_keywords)} keyword suggestions for ASIN {asin}")
            return suggested_keywords
        except Exception as e:
            logger.error(f"Failed to get keyword suggestions: {e}")
            return []


# ============================================================================
# AUTOMATION FEATURES
# ============================================================================

class BidOptimizer:
    """Bid optimization based on performance metrics"""
    
    def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger):
        self.config = config
        self.api = api
        self.audit = audit_logger
    
    def optimize(self, dry_run: bool = False) -> Dict:
        """Run bid optimization with performance timing"""
        start_time = time.time()
        logger.info("=== Starting Bid Optimization ===")
        
        results = {
            'keywords_analyzed': 0,
            'bids_increased': 0,
            'bids_decreased': 0,
            'no_change': 0
        }
        
        # Get performance data
        lookback_days = self.config.get('bid_optimization.lookback_days', 14)
        report_id = self.api.create_report(
            'keywords',
            ['campaignId', 'adGroupId', 'keywordId', 'impressions', 'clicks', 
             'cost', 'attributedSales14d', 'attributedConversions14d'],
            report_date=(datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        )
        
        if not report_id:
            logger.error("Failed to create performance report")
            return results
        
        report_url = self.api.wait_for_report(report_id)
        if not report_url:
            logger.error("Failed to get report data")
            return results
        
        report_data = self.api.download_report(report_url)
        
        # Process keywords in batches to optimize memory usage
        batch_size = 100
        keyword_updates = []  # Collect all updates for batch processing
        
        # Get current keywords
        keywords = self.api.get_keywords()
        keyword_map = {kw.keyword_id: kw for kw in keywords}
        
        logger.info(f"Processing {len(report_data)} performance records in batches of {batch_size}")
        
        # Analyze each keyword
        for idx, row in enumerate(report_data):
            keyword_id = row.get('keywordId')
            if not keyword_id or keyword_id not in keyword_map:
                continue
            
            results['keywords_analyzed'] += 1
            keyword = keyword_map[keyword_id]
            
            # Calculate metrics
            metrics = PerformanceMetrics(
                impressions=int(row.get('impressions', 0) or 0),
                clicks=int(row.get('clicks', 0) or 0),
                cost=float(row.get('cost', 0) or 0),
                sales=float(row.get('attributedSales14d', 0) or 0),
                orders=int(row.get('attributedConversions14d', 0) or 0)
            )
            
            # Determine bid change
            new_bid = self._calculate_new_bid(keyword, metrics)
            
            if new_bid and abs(new_bid - keyword.bid) > 0.01:
                reason = self._get_bid_change_reason(keyword, metrics, new_bid)
                
                if new_bid > keyword.bid:
                    results['bids_increased'] += 1
                else:
                    results['bids_decreased'] += 1
                
                self.audit.log(
                    'BID_UPDATE',
                    'KEYWORD',
                    keyword_id,
                    f"${keyword.bid:.2f}",
                    f"${new_bid:.2f}",
                    reason,
                    dry_run
                )
                
                # Collect updates for batch processing
                keyword_updates.append({
                    'keywordId': int(keyword_id),
                    'bid': round(new_bid, 2)
                })
            else:
                results['no_change'] += 1
            
            # Log progress every batch_size records
            if (idx + 1) % batch_size == 0:
                logger.info(f"Processed {idx + 1}/{len(report_data)} records...")
        
        # Apply batch updates
        if keyword_updates and not dry_run:
            logger.info(f"Applying {len(keyword_updates)} bid updates in batches...")
            batch_results = self.api.batch_update_keywords(keyword_updates)
            logger.info(f"Batch update results: {batch_results}")
        
        elapsed = time.time() - start_time
        logger.info(f"Bid optimization complete in {elapsed:.2f}s: {results}")
        results['execution_time_seconds'] = round(elapsed, 2)
        return results
    
    def _calculate_new_bid(self, keyword: Keyword, metrics: PerformanceMetrics) -> Optional[float]:
        """Calculate new bid based on performance"""
        # Get thresholds from config
        min_clicks = self.config.get('bid_optimization.min_clicks', 25)
        min_spend = self.config.get('bid_optimization.min_spend', 5.0)
        target_acos = self.config.get('bid_optimization.target_acos', 0.45)
        high_acos = self.config.get('bid_optimization.high_acos', 0.60)
        low_acos = self.config.get('bid_optimization.low_acos', 0.25)
        up_pct = self.config.get('bid_optimization.up_pct', 0.15)
        down_pct = self.config.get('bid_optimization.down_pct', 0.20)
        min_bid = self.config.get('bid_optimization.min_bid', 0.25)
        max_bid = self.config.get('bid_optimization.max_bid', 5.0)
        
        # Check if we have enough data
        if metrics.clicks < min_clicks and metrics.cost < min_spend:
            return None
        
        current_bid = keyword.bid
        
        # No sales - reduce bid
        if metrics.sales <= 0 and metrics.clicks >= min_clicks:
            new_bid = current_bid * (1 - down_pct)
        # High ACOS - reduce bid
        elif metrics.acos > high_acos:
            new_bid = current_bid * (1 - down_pct)
        # Low ACOS - increase bid
        elif metrics.acos < low_acos and metrics.sales > 0:
            new_bid = current_bid * (1 + up_pct)
        # Medium ACOS - no change
        else:
            return None
        
        # Clamp to min/max
        new_bid = max(min_bid, min(max_bid, new_bid))
        
        return round(new_bid, 2)
    
    def _get_bid_change_reason(self, keyword: Keyword, metrics: PerformanceMetrics, 
                               new_bid: float) -> str:
        """Get reason for bid change"""
        if metrics.sales <= 0:
            return f"No sales after {metrics.clicks} clicks"
        elif metrics.acos > self.config.get('bid_optimization.high_acos', 0.60):
            return f"High ACOS ({metrics.acos:.1%}) - reducing bid"
        elif metrics.acos < self.config.get('bid_optimization.low_acos', 0.25):
            return f"Low ACOS ({metrics.acos:.1%}) - increasing bid"
        else:
            return f"ACOS: {metrics.acos:.1%}, CTR: {metrics.ctr:.2%}"


class DaypartingManager:
    """Time-based bid adjustments"""
    
    def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger):
        self.config = config
        self.api = api
        self.audit = audit_logger
        self.base_bids: Dict[str, float] = {}  # Store original bids
    
    def apply_dayparting(self, dry_run: bool = False) -> Dict:
        """Apply dayparting bid adjustments with timezone awareness"""
        logger.info("=== Applying Dayparting ===")
        
        # Check if dayparting is enabled
        if not self.config.get('dayparting.enabled', False):
            logger.info("Dayparting is disabled in config")
            return {}
        
        # Get timezone from config (default to US/Pacific for Amazon sellers)
        timezone_str = self.config.get('dayparting.timezone', 'US/Pacific')
        
        if pytz:
            try:
                tz = pytz.timezone(timezone_str)
                current_time = datetime.now(tz)
                logger.info(f"Using timezone: {timezone_str}")
            except Exception as e:
                logger.warning(f"Invalid timezone '{timezone_str}', using UTC: {e}")
                current_time = datetime.now(pytz.UTC)
        else:
            # Fallback to server time if pytz not available
            current_time = datetime.now()
            logger.warning("pytz not available, using server timezone (UTC)")
        
        current_hour = current_time.hour
        current_day = current_time.strftime('%A').upper()
        
        # Get multiplier for current hour
        multiplier = self._get_multiplier(current_hour, current_day)
        
        logger.info(f"Current time ({timezone_str}): {current_day} {current_hour}:00, Multiplier: {multiplier:.2f}")
        
        results = {
            'keywords_updated': 0,
            'current_hour': current_hour,
            'current_day': current_day,
            'multiplier': multiplier
        }
        
        # Get all keywords
        keywords = self.api.get_keywords()
        
        for keyword in keywords:
            # Store base bid if not stored
            if keyword.keyword_id not in self.base_bids:
                self.base_bids[keyword.keyword_id] = keyword.bid
            
            base_bid = self.base_bids[keyword.keyword_id]
            new_bid = base_bid * multiplier
            
            # Apply bid caps
            min_bid = self.config.get('bid_optimization.min_bid', 0.25)
            max_bid = self.config.get('bid_optimization.max_bid', 5.0)
            new_bid = max(min_bid, min(max_bid, new_bid))
            new_bid = round(new_bid, 2)
            
            if abs(new_bid - keyword.bid) > 0.01:
                self.audit.log(
                    'DAYPARTING_ADJUSTMENT',
                    'KEYWORD',
                    keyword.keyword_id,
                    f"${keyword.bid:.2f}",
                    f"${new_bid:.2f}",
                    f"Dayparting: {current_day} {current_hour}:00 {timezone_str} ({multiplier:.2f}x)",
                    dry_run
                )
                
                if not dry_run:
                    self.api.update_keyword_bid(keyword.keyword_id, new_bid)
                
                results['keywords_updated'] += 1
        
        logger.info(f"Dayparting applied: {results}")
        return results
    
    def _get_multiplier(self, hour: int, day: str) -> float:
        """Get bid multiplier for specific hour and day"""
        # Get day-specific multipliers
        day_multipliers = self.config.get('dayparting.day_multipliers', {})
        day_multiplier = day_multipliers.get(day, 1.0)
        
        # Get hour-specific multipliers
        hour_multipliers = self.config.get('dayparting.hour_multipliers', {})
        hour_multiplier = hour_multipliers.get(hour, 1.0)
        
        # Combined multiplier
        combined = day_multiplier * hour_multiplier
        
        # Clamp to reasonable range
        min_mult = self.config.get('dayparting.min_multiplier', 0.4)
        max_mult = self.config.get('dayparting.max_multiplier', 1.8)
        
        return max(min_mult, min(max_mult, combined))


class CampaignManager:
    """Campaign activation/deactivation based on performance"""
    
    def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger):
        self.config = config
        self.api = api
        self.audit = audit_logger
    
    def manage_campaigns(self, dry_run: bool = False) -> Dict:
        """Activate/deactivate campaigns based on ACOS with performance timing"""
        start_time = time.time()
        logger.info("=== Managing Campaigns ===")
        
        results = {
            'campaigns_activated': 0,
            'campaigns_paused': 0,
            'no_change': 0
        }
        
        # Get performance data
        report_id = self.api.create_report(
            'campaigns',
            ['campaignId', 'impressions', 'clicks', 'cost', 
             'attributedSales14d', 'attributedConversions14d']
        )
        
        if not report_id:
            logger.error("Failed to create campaign report")
            return results
        
        report_url = self.api.wait_for_report(report_id)
        if not report_url:
            return results
        
        report_data = self.api.download_report(report_url)
        
        # Get current campaigns
        campaigns = self.api.get_campaigns()
        campaign_map = {c.campaign_id: c for c in campaigns}
        
        acos_threshold = self.config.get('campaign_management.acos_threshold', 0.45)
        min_spend = self.config.get('campaign_management.min_spend', 20.0)
        
        for row in report_data:
            campaign_id = row.get('campaignId')
            if not campaign_id or campaign_id not in campaign_map:
                continue
            
            campaign = campaign_map[campaign_id]
            
            # Calculate metrics
            cost = float(row.get('cost', 0) or 0)
            sales = float(row.get('attributedSales14d', 0) or 0)
            
            # Skip if not enough data
            if cost < min_spend:
                results['no_change'] += 1
                continue
            
            acos = (cost / sales) if sales > 0 else float('inf')
            
            # Determine action
            if acos < acos_threshold and campaign.state != 'enabled':
                # Activate campaign
                self.audit.log(
                    'CAMPAIGN_ACTIVATE',
                    'CAMPAIGN',
                    campaign_id,
                    campaign.state,
                    'enabled',
                    f"ACOS {acos:.1%} below threshold {acos_threshold:.1%}",
                    dry_run
                )
                
                if not dry_run:
                    self.api.update_campaign(campaign_id, {'state': 'enabled'})
                
                results['campaigns_activated'] += 1
            
            elif acos > acos_threshold and campaign.state == 'enabled':
                # Pause campaign
                self.audit.log(
                    'CAMPAIGN_PAUSE',
                    'CAMPAIGN',
                    campaign_id,
                    campaign.state,
                    'paused',
                    f"ACOS {acos:.1%} above threshold {acos_threshold:.1%}",
                    dry_run
                )
                
                if not dry_run:
                    self.api.update_campaign(campaign_id, {'state': 'paused'})
                
                results['campaigns_paused'] += 1
            else:
                results['no_change'] += 1
        
        elapsed = time.time() - start_time
        logger.info(f"Campaign management complete in {elapsed:.2f}s: {results}")
        results['execution_time_seconds'] = round(elapsed, 2)
        return results


class KeywordDiscovery:
    """Discover and add new keywords"""
    
    def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger):
        self.config = config
        self.api = api
        self.audit = audit_logger
    
    def discover_keywords(self, dry_run: bool = False) -> Dict:
        """Discover and add new keywords with performance timing"""
        start_time = time.time()
        logger.info("=== Discovering Keywords ===")
        
        results = {
            'keywords_discovered': 0,
            'keywords_added': 0
        }
        
        # Get search term report to find high-performing queries
        report_id = self.api.create_report(
            'targets',
            ['campaignId', 'adGroupId', 'query', 'impressions', 'clicks', 
             'cost', 'attributedSales14d', 'attributedConversions14d'],
            segment='query'
        )
        
        if not report_id:
            logger.error("Failed to create search term report")
            return results
        
        report_url = self.api.wait_for_report(report_id)
        if not report_url:
            return results
        
        report_data = self.api.download_report(report_url)
        
        # Get existing keywords to avoid duplicates
        existing_keywords = self.api.get_keywords()
        
        # Use frozenset for immutable data (good for lookups)
        existing_keyword_texts = frozenset(
            (kw.ad_group_id, kw.keyword_text.lower(), kw.match_type) 
            for kw in existing_keywords
        )
        
        # Create keyword_id index for faster lookups
        keyword_by_id = {kw.keyword_id: kw for kw in existing_keywords}
        
        # Create campaign_id index for faster filtering
        keywords_by_campaign = defaultdict(list)
        for kw in existing_keywords:
            keywords_by_campaign[kw.campaign_id].append(kw)
        
        logger.debug(f"Indexed {len(existing_keywords)} keywords across {len(keywords_by_campaign)} campaigns")
        
        # Analyze search terms
        min_clicks = self.config.get('keyword_discovery.min_clicks', 5)
        max_acos = self.config.get('keyword_discovery.max_acos', 0.40)
        
        new_keywords_to_add = []
        
        for row in report_data:
            query = row.get('query', '').strip().lower()
            ad_group_id = row.get('adGroupId')
            campaign_id = row.get('campaignId')
            
            if not query or not ad_group_id:
                continue
            
            # Calculate metrics
            clicks = int(row.get('clicks', 0) or 0)
            cost = float(row.get('cost', 0) or 0)
            sales = float(row.get('attributedSales14d', 0) or 0)
            
            if clicks < min_clicks:
                continue
            
            acos = (cost / sales) if sales > 0 else float('inf')
            
            if acos > max_acos:
                continue
            
            # Check if already exists
            if (ad_group_id, query, 'exact') in existing_keyword_texts:
                continue
            
            results['keywords_discovered'] += 1
            
            # Prepare keyword for addition
            suggested_bid = self.config.get('keyword_discovery.initial_bid', 0.75)
            
            new_keywords_to_add.append({
                'campaignId': int(campaign_id),
                'adGroupId': int(ad_group_id),
                'keywordText': query,
                'matchType': 'exact',
                'state': 'enabled',
                'bid': suggested_bid
            })
            
            self.audit.log(
                'KEYWORD_DISCOVERY',
                'KEYWORD',
                'NEW',
                '',
                query,
                f"Added from search term: {clicks} clicks, ACOS {acos:.1%}",
                dry_run
            )
        
        # Add keywords in batches
        if new_keywords_to_add and not dry_run:
            batch_size = 100
            for i in range(0, len(new_keywords_to_add), batch_size):
                batch = new_keywords_to_add[i:i+batch_size]
                created_ids = self.api.create_keywords(batch)
                results['keywords_added'] += len(created_ids)
        elif dry_run:
            results['keywords_added'] = len(new_keywords_to_add)
        
        elapsed = time.time() - start_time
        logger.info(f"Keyword discovery complete in {elapsed:.2f}s: {results}")
        results['execution_time_seconds'] = round(elapsed, 2)
        return results


class NegativeKeywordManager:
    """Manage negative keywords"""
    
    def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger):
        self.config = config
        self.api = api
        self.audit = audit_logger
    
    def add_negative_keywords(self, dry_run: bool = False) -> Dict:
        """Add poor-performing keywords as negatives"""
        logger.info("=== Managing Negative Keywords ===")
        
        results = {
            'negative_keywords_added': 0
        }
        
        # Get search term report
        report_id = self.api.create_report(
            'targets',
            ['campaignId', 'adGroupId', 'query', 'impressions', 'clicks', 
             'cost', 'attributedSales14d', 'attributedConversions14d'],
            segment='query'
        )
        
        if not report_id:
            return results
        
        report_url = self.api.wait_for_report(report_id)
        if not report_url:
            return results
        
        report_data = self.api.download_report(report_url)
        
        # Get existing negative keywords
        existing_negatives = self.api.get_negative_keywords()
        existing_negative_texts = {
            (nk.get('campaignId'), nk.get('keywordText', '').lower())
            for nk in existing_negatives
        }
        
        # Analyze search terms
        min_spend = self.config.get('negative_keywords.min_spend', 10.0)
        max_acos = self.config.get('negative_keywords.max_acos', 1.0)
        
        negatives_to_add = []
        
        for row in report_data:
            query = row.get('query', '').strip().lower()
            campaign_id = row.get('campaignId')
            
            if not query or not campaign_id:
                continue
            
            cost = float(row.get('cost', 0) or 0)
            sales = float(row.get('attributedSales14d', 0) or 0)
            
            if cost < min_spend:
                continue
            
            acos = (cost / sales) if sales > 0 else float('inf')
            
            if acos < max_acos:
                continue
            
            # Check if already negative
            if (campaign_id, query) in existing_negative_texts:
                continue
            
            negatives_to_add.append({
                'campaignId': int(campaign_id),
                'keywordText': query,
                'matchType': 'negativePhrase',
                'state': 'enabled'
            })
            
            self.audit.log(
                'NEGATIVE_KEYWORD_ADD',
                'NEGATIVE_KEYWORD',
                campaign_id,
                '',
                query,
                f"Poor performer: ${cost:.2f} spend, ACOS {acos:.1%}",
                dry_run
            )
        
        # Add negative keywords
        if negatives_to_add and not dry_run:
            batch_size = 100
            for i in range(0, len(negatives_to_add), batch_size):
                batch = negatives_to_add[i:i+batch_size]
                created_ids = self.api.create_negative_keywords(batch)
                results['negative_keywords_added'] += len(created_ids)
        elif dry_run:
            results['negative_keywords_added'] = len(negatives_to_add)
        
        logger.info(f"Negative keyword management complete: {results}")
        return results


# ============================================================================
# MAIN AUTOMATION ORCHESTRATOR
# ============================================================================

class PPCAutomation:
    """Main automation orchestrator"""
    
    def __init__(self, config_path: str, profile_id: str, dry_run: bool = False):
        self.config = Config(config_path)
        self.profile_id = profile_id
        self.dry_run = dry_run
        
        # Initialize API client with configurable rate limit
        region = self.config.get('api.region', 'NA')
        max_requests_per_second = self.config.get('api.max_requests_per_second', MAX_REQUESTS_PER_SECOND)
        self.api = AmazonAdsAPI(profile_id, region, max_requests_per_second=max_requests_per_second)
        
        # Initialize audit logger
        audit_output_dir = self.config.get('logging.output_dir', './logs')
        self.audit = AuditLogger(audit_output_dir)
        
        # Initialize feature modules
        self.bid_optimizer = BidOptimizer(self.config, self.api, self.audit)
        self.dayparting = DaypartingManager(self.config, self.api, self.audit)
        self.campaign_manager = CampaignManager(self.config, self.api, self.audit)
        self.keyword_discovery = KeywordDiscovery(self.config, self.api, self.audit)
        self.negative_keywords = NegativeKeywordManager(self.config, self.api, self.audit)
    
    def run(self, features: List[str] = None):
        """Run automation with specified features"""
        logger.info("=" * 80)
        logger.info("AMAZON PPC AUTOMATION SUITE")
        logger.info("=" * 80)
        logger.info(f"Profile ID: {self.profile_id}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 80)
        
        if features is None:
            features = self.config.get('features.enabled', [])
        
        logger.info(f"Enabled features: {', '.join(features)}")
        
        results = {}
        
        try:
            # Run each feature
            if 'bid_optimization' in features:
                results['bid_optimization'] = self.bid_optimizer.optimize(self.dry_run)
            
            if 'dayparting' in features:
                results['dayparting'] = self.dayparting.apply_dayparting(self.dry_run)
            
            if 'campaign_management' in features:
                results['campaign_management'] = self.campaign_manager.manage_campaigns(self.dry_run)
            
            if 'keyword_discovery' in features:
                results['keyword_discovery'] = self.keyword_discovery.discover_keywords(self.dry_run)
            
            if 'negative_keywords' in features:
                results['negative_keywords'] = self.negative_keywords.add_negative_keywords(self.dry_run)
            
        except Exception as e:
            logger.error(f"Automation failed: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Save audit trail
            self.audit.save()
        
        # Print summary
        logger.info("=" * 80)
        logger.info("AUTOMATION SUMMARY")
        logger.info("=" * 80)
        for feature, result in results.items():
            logger.info(f"\n{feature.upper().replace('_', ' ')}:")
            for key, value in result.items():
                logger.info(f"  {key}: {value}")
        logger.info("=" * 80)
        
        return results


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Amazon PPC Automation Suite')
    parser.add_argument('--config', required=True, help='Path to configuration YAML file')
    parser.add_argument('--profile-id', help='Amazon Ads Profile ID (overrides config)')
    parser.add_argument('--dry-run', action='store_true', help='Run without making actual changes')
    parser.add_argument('--features', nargs='+',
                       choices=['bid_optimization', 'dayparting', 'campaign_management',
                               'keyword_discovery', 'negative_keywords'],
                       help='Specific features to run (default: all enabled in config)')
    parser.add_argument('--verify-connection', action='store_true',
                        help='Check Amazon Ads API connectivity and exit')
    parser.add_argument('--verify-sample-size', type=int, default=5,
                        help='Number of campaigns to include in verification sample (default: 5)')

    args = parser.parse_args()

    # Run automation
    automation = PPCAutomation(args.config, args.profile_id, args.dry_run)

    if args.verify_connection:
        verification = automation.api.verify_connection(args.verify_sample_size)
        print(json.dumps(verification, indent=2))
        if verification.get('success'):
            sys.exit(0)
        sys.exit(1)

    automation.run(args.features)


if __name__ == '__main__':
    main()
