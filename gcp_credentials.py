"""
GCP Credentials Module
=======================

Handles loading and validation of Google Cloud Platform service account credentials.
Supports multiple credential formats:
- Raw JSON (service account key file contents)
- Base64-encoded JSON (useful for CI/CD environments)
- File path (for local development)

Author: Nature's Way Soil
Version: 1.0.0
"""

import base64
import json
import logging
import os
from typing import Dict, Optional, Tuple, Any

from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class GCPCredentialError(Exception):
    """Custom exception for GCP credential errors with helpful guidance."""
    
    def __init__(self, message: str, guidance: Optional[str] = None):
        self.message = message
        self.guidance = guidance
        super().__init__(self.format_error())
    
    def format_error(self) -> str:
        """Format error message with guidance."""
        if self.guidance:
            return f"{self.message}\n\nGuidance:\n{self.guidance}"
        return self.message


def _combine_split_env_value(base_name: str) -> Optional[str]:
    """
    Reconstruct environment values stored across multiple numbered variables.
    
    Some deployment platforms split long environment variables into parts.
    This function combines them back together.
    
    Examples:
        GCP_SERVICE_ACCOUNT_KEY_PART1, GCP_SERVICE_ACCOUNT_KEY_PART2
        GCP_SERVICE_ACCOUNT_KEY_1, GCP_SERVICE_ACCOUNT_KEY_2
    
    Args:
        base_name: Base variable name (e.g., "GCP_SERVICE_ACCOUNT_KEY")
    
    Returns:
        Combined value if parts exist, None otherwise
    """
    from typing import List
    
    prefix_len = len(base_name)
    parts: List[Tuple[int, str]] = []

    for env_name, env_value in os.environ.items():
        if not env_value or not env_name.startswith(base_name):
            continue

        suffix = env_name[prefix_len:]
        if not suffix:
            continue

        trimmed = suffix.strip("_- ")
        if not trimmed:
            continue

        index: Optional[int] = None
        upper = trimmed.upper()

        if upper.startswith("PART"):
            remainder = trimmed[4:].strip("_- ")
            if remainder.isdigit():
                index = int(remainder)
        elif trimmed.isdigit():
            index = int(trimmed)

        if index is None:
            continue

        parts.append((index, env_value))

    if not parts:
        return None

    parts.sort(key=lambda item: item[0])
    return "".join(value for _, value in parts)


def _get_env_value_with_parts(*names: str) -> Optional[str]:
    """
    Return the first populated environment variable, combining split parts if needed.
    
    Args:
        *names: Environment variable names to check in order
    
    Returns:
        First non-empty value found, or None
    """
    # First check for direct environment variables
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value

    # Then check for split parts
    for name in names:
        combined = _combine_split_env_value(name)
        if combined:
            return combined

    return None


def _parse_json_credentials(raw_value: str, source_name: str) -> Dict[str, Any]:
    """
    Parse credentials from raw JSON or base64-encoded JSON.
    
    Args:
        raw_value: Raw credential string (JSON or base64)
        source_name: Name of the source (for error messages)
    
    Returns:
        Parsed credentials dictionary
    
    Raises:
        GCPCredentialError: If parsing fails with helpful guidance
    """
    # Try parsing as raw JSON first
    try:
        credentials_info = json.loads(raw_value)
        logger.info(f"Successfully parsed {source_name} as raw JSON")
        return credentials_info
    except json.JSONDecodeError as json_err:
        logger.debug(f"{source_name} is not raw JSON, attempting base64 decode...")
    
    # Try base64-encoded JSON
    try:
        decoded_value = base64.b64decode(raw_value).decode("utf-8")
        logger.info(f"Successfully decoded {source_name} from base64")
    except (base64.binascii.Error, UnicodeDecodeError) as b64_err:
        raise GCPCredentialError(
            f"{source_name} is not valid JSON or base64 encoded JSON.",
            guidance="""
To fix this issue, provide credentials in one of these formats:

1. Raw JSON (recommended for most cases):
   - Copy the entire contents of your service account key file
   - Example: export GCP_SERVICE_ACCOUNT_KEY='{"type":"service_account",...}'

2. Base64-encoded JSON (for environments with special character issues):
   - Encode your service account key: cat service-account.json | base64 | tr -d '\\n'
   - Set the environment variable: export GCP_SERVICE_ACCOUNT_KEY="<base64-output>"

3. File path (local development only):
   - Set GOOGLE_APPLICATION_CREDENTIALS to the file path
   - Example: export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

For more details, see the README.md section on GCP credentials.
"""
        )
    
    # Parse the decoded JSON
    try:
        credentials_info = json.loads(decoded_value)
        logger.info(f"Successfully parsed decoded {source_name} as JSON")
        return credentials_info
    except json.JSONDecodeError as json_err2:
        raise GCPCredentialError(
            f"{source_name} was successfully base64 decoded but does not contain valid JSON.",
            guidance="""
The base64 decoding succeeded, but the result is not valid JSON.

To fix this issue:
1. Verify you're encoding valid JSON:
   - Check: cat service-account.json | jq .
   - This should display formatted JSON without errors

2. Re-encode the file:
   - Run: cat service-account.json | base64 | tr -d '\\n' > encoded.txt
   - Set: export GCP_SERVICE_ACCOUNT_KEY="$(cat encoded.txt)"

3. Ensure no extra spaces or characters were added when setting the variable
"""
        )


def _validate_service_account_credentials(credentials_info: Dict[str, Any], source_name: str) -> None:
    """
    Validate that credentials have the required service account structure.
    
    Args:
        credentials_info: Parsed credentials dictionary
        source_name: Name of the source (for error messages)
    
    Raises:
        GCPCredentialError: If validation fails with helpful guidance
    """
    if not isinstance(credentials_info, dict):
        raise GCPCredentialError(
            f"{source_name} contains data but is not a valid JSON object.",
            guidance="""
The credentials must be a JSON object (dictionary) with service account fields.

Expected structure:
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
  "client_email": "...@your-project.iam.gserviceaccount.com",
  ...
}

To obtain valid credentials:
1. Go to Google Cloud Console: https://console.cloud.google.com
2. Navigate to: IAM & Admin → Service Accounts
3. Select your service account (or create a new one)
4. Go to Keys tab → Add Key → Create new key
5. Choose JSON format and download
"""
        )
    
    # Check credential type
    cred_type = credentials_info.get("type")
    if cred_type != "service_account":
        raise GCPCredentialError(
            f"{source_name} contains valid JSON but is not a service account credential. "
            f"Expected type='service_account' but got type='{cred_type}'.",
            guidance="""
The credentials must be a service account key, not other types of credentials.

To obtain valid service account credentials:
1. Go to Google Cloud Console: https://console.cloud.google.com
2. Navigate to: IAM & Admin → Service Accounts
3. Select or create a service account
4. Go to Keys tab → Add Key → Create new key
5. Choose JSON format (not P12)
6. Download and use the JSON file contents

Note: Do not use OAuth client credentials or API keys.
"""
        )
    
    # Check required fields
    required_fields = ["type", "project_id", "private_key_id", "private_key", "client_email"]
    missing_fields = [field for field in required_fields if field not in credentials_info]
    
    if missing_fields:
        raise GCPCredentialError(
            f"{source_name} is missing required service account fields: {', '.join(missing_fields)}.",
            guidance=f"""
The service account key is incomplete. Missing fields: {', '.join(missing_fields)}

This usually means:
1. The downloaded file was corrupted or truncated
2. Only part of the JSON was copied
3. The file format was modified

To fix this:
1. Download a fresh service account key from Google Cloud Console
2. Do not edit or modify the JSON file
3. Copy the entire contents when setting environment variables
4. Verify the JSON is complete: cat service-account.json | jq .

Required fields for a valid service account key:
- type: Must be "service_account"
- project_id: Your GCP project ID
- private_key_id: Key identifier
- private_key: RSA private key (including BEGIN/END markers)
- client_email: Service account email address
"""
        )


def load_credentials() -> Optional[service_account.Credentials]:
    """
    Load and validate GCP service account credentials from environment.
    
    Checks multiple environment variable sources in priority order:
    1. GCP_SERVICE_ACCOUNT_KEY (raw JSON or base64)
    2. GCP_SA_KEY (alternative name)
    3. GOOGLE_APPLICATION_CREDENTIALS (file path)
    
    Supports split environment variables for platforms with size limits.
    
    Returns:
        service_account.Credentials object if credentials found and valid,
        None if no credentials configured (will use Application Default Credentials)
    
    Raises:
        GCPCredentialError: If credentials are found but invalid, with helpful guidance
    """
    logger.info("Loading GCP service account credentials...")
    
    # Define credential sources in priority order
    credential_sources = []
    
    # Check for service account key environment variables
    service_account_value = _get_env_value_with_parts("GCP_SERVICE_ACCOUNT_KEY", "GCP_SA_KEY")
    if service_account_value:
        if os.environ.get("GCP_SERVICE_ACCOUNT_KEY"):
            source_name = "GCP_SERVICE_ACCOUNT_KEY"
        elif os.environ.get("GCP_SA_KEY"):
            source_name = "GCP_SA_KEY"
        elif _combine_split_env_value("GCP_SERVICE_ACCOUNT_KEY"):
            source_name = "GCP_SERVICE_ACCOUNT_KEY (combined from split parts)"
        elif _combine_split_env_value("GCP_SA_KEY"):
            source_name = "GCP_SA_KEY (combined from split parts)"
        else:
            source_name = "GCP_SERVICE_ACCOUNT_KEY"
        credential_sources.append((source_name, service_account_value))
    
    # Check for GOOGLE_APPLICATION_CREDENTIALS (file path or JSON)
    google_credentials_value = _get_env_value_with_parts("GOOGLE_APPLICATION_CREDENTIALS")
    if google_credentials_value:
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            google_source = "GOOGLE_APPLICATION_CREDENTIALS"
        else:
            google_source = "GOOGLE_APPLICATION_CREDENTIALS (combined from split parts)"
        credential_sources.append((google_source, google_credentials_value))
    
    # No credentials configured - will use Application Default Credentials
    if not credential_sources:
        logger.info(
            "No explicit GCP credentials configured. "
            "Application Default Credentials will be used if available."
        )
        return None
    
    # Try each credential source
    for source_name, raw_value in credential_sources:
        logger.info(f"Attempting to load credentials from {source_name}...")
        
        # Check if value is a file path
        if os.path.isfile(raw_value):
            try:
                logger.info(f"Loading credentials from file path in {source_name}")
                credentials = service_account.Credentials.from_service_account_file(raw_value)
                logger.info(f"✓ Successfully loaded credentials from file: {raw_value}")
                return credentials
            except Exception as exc:
                raise GCPCredentialError(
                    f"Failed to load service account credentials from file: {raw_value}",
                    guidance=f"""
The environment variable {source_name} points to a file path, but the file could not be loaded.

Error: {str(exc)}

To fix this:
1. Verify the file exists: ls -l {raw_value}
2. Check file permissions: chmod 600 {raw_value}
3. Verify file contains valid JSON: cat {raw_value} | jq .
4. Ensure the file hasn't been corrupted

Alternatively, set {source_name} to the JSON contents directly instead of a file path.
"""
                )
        
        # Parse as JSON or base64
        try:
            credentials_info = _parse_json_credentials(raw_value, source_name)
            _validate_service_account_credentials(credentials_info, source_name)
            
            # Create credentials object
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            logger.info(f"✓ Successfully loaded valid service account credentials from {source_name}")
            logger.info(f"  Service Account: {credentials_info.get('client_email', 'unknown')}")
            logger.info(f"  Project ID: {credentials_info.get('project_id', 'unknown')}")
            return credentials
            
        except GCPCredentialError:
            # Re-raise our custom errors with guidance
            raise
        except Exception as exc:
            # Catch any unexpected errors
            raise GCPCredentialError(
                f"Unexpected error while processing {source_name}: {str(exc)}",
                guidance="""
An unexpected error occurred while loading credentials.

Please ensure:
1. You're providing valid service account key JSON
2. The JSON is properly formatted (test with: echo "$GCP_SERVICE_ACCOUNT_KEY" | jq .)
3. No special characters were corrupted during copy/paste
4. The environment variable was set correctly in your deployment platform

For CI/CD environments (GitHub Actions, Vercel, etc.):
- Store the service account key JSON in a secret
- Reference it in your deployment configuration
- Do not modify or escape the JSON when setting the secret
"""
            )
    
    # This should never be reached, but just in case
    logger.warning("No valid credentials found from any source.")
    return None


def validate_credentials_early() -> Tuple[bool, Optional[str]]:
    """
    Validate GCP credentials early in application startup.
    
    This function should be called before any Google Cloud SDK services
    are instantiated to catch credential issues early with helpful errors.
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - (True, None) if credentials are valid or not configured (will use ADC)
        - (False, error_message) if credentials are invalid with diagnostic info
    """
    try:
        credentials = load_credentials()
        
        if credentials:
            logger.info("✓ GCP credentials validated successfully")
            return True, None
        else:
            logger.info("No explicit GCP credentials configured. Will use Application Default Credentials.")
            return True, None
            
    except GCPCredentialError as e:
        error_msg = f"GCP credential validation failed: {e.format_error()}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error during GCP credential validation: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def get_project_id_from_credentials() -> Optional[str]:
    """
    Extract project ID from loaded credentials.
    
    Returns:
        Project ID if available in credentials, None otherwise
    """
    try:
        credentials = load_credentials()
        if credentials and hasattr(credentials, 'project_id'):
            return credentials.project_id
        
        # Try to get from environment if credentials were JSON
        service_account_value = _get_env_value_with_parts("GCP_SERVICE_ACCOUNT_KEY", "GCP_SA_KEY")
        if service_account_value:
            try:
                credentials_info = _parse_json_credentials(service_account_value, "GCP_SERVICE_ACCOUNT_KEY")
                return credentials_info.get('project_id')
            except:
                pass
        
        return None
    except:
        return None
