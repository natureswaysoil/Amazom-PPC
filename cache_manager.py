"""
Cache Manager
=============

Simple in-memory caching layer for API responses to reduce API calls
and improve performance.

Features:
- Time-based expiration (TTL)
- Automatic cache invalidation
- Thread-safe operations
- Memory-efficient storage

Author: Nature's Way Soil
Version: 1.0.0
"""

import logging
import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, Optional, Callable
from functools import wraps
import hashlib
import json

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Simple in-memory cache with TTL support
    
    Features:
    - Time-to-live (TTL) expiration
    - Thread-safe operations
    - Automatic cleanup
    - Size limits
    """
    
    def __init__(self, default_ttl_seconds: int = 300, max_entries: int = 1000):
        """
        Initialize cache manager
        
        Args:
            default_ttl_seconds: Default TTL in seconds (5 minutes)
            max_entries: Maximum number of cache entries
                        Default 1000 entries ~= 1-10MB depending on data size
                        For high-memory systems, increase to 5000-10000
                        For memory-constrained systems, reduce to 100-500
        """
        self.default_ttl = default_ttl_seconds
        self.max_entries = max_entries
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        logger.info(f"Cache manager initialized (TTL: {default_ttl_seconds}s, Max entries: {max_entries})")
    
    def _generate_key(self, key: str, **kwargs) -> str:
        """
        Generate cache key from function arguments
        
        Args:
            key: Base key
            **kwargs: Additional key components
            
        Returns:
            Cache key string
        """
        if kwargs:
            # Create deterministic key from kwargs
            key_parts = [key]
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, sort_keys=True)
                key_parts.append(f"{k}:{v}")
            combined_key = "|".join(key_parts)
            return hashlib.md5(combined_key.encode()).hexdigest()
        return key
    
    def get(self, key: str, **kwargs) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            **kwargs: Additional key components
            
        Returns:
            Cached value or None if not found or expired
        """
        cache_key = self._generate_key(key, **kwargs)
        
        with self._lock:
            if cache_key not in self._cache:
                return None
            
            entry = self._cache[cache_key]
            
            # Check expiration
            if time.time() > entry["expires_at"]:
                logger.debug(f"Cache expired: {cache_key}")
                del self._cache[cache_key]
                return None
            
            logger.debug(f"Cache hit: {cache_key}")
            return entry["value"]
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None, **kwargs):
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (uses default if not specified)
            **kwargs: Additional key components
        """
        cache_key = self._generate_key(key, **kwargs)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        
        with self._lock:
            # Evict oldest entries if at capacity
            if len(self._cache) >= self.max_entries:
                self._evict_oldest()
            
            self._cache[cache_key] = {
                "value": value,
                "created_at": time.time(),
                "expires_at": time.time() + ttl
            }
            logger.debug(f"Cache set: {cache_key} (TTL: {ttl}s)")
    
    def invalidate(self, key: str, **kwargs):
        """
        Invalidate cache entry
        
        Args:
            key: Cache key
            **kwargs: Additional key components
        """
        cache_key = self._generate_key(key, **kwargs)
        
        with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                logger.debug(f"Cache invalidated: {cache_key}")
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def _evict_oldest(self):
        """Evict oldest cache entry"""
        if not self._cache:
            return
        
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["created_at"])
        del self._cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            total_entries = len(self._cache)
            expired_count = sum(
                1 for entry in self._cache.values()
                if time.time() > entry["expires_at"]
            )
            
            return {
                "total_entries": total_entries,
                "expired_entries": expired_count,
                "active_entries": total_entries - expired_count,
                "max_entries": self.max_entries,
                "utilization": total_entries / self.max_entries if self.max_entries > 0 else 0
            }


# Global cache instance
_cache_instance: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """
    Get or create global cache instance
    
    Returns:
        CacheManager instance
    """
    global _cache_instance
    
    if _cache_instance is None:
        _cache_instance = CacheManager()
    
    return _cache_instance


def cached(ttl_seconds: int = 300, cache_key_prefix: Optional[str] = None):
    """
    Decorator for caching function results
    
    Args:
        ttl_seconds: Cache TTL in seconds
        cache_key_prefix: Custom cache key prefix (uses function name if not provided)
        
    Example:
        @cached(ttl_seconds=600)
        def get_expensive_data(param1, param2):
            # ... expensive operation
            return result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            key_prefix = cache_key_prefix or func.__name__
            
            # Generate cache key from args and kwargs
            cache_kwargs = {}
            if args:
                cache_kwargs["args"] = str(args)
            if kwargs:
                cache_kwargs.update(kwargs)
            
            # Try to get from cache
            cached_value = cache.get(key_prefix, **cache_kwargs)
            if cached_value is not None:
                logger.debug(f"Returning cached result for {func.__name__}")
                return cached_value
            
            # Execute function and cache result
            logger.debug(f"Cache miss for {func.__name__}, executing function")
            result = func(*args, **kwargs)
            cache.set(key_prefix, result, ttl_seconds=ttl_seconds, **cache_kwargs)
            
            return result
        
        return wrapper
    return decorator
