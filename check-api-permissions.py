#!/usr/bin/env python3
"""
Check Amazon Advertising API access and permissions.
Systematically test different endpoints to see what's accessible.
"""

import os
import sys
import json
import requests

PROJECT_ID = "amazon-ppc-474902"

def get_secret(name):
    """Get secret from gcloud."""
    import subprocess
    result = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest", 
         "--secret", name, "--project", PROJECT_ID],
        capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""

print("=" * 70)
print("Amazon Advertising API Permission Checker")
print("=" * 70)
print()

# Load credentials
client_id = get_secret("AMAZON_CLIENT_ID")
client_secret = get_secret("AMAZON_CLIENT_SECRET")
refresh_token = get_secret("AMAZON_REFRESH_TOKEN")
profile_id = get_secret("AMAZON_PROFILE_ID")

# Get access token
print("Getting access token...")
token_response = requests.post("https://api.amazon.com/auth/o2/token", data={
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": client_id,
    "client_secret": client_secret
})

if token_response.status_code != 200:
    print(f"❌ Token refresh failed: {token_response.status_code}")
    sys.exit(1)

access_token = token_response.json()["access_token"]
print(f"✓ Access token obtained\n")

# Base headers
base_headers = {
    "Authorization": f"Bearer {access_token}",
    "Amazon-Advertising-API-ClientId": client_id,
    "Content-Type": "application/json"
}

# Test endpoints systematically
endpoints = [
    {
        "name": "Profiles (v2)",
        "url": "https://advertising-api.amazon.com/v2/profiles",
        "headers": base_headers.copy(),
        "needs_scope": False
    },
    {
        "name": "Portfolios (v2)",
        "url": "https://advertising-api.amazon.com/v2/portfolios",
        "headers": {**base_headers, "Amazon-Advertising-API-Scope": profile_id},
        "needs_scope": True
    },
    {
        "name": "SP Campaigns (v2 path)",
        "url": "https://advertising-api.amazon.com/v2/sp/campaigns",
        "headers": {**base_headers, "Amazon-Advertising-API-Scope": profile_id},
        "needs_scope": True
    },
    {
        "name": "SP Campaigns (v2 path + v2 version header)",
        "url": "https://advertising-api.amazon.com/v2/sp/campaigns",
        "headers": {
            **base_headers, 
            "Amazon-Advertising-API-Scope": profile_id,
            "Amazon-Advertising-API-Version": "v2"
        },
        "needs_scope": True
    },
    {
        "name": "SP Campaigns (WITH v3 version header - WRONG)",
        "url": "https://advertising-api.amazon.com/v2/sp/campaigns",
        "headers": {
            **base_headers,
            "Amazon-Advertising-API-Scope": profile_id,
            "Amazon-Advertising-API-Version": "v3"
        },
        "needs_scope": True
    },
    {
        "name": "V2 Campaigns (old endpoint)",
        "url": "https://advertising-api.amazon.com/v2/sp/campaigns",
        "headers": {**base_headers, "Amazon-Advertising-API-Scope": profile_id},
        "needs_scope": True
    }
]

print("=" * 70)
print("Testing API Endpoints:")
print("=" * 70)
print()

for endpoint in endpoints:
    print(f"Testing: {endpoint['name']}")
    print(f"  URL: {endpoint['url']}")
    
    try:
        response = requests.get(endpoint['url'], headers=endpoint['headers'], timeout=10)
        status = response.status_code
        
        if status == 200:
            print(f"  ✅ SUCCESS (200)")
            try:
                data = response.json()
                if isinstance(data, list):
                    print(f"     Returned {len(data)} items")
                elif isinstance(data, dict):
                    print(f"     Keys: {list(data.keys())[:5]}")
            except:
                pass
        elif status == 401:
            print(f"  ❌ UNAUTHORIZED (401)")
            print(f"     Auth issue: {response.text[:200]}")
        elif status == 403:
            print(f"  ❌ FORBIDDEN (403)")
            error_msg = response.text[:300]
            print(f"     Error: {error_msg}")
            if "Invalid key=value pair" in error_msg:
                print(f"     ⚠️  This is the PROBLEMATIC error")
        elif status == 404:
            print(f"  ⚠️  NOT FOUND (404) - endpoint may not exist")
        else:
            print(f"  ⚠️  Status: {status}")
            print(f"     Response: {response.text[:200]}")
    except Exception as e:
        print(f"  ❌ EXCEPTION: {e}")
    
    print()

print("=" * 70)
print("Summary:")
print("=" * 70)
print()
print("If ALL SP campaigns endpoints return 403 with 'Invalid key=value pair':")
print("  → Your API credentials may not have Sponsored Products API access")
print("  → Check Amazon Advertising Console → Account Settings → API")
print("  → You may need to request Sponsored Products API beta access")
print()
print("If ONLY certain endpoints fail:")
print("  → It's a versioning or URL format issue")
print()
