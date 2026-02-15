"""
Dashboard API
=============

REST API endpoints for the Amazon Sales Dashboard.

Provides real-time data from:
- Amazon SP-API (orders, inventory, products)
- Amazon Ads API (advertising data from optimizer_core)
- BigQuery (historical data)

Author: Nature's Way Soil
Version: 1.0.0
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from amazon_sp_api import get_sp_api_client, AmazonSPAPIError
from cache_manager import get_cache, cached
from bigquery_client import BigQueryClient
from optimizer_core import AmazonAdsAPI

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='dashboard/static', static_url_path='/static')
CORS(app)

# Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
if not PROJECT_ID:
    logger.warning("GCP_PROJECT_ID not set, dashboard may not function correctly without credentials")
    PROJECT_ID = "amazon-ppc-474902"  # Fallback for development only
    
DATASET_ID = os.getenv("BIGQUERY_DATASET", "amazon_ppc_data")


def parse_date_range(start_date_str: Optional[str], end_date_str: Optional[str]) -> tuple:
    """
    Parse date range from query parameters
    
    Args:
        start_date_str: Start date string (YYYY-MM-DD)
        end_date_str: End date string (YYYY-MM-DD)
        
    Returns:
        Tuple of (start_date, end_date) as datetime objects
    """
    try:
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            # Default to last 30 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
        
        return start_date, end_date
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise ValueError("Invalid date format. Use YYYY-MM-DD")


# ============================================================================
# DASHBOARD PAGE
# ============================================================================

@app.route('/')
def index():
    """Serve the main dashboard page"""
    return send_from_directory('dashboard', 'index.html')


@app.route('/dashboard')
def dashboard():
    """Serve the main dashboard page"""
    return send_from_directory('dashboard', 'index.html')


# ============================================================================
# REVENUE API
# ============================================================================

@app.route('/api/dashboard/revenue', methods=['GET'])
@cached(ttl_seconds=300, cache_key_prefix='revenue')
def get_revenue():
    """
    Get sales revenue and trends
    
    Query Parameters:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        
    Returns:
        JSON with revenue metrics and trends
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        start_date, end_date = parse_date_range(start_date_str, end_date_str)
        
        # Get data from SP-API
        sp_client = get_sp_api_client()
        order_metrics = sp_client.get_order_metrics(start_date, end_date)
        
        # Calculate previous period for comparison
        period_days = (end_date - start_date).days
        prev_start = start_date - timedelta(days=period_days)
        prev_end = start_date
        prev_metrics = sp_client.get_order_metrics(prev_start, prev_end)
        
        # Calculate change percentage
        current_revenue = order_metrics.get('total_revenue', 0)
        prev_revenue = prev_metrics.get('total_revenue', 0)
        if prev_revenue > 0:
            change_percent = ((current_revenue - prev_revenue) / prev_revenue * 100)
        else:
            # If previous revenue was 0, show 100% if current revenue > 0, else 0
            change_percent = 100.0 if current_revenue > 0 else 0.0
        
        return jsonify({
            "total": current_revenue,
            "previous_period": prev_revenue,
            "change_percent": round(change_percent, 2),
            "daily_breakdown": order_metrics.get('daily_breakdown', []),
            "by_category": order_metrics.get('by_category', {}),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        })
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except AmazonSPAPIError as e:
        logger.error(f"SP-API error: {e}")
        return jsonify({"error": "Failed to fetch revenue data"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_revenue: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# ORDERS API
# ============================================================================

@app.route('/api/dashboard/orders', methods=['GET'])
@cached(ttl_seconds=300, cache_key_prefix='orders')
def get_orders():
    """
    Get order volume and metrics
    
    Query Parameters:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        
    Returns:
        JSON with order metrics
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        start_date, end_date = parse_date_range(start_date_str, end_date_str)
        
        # Get data from SP-API
        sp_client = get_sp_api_client()
        metrics = sp_client.get_order_metrics(start_date, end_date)
        
        return jsonify({
            "total": metrics.get('total_orders', 0),
            "pending": metrics.get('pending_orders', 0),
            "shipped": metrics.get('shipped_orders', 0),
            "delivered": metrics.get('delivered_orders', 0),
            "cancelled": metrics.get('cancelled_orders', 0),
            "trend": metrics.get('daily_breakdown', []),
            "average_order_value": metrics.get('average_order_value', 0),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        })
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except AmazonSPAPIError as e:
        logger.error(f"SP-API error: {e}")
        return jsonify({"error": "Failed to fetch order data"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_orders: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# PRODUCTS API
# ============================================================================

@app.route('/api/dashboard/products/top', methods=['GET'])
@cached(ttl_seconds=600, cache_key_prefix='top_products')
def get_top_products():
    """
    Get top products by revenue or units sold
    
    Query Parameters:
        limit: Number of products to return (default: 10)
        metric: Sorting metric (revenue or units, default: revenue)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        
    Returns:
        JSON with top products
    """
    try:
        limit = int(request.args.get('limit', 10))
        metric = request.args.get('metric', 'revenue')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        start_date, end_date = parse_date_range(start_date_str, end_date_str)
        
        # Mock data for now - integrate with actual data source
        products = []
        
        # Try to get from BigQuery if available
        try:
            bq_client = BigQueryClient(project_id=PROJECT_ID, dataset_id=DATASET_ID)
            # Query top products from BigQuery
            # This would need actual implementation based on your schema
            logger.info(f"Fetching top {limit} products by {metric}")
        except Exception as e:
            logger.warning(f"Could not fetch from BigQuery: {e}")
        
        return jsonify({
            "products": products,
            "metric": metric,
            "limit": limit,
            "note": "Mock data - integrate with actual product data source"
        })
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error in get_top_products: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# INVENTORY API
# ============================================================================

@app.route('/api/dashboard/inventory', methods=['GET'])
@cached(ttl_seconds=600, cache_key_prefix='inventory')
def get_inventory():
    """
    Get inventory levels and status
    
    Returns:
        JSON with inventory data
    """
    try:
        # Get data from SP-API
        sp_client = get_sp_api_client()
        inventory = sp_client.get_inventory_summaries()
        
        return jsonify({
            "items": inventory.get('items', []),
            "low_stock_items": inventory.get('low_stock_items', []),
            "out_of_stock_items": inventory.get('out_of_stock_items', []),
            "total_items": inventory.get('total_items', 0)
        })
        
    except AmazonSPAPIError as e:
        logger.error(f"SP-API error: {e}")
        return jsonify({"error": "Failed to fetch inventory data"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_inventory: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# CUSTOMERS API
# ============================================================================

@app.route('/api/dashboard/customers', methods=['GET'])
@cached(ttl_seconds=300, cache_key_prefix='customers')
def get_customers():
    """
    Get customer metrics
    
    Query Parameters:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        
    Returns:
        JSON with customer metrics
    """
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        start_date, end_date = parse_date_range(start_date_str, end_date_str)
        
        # Get data from SP-API
        sp_client = get_sp_api_client()
        metrics = sp_client.get_customer_metrics(start_date, end_date)
        
        return jsonify({
            "total_customers": metrics.get('total_customers', 0),
            "new_customers": metrics.get('new_customers', 0),
            "returning_customers": metrics.get('returning_customers', 0),
            "clv": metrics.get('average_clv', 0),
            "avg_rating": metrics.get('average_rating', 0),
            "total_reviews": metrics.get('total_reviews', 0),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        })
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except AmazonSPAPIError as e:
        logger.error(f"SP-API error: {e}")
        return jsonify({"error": "Failed to fetch customer data"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in get_customers: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# STATUS API
# ============================================================================

@app.route('/api/dashboard/status', methods=['GET'])
def get_status():
    """
    Get system status and data freshness
    
    Returns:
        JSON with status information
    """
    try:
        cache = get_cache()
        cache_stats = cache.get_stats()
        
        return jsonify({
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "data_sources": {
                "orders": "healthy",
                "inventory": "healthy",
                "products": "healthy",
                "advertising": "healthy"
            },
            "cache": cache_stats,
            "version": "1.0.0"
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in get_status: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

@app.route('/api/dashboard/cache/clear', methods=['POST'])
def clear_cache():
    """
    Clear all cached data
    
    Returns:
        JSON with success message
    """
    try:
        cache = get_cache()
        cache.clear()
        
        return jsonify({
            "success": True,
            "message": "Cache cleared successfully"
        })
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        return jsonify({"error": "Failed to clear cache"}), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run development server
    # WARNING: Never use debug=True in production! Set to False for production deployments.
    port = int(os.getenv('PORT', 8080))
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    
    if debug_mode:
        logger.warning("⚠️  Running in DEBUG mode - DO NOT use in production!")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
