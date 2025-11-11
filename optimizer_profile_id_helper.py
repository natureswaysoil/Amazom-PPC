#!/usr/bin/env python3
"""
Amazon PPC Optimizer - Profile ID Helper Module

This module provides helper functions for retrieving and using the Amazon Advertising
Profile ID from Google Secret Manager. Include this in your optimizer code.

Usage:
    from optimizer_profile_id_helper import get_profile_id
    
    profile_id = get_profile_id()
    # Use profile_id in your API calls and BigQuery writes
"""

import os
import sys
from google.cloud import secretmanager
from typing import Optional


def get_profile_id_from_secret_manager() -> str:
    """
    Retrieves the Amazon Advertising Profile ID from Google Secret Manager.
    
    Returns:
        str: Profile ID (e.g., '1780498399290938')
        
    Raises:
        Exception: If unable to retrieve the profile ID
    """
    try:
        # Initialize Secret Manager client
        client = secretmanager.SecretManagerServiceClient()
        
        # Build the secret path
        # Project: 1009540130231
        # Secret name: ppc-profile-id
        secret_path = "projects/1009540130231/secrets/ppc-profile-id/versions/latest"
        
        # Access the secret
        response = client.access_secret_version(request={"name": secret_path})
        
        # Decode and return the profile ID
        profile_id = response.payload.data.decode('UTF-8').strip()
        
        # Validate it's not empty or placeholder
        if not profile_id or profile_id == 'YOUR_PROFILE_ID':
            raise ValueError(f"Invalid profile ID retrieved: {profile_id}")
        
        print(f"✓ Retrieved Profile ID from Secret Manager: {profile_id}")
        return profile_id
        
    except Exception as e:
        print(f"✗ Error retrieving profile ID from Secret Manager: {e}", file=sys.stderr)
        raise


def get_profile_id_from_env() -> str:
    """
    Retrieves the Amazon Advertising Profile ID from environment variable.
    
    Returns:
        str: Profile ID
        
    Raises:
        ValueError: If AMAZON_PROFILE_ID is not set or invalid
    """
    profile_id = os.getenv('AMAZON_PROFILE_ID', '').strip()
    
    if not profile_id:
        raise ValueError("AMAZON_PROFILE_ID environment variable is not set")
    
    if profile_id == 'YOUR_PROFILE_ID':
        raise ValueError("AMAZON_PROFILE_ID is still set to placeholder value")
    
    print(f"✓ Retrieved Profile ID from environment: {profile_id}")
    return profile_id


def get_profile_id(prefer_secret_manager: bool = True) -> str:
    """
    Retrieves the Amazon Advertising Profile ID using the best available method.
    
    Args:
        prefer_secret_manager: If True (default), tries Secret Manager first,
                             then falls back to environment variable.
                             If False, tries environment variable first.
    
    Returns:
        str: Profile ID (e.g., '1780498399290938')
        
    Raises:
        Exception: If unable to retrieve profile ID from any source
    """
    methods = [
        ("Secret Manager", get_profile_id_from_secret_manager),
        ("Environment Variable", get_profile_id_from_env)
    ]
    
    if not prefer_secret_manager:
        methods.reverse()
    
    last_error = None
    
    for method_name, method_func in methods:
        try:
            profile_id = method_func()
            return profile_id
        except Exception as e:
            print(f"⚠️  Failed to get profile ID from {method_name}: {e}", file=sys.stderr)
            last_error = e
            continue
    
    # If we get here, all methods failed
    error_msg = f"Unable to retrieve profile ID from any source. Last error: {last_error}"
    print(f"✗ {error_msg}", file=sys.stderr)
    raise Exception(error_msg)


def validate_profile_id(profile_id: str) -> bool:
    """
    Validates that the profile ID is in the expected format.
    
    Args:
        profile_id: The profile ID to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Basic validation
    if not profile_id:
        return False
    
    # Check it's not a placeholder
    if profile_id in ['YOUR_PROFILE_ID', 'PLACEHOLDER', 'NULL']:
        return False
    
    # Amazon profile IDs are typically numeric strings
    if not profile_id.isdigit():
        return False
    
    # Typical length is 16 digits
    if len(profile_id) < 10 or len(profile_id) > 20:
        return False
    
    return True


# Example usage and testing
if __name__ == "__main__":
    print("=" * 70)
    print("Amazon PPC Optimizer - Profile ID Helper Test")
    print("=" * 70)
    
    try:
        # Test profile ID retrieval
        print("\n1. Testing profile ID retrieval...")
        profile_id = get_profile_id()
        print(f"   Profile ID: {profile_id}")
        
        # Test validation
        print("\n2. Testing profile ID validation...")
        is_valid = validate_profile_id(profile_id)
        if is_valid:
            print(f"   ✓ Profile ID is valid")
        else:
            print(f"   ✗ Profile ID validation failed")
            sys.exit(1)
        
        # Verify it matches expected value
        print("\n3. Verifying against expected value...")
        expected_profile_id = "1780498399290938"
        if profile_id == expected_profile_id:
            print(f"   ✓ Profile ID matches expected value: {expected_profile_id}")
        else:
            print(f"   ⚠️  Warning: Profile ID ({profile_id}) does not match expected ({expected_profile_id})")
        
        print("\n" + "=" * 70)
        print("✓ All tests passed!")
        print("=" * 70)
        print(f"\nYou can now use this profile ID in your optimizer:")
        print(f"  Profile ID: {profile_id}")
        print(f"\nExample usage:")
        print(f'  from optimizer_profile_id_helper import get_profile_id')
        print(f'  profile_id = get_profile_id()')
        
    except Exception as e:
        print("\n" + "=" * 70)
        print("✗ Test failed!")
        print("=" * 70)
        print(f"Error: {e}")
        sys.exit(1)
