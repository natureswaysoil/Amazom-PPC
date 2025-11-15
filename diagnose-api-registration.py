#!/usr/bin/env python3
"""
According to Amazon Advertising API docs (as of 2024-2025):
Sponsored Products campaigns endpoint is STILL at /sp/campaigns
BUT it requires specific API scope permissions.

The "Invalid key=value pair" error is Amazon's way of saying:
"Your credentials don't have permission for this specific API scope"

Let's verify your API registration and try using the API correctly.
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
print("Amazon Advertising API - Proper Authentication Test")
print("=" * 70)
print()

# Load credentials
client_id = get_secret("AMAZON_CLIENT_ID")
client_secret = get_secret("AMAZON_CLIENT_SECRET")
refresh_token = get_secret("AMAZON_REFRESH_TOKEN")
profile_id = get_secret("AMAZON_PROFILE_ID")

print("Step 1: Checking credential format...")
print(f"  Client ID starts with: {client_id[:20]}...")
print(f"  Client ID length: {len(client_id)}")

# Amazon Advertising API credentials should start with "amzn1.application-oa2-client."
if not client_id.startswith("amzn1.application-oa2-client."):
    print("  ⚠️  WARNING: Client ID doesn't start with 'amzn1.application-oa2-client.'")
    print("  This might be Product Advertising API credentials, not Advertising API!")
else:
    print("  ✓ Client ID format looks correct for Advertising API")

print()
print("Step 2: Getting access token with EXPLICIT SCOPE...")

# Request token with explicit advertising scope
token_response = requests.post("https://api.amazon.com/auth/o2/token", data={
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": client_id,
    "client_secret": client_secret,
    "scope": "advertising::campaign_management"  # Explicit scope request
})

if token_response.status_code != 200:
    print(f"❌ Token request failed: {token_response.status_code}")
    print(token_response.text)
    sys.exit(1)

token_data = token_response.json()
access_token = token_data["access_token"]
scope_returned = token_data.get("scope", "NOT_RETURNED")

print(f"✓ Access token obtained")
print(f"  Token length: {len(access_token)}")
print(f"  Scope returned: {scope_returned}")

if scope_returned == "NOT_RETURNED" or "advertising" not in scope_returned.lower():
    print("  ⚠️  WARNING: Token doesn't have advertising scope!")
    print("  Your refresh token may not have been authorized for advertising API")
else:
    print("  ✓ Token has advertising scope")

print()
print("Step 3: Testing campaigns endpoint...")

headers = {
    "Authorization": f"Bearer {access_token}",
    "Amazon-Advertising-API-ClientId": client_id,
    "Amazon-Advertising-API-Scope": profile_id,
    "Content-Type": "application/vnd.spCampaign.v3+json",  # Correct content type for SP v3
    "Accept": "application/vnd.spCampaign.v3+json"
}

# Try the correct endpoint per Amazon's docs
url = "https://advertising-api.amazon.com/sp/campaigns"

response = requests.get(url, headers=headers, timeout=10)

print(f"Response status: {response.status_code}")

if response.status_code == 200:
    print("✅ SUCCESS!")
    campaigns = response.json()
    print(f"Campaigns returned: {len(campaigns)}")
    if campaigns:
        print(f"\nFirst campaign:")
        print(json.dumps(campaigns[0], indent=2))
elif response.status_code == 403:
    error = response.json()
    print(f"❌ 403 FORBIDDEN")
    print(json.dumps(error, indent=2))
    print()
    print("=" * 70)
    print("DIAGNOSIS:")
    print("=" * 70)
    
    if "Invalid key=value pair" in response.text:
        print("This error means ONE of:")
        print("1. Your LWA application is NOT registered for Advertising API")
        print("2. Your refresh token was NOT authorized with advertising::campaign_management scope")
        print("3. You need to re-authorize and get a NEW refresh token")
        print()
        print("ACTION REQUIRED:")
        print("1. Go to: https://advertising.amazon.com/")
        print("2. Settings → Account Settings → API")
        print("3. Check 'API Type' - it should say 'Advertising API'")
        print("4. If you see 'Product Advertising API' instead, you have WRONG credentials")
        print("5. Generate NEW refresh token from Advertising Console with proper scope")
    else:
        print(f"Different error: {error}")
else:
    print(f"Status {response.status_code}: {response.text[:500]}")

print()
