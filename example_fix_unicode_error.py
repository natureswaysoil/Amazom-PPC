#!/usr/bin/env python3
"""
Example: How to fix UnicodeDecodeError in amazon_ads_sync.py

This example shows how to use the decode_api_response utility
to fix the UnicodeDecodeError that occurs when Amazon Ads API
returns gzip-compressed responses.

The problematic code (line 762 in /app/jobs/data_sync/amazon_ads_sync.py):
    content = data_bytes.decode('utf-8')  # ❌ Fails on gzip data

Should be replaced with:
    from amazon_api_utils import decode_api_response
    content = decode_api_response(data_bytes)  # ✅ Handles both plain and gzip
"""

import json
import gzip
from amazon_api_utils import decode_api_response


def example_placement_performance_sync():
    """
    Example showing how to use decode_api_response in placement performance sync.
    
    This simulates the scenario described in the problem statement where
    amazon_ads_sync.py line 762 was failing with UnicodeDecodeError.
    """
    print("=" * 80)
    print("Example: Fixing UnicodeDecodeError in Placement Performance Sync")
    print("=" * 80)
    
    # Simulate Amazon Ads API response (could be plain or gzip-compressed)
    api_response_data = {
        "placements": [
            {"placement": "top-of-search", "impressions": 1000, "clicks": 50},
            {"placement": "product-pages", "impressions": 500, "clicks": 25}
        ],
        "total_spend": 125.50,
        "total_sales": 450.00
    }
    
    # Simulate both response types
    print("\n1. Testing with PLAIN UTF-8 response:")
    print("-" * 80)
    plain_bytes = json.dumps(api_response_data).encode('utf-8')
    print(f"   Response bytes (first 50): {plain_bytes[:50]}...")
    
    # OLD WAY (would work for plain text, but fail for gzip):
    # content = plain_bytes.decode('utf-8')  # ❌
    
    # NEW WAY (works for both):
    content = decode_api_response(plain_bytes)  # ✅
    parsed_data = json.loads(content)
    print(f"   ✓ Successfully decoded: {len(content)} characters")
    print(f"   ✓ Parsed data: {parsed_data['placements'][0]}")
    
    print("\n2. Testing with GZIP-COMPRESSED response:")
    print("-" * 80)
    gzip_bytes = gzip.compress(json.dumps(api_response_data).encode('utf-8'))
    print(f"   Response bytes (first 50): {gzip_bytes[:50]}...")
    print(f"   Detected gzip magic number: 0x{gzip_bytes[0]:02x} 0x{gzip_bytes[1]:02x}")
    
    # OLD WAY (would fail with UnicodeDecodeError):
    # try:
    #     content = gzip_bytes.decode('utf-8')  # ❌ UnicodeDecodeError!
    # except UnicodeDecodeError as e:
    #     print(f"   ✗ ERROR: {e}")
    
    # NEW WAY (automatically detects and decompresses):
    content = decode_api_response(gzip_bytes)  # ✅
    parsed_data = json.loads(content)
    print(f"   ✓ Successfully decoded and decompressed: {len(content)} characters")
    print(f"   ✓ Parsed data: {parsed_data['placements'][1]}")
    
    print("\n3. Code comparison:")
    print("-" * 80)
    print("   Before (❌ fails on gzip):")
    print("       content = data_bytes.decode('utf-8')")
    print()
    print("   After (✅ works for both plain and gzip):")
    print("       from amazon_api_utils import decode_api_response")
    print("       content = decode_api_response(data_bytes)")
    
    print("\n" + "=" * 80)
    print("✓ Example completed successfully!")
    print("=" * 80)


def example_fix_for_amazon_ads_sync():
    """
    Shows the exact fix needed for /app/jobs/data_sync/amazon_ads_sync.py
    """
    print("\n\n" + "=" * 80)
    print("Fix for /app/jobs/data_sync/amazon_ads_sync.py")
    print("=" * 80)
    
    print("\nLine 762 currently has:")
    print("    content = data_bytes.decode('utf-8')  # ❌ Fails on gzip")
    
    print("\nChange to:")
    print("    from amazon_api_utils import decode_api_response")
    print("    content = decode_api_response(data_bytes)  # ✅ Handles both")
    
    print("\nOr at the top of the file, add to imports:")
    print("    from amazon_api_utils import decode_api_response")
    
    print("\nThen replace line 762 with:")
    print("    content = decode_api_response(data_bytes)")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    example_placement_performance_sync()
    example_fix_for_amazon_ads_sync()
