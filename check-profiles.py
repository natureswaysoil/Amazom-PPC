#!/usr/bin/env python3
"""
Quick profile checker - validates which Amazon Advertising profiles are accessible
and compares with the configured AMAZON_PROFILE_ID.
"""

import os
import sys
import json
import requests

def check_profiles():
    """Check accessible Amazon Advertising profiles."""
    
    # Get credentials
    client_id = os.getenv("AMAZON_CLIENT_ID", "")
    client_secret = os.getenv("AMAZON_CLIENT_SECRET", "")
    refresh_token = os.getenv("AMAZON_REFRESH_TOKEN", "")
    configured_profile_id = os.getenv("AMAZON_PROFILE_ID", "")
    
    if not all([client_id, client_secret, refresh_token]):
        print("ERROR: Missing required credentials")
        return False
    
    print("=" * 70)
    print("Amazon Advertising Profile Checker")
    print("=" * 70)
    print()
    
    # Step 1: Get access token
    print("Step 1: Getting access token...")
    token_url = "https://api.amazon.com/auth/o2/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    
    try:
        response = requests.post(token_url, data=payload, timeout=30)
        if response.status_code != 200:
            print(f"ERROR: Token refresh failed: {response.status_code}")
            print(response.text)
            return False
        
        access_token = response.json()["access_token"]
        print(f"✓ Access token obtained (length: {len(access_token)})")
        print()
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    
    # Step 2: Get profiles
    print("Step 2: Fetching accessible profiles...")
    profiles_url = "https://advertising-api.amazon.com/v2/profiles"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": client_id,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(profiles_url, headers=headers, timeout=30)
        print(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"ERROR: {response.text}")
            return False
        
        profiles = response.json()
        print(f"✓ Found {len(profiles)} accessible profile(s)")
        print()
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    
    # Step 3: Display profiles
    print("=" * 70)
    print("Accessible Profiles:")
    print("=" * 70)
    
    for profile in profiles:
        profile_id = str(profile.get("profileId", ""))
        country = profile.get("countryCode", "N/A")
        currency = profile.get("currencyCode", "N/A")
        timezone = profile.get("timezone", "N/A")
        account_type = profile.get("accountInfo", {}).get("type", "N/A")
        marketplace_id = profile.get("accountInfo", {}).get("marketplaceStringId", "N/A")
        
        is_configured = "<<< CONFIGURED" if profile_id == configured_profile_id else ""
        
        print(f"\nProfile ID: {profile_id} {is_configured}")
        print(f"  Country: {country}")
        print(f"  Currency: {currency}")
        print(f"  Timezone: {timezone}")
        print(f"  Account Type: {account_type}")
        print(f"  Marketplace: {marketplace_id}")
    
    print()
    print("=" * 70)
    
    # Step 4: Validate configured profile
    if configured_profile_id:
        print(f"Configured AMAZON_PROFILE_ID: {configured_profile_id}")
        profile_ids = [str(p.get("profileId")) for p in profiles]
        
        if configured_profile_id in profile_ids:
            print("✅ Configured profile IS accessible")
            
            # Try to fetch campaigns for this profile
            print()
            print("Step 3: Testing campaigns endpoint for configured profile...")
            campaigns_url = f"https://advertising-api.amazon.com/v2/sp/campaigns?startIndex=0&count=5"
            headers["Amazon-Advertising-API-Scope"] = configured_profile_id
            
            response = requests.get(campaigns_url, headers=headers, timeout=30)
            print(f"Campaigns endpoint status: {response.status_code}")
            
            if response.status_code == 200:
                campaigns = response.json()
                print(f"✅ SUCCESS! Retrieved {len(campaigns)} campaigns")
                if campaigns:
                    print("\nFirst campaign:")
                    print(json.dumps(campaigns[0], indent=2))
            else:
                print(f"❌ Campaigns endpoint failed: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                
                if response.status_code == 403:
                    print("\n⚠️  403 Forbidden - Possible causes:")
                    print("  1. API user lacks 'Campaign Manager' role for this profile")
                    print("  2. Sponsored Products API access not enabled")
                    print("  3. Profile is in wrong state (e.g., suspended)")
                    print("\nAction: Log into advertising.amazon.com and check:")
                    print("  - Account Settings → Users → Your API user role")
                    print("  - Profile status and permissions")
        else:
            print(f"❌ Configured profile NOT in accessible list")
            print(f"\nAvailable profile IDs: {', '.join(profile_ids)}")
            print("\nAction: Update AMAZON_PROFILE_ID to one of the accessible profiles above")
    else:
        print("⚠️  No AMAZON_PROFILE_ID configured")
    
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = check_profiles()
    sys.exit(0 if success else 1)
