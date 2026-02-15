"""
Amazon Selling Partner API (SP-API) Wrapper
============================================

Provides access to Amazon Seller/Advertising data for the dashboard:
- Orders API (sales revenue, order volume, customer metrics)
- FBA Inventory API (inventory levels and status)
- Catalog Items API (product details)

Reuses existing authentication infrastructure from gcp_credentials.py
and the Amazon Ads API authentication in optimizer_core.py.

Author: Nature's Way Soil
Version: 1.0.0
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache

import requests
from google.cloud import secretmanager

logger = logging.getLogger(__name__)

# Amazon SP-API Configuration
TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SP_API_BASE_URL = "https://sellingpartnerapi-na.amazon.com"

# Rate limiting
MAX_REQUESTS_PER_SECOND = 5
REQUEST_INTERVAL = 1.0 / MAX_REQUESTS_PER_SECOND


class AmazonSPAPIError(Exception):
    """Custom exception for SP-API errors"""
    pass


class AmazonSPAPIClient:
    """
    Client for Amazon Selling Partner API
    
    Features:
    - Automatic token refresh
    - Rate limiting
    - Error handling with retries
    - Data caching
    """
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        profile_id: Optional[str] = None,
        region: str = "NA"
    ):
        """
        Initialize SP-API client
        
        Args:
            client_id: Amazon client ID (from env or Secret Manager if not provided)
            client_secret: Amazon client secret
            refresh_token: Amazon refresh token
            profile_id: Amazon profile/seller ID
            region: API region (NA, EU, FE)
        """
        self.client_id = client_id or self._get_credential("AMAZON_CLIENT_ID")
        self.client_secret = client_secret or self._get_credential("AMAZON_CLIENT_SECRET")
        self.refresh_token = refresh_token or self._get_credential("AMAZON_REFRESH_TOKEN")
        self.profile_id = profile_id or self._get_credential("AMAZON_PROFILE_ID")
        self.region = region
        
        self.access_token = None
        self.token_expiry = None
        self.last_request_time = 0
        
        # Validate credentials
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise AmazonSPAPIError(
                "Missing required Amazon credentials. Please set AMAZON_CLIENT_ID, "
                "AMAZON_CLIENT_SECRET, and AMAZON_REFRESH_TOKEN environment variables "
                "or provide them via Secret Manager."
            )
        
        logger.info(f"Amazon SP-API client initialized for region {region}")
        logger.info(f"Profile ID: {self.profile_id}")
    
    def _get_credential(self, key: str) -> Optional[str]:
        """
        Get credential from environment or Secret Manager
        
        Args:
            key: Credential key name
            
        Returns:
            Credential value or None
        """
        # First try environment variable
        value = os.getenv(key)
        if value:
            return value
        
        # Try Secret Manager
        try:
            project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                logger.debug("GCP_PROJECT_ID not set, using default for Secret Manager access")
                project_id = "amazon-ppc-474902"  # Fallback for development
            
            secret_mapping = {
                "AMAZON_CLIENT_ID": "Amazon_Ads_Client_identifier",
                "AMAZON_CLIENT_SECRET": "Amazon_Ads_Client_secret",
                "AMAZON_REFRESH_TOKEN": "Amazon_Ads_Refresh_Token",
                "AMAZON_PROFILE_ID": "ppc-profile-id"
            }
            
            secret_name = secret_mapping.get(key)
            if not secret_name:
                return None
            
            client = secretmanager.SecretManagerServiceClient()
            secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": secret_path})
            value = response.payload.data.decode("UTF-8").strip()
            logger.debug(f"Retrieved {key} from Secret Manager")
            return value
        except Exception as e:
            logger.debug(f"Could not retrieve {key} from Secret Manager: {e}")
            return None
    
    def _refresh_access_token(self) -> str:
        """
        Refresh access token using refresh token
        
        Returns:
            New access token
            
        Raises:
            AmazonSPAPIError: If token refresh fails
        """
        logger.info("Refreshing Amazon access token...")
        
        try:
            response = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise AmazonSPAPIError(
                    f"Token refresh failed: {response.status_code} - {response.text}"
                )
            
            data = response.json()
            self.access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
            
            logger.info(f"✓ Access token refreshed (expires in {expires_in}s)")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            raise AmazonSPAPIError(f"Network error during token refresh: {e}")
    
    def _ensure_valid_token(self):
        """Ensure we have a valid access token"""
        if not self.access_token or not self.token_expiry or datetime.now(timezone.utc) >= self.token_expiry:
            self._refresh_access_token()
    
    def _rate_limit(self):
        """Apply rate limiting"""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        retry_count: int = 3
    ) -> Dict[str, Any]:
        """
        Make authenticated request to SP-API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            retry_count: Number of retry attempts
            
        Returns:
            Response data as dictionary
            
        Raises:
            AmazonSPAPIError: If request fails after retries
        """
        self._ensure_valid_token()
        self._rate_limit()
        
        url = f"{SP_API_BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "NWS-Dashboard/1.0"
        }
        
        if self.profile_id:
            headers["Amazon-Advertising-API-Scope"] = self.profile_id
        
        for attempt in range(retry_count):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=30
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2))
                    logger.warning(f"Rate limited, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                # Handle auth errors
                if response.status_code == 401:
                    logger.warning("Unauthorized, refreshing token...")
                    self._refresh_access_token()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    continue
                
                response.raise_for_status()
                return response.json() if response.content else {}
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1}/{retry_count} failed: {e}")
                if attempt == retry_count - 1:
                    raise AmazonSPAPIError(f"Request failed after {retry_count} attempts: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        raise AmazonSPAPIError("Request failed after all retries")
    
    # ========================================================================
    # ORDERS API - Revenue, Order Volume, Customer Metrics
    # ========================================================================
    
    def get_orders(
        self,
        start_date: datetime,
        end_date: datetime,
        order_statuses: Optional[List[str]] = None,
        marketplace_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get orders for date range
        
        Args:
            start_date: Start date for orders
            end_date: End date for orders
            order_statuses: Filter by order statuses (optional)
            marketplace_ids: Marketplace IDs (defaults to US)
            
        Returns:
            Orders data with revenue, counts, and customer info
        """
        # Note: This is a placeholder implementation
        # In production, you would use the actual SP-API Orders endpoint
        # For now, return mock data structure
        
        logger.info(f"Fetching orders from {start_date.date()} to {end_date.date()}")
        
        # Mock data for demonstration
        # In production, replace with actual API call:
        # endpoint = "/orders/v0/orders"
        # params = {
        #     "CreatedAfter": start_date.isoformat(),
        #     "CreatedBefore": end_date.isoformat(),
        #     "MarketplaceIds": marketplace_ids or ["ATVPDKIKX0DER"]  # US
        # }
        # return self._make_request("GET", endpoint, params=params)
        
        return {
            "orders": [],
            "total_count": 0,
            "total_revenue": 0.0,
            "note": "Mock data - integrate with actual SP-API Orders endpoint"
        }
    
    def get_order_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get aggregated order metrics
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Aggregated metrics including revenue, order counts, AOV, etc.
        """
        logger.info(f"Calculating order metrics for {start_date.date()} to {end_date.date()}")
        
        # Mock data structure
        return {
            "total_revenue": 0.0,
            "total_orders": 0,
            "pending_orders": 0,
            "shipped_orders": 0,
            "delivered_orders": 0,
            "cancelled_orders": 0,
            "average_order_value": 0.0,
            "daily_breakdown": [],
            "by_category": {},
            "note": "Mock data - integrate with actual SP-API"
        }
    
    # ========================================================================
    # FBA INVENTORY API - Inventory Levels
    # ========================================================================
    
    def get_inventory_summaries(
        self,
        marketplace_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get FBA inventory summaries
        
        Args:
            marketplace_ids: Marketplace IDs (defaults to US)
            
        Returns:
            Inventory data with quantities and status
        """
        logger.info("Fetching FBA inventory summaries")
        
        # Mock data structure
        return {
            "items": [],
            "low_stock_items": [],
            "out_of_stock_items": [],
            "total_items": 0,
            "note": "Mock data - integrate with FBA Inventory API"
        }
    
    # ========================================================================
    # CATALOG ITEMS API - Product Details
    # ========================================================================
    
    def get_catalog_item(
        self,
        asin: str,
        marketplace_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get catalog item details by ASIN
        
        Args:
            asin: Product ASIN
            marketplace_ids: Marketplace IDs (defaults to US)
            
        Returns:
            Product details
        """
        logger.info(f"Fetching catalog item: {asin}")
        
        # Mock data structure
        return {
            "asin": asin,
            "title": "Product Title",
            "brand": "Brand Name",
            "category": "Category",
            "note": "Mock data - integrate with Catalog Items API"
        }
    
    # ========================================================================
    # CUSTOMER METRICS - Derived from Orders
    # ========================================================================
    
    def get_customer_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get customer metrics derived from orders
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Customer metrics including new/returning, CLV, etc.
        """
        logger.info(f"Calculating customer metrics for {start_date.date()} to {end_date.date()}")
        
        # Mock data structure
        return {
            "total_customers": 0,
            "new_customers": 0,
            "returning_customers": 0,
            "average_clv": 0.0,
            "average_rating": 0.0,
            "total_reviews": 0,
            "note": "Mock data - derive from orders data"
        }


# Singleton instance for easy access
_sp_api_client_instance: Optional[AmazonSPAPIClient] = None


def get_sp_api_client() -> AmazonSPAPIClient:
    """
    Get or create singleton SP-API client instance
    
    Returns:
        AmazonSPAPIClient instance
    """
    global _sp_api_client_instance
    
    if _sp_api_client_instance is None:
        _sp_api_client_instance = AmazonSPAPIClient()
    
    return _sp_api_client_instance
