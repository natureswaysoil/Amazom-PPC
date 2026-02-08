#!/usr/bin/env python3
"""
Test different campaign retrieval methods to find what works.
Since you successfully retrieved 254 campaigns before, we need to find the working format.
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
print("Campaign Retrieval Method Finder")
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

access_token = token_response.json()["access_token"]
print(f"✓ Access token obtained (length: {len(access_token)})\n")

# Try different request methods
test_cases = [
    {
        "name": "Method 1: Standard GET with query params",
        "method": "GET",
        "url": f"https://advertising-api.amazon.com/v2/sp/campaigns?startIndex=0&count=10",
        "headers": {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Amazon-Advertising-API-Scope": profile_id,
            "Content-Type": "application/json"
        }
    },
    {
        "name": "Method 2: GET without Content-Type",
        "method": "GET",
        "url": f"https://advertising-api.amazon.com/v2/sp/campaigns?startIndex=0&count=10",
        "headers": {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Amazon-Advertising-API-Scope": profile_id
        }
    },
    {
        "name": "Method 3: POST with empty body",
        "method": "POST",
        "url": f"https://advertising-api.amazon.com/sp/campaigns/list",
        "headers": {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Amazon-Advertising-API-Scope": profile_id,
            "Content-Type": "application/json"
        },
        "body": {}
    },
    {
        "name": "Method 4: Extended GET (no pagination)",
        "method": "GET",
        "url": f"https://advertising-api.amazon.com/v2/sp/campaigns",
        "headers": {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Amazon-Advertising-API-Scope": profile_id,
            "Content-Type": "application/json"
        }
    },
    {
        "name": "Method 5: V3 campaigns endpoint",
        "method": "GET",
        "url": f"https://advertising-api.amazon.com/v2/sp/campaigns?startIndex=0&count=10",
        "headers": {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Amazon-Advertising-API-Scope": profile_id,
            "Amazon-Advertising-API-Version": "v3",
            "Content-Type": "application/json"
        }
    },
    {
        "name": "Method 6: Legacy v2 campaigns",
        "method": "GET",
        "url": f"https://advertising-api.amazon.com/v2/campaigns?profileId={profile_id}&startIndex=0&count=10",
        "headers": {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Content-Type": "application/json"
        }
    },
    {
        "name": "Method 7: SB Campaigns (Sponsored Brands - different product)",
        "method": "GET",
        "url": f"https://advertising-api.amazon.com/sb/campaigns?startIndex=0&count=10",
        "headers": {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Amazon-Advertising-API-Scope": profile_id,
            "Content-Type": "application/json"
        }
    }
]

successful_methods = []

for i, test in enumerate(test_cases, 1):
    print(f"\n{'=' * 70}")
    print(f"Test {i}: {test['name']}")
    print(f"{'=' * 70}")
    print(f"URL: {test['url']}")
    print(f"Method: {test['method']}")
    
    try:
        if test['method'] == 'GET':
            response = requests.get(test['url'], headers=test['headers'], timeout=10)
        else:
            response = requests.post(test['url'], headers=test['headers'], 
                                    json=test.get('body', {}), timeout=10)
        
        status = response.status_code
        print(f"Status: {status}")
        
        if status == 200:
            print("✅ SUCCESS!")
            try:
                data = response.json()
                if isinstance(data, list):
                    print(f"   Campaigns returned: {len(data)}")
                    if len(data) > 0:
                        print(f"   First campaign ID: {data[0].get('campaignId', 'N/A')}")
                        print(f"   First campaign name: {data[0].get('name', 'N/A')}")
                    successful_methods.append(test['name'])
                elif isinstance(data, dict):
                    print(f"   Response keys: {list(data.keys())}")
                    successful_methods.append(test['name'])
            except:
                print(f"   Response (first 200 chars): {response.text[:200]}")
                successful_methods.append(test['name'])
        elif status == 403:
            error = response.text[:200]
            print(f"❌ FORBIDDEN: {error}")
            if "Invalid key=value pair" in error:
                print("   (Same error as before)")
        elif status == 404:
            print("⚠️  NOT FOUND - endpoint doesn't exist")
        else:
            print(f"⚠️  Status {status}: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

print(f"\n{'=' * 70}")
print("SUMMARY")
print(f"{'=' * 70}")
print()

if successful_methods:
    print(f"✅ Found {len(successful_methods)} working method(s):")
    for method in successful_methods:
        print(f"   • {method}")
    print()
    print("We can update the optimizer to use the working method!")
else:
    print("❌ No working methods found.")
    print()
    print("This confirms: Your credentials do NOT have Sponsored Products API access.")
    print("Action required: Request SP API access from Amazon Advertising Console")

print()
