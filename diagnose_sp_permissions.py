#!/usr/bin/env python3
"""Diagnose Amazon Advertising API product permissions.

This script helps distinguish between:
- Missing Sponsored Products (SP) permission (consistent 403 on /sp endpoints)
- Valid access for Sponsored Brands (SB) and/or Sponsored Display (SD)
- Generic auth / token issues

It uses the refresh token to obtain a new access token, then probes minimal
endpoints for each ad product and reports structured results.

Prerequisites (env vars):
  AMAZON_CLIENT_ID
  AMAZON_CLIENT_SECRET
  AMAZON_REFRESH_TOKEN
  AMAZON_PROFILE_ID   (or PPC_PROFILE_ID)

Optional overrides:
  AMAZON_AUTH_URL (default: https://api.amazon.com/auth/o2/token)
  AMAZON_API_BASE (default: https://advertising-api.amazon.com)

Usage:
  python diagnose_sp_permissions.py

Exit codes:
  0 - Script ran; results printed (even if failures detected)
  1 - Missing required environment configuration
"""
from __future__ import annotations
import os, sys, json, time, hashlib
from typing import Dict, Any
import requests

AUTH_URL = os.getenv("AMAZON_AUTH_URL", "https://api.amazon.com/auth/o2/token")
API_BASE = os.getenv("AMAZON_API_BASE", "https://advertising-api.amazon.com")

REQUIRED_ENVS = ["AMAZON_CLIENT_ID", "AMAZON_CLIENT_SECRET", "AMAZON_REFRESH_TOKEN"]
PROFILE_ID = os.getenv("AMAZON_PROFILE_ID") or os.getenv("PPC_PROFILE_ID")

def missing_envs():
    return [e for e in REQUIRED_ENVS if not os.getenv(e)] + (["AMAZON_PROFILE_ID/PPC_PROFILE_ID"] if not PROFILE_ID else [])

def obtain_access_token() -> Dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": os.getenv("AMAZON_REFRESH_TOKEN"),
        "client_id": os.getenv("AMAZON_CLIENT_ID"),
        "client_secret": os.getenv("AMAZON_CLIENT_SECRET"),
    }
    r = requests.post(AUTH_URL, data=data, timeout=30)
    return {"status_code": r.status_code, "body": safe_json(r), "raw": r.text}

def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {"_raw": resp.text[:400]}

class Probe:
    def __init__(self, name: str, path: str, notes: str = "", headers: Dict[str, str] | None = None):
        self.name = name
        self.path = path
        self.notes = notes
        # Provide sensible default Accept headers for versioned endpoints
        default_headers: Dict[str, str] = {}
        if name.startswith("SB") and "v4" in path:
            # SB v4 multi-ad group campaigns require explicit accept header
            default_headers['Accept'] = 'application/vnd.sbCampaign.v4+json'
        elif name.startswith("SP") and "/sp/v3/" in path:
            # Future-proofing: SP v3 representation accept header if needed
            default_headers['Accept'] = 'application/vnd.spCampaign.v3+json'
        self.headers = {**default_headers, **(headers or {})}

    def run(self, token: str) -> Dict[str, Any]:
        url = f"{API_BASE}{self.path}"
        h = {
            "Authorization": f"Bearer {token}",
            "Amazon-Advertising-API-ClientId": os.getenv("AMAZON_CLIENT_ID", ""),
            "Amazon-Advertising-API-Scope": PROFILE_ID or "",
            **self.headers,
        }
        started = time.time()
        try:
            resp = requests.get(url, headers=h, timeout=30)
            elapsed = time.time() - started
            return {
                "probe": self.name,
                "path": self.path,
                "status": resp.status_code,
                "elapsed_ms": int(elapsed * 1000),
                "sample_body": truncate_body(resp),
                "classification": classify(self.name, resp.status_code, resp.text),
            }
        except Exception as e:
            return {
                "probe": self.name,
                "path": self.path,
                "status": -1,
                "error": str(e),
                "classification": "network_error",
            }

def truncate_body(resp: requests.Response, limit: int = 300) -> str:
    text = resp.text.replace("\n", " ")
    return text[:limit]

def classify(name: str, status: int, body: str) -> str:
    if status == -1:
        return "network_error"
    if status == 401:
        return "unauthorized_invalid_token"
    if status == 429:
        return "rate_limited"
    if status == 403:
        if "Invalid key=value pair" in body:
            # Common SP permission loss pattern
            if name.startswith("SP"):
                return "sp_permission_missing"
            return "permission_denied_generic"
        return "permission_denied"
    if status == 404:
        return "not_found_or_version"
    if status == 200:
        if name.startswith("SP"):
            return "sp_access_ok"
        if name.startswith("SB"):
            return "sb_access_ok"
        if name.startswith("SD"):
            return "sd_access_ok"
        return "access_ok"
    if status >= 500:
        return "server_error"
    return "other"

PROBES = [
    Probe("Profiles", "/v2/profiles", "Baseline profile access"),
    Probe("SP Campaigns v2", "/v2/sp/campaigns?startIndex=0&count=1"),
    Probe("SP Campaigns v3", "/sp/v3/campaigns?startIndex=0&count=1"),
    Probe("SB Campaigns v4", "/sb/v4/campaigns?startIndex=0&count=1"),
    Probe("SB Campaigns legacy", "/sb/campaigns?startIndex=0&count=1"),
    Probe("SD Campaigns", "/sd/campaigns?startIndex=0&count=1"),
]

def main():
    missing = missing_envs()
    if missing:
        print(json.dumps({
            "status": "error",
            "error": "missing_environment",
            "missing": missing,
            "message": "Set required env vars before running diagnostics."
        }, indent=2))
        sys.exit(1)

    token_resp = obtain_access_token()
    if token_resp["status_code"] != 200:
        print(json.dumps({
            "status": "error",
            "error": "token_exchange_failed",
            "token_status_code": token_resp["status_code"],
            "token_body": token_resp["body"],
        }, indent=2))
        sys.exit(0)

    access_token = token_resp["body"].get("access_token", "")
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()[:16]

    results = []
    for probe in PROBES:
        results.append(probe.run(access_token))

    summary = summarize(results)

    print(json.dumps({
        "status": "ok",
        "profile_id": PROFILE_ID,
        "token_sha256_prefix": token_hash,
        "probes": results,
        "summary": summary,
    }, indent=2))
    sys.exit(0)

def summarize(results: list[Dict[str, Any]]) -> Dict[str, Any]:
    classification_counts = {}
    for r in results:
        c = r.get("classification")
        classification_counts[c] = classification_counts.get(c, 0) + 1
    # High-level SP permission inference
    sp_results = [r for r in results if r["probe"].startswith("SP")]
    sp_perm = "unknown"
    if all(r.get("classification") == "sp_permission_missing" for r in sp_results if sp_results):
        sp_perm = "missing"
    elif any(r.get("classification") == "sp_access_ok" for r in sp_results):
        sp_perm = "present"
    return {
        "classification_counts": classification_counts,
        "sp_permission_inference": sp_perm,
    }

if __name__ == "__main__":
    main()
