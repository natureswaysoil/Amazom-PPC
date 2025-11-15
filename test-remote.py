#!/usr/bin/env python3
"""
Test the deployed Cloud Function's profile access remotely.
This doesn't need gcloud - just calls the function endpoint.
"""

import sys
import json
import requests

FUNCTION_URL = "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app"

def test_remote_profiles():
    """Test profiles via the deployed function."""
    
    print("=" * 70)
    print("Testing Amazon Advertising Profile Access (Remote)")
    print("=" * 70)
    print()
    
    # Add a profiles check endpoint call
    print("Testing verify endpoint...")
    verify_url = f"{FUNCTION_URL}?verify_connection=true&verify_sample_size=5"
    
    try:
        response = requests.get(verify_url, timeout=30)
        print(f"Status: {response.status_code}")
        print()
        
        result = response.json()
        print(json.dumps(result, indent=2))
        
        if result.get("status") == "error":
            print()
            print("=" * 70)
            print("Next Steps:")
            print("=" * 70)
            print()
            print("The 403 error suggests profile access issues. To diagnose:")
            print()
            print("1. Run in Cloud Shell (has access to secrets):")
            print("   cd ~/Amazom-PPC")
            print("   git pull origin main")
            print("   python3 check-profiles.py")
            print()
            print("2. That will show:")
            print("   - Which profiles your API credentials can access")
            print("   - If profile 1780498399290938 is accessible")
            print("   - Direct campaigns endpoint test results")
            print()
            return False
        else:
            print()
            print("✅ Success! Campaigns are accessible.")
            return True
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_remote_profiles()
    sys.exit(0 if success else 1)
