import argparse
import os
import time
import tempfile
import logging
from typing import Any, Dict, List, Optional

import yaml

from optimizer_core import PPCAutomation
from dashboard_client import DashboardClient
from main import load_config, _get_bigquery_client_from_config

logger = logging.getLogger(__name__)


def _truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_features(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    # Support comma-separated or space-separated
    parts = []
    for chunk in text.replace(",", " ").split():
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts or None


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the optimizer pipeline in a job-friendly way (BigQuery-first).",
    )
    parser.add_argument(
        "--profile-id",
        default=None,
        help="Amazon Ads profile id. Overrides PPC_PROFILE_ID/AMAZON_PROFILE_ID and config amazon_api.profile_id.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no changes applied).",
    )
    parser.add_argument(
        "--features",
        default=None,
        help="Comma/space-separated list of features to run (overrides PPC_FEATURES).",
    )
    parser.add_argument(
        "--enable-dashboard-http",
        action="store_true",
        help="Allow sending HTTP updates to the dashboard (default: disabled; BigQuery writes still happen).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    # Ensure we always have some logging configured.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)

    config: Dict[str, Any] = load_config()

    # Prefer explicit profile from env, then config.
    profile_id = (
        (args.profile_id or "").strip()
        or (os.getenv("PPC_PROFILE_ID") or "").strip()
        or (os.getenv("AMAZON_PROFILE_ID") or "").strip()
        or str((config.get("amazon_api") or {}).get("profile_id") or "").strip()
    )
    if not profile_id:
        raise ValueError("Missing profile id (set PPC_PROFILE_ID or AMAZON_PROFILE_ID)")

    # Ensure config carries the chosen profile id (DashboardClient uses this).
    config.setdefault("amazon_api", {})
    if isinstance(config["amazon_api"], dict):
        config["amazon_api"]["profile_id"] = profile_id

    dry_run = bool(args.dry_run) or _truthy(os.getenv("PPC_DRY_RUN")) or _truthy(os.getenv("DRY_RUN"))
    features = _parse_features(args.features) or _parse_features(os.getenv("PPC_FEATURES"))

    # BigQuery client uses env overrides (BQ_DATASET_ID/BQ_LOCATION) already.
    bq = _get_bigquery_client_from_config(config)

    # Default: BigQuery-first. Disable dashboard HTTP updates unless explicitly enabled.
    if not args.enable_dashboard_http:
        config.setdefault("dashboard", {})
        if isinstance(config["dashboard"], dict):
            config["dashboard"].setdefault("enabled", False)
            config["dashboard"].setdefault("send_real_time_updates", False)

    # We want BigQuery writes even if dashboard URL isn't reachable.
    dashboard = DashboardClient(config, bigquery_client=bq)
    run_id = dashboard.start_run(dry_run=dry_run)
    logger.info("Starting optimization run_id=%s dry_run=%s", run_id, dry_run)

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
        logger.info("Completed optimization run_id=%s duration=%.2fs", run_id, duration)
        return 0
    finally:
        try:
            os.unlink(config_path)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
