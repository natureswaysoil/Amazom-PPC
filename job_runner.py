import json
import logging
import os
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

import yaml

from bigquery_client import BigQueryClient
from dashboard_client import DashboardClient
from main import load_config
from optimizer_core import PPCAutomation


logger = logging.getLogger(__name__)


def _truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _resolve_profile_id(config: Dict[str, Any]) -> str:
    profile_id = (
        (os.getenv("PPC_PROFILE_ID") or "").strip()
        or (os.getenv("AMAZON_PROFILE_ID") or "").strip()
        or str((config.get("amazon_api") or {}).get("profile_id") or "").strip()
    )
    if not profile_id:
        raise ValueError("Missing profile id (set PPC_PROFILE_ID or AMAZON_PROFILE_ID)")
    return profile_id


def _features_for_job_type(job_type: str) -> List[str]:
    jt = (job_type or "").strip().lower()

    # Historic names from Cloud Run Job config.
    if jt in {"keyword_harvest", "keyword-harvest", "keywordharvest"}:
        return ["keyword_discovery"]
    
    # AOV-based bid optimizer
    if jt in {"bid_optimizer", "bid-optimizer", "aov_optimizer", "aov-optimizer"}:
        return ["aov_bid_optimization"]

    # Allow running the full suite if desired.
    if jt in {"optimize", "optimizer", "run_optimizer"}:
        return []  # empty means use config defaults inside PPCAutomation

    # Diagnostic mode: probe API product permissions.
    if jt in {"diagnose_permissions", "diagnose-permissions", "diagnose"}:
        return ["__DIAGNOSE_PERMISSIONS__"]

    raise ValueError(
        f"Unknown JOB_TYPE '{job_type}'. Expected keyword_harvest, bid_optimizer, optimize, or diagnose_permissions."
    )


def _truncate(text: str, limit: int = 400) -> str:
    if text is None:
        return ""
    return text.replace("\n", " ")[:limit]


def _diagnose_permissions(config: Dict[str, Any], profile_id: str) -> int:
    """Probe a few endpoints to classify SP/SB/SD access.

    This runs inside Cloud Run Jobs with secrets already injected, so it avoids
    printing any credential values while still producing actionable output.
    """
    import requests
    from optimizer_core import ENDPOINTS

    region = ((config.get("api") or {}).get("region") or "NA").strip().upper()
    base_url = ENDPOINTS.get(region, ENDPOINTS["NA"])

    # Get an access token by constructing PPCAutomation (which initializes AmazonAdsAPI).
    # This avoids duplicating token exchange logic here.
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
        config_path = handle.name

    try:
        automation = PPCAutomation(config_path=config_path, profile_id=profile_id, dry_run=True)
        api = getattr(automation, "api", None)
        if api is None or getattr(api, "auth", None) is None:
            logger.error("Unable to initialize AmazonAdsAPI for diagnostics")
            return 1

        token = api.auth.access_token
        client_id = api.client_id or os.getenv("AMAZON_CLIENT_ID", "")

        def call(
            name: str,
            path: str,
            *,
            scope_profile_id: Optional[str],
            extra_headers: Optional[Dict[str, str]] = None,
        ):
            url = f"{base_url}{path}"
            headers: Dict[str, str] = {
                "Authorization": f"Bearer {token}",
                "Amazon-Advertising-API-ClientId": client_id,
                "Accept": "application/json",
            }
            if scope_profile_id:
                headers["Amazon-Advertising-API-Scope"] = scope_profile_id
            if extra_headers:
                headers.update(extra_headers)
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                parsed_summary = None
                if name == "profiles_v2" and resp.status_code == 200:
                    try:
                        profiles = resp.json()
                        if isinstance(profiles, list):
                            parsed_summary = [
                                {
                                    "profileId": p.get("profileId"),
                                    "countryCode": p.get("countryCode"),
                                    "currencyCode": p.get("currencyCode"),
                                    "type": ((p.get("accountInfo") or {}).get("type")),
                                    "name": ((p.get("accountInfo") or {}).get("name")),
                                }
                                for p in profiles
                            ]
                    except Exception:
                        parsed_summary = None
                return {
                    "probe": name,
                    "url": url,
                    "status": resp.status_code,
                    "body": parsed_summary if parsed_summary is not None else _truncate(resp.text),
                }
            except Exception as exc:
                return {
                    "probe": name,
                    "url": url,
                    "status": -1,
                    "error": str(exc),
                }

        profiles_probe = call("profiles_v2", "/v2/profiles", scope_profile_id=None)

        probe_all = _truthy(os.getenv("DIAGNOSE_ALL_PROFILES"))
        explicit_ids = (os.getenv("DIAGNOSE_PROFILE_IDS") or "").strip()
        profile_ids: List[str]
        if explicit_ids:
            profile_ids = [p.strip() for p in explicit_ids.split(",") if p.strip()]
        elif probe_all and isinstance(profiles_probe.get("body"), list):
            profile_ids = [str(p.get("profileId")) for p in profiles_probe["body"] if p.get("profileId")]
        else:
            profile_ids = [profile_id]

        per_profile: List[Dict[str, Any]] = []
        for pid in profile_ids:
            per_profile.append(
                {
                    "profile_id": pid,
                    "sp_campaigns": call(
                        "sp_campaigns",
                        "/v2/sp/campaigns?startIndex=0&count=1",
                        scope_profile_id=pid,
                    ),
                    "sp_campaigns_v3": call(
                        "sp_campaigns_v3",
                        "/sp/v3/campaigns?startIndex=0&count=1",
                        scope_profile_id=pid,
                        extra_headers={"Accept": "application/vnd.spCampaign.v3+json"},
                    ),
                    "sb_campaigns_v4": call(
                        "sb_campaigns_v4",
                        "/sb/v4/campaigns?startIndex=0&count=1",
                        scope_profile_id=pid,
                        extra_headers={"Accept": "application/vnd.sbCampaign.v4+json"},
                    ),
                    "sd_campaigns": call(
                        "sd_campaigns",
                        "/sd/campaigns?startIndex=0&count=1",
                        scope_profile_id=pid,
                    ),
                }
            )

        summary = {
            "region": region,
            "configured_profile_id": profile_id,
            "probed_profile_ids": profile_ids,
            "profiles": profiles_probe,
            "per_profile": per_profile,
        }
        logger.info("PERMISSIONS_DIAGNOSTIC %s", json.dumps(summary))
        return 0
    finally:
        try:
            os.unlink(config_path)
        except Exception:
            pass


def main() -> int:
    # Ensure we always have some logging configured.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)

    job_type = os.getenv("JOB_TYPE")
    if not job_type:
        raise ValueError("JOB_TYPE not set")

    logger.info("Starting job type: %s", job_type)

    config: Dict[str, Any] = load_config()
    profile_id = _resolve_profile_id(config)

    # Ensure config carries the chosen profile id.
    config.setdefault("amazon_api", {})
    if isinstance(config["amazon_api"], dict):
        config["amazon_api"]["profile_id"] = profile_id

    dry_run = _truthy(os.getenv("PPC_DRY_RUN")) or _truthy(os.getenv("DRY_RUN"))

    # Determine job behavior early; diagnostics should be side-effect free.
    features = _features_for_job_type(job_type)
    if features == ["__DIAGNOSE_PERMISSIONS__"]:
        return _diagnose_permissions(config, profile_id)

    # Initialize BigQuery client (matches main.py behavior, but without request context).
    bq = None
    bigquery_config = config.get("bigquery", {}) if isinstance(config, dict) else {}
    if isinstance(bigquery_config, dict) and bigquery_config.get("enabled", False):
        project_id = (
            bigquery_config.get("project_id")
            or os.getenv("GCP_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
        )
        if project_id:
            dataset_id = bigquery_config.get("dataset_id", "amazon_ppc_data")
            location = bigquery_config.get("location", "us-east4")
            try:
                bq = BigQueryClient(project_id, dataset_id, location)
                logger.info(
                    "BigQuery client initialized for project %s dataset %s", project_id, dataset_id
                )
            except Exception as exc:
                logger.warning("Failed to initialize BigQuery client: %s", exc)
        else:
            logger.warning("BigQuery enabled but no project_id configured")

    # Default: BigQuery-first. Disable dashboard HTTP updates unless explicitly enabled.
    enable_dashboard_http = _truthy(os.getenv("ENABLE_DASHBOARD_HTTP"))
    if not enable_dashboard_http:
        config.setdefault("dashboard", {})
        if isinstance(config["dashboard"], dict):
            config["dashboard"].setdefault("enabled", False)
            config["dashboard"].setdefault("send_real_time_updates", False)

    dashboard = DashboardClient(config, bigquery_client=bq)
    run_id = dashboard.start_run(dry_run=dry_run)
    logger.info("Run started run_id=%s dry_run=%s", run_id, dry_run)

    # Handle AOV bid optimizer separately
    if features == ["aov_bid_optimization"]:
        from jobs.optimization.aov_bid_optimizer import AOVBidOptimizer
        
        optimizer = AOVBidOptimizer(
            project_id=bq.project_id if bq else os.getenv("GOOGLE_CLOUD_PROJECT"),
            dataset_id=bq.dataset_id if bq else "amazon_ppc"
        )
        
        start = time.time()
        result = optimizer.run(dry_run=dry_run, auto_apply=not dry_run)
        duration = time.time() - start
        
        logger.info(f"AOV Bid Optimizer completed: {result.get('status')} - "
                   f"{result.get('bids_changed', 0)} bids changed of {result.get('bids_processed', 0)} processed")
        
        dashboard.send_results(result, config, duration_seconds=duration, dry_run=dry_run)
        return 0

    if not features:
        features = None

    # PPCAutomation requires a file path config; emit a temp YAML.
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
        config_path = handle.name

    try:
        automation = PPCAutomation(
            config_path=config_path,
            profile_id=profile_id,
            dry_run=dry_run,
            bigquery_client=bq,
            dashboard_client=dashboard,
        )

        start = time.time()
        results = automation.run(features)
        duration = time.time() - start
        dashboard.send_results(results, config, duration_seconds=duration, dry_run=dry_run)
        logger.info("Job '%s' completed in %.2fs with code 0", job_type, duration)
        return 0
    finally:
        try:
            os.unlink(config_path)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logger.exception("Job failed: %s", exc)
        print({"status": "error", "error": str(exc)})
        raise
