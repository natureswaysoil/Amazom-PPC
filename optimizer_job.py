import os
import time
import uuid
import yaml

from typing import Any, Dict, List, Optional

from bigquery_client import BigQueryClient
from dashboard_client import DashboardClient
from optimizer_core import PPCAutomation


def _get_env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    val = str(raw).strip().lower()
    if val in ("1", "true", "yes", "y", "on"):
        return True
    if val in ("0", "false", "no", "n", "off"):
        return False
    return default


def _get_env_list(name: str) -> Optional[List[str]]:
    raw = os.getenv(name)
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]
    return parts or None


def _load_base_config() -> Dict[str, Any]:
    # Reuse main.py config resolution to stay consistent with the service.
    import main  # local import to avoid side effects during module import

    cfg = main.load_config()
    if not isinstance(cfg, dict):
        raise ValueError("load_config() did not return a dict")

    # Ensure BigQuery points at the desired dataset for this job.
    # (Env vars are already honored inside BigQueryClient.)
    return cfg


def _write_yaml_config_file(config: Dict[str, Any]) -> str:
    path = "/tmp/ppc_optimizer_job_config.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return path


def _resolve_project_id(config: Dict[str, Any]) -> str:
    bq_cfg = config.get("bigquery") if isinstance(config, dict) else None
    if isinstance(bq_cfg, dict):
        pid = (bq_cfg.get("project_id") or "").strip()
        if pid:
            return pid
    pid = (os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
    if not pid:
        raise ValueError("Missing GCP project id")
    return pid


def _resolve_profile_id(config: Dict[str, Any]) -> str:
    for name in ("AMAZON_PROFILE_ID", "PPC_PROFILE_ID"):
        raw = (os.getenv(name) or "").strip()
        if raw:
            return raw

    amazon_cfg = config.get("amazon_api") if isinstance(config, dict) else None
    if isinstance(amazon_cfg, dict):
        pid = (amazon_cfg.get("profile_id") or "").strip()
        if pid:
            return pid

    raise ValueError("Missing Amazon Ads profile id")


def main() -> int:
    config = _load_base_config()

    # Disable HTTP calls to the dashboard; we only want BigQuery writes.
    if isinstance(config.get("dashboard"), dict):
        config["dashboard"] = dict(config["dashboard"])
    else:
        config["dashboard"] = {}
    config["dashboard"]["enabled"] = False

    project_id = _resolve_project_id(config)
    bq = BigQueryClient(project_id)

    dashboard_client = DashboardClient(config, bigquery_client=bq)

    dry_run = _get_env_bool("PPC_DRY_RUN", default=True)
    dry_run = _get_env_bool("DRY_RUN", default=dry_run)

    features = _get_env_list("PPC_FEATURES")

    config_path = _write_yaml_config_file(config)
    profile_id = _resolve_profile_id(config)

    # Create a stable-ish run id so the dashboard can group runs.
    run_id = os.getenv("RUN_ID") or f"optimizer-job_{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    dashboard_client.current_run_id = run_id

    start = time.time()
    automation = PPCAutomation(
        config_path,
        profile_id,
        dry_run,
        bigquery_client=bq,
        dashboard_client=dashboard_client,
    )

    results = automation.run(features)
    duration = time.time() - start

    # This writes to BigQuery (even though dashboard is disabled).
    ok = dashboard_client.send_results(results, config, duration_seconds=duration, dry_run=dry_run)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
