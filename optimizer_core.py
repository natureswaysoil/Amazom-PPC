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
import re
import sys
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import traceback

import requests

try:
    import yaml
except ImportError as e:
    import sys
    print(f"FATAL ERROR during import: pyyaml is required. Install with: pip install pyyaml. Error: {e}", file=sys.stderr)
    raise ImportError(f"Required dependency 'pyyaml' not found: {e}") from e

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

# Amazon Ads API versions for Amazon-Advertising-API-Version header
# Sponsored Products (SP) endpoints expect version v2.
# Reporting API uses version v3.
SP_API_VERSION = "v2"
REPORTS_API_VERSION = "v3"

# Rate limiting - Amazon Advertising API supports 10 requests/second
MAX_REQUESTS_PER_SECOND = 10
REQUEST_INTERVAL = 1.0 / MAX_REQUESTS_PER_SECOND

# ============================================================================
# LOGGING SETUP
# ============================================================================

# Detect if running in Cloud Functions environment
IS_CLOUD_FUNCTION = os.getenv('K_SERVICE') is not None or os.getenv('FUNCTION_TARGET') is not None

if IS_CLOUD_FUNCTION:
    # Use only StreamHandler for Cloud Functions (logs go to Cloud Logging)
    # File logging doesn't work in Cloud Functions (ephemeral filesystem)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger(__name__)
    logger.info("Running in Cloud Functions environment - using Cloud Logging")
else:
    # For local development, use both console and file logging with log rotation
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'ppc_automation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("Running in local environment - using file and console logging")

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

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass


class AuthenticationError(Exception):
    """Amazon Ads API authentication error"""
    pass


class DeprecatedEndpointError(Exception):
    """Raised when an endpoint is known to be deprecated/unavailable."""
    pass


class Config:
    """Configuration manager with enhanced error handling"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.data = self._load_config()
    
    def _load_config(self) -> Dict:
        """
        Load configuration from YAML file
        
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigurationError: If config file cannot be loaded or parsed
        """
        if not os.path.exists(self.config_path):
            error_msg = f"Configuration file not found: {self.config_path}"
            logger.error(error_msg)
            raise ConfigurationError(error_msg)
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not isinstance(config, dict):
                error_msg = f"Invalid configuration format: expected dictionary, got {type(config)}"
                logger.error(error_msg)
                raise ConfigurationError(error_msg)
            
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
            
        except yaml.YAMLError as e:
            error_msg = f"Failed to parse YAML configuration: {e}"
            logger.error(error_msg)
            raise ConfigurationError(error_msg)
            
        except IOError as e:
            error_msg = f"Failed to read configuration file: {e}"
            logger.error(error_msg)
            raise ConfigurationError(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error loading configuration: {e}"
            logger.error(error_msg)
            raise ConfigurationError(error_msg)
    
    def get(self, key: str, default=None):
        """
        Get configuration value with dot notation support
        
        Args:
            key: Configuration key (supports dot notation like 'section.subsection.key')
            default: Default value to return if key not found
            
        Returns:
            Configuration value or default
        """
        if not key:
            return default
        
        keys = key.split('.')
        value = self.data
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, None)
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
            timestamp=datetime.now(timezone.utc).isoformat(),
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
    
    def __init__(
        self,
        profile_id: str,
        region: str = "NA",
        max_requests_per_second: int = None,
        session: Optional[requests.Session] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        self.profile_id = profile_id
        self.region = region.upper()
        self.base_url = ENDPOINTS.get(self.region, ENDPOINTS["NA"])

        # Avoid tight auth retry loops when credentials are invalid.
        # If authentication fails, subsequent attempts within this window
        # will re-raise the cached error instead of spamming token requests.
        try:
            self._auth_failure_backoff_seconds = int(os.getenv("AMAZON_AUTH_FAILURE_BACKOFF_SECONDS", "15"))
        except Exception:
            self._auth_failure_backoff_seconds = 15
        self._last_auth_failure_at: Optional[float] = None
        self._last_auth_failure_message: Optional[str] = None

        # Allow explicit credentials (primarily for tests).
        if client_id and not os.getenv("AMAZON_CLIENT_ID"):
            os.environ["AMAZON_CLIENT_ID"] = client_id
        if client_secret and not os.getenv("AMAZON_CLIENT_SECRET"):
            os.environ["AMAZON_CLIENT_SECRET"] = client_secret
        if refresh_token and not os.getenv("AMAZON_REFRESH_TOKEN"):
            os.environ["AMAZON_REFRESH_TOKEN"] = refresh_token

        # Initialize client_id from environment; will be refreshed in _authenticate
        self.client_id: Optional[str] = os.getenv("AMAZON_CLIENT_ID", "") or None
        self.auth = self._authenticate()
        self.rate_limiter = RateLimiter(max_requests_per_second or MAX_REQUESTS_PER_SECOND)

        # Default to requests.request (unit tests patch requests.request).
        # A session can be provided for connection pooling.
        self.session = session

        # Cache of deprecated endpoint signatures discovered at runtime.
        self._deprecated_endpoint_signatures: set[str] = set()
        # Pre-block known hard-deprecated endpoints.
        self._deprecated_endpoint_signatures.add("/sp/keywords/:id/bidRecommendations")

        # Cache for campaigns and ad groups (lifetime of API instance)
        self._campaigns_cache = None
        self._ad_groups_cache = None
        # Track last fetch error for campaigns to distinguish true empty set from failure
        self._last_campaigns_error: Optional[Exception] = None

    def _endpoint_signature(self, endpoint: str) -> str:
        """Normalize endpoint to a stable signature for deprecation caching."""

        ep = (endpoint or "").strip()
        # Accept full URLs as input.
        if ep.startswith("http://") or ep.startswith("https://"):
            try:
                ep = "/" + ep.split("//", 1)[1].split("/", 1)[1]
            except Exception:
                pass

        ep = ep.split("?", 1)[0]
        ep = ep.rstrip("/")

        # Strip legacy /v2 prefix for signature stability.
        if ep.startswith("/v2/"):
            ep = ep[len("/v2"):]

        # Replace numeric IDs with :id so different IDs map to one signature.
        ep = re.sub(r"/\d+", "/:id", ep)
        return ep
    
    def _authenticate(self) -> Auth:
        """Authenticate and get access token"""
        if self._last_auth_failure_at is not None and self._auth_failure_backoff_seconds > 0:
            elapsed = time.time() - self._last_auth_failure_at
            if elapsed < self._auth_failure_backoff_seconds:
                cached = self._last_auth_failure_message or "Previous authentication attempt failed"
                raise AuthenticationError(
                    f"{cached} (backing off; retry in {int(self._auth_failure_backoff_seconds - elapsed)}s)"
                )

        def _looks_like_secret_ref(value: str) -> bool:
            if not value:
                return False
            lower = value.lower()
            if lower.startswith('projects/') and '/secrets/' in lower:
                return True
            if '/secrets/' in lower and '/versions/' in lower:
                return True
            return False

        def _looks_like_placeholder(value: str) -> bool:
            if not value:
                return False
            upper = value.upper()
            if 'YOUR_' in upper or upper in {'CHANGEME', 'REPLACE_ME'}:
                return True
            if 'XXXXX' in value:
                return True
            return False

        client_id = os.getenv("AMAZON_CLIENT_ID", "").strip()
        client_secret = os.getenv("AMAZON_CLIENT_SECRET", "").strip()
        refresh_token = os.getenv("AMAZON_REFRESH_TOKEN", "").strip()
        
        if not all([client_id, client_secret, refresh_token]):
            logger.error("Missing required environment variables")
            raise AuthenticationError(
                "Missing required environment variables: AMAZON_CLIENT_ID, "
                "AMAZON_CLIENT_SECRET, or AMAZON_REFRESH_TOKEN"
            )

        # Fast-fail common misconfigurations: secret references or placeholders.
        for field_name, value in [
            ('AMAZON_CLIENT_ID', client_id),
            ('AMAZON_CLIENT_SECRET', client_secret),
            ('AMAZON_REFRESH_TOKEN', refresh_token),
        ]:
            if _looks_like_secret_ref(value):
                raise AuthenticationError(
                    f"{field_name} appears to be a Secret Manager reference ({value}), not an actual credential value. "
                    "Ensure Secret Manager is bound into environment variables (e.g., --set-secrets) or provide a real value."
                )
            if _looks_like_placeholder(value):
                raise AuthenticationError(
                    f"{field_name} appears to be a placeholder value. Provide real Amazon OAuth credentials."
                )

        # Log credential status (masked)
        logger.debug(f"Auth attempt - client_id: {client_id[:8] if client_id else 'MISSING'}..., "
                    f"client_secret: {'SET' if client_secret else 'MISSING'}, "
                    f"refresh_token: {refresh_token[:12] if refresh_token else 'MISSING'}...")

        # Cache client ID for use in request headers (stripped of whitespace)
        self.client_id = client_id
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        oauth_scope = os.getenv("AMAZON_OAUTH_SCOPE", "").strip()
        if oauth_scope:
            # Some accounts/app registrations require requesting an explicit advertising scope
            # when exchanging refresh tokens for access tokens.
            payload["scope"] = oauth_scope
            logger.info("Using explicit OAuth scope for token refresh: %s", oauth_scope)
        
        try:
            logger.debug(f"POST {TOKEN_URL}")
            # Use an isolated session to avoid global hooks/proxies interfering
            auth_session = requests.Session()
            try:
                # Disable environment proxies for this critical call
                auth_session.trust_env = False
            except Exception:
                pass
            response = auth_session.post(
                TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            logger.debug(f"Response status: {response.status_code}")
            
            # Log response body for debugging (may contain error details)
            try:
                response_data = response.json()
                if response.status_code != 200:
                    logger.error(f"Amazon auth error response: {response_data}")
                    # Provide more actionable guidance for common auth failures
                    err_code = (response_data or {}).get("error")
                    err_desc = (response_data or {}).get("error_description")
                    if str(err_code).lower() == "unauthorized_client":
                        hint = (
                            "Amazon returned 'unauthorized_client' during token refresh. "
                            "Verify that AMAZON_CLIENT_ID, AMAZON_CLIENT_SECRET, and AMAZON_REFRESH_TOKEN "
                            "belong to the same Amazon Ads application registration and profile. "
                            "Refresh tokens are client-specific; re-authorize the Ads app to generate a new refresh token "
                            "if credentials were rotated. Also check Secret Manager for disabled/corrupted versions and whitespace."
                        )
                        logger.error(hint)
            except (ValueError, KeyError, AttributeError):
                logger.debug(f"Response body (first 200 chars): {response.text[:200]}")
            
            response.raise_for_status()
            data = response.json()
            
            # Strip any whitespace from the access token (common issue with Secret Manager)
            access_token = data["access_token"].strip() if isinstance(data["access_token"], str) else data["access_token"]
            
            auth = Auth(
                access_token=access_token,
                token_type=data.get("token_type", "Bearer"),
                expires_at=time.time() + int(data.get("expires_in", 3600))
            )
            logger.info("Successfully authenticated with Amazon Ads API")
            logger.debug(f"Access token length: {len(access_token)}")
            self._last_auth_failure_at = None
            self._last_auth_failure_message = None
            return auth
        except requests.exceptions.RequestException as e:
            # Surface more specific error details when available
            body = None
            try:
                body = response.json() if 'response' in locals() else None
            except Exception:
                body = None
            msg = f"Failed to authenticate with Amazon Ads API: {e}"
            if isinstance(body, dict) and body.get('error'):
                msg += f" | error={body.get('error')} desc={body.get('error_description')}"
            logger.error(msg)
            self._last_auth_failure_at = time.time()
            self._last_auth_failure_message = msg
            raise AuthenticationError(msg)
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid authentication response: {e}")
            msg = f"Invalid response from Amazon Ads API: {e}"
            self._last_auth_failure_at = time.time()
            self._last_auth_failure_message = msg
            raise AuthenticationError(msg)
    
    def _refresh_auth_if_needed(self):
        """Refresh authentication if token expired"""
        if self.auth.is_expired():
            logger.info("Access token expired, refreshing...")
            self.auth = self._authenticate()

    def _headers(self, api_version: str = None) -> Dict[str, str]:
        """Get API request headers with optional API version"""
        self._refresh_auth_if_needed()

        client_id = self.client_id or os.getenv("AMAZON_CLIENT_ID", "")
        if not client_id:
            logger.warning("Amazon client ID missing when preparing headers")

        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
            "Amazon-Advertising-API-ClientId": client_id,
            "Amazon-Advertising-API-Scope": self.profile_id,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        
        # Add API version header if specified (for new versioned endpoints)
        if api_version:
            headers["Amazon-Advertising-API-Version"] = api_version
            
        return headers

    def _upgrade_endpoint(self, endpoint: str) -> tuple[str, str]:
        """Resolve endpoint path and optional API version header.

        Historically, many Amazon Ads endpoints are versioned via the URL path
        (e.g., `/v2/sp/keywords`). Some environments/scripts in this repo also
        attempted header-based versioning by rewriting `/v2/...` -> `/...` and
        adding `Amazon-Advertising-API-Version`.

        In practice, calling unversioned paths (e.g., `/sp/keywords`) can yield
        confusing 403s like "Invalid key=value pair" even with a valid Bearer
        token. To maximize compatibility, we default to *path-based* versioning
        and only use the header-rewrite behavior when explicitly enabled.

        Returns: (endpoint_path, api_version_header_or_none)
        """

        ep = (endpoint or "").strip()
        if not ep.startswith("/v2/"):
            return ep, None

        # Reports are a special case: legacy `/v2/reports` should be routed to
        # the modern reporting service path.
        if ep.startswith("/v2/reports"):
            suffix = ep[len("/v2/reports"):]
            return f"/reporting/reports{suffix}", REPORTS_API_VERSION

        versioning_mode = os.getenv("AMAZON_ADS_VERSIONING_MODE", "path").strip().lower()
        # Modes:
        # - "path" (default): keep `/v2/...` in the URL and do not set version header.
        # - "header": rewrite `/v2/...` -> `/...` and set `Amazon-Advertising-API-Version`.
        if versioning_mode != "header":
            return ep, None

        # Header-based versioning (opt-in)
        replacements = {
            "/v2/sp/campaigns": ("/sp/campaigns", SP_API_VERSION),
            "/v2/sp/adGroups": ("/sp/adGroups", SP_API_VERSION),
            "/v2/sp/keywords/extended": ("/sp/keywords/extended", SP_API_VERSION),
            "/v2/sp/keywords": ("/sp/keywords", SP_API_VERSION),
            "/v2/sp/negativeKeywords": ("/sp/negativeKeywords", SP_API_VERSION),
            "/v2/sp/targets/keywords/recommendations": (
                "/sp/targets/keywords/recommendations", SP_API_VERSION
            ),
            "/v2/reports": ("/reporting/reports", REPORTS_API_VERSION),
        }

        for old_prefix, (new_prefix, api_version) in replacements.items():
            if ep.startswith(old_prefix):
                suffix = ep[len(old_prefix):]
                return f"{new_prefix}{suffix}", api_version

        logger.warning(f"Unknown v2 endpoint format (header mode): {ep}")
        return ep, None

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make API request with retry logic and rate limiting using connection pooling"""
        signature = self._endpoint_signature(endpoint)
        if signature in self._deprecated_endpoint_signatures:
            raise DeprecatedEndpointError(f"Endpoint is deprecated: {signature}")

        self.rate_limiter.wait_if_needed()

        # Optional extra headers (merged on top of default headers)
        headers_extra = kwargs.pop('headers_extra', None)

        upgraded_endpoint, api_version = self._upgrade_endpoint(endpoint)
        url = f"{self.base_url}{upgraded_endpoint}"
        max_retries = 3
        retry_delay = 1
        
        reauth_attempted = False

        for attempt in range(max_retries):
            try:
                # Log request details (mask sensitive headers)
                headers = self._headers(api_version=api_version)
                if headers_extra:
                    headers.update(headers_extra)
                safe_headers = {k: ('REDACTED' if 'auth' in k.lower() else v) for k, v in headers.items()}
                logger.info(f"Amazon API {method} {url} (attempt {attempt + 1}/{max_retries})")
                logger.info(f"Request headers: {safe_headers}")
                logger.info(f"API version for this request: {api_version}")
                if 'json' in kwargs:
                    logger.debug(f"Request body preview: {str(kwargs['json'])[:500]}")
                
                requester = self.session.request if self.session is not None else requests.request
                response = requester(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=30,
                    **kwargs
                )
                
                # Log response details
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                
                if response.status_code == 429:  # Rate limit
                    # Distinguish normal throttling from deprecated-resource throttling.
                    body_text = response.text or ""
                    if "deprecated resource" in body_text.lower():
                        self._deprecated_endpoint_signatures.add(signature)
                        raise DeprecatedEndpointError(f"Deprecated resource: {signature}")

                    retry_after = int(response.headers.get('Retry-After', retry_delay * (attempt + 1)))
                    logger.warning(f"Rate limit hit, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                # Log response body preview for errors
                if response.status_code >= 400:
                    body_preview = response.text[:1000] if response.text else 'Empty response'
                    logger.error(f"Amazon API error {response.status_code}: {body_preview}")

                    # Special-case a common SP permission / API registration failure signature.
                    # This is frequently NOT resolvable by re-authenticating; retrying just burns time.
                    if response.status_code == 403 and "Invalid key=value pair" in body_preview:
                        logger.error(
                            "403 with 'Invalid key=value pair' is often caused by either (a) calling an unversioned path "
                            "like '/sp/...' instead of '/v2/sp/...' (request gets routed to a gateway that expects a different "
                            "Authorization format), or (b) missing Sponsored Products API permission / API registration for the "
                            "LWA app+refresh token. Verify the request URL includes '/v2' for SP v2 endpoints, then verify API "
                            "registration in Amazon Advertising Console (Account Settings → API) and re-authorize to generate a "
                            "refresh token with the correct advertising scope. If needed, set AMAZON_OAUTH_SCOPE=advertising::campaign_management."
                        )

                    # Extra diagnostics for auth-related 401/403 - BEFORE any exception raising
                    if response.status_code in (401, 403):
                        auth_header = headers.get("Authorization", "")
                        token_part = auth_header.split(" ", 1)[1] if " " in auth_header else auth_header
                        token_len = len(token_part)
                        # Detect suspicious whitespace characters
                        has_newline = any(ch in token_part for ch in ['\n', '\r', '\t'])
                        has_space = ' ' in token_part
                        # Avoid logging any token fragments; log only non-sensitive diagnostics.
                        token_hash8 = None
                        try:
                            import hashlib
                            token_hash8 = hashlib.sha256(token_part.encode('utf-8', errors='ignore')).hexdigest()[:8]
                        except Exception:
                            token_hash8 = None
                        
                        # Log full diagnostics
                        logger.error(
                            "AUTH DIAGNOSTIC - token_len=%d has_newline=%s has_space=%s", 
                            token_len, has_newline, has_space
                        )
                        if token_hash8:
                            logger.error("AUTH DIAGNOSTIC - token_sha256_8=%s", token_hash8)
                        logger.error("AUTH DIAGNOSTIC - profile_id=%s", self.profile_id)
                        logger.error("AUTH DIAGNOSTIC - client_id=%s", 
                                   (self.client_id[:12] + '...' if self.client_id and len(self.client_id) > 12 else self.client_id or 'MISSING'))
                        
                        # Check for Authorization header format issues
                        if not auth_header.startswith("Bearer "):
                            logger.error("AUTH DIAGNOSTIC - Authorization header does NOT start with 'Bearer '!")
                        
                        # Confirm presence of required headers
                        missing_headers = [h for h in ["Amazon-Advertising-API-ClientId", "Amazon-Advertising-API-Scope"] if h not in headers]
                        if missing_headers:
                            logger.error(f"AUTH DIAGNOSTIC - Missing required headers: {missing_headers}")
                        else:
                            logger.info("AUTH DIAGNOSTIC - All required Amazon Ads headers present")

                        # Do not log Authorization header contents.
                        if auth_header:
                            logger.error("AUTH DIAGNOSTIC - Authorization scheme=%s", auth_header.split(' ', 1)[0])

                    if response.status_code == 401 and not reauth_attempted:
                        logger.info(
                            "Received %s from Amazon Ads API; refreshing credentials and retrying",
                            response.status_code,
                        )
                        self.auth = self._authenticate()
                        reauth_attempted = True
                        time.sleep(retry_delay * (attempt + 1))
                        continue

                response.raise_for_status()
                return response

            except requests.exceptions.HTTPError as e:
                # Do not retry most client errors; let higher-level fallbacks handle them.
                status_code = None
                if hasattr(e, 'response') and e.response is not None:
                    status_code = getattr(e.response, 'status_code', None)
                if status_code is not None and 400 <= int(status_code) < 500 and int(status_code) != 429:
                    logger.error(f"Request failed with non-retryable client error {status_code}: {e}")
                    raise

                if attempt == max_retries - 1:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    if hasattr(e, 'response') and e.response is not None:
                        logger.error(f"Final error response body: {e.response.text[:1000]}")
                    raise
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.debug(f"Error response body: {e.response.text[:500]}")
                time.sleep(retry_delay * (attempt + 1))
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    logger.error(f"Request exception after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"Request exception (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay * (attempt + 1))
        
        raise Exception("Max retries exceeded")

    def list_campaigns_v3(self, count: int = 10, start_index: int = 0) -> List[Dict[str, Any]]:
        """List Sponsored Products campaigns via the v3 list-style endpoint.

        This endpoint has proven more reliable than legacy GET-based collection endpoints
        for some accounts.
        """

        count = max(int(count), 1)
        start_index = max(int(start_index), 0)

        # Try a few header/body combinations to maximize compatibility.
        header_candidates = [
            {
                'Accept': 'application/vnd.spCampaign.v3+json',
                'Content-Type': 'application/vnd.spCampaign.v3+json',
            },
            {
                'Accept': 'application/vnd.spCampaign.v3+json',
                'Content-Type': 'application/json',
            },
            {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
        ]

        body_candidates = [
            {'startIndex': start_index, 'count': count},
            {},
        ]

        endpoint_candidates = [
            # Prefer path-versioned endpoint first to avoid certain gateway/auth parsing issues.
            '/v2/sp/campaigns/list',
            '/sp/campaigns/list',
        ]

        def _should_abort_variants(exc: Exception) -> bool:
            """Return True if further permutations are unlikely to succeed."""
            resp = getattr(exc, 'response', None)
            if resp is None:
                return False
            status = getattr(resp, 'status_code', None)
            if status not in (401, 403):
                return False
            body_text = (getattr(resp, 'text', '') or '')
            # This is the confusing gateway error we've been seeing when hitting unversioned paths.
            if "Invalid key=value pair" in body_text:
                return True
            return False

        last_exc: Optional[Exception] = None
        for endpoint in endpoint_candidates:
            for headers_extra in header_candidates:
                for body in body_candidates:
                    try:
                        response = self._request(
                            'POST',
                            endpoint,
                            json=body,
                            headers_extra=headers_extra,
                        )
                        payload = response.json() if response is not None else None

                        # Some APIs return a plain list; others wrap it.
                        if isinstance(payload, list):
                            return payload
                        if isinstance(payload, dict):
                            for key in ('campaigns', 'items', 'results'):
                                if isinstance(payload.get(key), list):
                                    return payload[key]
                            # Fallback for nested "response" wrappers
                            nested = payload.get('response') if isinstance(payload.get('response'), dict) else None
                            if nested:
                                for key in ('campaigns', 'items', 'results'):
                                    if isinstance(nested.get(key), list):
                                        return nested[key]

                        # Unknown shape: treat as empty rather than hard-failing.
                        return []
                    except Exception as exc:
                        last_exc = exc

                        # If the path-versioned candidate doesn't exist, try the next endpoint.
                        resp = getattr(exc, 'response', None)
                        status = getattr(resp, 'status_code', None) if resp is not None else None
                        if status == 404 and endpoint.startswith('/v2/'):
                            break

                        # Abort quickly on known gateway/auth-format error to allow verify_connection fallback.
                        if _should_abort_variants(exc):
                            raise
                        continue

        raise last_exc or Exception('Failed to list campaigns via /sp/campaigns/list')

    def verify_connection(self, sample_size: int = 5) -> Dict[str, Any]:
        """Verify API connectivity by retrieving a small campaign sample"""

        # Prefer list-style endpoint first; fall back to legacy collection endpoint.
        errors: List[str] = []

        try:
            campaigns = self.list_campaigns_v3(count=max(sample_size, 1), start_index=0)
            sample = []
            for entry in (campaigns or [])[:sample_size]:
                if not isinstance(entry, dict):
                    continue
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
                "campaign_count": len(campaigns or []),
                "sample": sample,
                "method": "POST /sp/campaigns/list",
            }
            logger.info(
                "Amazon Ads API connectivity verified (v3 list). Retrieved %d campaigns.",
                result["campaign_count"],
            )
            return result
        except Exception as exc:
            errors.append(f"v3_list_failed: {exc}")

        try:
            response = self._request(
                "GET",
                "/v2/sp/campaigns",
                params={"startIndex": 0, "count": max(sample_size, 1)}
            )
            campaigns = response.json() or []
            if not isinstance(campaigns, list):
                campaigns = []

            sample = []
            for entry in campaigns[:sample_size]:
                if not isinstance(entry, dict):
                    continue
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
                "method": "GET /v2/sp/campaigns (upgraded)",
            }
            logger.info(
                "Amazon Ads API connectivity verified (legacy GET). Retrieved %d campaigns.",
                result["campaign_count"],
            )
            return result
        except Exception as exc:
            errors.append(f"legacy_get_failed: {exc}")

        logger.error("Amazon Ads API verification failed: %s", " | ".join(errors))
        return {
            "success": False,
            "error": "Amazon Ads API verification failed",
            "details": errors,
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
            # Clear previous error before new attempt
            self._last_campaigns_error = None
            params = {}
            if state_filter:
                params['stateFilter'] = state_filter
            
            response = self._request('GET', '/v2/sp/campaigns', params=params)
            campaigns_data = response.json()
            
            if not isinstance(campaigns_data, list):
                logger.warning(f"Unexpected campaigns response format: {type(campaigns_data)}")
                return []
            
            campaigns = []
            for c in campaigns_data:
                if not isinstance(c, dict):
                    continue
                    
                campaign = Campaign(
                    campaign_id=str(c.get('campaignId', '')),
                    name=c.get('name', ''),
                    state=c.get('state', ''),
                    daily_budget=float(c.get('dailyBudget', 0.0)),
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
            self._last_campaigns_error = e

            # Fallback: try the list-style endpoint (often required for newer SP APIs)
            try:
                logger.info("Falling back to v3 list campaigns endpoint")
                all_items: List[Dict[str, Any]] = []
                start_index = 0
                page_size = 100
                max_pages = 50

                for _ in range(max_pages):
                    page = self.list_campaigns_v3(count=page_size, start_index=start_index)
                    if not page:
                        break
                    all_items.extend([p for p in page if isinstance(p, dict)])
                    if len(page) < page_size:
                        break
                    start_index += page_size

                campaigns: List[Campaign] = []
                for c in all_items:
                    campaign = Campaign(
                        campaign_id=str(c.get('campaignId', '')),
                        name=c.get('name', ''),
                        state=c.get('state', ''),
                        daily_budget=float(c.get('dailyBudget', 0.0)),
                        targeting_type=c.get('targetingType', ''),
                        campaign_type='sponsoredProducts'
                    )
                    campaigns.append(campaign)

                logger.info(f"Retrieved {len(campaigns)} campaigns (v3 list fallback)")

                if state_filter is None:
                    self._campaigns_cache = campaigns
                return campaigns
            except Exception as fallback_exc:
                logger.error(f"Fallback campaigns list also failed: {fallback_exc}")
                return []
    
    def invalidate_campaigns_cache(self):
        """Invalidate campaigns cache after updates"""
        self._campaigns_cache = None
    
    def fetch_campaign_budgets(self) -> List[Dict[str, Any]]:
        """
        Fetch campaign budget information for BigQuery storage
        
        Returns:
            List of campaign budget dictionaries with keys:
            - campaign_id: Campaign identifier
            - campaign_name: Campaign name
            - daily_budget: Daily budget amount
            - budget_type: Budget type (usually 'DAILY')
            - state: Campaign state (ENABLED, PAUSED, etc.)
            - targeting_type: Targeting type (AUTO, MANUAL)
        """
        try:
            campaigns = self.get_campaigns()
            budget_data = []
            
            for campaign in campaigns:
                if not campaign.campaign_id:
                    continue
                    
                budget_data.append({
                    'campaign_id': campaign.campaign_id,
                    'campaign_name': campaign.name,
                    'daily_budget': float(campaign.daily_budget or 0.0),
                    'budget_type': 'DAILY',  # Amazon Ads API v2 only supports daily budgets
                    'state': campaign.state,
                    'targeting_type': campaign.targeting_type,
                })
            
            logger.info(f"Fetched budget data for {len(budget_data)} campaigns")
            return budget_data
            
        except Exception as e:
            logger.error(f"Failed to fetch campaign budgets: {e}")
            return []
    
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
        """Get keywords using v2 endpoint with required filters"""
        def _is_sp_permission_error(exc: Exception) -> bool:
            """Detect the common 'Invalid key=value pair' 403 that indicates missing SP API permission."""
            try:
                # If we've already wrapped the failure, detect by message.
                msg = str(exc) if exc is not None else ""
                if "Sponsored Products API access denied" in msg or "Invalid key=value pair" in msg:
                    return True

                # Walk causal chain, if present.
                cause = getattr(exc, "__cause__", None)
                if cause is not None and cause is not exc:
                    if _is_sp_permission_error(cause):
                        return True

                resp = getattr(exc, "response", None)
                if resp is None:
                    return False
                body = (getattr(resp, "text", None) or "")
                return int(getattr(resp, "status_code", 0) or 0) == 403 and "Invalid key=value pair" in body
            except Exception:
                return False

        try:
            # v2 keywords endpoint requires filtering by campaign or ad group
            # Cannot list all keywords without filters
            if not campaign_id and not ad_group_id:
                logger.info("Keywords endpoint requires campaignIdFilter or adGroupIdFilter. Fetching by campaign...")
                # Get all campaigns first
                # Limit to active campaigns by default; archived campaigns can be numerous and
                # dramatically slow down enumeration.
                campaigns = self.get_campaigns(state_filter="enabled,paused", use_cache=False)
                all_keywords = []
                total_campaigns = len(campaigns)
                
                logger.info(f"Fetching keywords from {total_campaigns} campaigns...")
                
                # Process campaigns in batches with rate limiting
                for i, camp in enumerate(campaigns, 1):
                    try:
                        camp_keywords = self.get_keywords(campaign_id=camp.campaign_id)
                        all_keywords.extend(camp_keywords)
                        
                        if i % 10 == 0:
                            logger.info(f"Progress: {i}/{total_campaigns} campaigns processed, {len(all_keywords)} keywords found")
                    except Exception as e:
                        if _is_sp_permission_error(e):
                            # This will never succeed for any campaign under the current credentials;
                            # fail fast to avoid burning the entire Cloud Run Job timeout.
                            raise RuntimeError(
                                "Sponsored Products API access denied (403 with 'Invalid key=value pair'). "
                                "This indicates missing SP API permission / API registration for the LWA app+refresh token."
                            ) from e
                        logger.error(f"Failed to get keywords for campaign {camp.campaign_id}: {e}")
                
                logger.info(f"Completed: Retrieved {len(all_keywords)} keywords from {total_campaigns} campaigns")
                return all_keywords
            
            params = {}
            if campaign_id:
                params['campaignIdFilter'] = campaign_id
            if ad_group_id:
                params['adGroupIdFilter'] = ad_group_id
            
            # Use standard v2 keywords endpoint with filters
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
            if _is_sp_permission_error(e):
                raise RuntimeError(
                    "Sponsored Products API access denied (403 with 'Invalid key=value pair'). "
                    "This indicates missing SP API permission / API registration for the LWA app+refresh token."
                ) from e
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
        """Create performance report using the Amazon Ads Reporting v3 API."""

        report_type = (report_type or '').lower()
        segment = (segment or '').lower() or None

        # Special-case: SP Targets report creation still uses a legacy endpoint for now.
        if report_type == 'targets' and segment is None:
            payload = {
                'metrics': metrics or [],
            }

            # First try the legacy v2 path.
            try:
                response = self._request('POST', '/v2/sp/targets/report', json=payload)
                data = response.json() if response.content else {}
                rid = data.get('reportId') or data.get('report_id')
                return rid
            except Exception:
                pass

            # Then try upgraded path; if forbidden, retry with vendor Accept.
            try:
                response = self._request('POST', '/sp/targets/report', json=payload)
                data = response.json() if response.content else {}
                rid = data.get('reportId') or data.get('report_id')
                return rid
            except Exception:
                try:
                    response = self._request(
                        'POST',
                        '/sp/targets/report',
                        json=payload,
                        headers_extra={'Accept': 'application/vnd.spTargetingClause.v3+json'},
                    )
                    data = response.json() if response.content else {}
                    rid = data.get('reportId') or data.get('report_id')
                    return rid
                except Exception as exc:
                    logger.error(f"Failed to create targets report: {exc}")
                    return None

        report_definitions = {
            'campaigns': {
                'reportTypeId': 'spCampaigns',
                'groupBy': ['campaign'],
            },
            'keywords': {
                'reportTypeId': 'spKeywords',
                'groupBy': ['campaign', 'adGroup', 'keyword'],
            },
            'keywords:query': {
                'reportTypeId': 'spSearchTerm',
                'groupBy': ['searchTerm'],
            },
            'targets': {
                'reportTypeId': 'spTargets',
                'groupBy': ['campaign', 'adGroup', 'targeting'],
            },
            'targets:query': {
                'reportTypeId': 'spSearchTerm',
                'groupBy': ['searchTerm'],
            },
        }

        definition_key = report_type if segment is None else f"{report_type}:{segment}"
        definition = report_definitions.get(definition_key)

        if not definition:
            logger.error(f"Unsupported report configuration: type={report_type}, segment={segment}")
            return None

        try:
            if report_date:
                if len(report_date) == 8:
                    start_date = datetime.strptime(report_date, '%Y%m%d').date()
                else:
                    start_date = datetime.strptime(report_date, '%Y-%m-%d').date()
            else:
                start_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
            end_date = start_date
        except ValueError as exc:
            logger.error(f"Invalid report date '{report_date}': {exc}")
            return None

        columns = metrics or []

        # Reporting v3 requires format/timeUnit inside the configuration object.
        payload = {
            'name': f"{report_type}-report-{start_date.isoformat()}",
            'startDate': start_date.isoformat(),
            'endDate': end_date.isoformat(),
            'configuration': {
                'adProduct': 'SPONSORED_PRODUCTS',
                'reportTypeId': definition['reportTypeId'],
                'timeUnit': 'SUMMARY',
                'format': 'GZIP_JSON',
                'columns': columns,
                # Keep metrics for backward compatibility; some older flows used it.
                'metrics': columns,
            },
        }

        if definition.get('groupBy'):
            payload['configuration']['groupBy'] = definition['groupBy']

        try:
            # Use v2 format for reports (will be upgraded to v3 by _upgrade_endpoint)
            response = self._request('POST', '/v2/reports', json=payload)
            data = response.json() if response.content else {}
            report_id = data.get('reportId') or data.get('report_id')

            if not report_id:
                logger.error(f"Unexpected create_report response: {data}")
                return None

            logger.info(f"Created report {report_id} ({definition['reportTypeId']})")
            return report_id
        except Exception as exc:
            logger.error(f"Failed to create report: {exc}")
            return None

    def get_report_status(self, report_id: str) -> Dict:
        """Get report status"""
        try:
            # Use v2 format (will be upgraded to v3 by _upgrade_endpoint)
            endpoint = f"/v2/reports/{report_id}"
            response = self._request('GET', endpoint)
            data = response.json() if response.content else {}

            # Normalise status fields so downstream logic can continue to work.
            if 'status' not in data:
                if 'processingStatus' in data:
                    data['status'] = data['processingStatus']
                elif 'state' in data:
                    data['status'] = data['state']

            # Normalise download location keys
            if 'location' not in data:
                location = None
                if isinstance(data.get('url'), str):
                    location = data['url']
                elif isinstance(data.get('report'), dict):
                    location = data['report'].get('url') or data['report'].get('downloadUrl')
                elif isinstance(data.get('file'), dict):
                    location = data['file'].get('url')
                if location:
                    data['location'] = location

            return data
        except Exception as e:
            logger.error(f"Failed to get report status for report_id={report_id}: {e}")
            return {}
    
    def download_report(self, report_url: str) -> List[Dict]:
        """Download and parse report with retry logic"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Downloading report from {report_url} (attempt {attempt + 1}/{max_retries})")
                response = requests.get(report_url, timeout=60)
                
                # Log response details for debugging
                logger.debug(f"Report download status: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}, Size: {len(response.content)} bytes")
                
                if response.status_code >= 400:
                    logger.error(f"Report download failed with status {response.status_code}: {response.text[:500]}")
                
                response.raise_for_status()
                
                # Try to decompress as gzip or zip
                content = response.content
                
                try:
                    # Try ZIP format first
                    with zipfile.ZipFile(io.BytesIO(content)) as z:
                        names = z.namelist()
                        with z.open(names[0]) as f:
                            text = io.TextIOWrapper(f, encoding='utf-8', newline='')
                            data = list(csv.DictReader(text))
                            logger.info(f"Successfully parsed ZIP report with {len(data)} rows")
                            return data
                except zipfile.BadZipFile:
                    # Try GZIP format
                    try:
                        with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                            text = io.TextIOWrapper(gz, encoding='utf-8', newline='')
                            data = list(csv.DictReader(text))
                            logger.info(f"Successfully parsed GZIP report with {len(data)} rows")
                            return data
                    except Exception:
                        # Try as plain text
                        text = io.StringIO(content.decode('utf-8'))
                        data = list(csv.DictReader(text))
                        logger.info(f"Successfully parsed plain text report with {len(data)} rows")
                        return data
                        
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to download report after {max_retries} attempts: {e}")
                    return []
                logger.warning(f"Report download failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay * (attempt + 1))
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to parse report after {max_retries} attempts: {e}")
                    return []
                logger.warning(f"Report parsing failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay * (attempt + 1))
        
        return []
    
    def wait_for_report(self, report_id: str, timeout: int = 300) -> Optional[str]:
        """Wait for report to be ready with adaptive polling (exponential backoff).

        The default timeout is intentionally conservative for Cloud Function-style
        runtimes. For Cloud Run Jobs (or slower accounts), override via
        AMAZON_REPORT_TIMEOUT_SECONDS.
        """
        try:
            env_timeout = int(os.getenv("AMAZON_REPORT_TIMEOUT_SECONDS", "0"))
        except Exception:
            env_timeout = 0
        if env_timeout > 0 and timeout == 300:
            timeout = env_timeout
        start_time = time.time()
        try:
            poll_interval = float(os.getenv("AMAZON_REPORT_POLL_INITIAL_SECONDS", "2"))
        except Exception:
            poll_interval = 2.0
        try:
            max_poll_interval = float(os.getenv("AMAZON_REPORT_POLL_MAX_SECONDS", "10"))
        except Exception:
            max_poll_interval = 10.0
        poll_interval = max(poll_interval, 0.5)
        max_poll_interval = max(max_poll_interval, poll_interval)

        try:
            max_consecutive_status_failures = int(os.getenv("AMAZON_REPORT_MAX_STATUS_FAILURES", "8"))
        except Exception:
            max_consecutive_status_failures = 8
        max_consecutive_status_failures = max(1, max_consecutive_status_failures)

        poll_count = 0
        consecutive_status_failures = 0
        logger.info(
            "Waiting for report %s (timeout=%ss, poll_initial=%ss, poll_max=%ss)",
            report_id,
            int(timeout),
            poll_interval,
            max_poll_interval,
        )
        
        while time.time() - start_time < timeout:
            status_data = self.get_report_status(report_id)
            status = (status_data.get('status') or '').upper()

            if not status_data:
                consecutive_status_failures += 1
            else:
                consecutive_status_failures = 0

            poll_count += 1
            elapsed = time.time() - start_time
            # Log progress occasionally so long-running reports aren't "silent".
            if poll_count == 1 or poll_count % 6 == 0:
                logger.info(
                    "Report %s status=%s elapsed=%.1fs next_poll=%.1fs",
                    report_id,
                    status or "UNKNOWN",
                    elapsed,
                    poll_interval,
                )

            if consecutive_status_failures >= max_consecutive_status_failures:
                logger.error(
                    "Report %s status fetch failed %d times consecutively; aborting wait",
                    report_id,
                    consecutive_status_failures,
                )
                return None

            if status in {'SUCCESS', 'COMPLETED', 'DONE'}:
                logger.info(f"Report {report_id} ready in {elapsed:.1f}s")
                return status_data.get('location')
            elif status in {'FAILURE', 'FAILED', 'CANCELLED'}:
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
            'no_change': 0,
            # Keep track of how many keywords actually received a bid change
            'keywords_optimized': 0
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
        
        # Track keyword performance for top performers list
        keyword_performance = []
        
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
            
            # Calculate ACOS for this keyword
            acos = (metrics.cost / metrics.sales) if metrics.sales > 0 else 0.0
            
            # Determine bid change
            new_bid = self._calculate_new_bid(keyword, metrics)
            bid_change = 0.0
            
            if new_bid and abs(new_bid - keyword.bid) > 0.01:
                reason = self._get_bid_change_reason(keyword, metrics, new_bid)
                bid_change = new_bid - keyword.bid
                
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
            
            # Collect keyword performance data for top performers
            if metrics.sales > 0:  # Only include keywords with sales
                keyword_performance.append({
                    'keyword_text': keyword.keyword_text,
                    'keyword_id': keyword_id,
                    'clicks': metrics.clicks,
                    'sales': metrics.sales,
                    'cost': metrics.cost,
                    'acos': acos,
                    'bid_old': keyword.bid,
                    'bid_new': new_bid if new_bid else keyword.bid,
                    'bid_change': bid_change
                })

            # Log progress every batch_size records
            if (idx + 1) % batch_size == 0:
                logger.info(f"Processed {idx + 1}/{len(report_data)} records...")

        # Total keywords optimized equals all bid increases and decreases
        results['keywords_optimized'] = (
            results['bids_increased'] + results['bids_decreased']
        )
        
        # Apply batch updates
        if keyword_updates and not dry_run:
            logger.info(f"Applying {len(keyword_updates)} bid updates in batches...")
            batch_results = self.api.batch_update_keywords(keyword_updates)
            logger.info(f"Batch update results: {batch_results}")
        
        # Sort by sales and get top 20 performers for dashboard
        keyword_performance.sort(key=lambda x: x['sales'], reverse=True)
        top_performers = keyword_performance[:20]
        results['top_performers'] = top_performers
        
        # Calculate totals for summary
        results['total_spend'] = sum(kw['cost'] for kw in keyword_performance)
        results['total_sales'] = sum(kw['sales'] for kw in keyword_performance)
        
        logger.info(f"Collected {len(top_performers)} top performing keywords for dashboard")
        
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
    """Time-based bid adjustments with ML-driven optimization"""
    
    def __init__(self, config: Config, api: AmazonAdsAPI, audit_logger: AuditLogger, bigquery_client=None):
        self.config = config
        self.api = api
        self.audit = audit_logger
        self.bigquery_client = bigquery_client
        self.base_bids: Dict[str, float] = {}  # Store original bids
    
    def apply_intelligent_dayparting(self, dry_run: bool = False) -> Dict:
        """Apply ML-driven dayparting based on BigQuery performance data"""
        logger.info("=== Applying Intelligent Dayparting (Data-Driven) ===")
        
        # Check if dayparting is enabled
        if not self.config.get('dayparting.enabled', False):
            logger.info("Dayparting is disabled in config")
            return {}
        
        if not self.bigquery_client:
            logger.warning("BigQuery client not available, falling back to config-based dayparting")
            return self.apply_dayparting(dry_run)
        
        # Get timezone from config
        timezone_str = self.config.get('dayparting.timezone', 'US/Pacific')
        
        if pytz:
            try:
                tz = pytz.timezone(timezone_str)
                current_time = datetime.now(tz)
            except Exception as e:
                logger.warning(f"Invalid timezone '{timezone_str}', using UTC: {e}")
                current_time = datetime.now(pytz.UTC)
        else:
            current_time = datetime.now()
            logger.warning("pytz not available, using server timezone")
        
        current_hour = current_time.hour
        current_day = current_time.strftime('%A').upper()
        current_day_num = current_time.weekday()  # 0=Monday, 6=Sunday
        # Convert to SQL day_of_week (0=Sunday, 6=Saturday)
        sql_day_of_week = (current_day_num + 1) % 7
        
        logger.info(f"Current time ({timezone_str}): {current_day} (day {sql_day_of_week}) {current_hour}:00")
        
        # Fetch optimal multiplier from BigQuery
        multiplier = self._fetch_optimal_multiplier(sql_day_of_week, current_hour)
        
        if multiplier is None:
            logger.warning("No BigQuery data available, using config-based multiplier")
            multiplier = self._get_multiplier(current_hour, current_day)
        
        logger.info(f"Using multiplier: {multiplier:.2f} for {current_day} {current_hour}:00")
        
        results = {
            'keywords_updated': 0,
            'current_hour': current_hour,
            'current_day': current_day,
            'multiplier': multiplier,
            'data_source': 'bigquery' if multiplier else 'config'
        }
        
        # Get all campaigns first
        campaigns = self.api.get_campaigns()
        
        for campaign in campaigns:
            # Get keywords for this campaign
            keywords = self.api.get_keywords(campaign_id=campaign.campaign_id)
            
            for keyword in keywords:
                # Store base bid if not stored yet
                keyword_id = keyword.keyword_id
                if keyword_id not in self.base_bids:
                    self.base_bids[keyword_id] = keyword.bid
                
                base_bid = self.base_bids[keyword_id]
                new_bid = base_bid * multiplier
                
                # Apply bid caps
                min_bid = self.config.get('bid_optimization.min_bid', 0.25)
                max_bid = self.config.get('bid_optimization.max_bid', 5.0)
                new_bid = max(min_bid, min(max_bid, new_bid))
                new_bid = round(new_bid, 2)
                
                # Only update if there's a meaningful change
                if abs(new_bid - keyword.bid) > 0.01:
                    self.audit.log(
                        'INTELLIGENT_DAYPARTING',
                        'KEYWORD',
                        keyword_id,
                        f"${keyword.bid:.2f}",
                        f"${new_bid:.2f}",
                        f"Data-driven dayparting: {current_day} {current_hour}:00 ({multiplier:.2f}x) for campaign {campaign.campaign_name}",
                        dry_run
                    )
                    
                    if not dry_run:
                        self.api.update_keyword_bid(keyword_id, new_bid)
                    
                    results['keywords_updated'] += 1
        
        logger.info(f"Intelligent dayparting applied: {results}")
        return results
    
    def _fetch_optimal_multiplier(self, day_of_week: int, hour: int) -> Optional[float]:
        """Fetch optimal bid multiplier from BigQuery based on historical performance"""
        try:
            query = f"""
            SELECT 
                modifier,
                avg_acos,
                total_conversions,
                recommended
            FROM `{self.bigquery_client.dataset_ref}.hourly_bid_modifiers`
            WHERE day_of_week = {day_of_week}
              AND hour = {hour}
              AND recommended = TRUE
            ORDER BY total_conversions DESC, avg_acos ASC
            LIMIT 1
            """
            
            logger.debug(f"Fetching multiplier from BigQuery for day={day_of_week}, hour={hour}")
            
            query_job = self.bigquery_client.client.query(query)
            results = list(query_job.result())
            
            if results:
                row = results[0]
                modifier = float(row['modifier'])
                logger.info(
                    f"Found optimal multiplier from BigQuery: {modifier:.2f} "
                    f"(ACOS: {row['avg_acos']:.2f}%, Conversions: {row['total_conversions']})"
                )
                return modifier
            else:
                logger.debug(f"No BigQuery data for day={day_of_week}, hour={hour}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching multiplier from BigQuery: {e}")
            logger.debug(traceback.format_exc())
            return None
    
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
            'no_change': 0,
            # Additional metrics used by the dashboard summary
            'campaigns_analyzed': 0,
            'total_spend': 0.0,
            'total_sales': 0.0,
            'average_acos': 0.0,
            'budget_changes': 0
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
        campaign_map = {
            c.campaign_id: c
            for c in campaigns
            if c.campaign_id and (c.state or '').lower() != 'archived'
        }
        total_active_campaigns = len(campaign_map)

        analyzed_campaign_ids: Set[str] = set()
        
        # Track campaign details for dashboard
        campaign_details = []
        
        acos_threshold = self.config.get('campaign_management.acos_threshold', 0.45)
        min_spend = self.config.get('campaign_management.min_spend', 20.0)
        
        for row in report_data:
            campaign_id_raw = row.get('campaignId')
            if not campaign_id_raw:
                continue

            campaign_id = str(campaign_id_raw)
            if campaign_id not in campaign_map:
                continue

            campaign = campaign_map[campaign_id]

            analyzed_campaign_ids.add(campaign_id)
            
            # Calculate metrics
            cost = float(row.get('cost', 0) or 0)
            sales = float(row.get('attributedSales14d', 0) or 0)
            
            # Skip if not enough data
            if cost < min_spend:
                results['no_change'] += 1
                continue

            acos = (cost / sales) if sales > 0 else float('inf')

            # Track aggregated metrics for dashboard reporting
            results['total_spend'] += cost
            results['total_sales'] += sales
            
            # Calculate ACOS and other metrics for this campaign
            campaign_acos = (cost / sales) if sales > 0 else 0.0
            impressions = int(row.get('impressions', 0) or 0)
            clicks = int(row.get('clicks', 0) or 0)
            conversions = int(row.get('attributedConversions14d', 0) or 0)
            
            # Collect campaign details for dashboard
            campaign_details.append({
                'campaign_id': campaign_id,
                'campaign_name': campaign.name,
                'status': campaign.state,
                'spend': cost,
                'sales': sales,
                'acos': campaign_acos,
                'impressions': impressions,
                'clicks': clicks,
                'conversions': conversions,
                'budget': campaign.daily_budget,
                'changes_made': 0  # Will be updated if campaign state changes
            })

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
                # Mark this campaign as having changes
                if campaign_details:
                    campaign_details[-1]['changes_made'] = 1
            
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
                # Mark this campaign as having changes
                if campaign_details:
                    campaign_details[-1]['changes_made'] = 1
            else:
                results['no_change'] += 1

        results['campaigns_analyzed'] = total_active_campaigns
        results['campaigns_with_metrics'] = len(analyzed_campaign_ids)

        # Budget changes reflect any pacing adjustments
        results['budget_changes'] = (
            results['campaigns_activated'] + results['campaigns_paused']
        )

        if results['total_sales'] > 0:
            results['average_acos'] = results['total_spend'] / results['total_sales']
        else:
            results['average_acos'] = 0.0
        
        # Sort campaigns by spend and add to results for dashboard
        campaign_details.sort(key=lambda x: x['spend'], reverse=True)
        results['campaigns'] = campaign_details
        
        logger.info(f"Collected {len(campaign_details)} campaign details for dashboard")

        elapsed = time.time() - start_time
        logger.info(f"Campaign management complete in {elapsed:.2f}s: {results}")
        results['execution_time_seconds'] = round(elapsed, 2)

        # Propagate fetch error for visibility if no campaigns were analyzed
        if total_active_campaigns == 0 and getattr(self.api, '_last_campaigns_error', None) is not None:
            results['error'] = 'campaign_fetch_failed'
            results['campaign_fetch_error'] = str(self.api._last_campaigns_error)
            logger.warning("Campaign fetch failed; exposing error in results payload")
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
            'keywords_added': 0,
            'keywords_would_add': 0,
        }
        
        # Get search term report to find high-performing queries
        report_id = self.api.create_report(
            'keywords',
            ['campaignId', 'adGroupId', 'searchTerm', 'clicks', 'cost', 'sales14d'],
            segment='query'
        )
        
        if not report_id:
            logger.error("Failed to create search term report")
            return results
        
        report_url = self.api.wait_for_report(report_id)
        if not report_url:
            return results
        
        report_data = self.api.download_report(report_url)

        try:
            report_rows = len(report_data or [])
        except Exception:
            report_rows = 0
        logger.info("Keyword discovery: report_rows=%s", report_rows)

        # Track why candidates are skipped so all-zero runs are explainable.
        skip_counts = {
            'missing_query_or_ad_group': 0,
            'below_min_clicks': 0,
            'zero_sales_not_allowed': 0,
            'zero_sales_below_clicks': 0,
            'zero_sales_cost_above_limit': 0,
            'acos_above_max': 0,
            'already_exists': 0,
        }

        # Avoid an expensive full-account keyword crawl.
        # Instead, fetch existing keywords on-demand per ad group.
        existing_by_ad_group: Dict[str, set] = {}

        def _ensure_existing_loaded(ad_group_id_value: Any) -> None:
            ad_group_key = str(ad_group_id_value or "").strip()
            if not ad_group_key or ad_group_key in existing_by_ad_group:
                return

            try:
                keywords = self.api.get_keywords(ad_group_id=ad_group_key)
            except Exception as exc:
                logger.warning(
                    "Failed to fetch existing keywords for adGroupId=%s: %s",
                    ad_group_key,
                    exc,
                )
                existing_by_ad_group[ad_group_key] = set()
                return

            existing_by_ad_group[ad_group_key] = set(
                (
                    (kw.keyword_text or "").strip().lower(),
                    (kw.match_type or "").strip().lower(),
                )
                for kw in (keywords or [])
            )
        
        # Analyze search terms
        min_clicks = int(self.config.get('keyword_discovery.min_clicks', 5) or 0)
        max_acos = float(self.config.get('keyword_discovery.max_acos', 0.40) or 0.0)

        allow_zero_sales = bool(self.config.get('keyword_discovery.allow_zero_sales', False))
        zero_sales_min_clicks = int(self.config.get('keyword_discovery.zero_sales_min_clicks', min_clicks) or 0)
        zero_sales_max_cost = float(self.config.get('keyword_discovery.zero_sales_max_cost', 0.0) or 0.0)
        
        new_keywords_to_add = []
        
        for row in report_data:
            query = (row.get('searchTerm') or row.get('query') or '').strip().lower()
            ad_group_id = row.get('adGroupId')
            campaign_id = row.get('campaignId')
            
            if not query or not ad_group_id:
                skip_counts['missing_query_or_ad_group'] += 1
                continue
            
            # Calculate metrics
            clicks = int(row.get('clicks', 0) or 0)
            cost = float(row.get('cost', 0) or 0)
            sales = float(row.get('sales14d', row.get('attributedSales14d', 0)) or 0)
            
            if clicks < min_clicks:
                skip_counts['below_min_clicks'] += 1
                continue
            
            if sales <= 0:
                if not allow_zero_sales:
                    skip_counts['zero_sales_not_allowed'] += 1
                    continue
                if clicks < zero_sales_min_clicks:
                    skip_counts['zero_sales_below_clicks'] += 1
                    continue
                if zero_sales_max_cost > 0 and cost > zero_sales_max_cost:
                    skip_counts['zero_sales_cost_above_limit'] += 1
                    continue
                acos = float('inf')
            else:
                acos = (cost / sales)
                if acos > max_acos:
                    skip_counts['acos_above_max'] += 1
                    continue
            
            # Check if already exists
            _ensure_existing_loaded(ad_group_id)
            if (query, 'exact') in existing_by_ad_group.get(str(ad_group_id), set()):
                skip_counts['already_exists'] += 1
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
            results['keywords_would_add'] = len(new_keywords_to_add)
        
        elapsed = time.time() - start_time
        logger.info(
            "Keyword discovery skip summary: %s",
            {
                **skip_counts,
                'candidates': len(new_keywords_to_add),
                'min_clicks': min_clicks,
                'max_acos': max_acos,
                'allow_zero_sales': allow_zero_sales,
                'zero_sales_min_clicks': zero_sales_min_clicks,
                'zero_sales_max_cost': zero_sales_max_cost,
            },
        )
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

        try:
            report_rows = len(report_data or [])
        except Exception:
            report_rows = 0
        logger.info("Negative keywords: report_rows=%s", report_rows)
        
        # Get existing negative keywords
        existing_negatives = self.api.get_negative_keywords()
        logger.info("Negative keywords: existing_negatives=%s", len(existing_negatives or []))
        existing_negative_texts = {
            (nk.get('campaignId'), nk.get('keywordText', '').lower())
            for nk in existing_negatives
        }
        
        # Analyze search terms
        min_spend = self.config.get('negative_keywords.min_spend', 10.0)
        max_acos = self.config.get('negative_keywords.max_acos', 1.0)

        skip_counts = {
            'missing_query_or_campaign': 0,
            'below_min_spend': 0,
            'acos_below_threshold': 0,
            'already_negative': 0,
        }
        
        negatives_to_add = []
        
        for row in report_data:
            query = row.get('query', '').strip().lower()
            campaign_id = row.get('campaignId')
            
            if not query or not campaign_id:
                skip_counts['missing_query_or_campaign'] += 1
                continue
            
            cost = float(row.get('cost', 0) or 0)
            sales = float(row.get('attributedSales14d', 0) or 0)
            
            if cost < min_spend:
                skip_counts['below_min_spend'] += 1
                continue
            
            acos = (cost / sales) if sales > 0 else float('inf')
            
            if acos < max_acos:
                skip_counts['acos_below_threshold'] += 1
                continue
            
            # Check if already negative
            if (campaign_id, query) in existing_negative_texts:
                skip_counts['already_negative'] += 1
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
        
        logger.info(
            "Negative keywords skip summary: %s",
            {
                **skip_counts,
                'candidates': len(negatives_to_add),
                'min_spend': min_spend,
                'max_acos': max_acos,
            },
        )
        logger.info(f"Negative keyword management complete: {results}")
        return results


# ============================================================================
# MAIN AUTOMATION ORCHESTRATOR
# ============================================================================

class PPCAutomation:
    """Main automation orchestrator with comprehensive error handling.

    Optionally accepts a dashboard client for streaming granular progress.
    """
    
    def __init__(self, config_path: str, profile_id: str, dry_run: bool = False, bigquery_client=None, dashboard_client=None):
        self.config = Config(config_path)
        self.profile_id = profile_id
        self.dry_run = dry_run
        self.bigquery_client = bigquery_client
        self.dashboard_client = dashboard_client
        
        # Initialize API client with configurable rate limit
        region = self.config.get('api.region', 'NA')
        max_requests_per_second = self.config.get('api.max_requests_per_second', MAX_REQUESTS_PER_SECOND)
        self.api = AmazonAdsAPI(profile_id, region, max_requests_per_second=max_requests_per_second)
        
        # Initialize audit logger
        audit_output_dir = self.config.get('logging.output_dir', './logs')
        self.audit = AuditLogger(audit_output_dir)
        
        # Initialize feature modules
        self.bid_optimizer = BidOptimizer(self.config, self.api, self.audit)
        self.dayparting = DaypartingManager(self.config, self.api, self.audit, bigquery_client)
        self.campaign_manager = CampaignManager(self.config, self.api, self.audit)
        self.keyword_discovery = KeywordDiscovery(self.config, self.api, self.audit)
        self.negative_keywords = NegativeKeywordManager(self.config, self.api, self.audit)
    
    def run(self, features: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run automation with specified features
        
        Args:
            features: List of features to run (None = use config defaults)
            
        Returns:
            Dictionary of results for each feature
        """
        logger.info("=" * 80)
        logger.info("AMAZON PPC AUTOMATION SUITE")
        logger.info("=" * 80)
        logger.info(f"Profile ID: {self.profile_id}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 80)
        
        if features is None:
            features = self.config.get('features.enabled', [])
        
        # Ensure features is a list
        if not isinstance(features, list):
            logger.warning(f"Invalid features type: {type(features)}, using default features")
            features = []
        
        logger.info(f"Enabled features: {', '.join(features) if features else 'None'}")
        
        results = {}
        
        try:
            total = len(features)
            # Define progress window (internal feature execution stays between 25% and 80%)
            start_pct = 25.0
            end_pct = 80.0
            pct_span = end_pct - start_pct if total > 0 else 0

            for idx, feature in enumerate(features):
                current_pct = start_pct + (idx / max(total, 1)) * pct_span
                if self.dashboard_client:
                    try:
                        self.dashboard_client.send_progress(f"Starting {feature}...", current_pct)
                    except Exception:
                        logger.debug("Dashboard progress send failed (non-blocking)")

                try:
                    if feature == 'bid_optimization':
                        results['bid_optimization'] = self.bid_optimizer.optimize(self.dry_run)
                    elif feature == 'dayparting':
                        if self.bigquery_client:
                            results['dayparting'] = self.dayparting.apply_intelligent_dayparting(self.dry_run)
                        else:
                            results['dayparting'] = self.dayparting.apply_dayparting(self.dry_run)
                    elif feature == 'campaign_management':
                        results['campaign_management'] = self.campaign_manager.manage_campaigns(self.dry_run)
                    elif feature == 'keyword_discovery':
                        results['keyword_discovery'] = self.keyword_discovery.discover_keywords(self.dry_run)
                    elif feature == 'negative_keywords':
                        results['negative_keywords'] = self.negative_keywords.add_negative_keywords(self.dry_run)
                    else:
                        logger.warning(f"Unknown feature '{feature}' encountered; skipping")
                        results[feature] = {'warning': 'unknown_feature'}
                except Exception as e:
                    logger.error(f"{feature} failed: {e}")
                    logger.debug(traceback.format_exc())
                    results[feature] = {'error': str(e)}

                # After feature completion, emit feature-level update
                post_pct = start_pct + ((idx + 1) / max(total, 1)) * pct_span
                if self.dashboard_client:
                    try:
                        self.dashboard_client.send_feature_update(feature, results.get(feature, {}), post_pct)
                    except Exception:
                        logger.debug("Dashboard feature update failed (non-blocking)")

        except Exception as e:
            logger.error(f"Automation failed with unexpected error: {e}")
            logger.error(traceback.format_exc())
            results['error'] = str(e)
        finally:
            # Save audit trail
            try:
                self.audit.save()
            except Exception as e:
                logger.error(f"Failed to save audit trail: {e}")
        
        # Print summary
        logger.info("=" * 80)
        logger.info("AUTOMATION SUMMARY")
        logger.info("=" * 80)
        for feature, result in results.items():
            if isinstance(result, dict):
                logger.info(f"\n{feature.upper().replace('_', ' ')}:")
                for key, value in result.items():
                    logger.info(f"  {key}: {value}")
            else:
                logger.info(f"\n{feature.upper().replace('_', ' ')}: {result}")
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
