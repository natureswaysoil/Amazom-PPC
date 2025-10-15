import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from optimizer_core import PPCAutomation

logger = logging.getLogger(__name__)


def _json_response(payload: Dict[str, Any], status: int = 200):
    """Return a Flask-compatible JSON response tuple."""
    return (json.dumps(payload), status, {"Content-Type": "application/json"})


def _coerce_bool(value: Any) -> Optional[bool]:
    """Convert various representations of truthy/falsey values to bool."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if cleaned in {"0", "false", "f", "no", "n", "off"}:
            return False
    return None


def _normalize_features(raw: Any) -> Optional[List[str]]:
    """Normalize feature lists from strings or iterables."""
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(',')]
    elif isinstance(raw, (list, tuple, set)):
        raw = [str(part).strip() for part in raw]
    else:
        raise ValueError("features must be a comma separated string or list")

    features = [feature for feature in raw if feature]
    return features or []


_TEMP_CONFIG_PATH = os.path.join(tempfile.gettempdir(), "ppc_config_env.yaml")


def _write_temp_config(contents: str) -> str:
    with open(_TEMP_CONFIG_PATH, "w", encoding="utf-8") as handle:
        handle.write(contents)
    return _TEMP_CONFIG_PATH


def _resolve_config_path(request_data: Dict[str, Any]) -> str:
    request_path = request_data.get("config_path")
    if request_path:
        if os.path.exists(request_path):
            return request_path
        logger.warning("Requested config_path '%s' was not found; falling back to defaults", request_path)

    env_path = os.getenv("PPC_CONFIG_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    request_config = request_data.get("config")
    if request_config:
        if isinstance(request_config, (dict, list)):
            contents = json.dumps(request_config)
        else:
            contents = str(request_config)
        return _write_temp_config(contents)

    env_config = os.getenv("PPC_CONFIG")
    if env_config:
        return _write_temp_config(env_config)

    default_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(default_path):
        return default_path

    raise FileNotFoundError(
        "No PPC configuration found. Provide PPC_CONFIG, PPC_CONFIG_PATH, or config_path in the request."
    )

def load_config():
    # Read from environment variables
    config = {}
    config['dashboard'] = {
        'url': os.getenv('DASHBOARD_URL', ''),
        'api_key': os.getenv('DASHBOARD_API_KEY', ''),
        'profile_id': os.getenv('DASHBOARD_PROFILE_ID', 'health-profile')
    }
    config['email'] = {
        'api_key': os.getenv('RESEND_API_KEY', ''),
        'from': os.getenv('RESEND_FROM', ''),
        'test_to': os.getenv('RESEND_TEST_TO', '')
    }
    return config

def check_dashboard(cfg):
    url = cfg['dashboard']['url']
    api_key = cfg['dashboard']['api_key']
    profile_id = cfg['dashboard']['profile_id']
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    headers['X-Profile-ID'] = str(profile_id)
    try:
        resp = requests.get(f"{url}/api/health", headers=headers, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Dashboard health error: {e}")
        return False

def check_email(cfg):
    api_key = cfg['email']['api_key']
    from_addr = cfg['email']['from']
    to_addr = cfg['email']['test_to']
    if not (api_key and from_addr and to_addr):
        print("Email config missing api_key, from, or test_to address.")
        return False
    email_url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": from_addr,
        "to": to_addr,
        "subject": "Health Check Email from PPC Optimizer",
        "html": f"<strong>Health check at {datetime.now().isoformat()}</strong>"
    }
    try:
        resp = requests.post(email_url, json=payload, headers=headers, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Email send error: {e}")
        return False


def run_optimizer(request):
    """Google Cloud Functions entry point for executing the optimizer."""
    request_json: Dict[str, Any] = {}
    if request is not None:
        try:
            request_json = request.get_json(silent=True) or {}
        except Exception:  # pragma: no cover - defensive
            request_json = {}

    if not isinstance(request_json, dict):
        logger.warning("Request JSON body is not an object; ignoring payload")
        request_json = {}

    try:
        config_path = _resolve_config_path(request_json)
    except FileNotFoundError as exc:
        logger.error("Configuration resolution failed: %s", exc)
        return _json_response({
            "status": "error",
            "error": str(exc)
        }, status=500)

    query_args = getattr(request, "args", {}) or {}

    profile_id = (
        request_json.get("profile_id")
        or query_args.get("profile_id")
        or os.getenv("AMAZON_PROFILE_ID")
        or os.getenv("PPC_PROFILE_ID")
    )

    dry_run_value = (
        request_json.get("dry_run")
        if "dry_run" in request_json
        else query_args.get("dry_run", os.getenv("PPC_DRY_RUN"))
    )
    dry_run = _coerce_bool(dry_run_value)
    dry_run = dry_run if dry_run is not None else False

    features_value = (
        request_json.get("features")
        if "features" in request_json
        else query_args.get("features", os.getenv("PPC_FEATURES"))
    )
    try:
        features = _normalize_features(features_value)
    except ValueError as exc:
        logger.error("Invalid features specification: %s", exc)
        return _json_response({
            "status": "error",
            "error": str(exc)
        }, status=400)

    verify_flag = (
        request_json.get("verify_connection")
        if "verify_connection" in request_json
        else query_args.get("verify_connection", os.getenv("PPC_VERIFY_CONNECTION"))
    )
    verify_connection = _coerce_bool(verify_flag) or False

    sample_size_value = (
        request_json.get("verify_sample_size")
        if "verify_sample_size" in request_json
        else query_args.get("verify_sample_size", os.getenv("PPC_VERIFY_SAMPLE_SIZE", 5))
    )
    try:
        sample_size = int(sample_size_value)
    except (TypeError, ValueError):
        sample_size = 5

    try:
        automation = PPCAutomation(config_path, profile_id, dry_run)
    except SystemExit as exc:  # PPCAutomation exits on fatal config errors
        logger.error("Optimizer initialization failed with exit code %s", exc.code)
        return _json_response({
            "status": "error",
            "error": "Optimizer initialization failed. Check logs for details."
        }, status=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error during optimizer initialization")
        return _json_response({
            "status": "error",
            "error": str(exc)
        }, status=500)

    timestamp = datetime.now().isoformat()

    if verify_connection:
        verification = automation.api.verify_connection(sample_size)
        automation.audit.save()
        status_code = 200 if verification.get("success") else 500
        return _json_response({
            "status": "ok" if verification.get("success") else "error",
            "timestamp": timestamp,
            "profile_id": automation.profile_id,
            "dry_run": dry_run,
            "verification": verification
        }, status=status_code)

    try:
        results = automation.run(features)
        response = {
            "status": "ok",
            "timestamp": timestamp,
            "profile_id": automation.profile_id,
            "dry_run": dry_run,
            "features": features,
            "results": results,
        }
        return _json_response(response)
    except SystemExit as exc:  # pragma: no cover - defensive
        logger.error("Optimizer execution terminated with exit code %s", exc.code)
        return _json_response({
            "status": "error",
            "error": "Optimizer run terminated prematurely.",
            "timestamp": timestamp
        }, status=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error during optimizer run")
        return _json_response({
            "status": "error",
            "error": str(exc),
            "timestamp": timestamp
        }, status=500)


def run_health_check(request):
    cfg = load_config()
    dashboard_ok = check_dashboard(cfg)
    email_ok = check_email(cfg)
    result = {
        "timestamp": datetime.now().isoformat(),
        "dashboard_ok": dashboard_ok,
        "email_ok": email_ok
    }
    print(json.dumps(result))
    status = 200 if dashboard_ok and email_ok else 500
    return _json_response(result, status=status)
