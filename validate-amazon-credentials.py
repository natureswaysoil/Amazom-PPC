#!/usr/bin/env python3
"""
Validate Amazon Advertising API credentials and diagnose common issues.
This helps distinguish between:
1. Wrong API (PA-API vs Advertising API)
2. Invalid credentials
3. Token format issues
4. Missing API access/permissions
"""

import os
import sys
import json
import requests
from urllib.parse import quote

def validate_credentials():
    """Validate Amazon Advertising API setup."""
    
    print("=" * 70)
    print("Amazon Advertising API Credential Validator")
    print("=" * 70)
    print()
    
    # Get credentials from environment
    client_id = os.getenv("AMAZON_CLIENT_ID", "")
    client_secret = os.getenv("AMAZON_CLIENT_SECRET", "")
    refresh_token = os.getenv("AMAZON_REFRESH_TOKEN", "")
    profile_id = os.getenv("AMAZON_PROFILE_ID", "")
    
    issues = []
    
    # Step 1: Check if credentials exist
    print("Step 1: Checking credential presence...")
    if not client_id:
        issues.append("❌ AMAZON_CLIENT_ID is missing")
    else:
        print(f"✓ AMAZON_CLIENT_ID: {client_id[:12]}... (length: {len(client_id)})")
    
    if not client_secret:
        issues.append("❌ AMAZON_CLIENT_SECRET is missing")
    else:
        print(f"✓ AMAZON_CLIENT_SECRET: {client_secret[:8]}... (length: {len(client_secret)})")
    
    if not refresh_token:
        issues.append("❌ AMAZON_REFRESH_TOKEN is missing")
    else:
        print(f"✓ AMAZON_REFRESH_TOKEN: {refresh_token[:8]}...{refresh_token[-8:]} (length: {len(refresh_token)})")
        # Check for suspicious characters
        if ' ' in refresh_token:
            issues.append("⚠️  AMAZON_REFRESH_TOKEN contains SPACES - this will cause authentication failures!")
        if '\n' in refresh_token or '\r' in refresh_token:
            issues.append("⚠️  AMAZON_REFRESH_TOKEN contains NEWLINES - this will cause authentication failures!")
    
    if not profile_id:
        issues.append("❌ AMAZON_PROFILE_ID is missing")
    else:
        print(f"✓ AMAZON_PROFILE_ID: {profile_id}")
    
    print()
    
    if not all([client_id, client_secret, refresh_token]):
        print("❌ Cannot proceed - missing required credentials")
        for issue in issues:
            print(f"   {issue}")
        return False
    
    # Step 2: Test token refresh
    print("Step 2: Testing token refresh (authentication)...")
    token_url = "https://api.amazon.com/auth/o2/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    
    try:
        response = requests.post(token_url, data=payload, timeout=30)
        print(f"   Token endpoint response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token", "")
            print(f"   ✓ Successfully obtained access token")
            print(f"   Token length: {len(access_token)}")
            print(f"   Token type: {data.get('token_type', 'N/A')}")
            print(f"   Expires in: {data.get('expires_in', 'N/A')} seconds")
            
            # Check token format
            if ' ' in access_token:
                issues.append("⚠️  ACCESS TOKEN contains SPACES - Amazon API will reject this!")
                print(f"   ⚠️  WARNING: Access token contains spaces!")
            if '\n' in access_token or '\r' in access_token:
                issues.append("⚠️  ACCESS TOKEN contains NEWLINES - Amazon API will reject this!")
                print(f"   ⚠️  WARNING: Access token contains newlines!")
            
            print(f"   First 20 chars: '{access_token[:20]}'")
            print(f"   Last 20 chars: '{access_token[-20:]}'")
            
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            error_type = error_data.get("error", "unknown")
            error_desc = error_data.get("error_description", response.text[:200])
            
            print(f"   ❌ Authentication failed: {error_type}")
            print(f"   Description: {error_desc}")
            
            if error_type == "invalid_grant":
                issues.append("❌ REFRESH TOKEN is invalid or expired - you need to regenerate it")
            elif error_type == "invalid_client":
                issues.append("❌ CLIENT_ID or CLIENT_SECRET is invalid")
            else:
                issues.append(f"❌ Authentication error: {error_type}")
            
            return False
            
    except Exception as e:
        print(f"   ❌ Token refresh failed: {e}")
        issues.append(f"❌ Token refresh exception: {e}")
        return False
    
    print()
    
    # Step 3: Test Amazon Advertising API access
    print("Step 3: Testing Amazon Advertising API access...")
    if not profile_id:
        print("   ⚠️  Skipping (no AMAZON_PROFILE_ID set)")
    else:
        api_url = "https://advertising-api.amazon.com/v2/profiles"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(api_url, headers=headers, timeout=30)
            print(f"   Profiles endpoint response: {response.status_code}")
            
            if response.status_code == 200:
                profiles = response.json()
                print(f"   ✓ Successfully accessed Amazon Advertising API")
                print(f"   Number of profiles: {len(profiles)}")
                
                # Check if requested profile exists
                profile_ids = [str(p.get("profileId")) for p in profiles]
                if profile_id in profile_ids:
                    print(f"   ✓ Profile {profile_id} is accessible")
                    matching_profile = next(p for p in profiles if str(p.get("profileId")) == profile_id)
                    print(f"   Marketplace: {matching_profile.get('countryCode', 'N/A')}")
                    print(f"   Account type: {matching_profile.get('accountInfo', {}).get('type', 'N/A')}")
                else:
                    print(f"   ⚠️  Profile {profile_id} NOT found in accessible profiles")
                    print(f"   Available profiles: {', '.join(profile_ids)}")
                    issues.append(f"⚠️  AMAZON_PROFILE_ID {profile_id} is not accessible with these credentials")
                
            elif response.status_code == 401:
                print(f"   ❌ 401 Unauthorized - access token is invalid")
                issues.append("❌ Access token rejected by Amazon Advertising API (401)")
                
            elif response.status_code == 403:
                error_body = response.text[:500]
                print(f"   ❌ 403 Forbidden - no access to Amazon Advertising API")
                print(f"   Error: {error_body}")
                
                if "Invalid key=value pair" in error_body:
                    issues.append("❌ CRITICAL: Authorization header has 'Invalid key=value pair' - token likely contains SPACES")
                    print(f"   ⚠️  This error typically means the access token contains spaces!")
                else:
                    issues.append("❌ Your credentials may not have Amazon Advertising API access")
                    issues.append("   You may have Product Advertising API (PA-API) credentials instead")
                    issues.append("   Register for Advertising API at: https://advertising.amazon.com/API")
                
            else:
                print(f"   ❌ Unexpected response: {response.status_code}")
                print(f"   Body: {response.text[:500]}")
                issues.append(f"❌ Unexpected API response: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ API request failed: {e}")
            issues.append(f"❌ API request exception: {e}")
    
    print()
    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    
    if not issues:
        print("✅ All checks passed! Your credentials are valid.")
        return True
    else:
        print(f"❌ Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"   {issue}")
        print()
        print("Next steps:")
        if any("SPACES" in i or "NEWLINES" in i for i in issues):
            print("1. Check your Secret Manager secrets for whitespace corruption")
            print("2. Re-create secrets without copy/paste (use 'echo -n' or file upload)")
            print("3. Redeploy the function")
        if any("not have Amazon Advertising API access" in i for i in issues):
            print("1. Verify you registered for Amazon Advertising API (not PA-API)")
            print("2. Visit: https://advertising.amazon.com/API")
            print("3. Generate new API credentials from Advertising Console")
        if any("REFRESH TOKEN is invalid" in i for i in issues):
            print("1. Generate a new refresh token from Amazon Advertising Console")
            print("2. Update AMAZON_REFRESH_TOKEN in Secret Manager")
            print("3. Redeploy the function")
        
        return False

if __name__ == "__main__":
    success = validate_credentials()
    sys.exit(0 if success else 1)
