"""
auth_utils.py
=============

Lightweight authentication helpers used by the optimizer Cloud Function.

These utilities are kept in a separate module with no heavy dependencies so
they can be unit-tested without initialising BigQuery, functions_framework,
or other runtime libraries.
"""

import base64
import json
import os


def is_cloud_platform() -> bool:
    """Return True when running inside Cloud Run, GCF, or App Engine."""
    return bool(
        os.getenv('K_SERVICE') or
        os.getenv('FUNCTION_TARGET') or
        os.getenv('GAE_SERVICE') or
        os.getenv('CLOUD_RUN_JOB')
    )


def is_google_oidc_token(token: str) -> bool:
    """Return True if *token* looks like a Google-issued OIDC ID token (JWT).

    The signature is NOT verified here because Google Cloud Run / GCF validates
    the token before the request reaches application code.  We only inspect the
    issuer claim to distinguish a Google ID token from an arbitrary string.
    """
    if not token or token.count('.') != 2:
        return False
    try:
        payload_b64 = token.split('.')[1]
        # JWT uses base64url encoding; pad to a multiple of 4.
        rem = len(payload_b64) % 4
        if rem:
            payload_b64 += '=' * (4 - rem)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        iss = payload.get('iss', '')
        return iss in ('https://accounts.google.com', 'accounts.google.com')
    except Exception:
        return False


def is_authorized_dashboard_request(request, api_key: str) -> bool:
    """Return True if *request* carries valid credentials for *api_key*.

    Accepted credential forms:
    1. ``Authorization: Bearer <api_key>`` header matching *api_key*.
    2. ``X-API-Key: <api_key>`` header matching *api_key*.
    3. A Google-issued OIDC ID token in the ``Authorization: Bearer`` header
       when running on Cloud Run or GCF (platform already validated the token).

    If *api_key* is empty the function always returns ``True`` so that
    deployments without a configured API key remain accessible.
    """
    if not api_key:
        return True

    auth_header = (
        request.headers.get('Authorization') or
        request.headers.get('authorization') or
        ''
    )
    token = ''
    if auth_header.startswith('Bearer '):
        token = auth_header[len('Bearer '):].strip()
    else:
        token = auth_header.strip()

    header_api_key = (
        request.headers.get('X-API-Key') or
        request.headers.get('x-api-key') or
        ''
    ).strip()

    if token == api_key or header_api_key == api_key:
        return True

    # Accept requests authenticated by Google Cloud IAM (Cloud Run / GCF).
    # On these platforms the runtime validates the OIDC ID token *before*
    # forwarding the request to the container, so a Google-issued JWT Bearer
    # token arriving here means IAM authentication has already succeeded.
    if is_cloud_platform() and is_google_oidc_token(token):
        return True

    return False
