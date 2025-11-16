#!/usr/bin/env python3
"""
Load credentials from Google Secret Manager
============================================

This script loads all required credentials from Google Secret Manager
and exports them as environment variables for the optimizer and dashboard.

Usage:
    # Load and export secrets
    eval $(python load_secrets.py)
    
    # Or source the output
    python load_secrets.py > .env.secrets
    source .env.secrets
    
    # Then run optimizer or dashboard
    python optimizer_core.py --config config.json
"""

import os
import sys
from google.cloud import secretmanager


def get_secret(secret_id, project_id=None, default=None):
    """
    Retrieve secret from Google Secret Manager
    
    Args:
        secret_id: Name of the secret
        project_id: GCP project ID (optional, uses GCP_PROJECT_ID env var)
        default: Default value if secret doesn't exist
        
    Returns:
        Secret value as string, or default if not found
    """
    if not project_id:
        project_id = os.getenv('GCP_PROJECT_ID', 'nature-way-soils')
    
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode('UTF-8')
    except Exception as e:
        if default is not None:
            return default
        print(f"Error retrieving secret '{secret_id}': {e}", file=sys.stderr)
        return None


def load_all_secrets(project_id=None):
    """
    Load all required secrets for optimizer and dashboard
    
    Returns:
        Dictionary of environment variable names and values
    """
    secrets = {}
    
    # Amazon Advertising API credentials
    amazon_secrets = {
        'AMAZON_CLIENT_ID': 'amazon-client-id',
        'AMAZON_CLIENT_SECRET': 'amazon-client-secret',
        'AMAZON_REFRESH_TOKEN': 'amazon-refresh-token',
        'AMAZON_PROFILE_ID': 'amazon-profile-id',
    }
    
    # BigQuery credentials
    bigquery_secrets = {
        'GCP_CREDENTIALS_JSON': 'bigquery-service-account',
        # or 'GCP_CREDENTIALS_BASE64': 'bigquery-service-account-base64',
    }
    
    # Optional secrets
    optional_secrets = {
        'DASHBOARD_URL': 'dashboard-url',
        'DASHBOARD_API_KEY': 'dashboard-api-key',
    }
    
    # Load Amazon secrets
    print("# Loading Amazon Advertising API credentials...", file=sys.stderr)
    for env_var, secret_id in amazon_secrets.items():
        value = get_secret(secret_id, project_id)
        if value:
            secrets[env_var] = value
            print(f"✓ Loaded {env_var}", file=sys.stderr)
        else:
            print(f"⚠ Missing {env_var} (secret: {secret_id})", file=sys.stderr)
    
    # Load BigQuery secrets
    print("\n# Loading BigQuery credentials...", file=sys.stderr)
    for env_var, secret_id in bigquery_secrets.items():
        value = get_secret(secret_id, project_id)
        if value:
            secrets[env_var] = value
            print(f"✓ Loaded {env_var}", file=sys.stderr)
        else:
            print(f"⚠ Missing {env_var} (secret: {secret_id})", file=sys.stderr)
    
    # Load optional secrets
    print("\n# Loading optional credentials...", file=sys.stderr)
    for env_var, secret_id in optional_secrets.items():
        value = get_secret(secret_id, project_id, default='')
        if value:
            secrets[env_var] = value
            print(f"✓ Loaded {env_var}", file=sys.stderr)
    
    # Always set project ID and dataset
    if not secrets.get('GCP_PROJECT_ID'):
        secrets['GCP_PROJECT_ID'] = project_id or os.getenv('GCP_PROJECT_ID', 'nature-way-soils')
    
    if not secrets.get('BIGQUERY_DATASET'):
        secrets['BIGQUERY_DATASET'] = os.getenv('BIGQUERY_DATASET', 'amazon_ppc')
    
    return secrets


def export_secrets_bash(secrets):
    """
    Output secrets in bash export format
    
    Args:
        secrets: Dictionary of environment variables
    """
    for key, value in secrets.items():
        # Escape single quotes in value
        escaped_value = value.replace("'", "'\\''")
        print(f"export {key}='{escaped_value}'")


def export_secrets_env_file(secrets):
    """
    Output secrets in .env file format
    
    Args:
        secrets: Dictionary of environment variables
    """
    for key, value in secrets.items():
        # Escape quotes for .env format
        escaped_value = value.replace('"', '\\"')
        print(f'{key}="{escaped_value}"')


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Load credentials from Google Secret Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Export as bash commands
    eval $(python load_secrets.py)
    
    # Save to .env file
    python load_secrets.py --format env > .env.secrets
    
    # Use with specific project
    python load_secrets.py --project my-project-id
    
    # Verify secrets are loaded
    python load_secrets.py --verify
        """
    )
    
    parser.add_argument(
        '--project',
        help='GCP Project ID (default: GCP_PROJECT_ID env var)',
        default=None
    )
    
    parser.add_argument(
        '--format',
        choices=['bash', 'env'],
        default='bash',
        help='Output format (default: bash)'
    )
    
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify secrets are loaded and show summary'
    )
    
    args = parser.parse_args()
    
    # Load secrets
    project_id = args.project or os.getenv('GCP_PROJECT_ID')
    if not project_id:
        print("Error: GCP_PROJECT_ID not set. Use --project or set environment variable.", file=sys.stderr)
        sys.exit(1)
    
    secrets = load_all_secrets(project_id)
    
    if args.verify:
        # Verification mode - show summary
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"Loaded {len(secrets)} secrets from Google Secret Manager", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        
        required = ['AMAZON_CLIENT_ID', 'AMAZON_CLIENT_SECRET', 'AMAZON_REFRESH_TOKEN', 
                   'AMAZON_PROFILE_ID', 'GCP_CREDENTIALS_JSON']
        
        missing = [key for key in required if not secrets.get(key)]
        
        if missing:
            print(f"\n⚠ Missing required secrets:", file=sys.stderr)
            for key in missing:
                print(f"  - {key}", file=sys.stderr)
            print("\nCannot run optimizer without these credentials.", file=sys.stderr)
            sys.exit(1)
        else:
            print("\n✓ All required secrets loaded successfully!", file=sys.stderr)
            print("\nYou can now run:", file=sys.stderr)
            print("  python optimizer_core.py --config config.json", file=sys.stderr)
            print("  cd dashboard && python app.py", file=sys.stderr)
        
        sys.exit(0)
    
    # Output in requested format
    if args.format == 'bash':
        export_secrets_bash(secrets)
    else:
        export_secrets_env_file(secrets)


if __name__ == '__main__':
    main()
