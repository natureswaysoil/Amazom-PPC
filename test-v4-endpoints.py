#!/usr/bin/env python3
"""
Test NEW Amazon Advertising API V4 endpoints.
Amazon has been migrating to v4 - this might be why sp/campaigns fails.
"""

import os
import sys
import json
import requests
import subprocess

PROJECT_ID = "amazon-ppc-474902"

def get_secret(name):
    result = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest", 
         "--secret", name, "--project", PROJECT_ID],
        capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""

print("=" * 70)
print("Testing Amazon Advertising API V4 Endpoints")
print("=" * 70)
print()

# Load credentials
client_id = get_secret("AMAZON_CLIENT_ID")
client_secret = get_secret("AMAZON_CLIENT_SECRET")
refresh_token = get_secret("AMAZON_REFRESH_TOKEN")
profile_id = get_secret("AMAZON_PROFILE_ID")

# Get access token
token_response = requests.post("https://api.amazon.com/auth/o2/token", data={
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": client_id,
    "client_secret": client_secret
})

access_token = token_response.json()["access_token"]
print(f"✓ Access token obtained\n")

# Test V4 and alternative endpoints
endpoints = [
    {
        "name": "SP V4 Campaigns",
        "url": "https://advertising-api.amazon.com/sp/v4/campaigns",
        "method": "GET"
    },
    {
        "name": "SP V3 Campaigns", 
        "url": "https://advertising-api.amazon.com/sp/v3/campaigns",
        "method": "GET"
    },
    {
        "name": "SP Campaigns Extended (original)",
        "url": "https://advertising-api.amazon.com/v2/sp/campaigns/extended",
        "method": "GET"
    },
    {
        "name": "SP Campaigns LIST endpoint",
        "url": "https://advertising-api.amazon.com/v2/sp/campaigns",
        "method": "GET"
    },
    {
        "name": "SD Campaigns (Sponsored Display)",
        "url": "https://advertising-api.amazon.com/sd/campaigns",
        "method": "GET"
    }
]

for endpoint in endpoints:
    print(f"\nTesting: {endpoint['name']}")
    print(f"URL: {endpoint['url']}")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": client_id,
        "Amazon-Advertising-API-Scope": profile_id,
        "Content-Type": "application/json"
    }
    
    try:
        if endpoint['method'] == 'GET':
            response = requests.get(endpoint['url'], headers=headers, timeout=10)
        else:
            response = requests.post(endpoint['url'], headers=headers, json={}, timeout=10)
        
        status = response.status_code
        print(f"Status: {status}")
        
        if status == 200:
            print("✅ SUCCESS!")
            data = response.json()
            if isinstance(data, list):
                print(f"   Campaigns: {len(data)}")
            elif isinstance(data, dict):
                print(f"   Keys: {list(data.keys())}")
        elif status == 403:
            error = response.text
            print(f"❌ 403: {error[:200]}")
        elif status == 404:
            print("⚠️  404 - Endpoint not found")
        else:
            print(f"Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n" + "=" * 70)
print("Checking Amazon Ads API documentation for correct endpoint...")
print("=" * 70)
print()
print("If none work, the issue is:")
print("1. Amazon deprecated /sp/campaigns without proper migration path")
print("2. OR your account needs Sponsored Products API re-enabled")
print()
print("Next step: Check https://advertising.amazon.com/API/docs/en-us/campaigns/sp/overview")
