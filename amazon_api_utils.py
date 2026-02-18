"""
Amazon Ads API Utility Functions

This module provides utility functions for working with Amazon Ads API responses,
including handling gzip-compressed responses that can cause UnicodeDecodeError.
"""

import gzip
import logging
from typing import Union

logger = logging.getLogger(__name__)


def decode_api_response(data_bytes: bytes, encoding: str = 'utf-8') -> str:
    """
    Safely decode API response data, handling both plain text and gzip compression.
    
    Amazon Ads API sometimes returns gzip-compressed responses even without
    Content-Encoding header. This function detects gzip magic number (0x1f 0x8b)
    and decompresses before decoding.
    
    Args:
        data_bytes: Raw bytes from API response
        encoding: Target encoding (default: utf-8)
        
    Returns:
        Decoded string content
        
    Raises:
        UnicodeDecodeError: If decompressed data can't be decoded
        gzip.BadGzipFile: If gzip header is invalid
        
    Example:
        >>> # Plain text response
        >>> response = requests.get(url)
        >>> content = decode_api_response(response.content)
        
        >>> # Works with gzip-compressed responses too
        >>> import gzip
        >>> compressed = gzip.compress(b"Hello, World!")
        >>> content = decode_api_response(compressed)
        >>> print(content)
        'Hello, World!'
    """
    if len(data_bytes) >= 2 and data_bytes[0] == 0x1f and data_bytes[1] == 0x8b:
        # Gzip-compressed response (magic number: 0x1f 0x8b)
        logger.debug(f"Detected gzip-compressed response ({len(data_bytes)} bytes)")
        try:
            decompressed = gzip.decompress(data_bytes)
            logger.debug(f"Decompressed to {len(decompressed)} bytes")
            return decompressed.decode(encoding)
        except Exception as e:
            logger.error(f"Failed to decompress gzip response: {e}")
            raise
    else:
        # Plain text response
        logger.debug(f"Decoding plain text response ({len(data_bytes)} bytes)")
        return data_bytes.decode(encoding)
