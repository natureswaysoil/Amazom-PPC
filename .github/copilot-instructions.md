# Copilot instructions (Amazom-PPC)

## What this is
Python 3.11 Cloud Functions Gen2 / Cloud Run HTTP service that runs Amazon Ads PPC optimizations.

## Architecture (read these first)
- Request entrypoint: `run_optimizer` in [main.py](../main.py) → resolves config/overrides → constructs `PPCAutomation` in [optimizer_core.py](../optimizer_core.py) → runs feature modules → writes an audit CSV via `AuditLogger` to `logging.output_dir` (default `./logs`).
- Feature modules are plain classes (e.g. `BidOptimizer`, `DaypartingManager`, `CampaignManager`) orchestrated by `PPCAutomation.run()`; feature enablement is string-based (`features.enabled`).

## Entrypoints & modes
- HTTP:
  - `GET /?health=true` returns metadata + `APP_VERSION` (no external calls).
  - `?verify_connection=true` calls `AmazonAdsAPI.verify_connection(sample_size)` and returns a small campaign sample.
  - `run_health_check` does external checks (dashboard `/api/health` + Resend email) and returns 500 unless BOTH succeed.
- Container default: [Dockerfile](../Dockerfile) runs `functions-framework --target run_optimizer --port 8080`.
- Optional jobs: [job_runner.py](../job_runner.py) dispatches `JOB_TYPE` into one-shot runs (or starts a health server when unset).

## Config + overrides (don’t break precedence)
- Config resolution in `run_optimizer`:
  1) request JSON `config_path` → 2) `PPC_CONFIG_PATH` → 3) request JSON `config` → 4) `PPC_CONFIG` → 5) bundled `config.json`.
- JSON configs are written to `/tmp/ppc_config_env.yaml` and loaded via `yaml.safe_load()` (YAML accepts JSON).
- Profile id precedence: request/query `profile_id` → `AMAZON_PROFILE_ID`/`PPC_PROFILE_ID` → config `amazon_api.profile_id` (enforced in `PPCAutomation.__init__`).
- Request/env parsing helpers: `_coerce_bool()` and `_normalize_features()` in [main.py](../main.py).

## Amazon Ads API sharp edges (important)
- All calls go through `AmazonAdsAPI._request()` (rate-limited ~5 rps, retries, best-effort `/v2/...` → non-`/v2` upgrade).
- Amazon sometimes returns HTTP 429 for *deprecated resources* (not real throttling). `_request()` raises `DeprecatedEndpointError` and caches the endpoint/signature as disabled for the rest of the run (see [test_deprecated_endpoints.py](../test_deprecated_endpoints.py)).
- Per-keyword `.../bidRecommendations` is pre-blocked; use batch `POST /sp/keywords/bidRecommendations` via `get_keyword_bid_recommendations_batch()` (it cycles header variants because some backends reject the standard `Authorization` header).

## Developer workflows
- Install: `pip install -r requirements.txt`
- Local HTTP: `functions-framework --target run_optimizer --port 8080` then `curl "http://localhost:8080/?health=true"`
- CLI run: `python optimizer_core.py --config sample_config.yaml --profile-id <ID> --dry-run --features bid_optimization dayparting`
- Connectivity check: `python optimizer_core.py --config sample_config.yaml --profile-id <ID> --verify-connection --verify-sample-size 5`
- Unit test: `python -m unittest -v test_deprecated_endpoints.py`

## Ops notes
- External health check env: `DASHBOARD_URL`/`DASHBOARD_API_KEY` + Resend (`RESEND_API_KEY`, `RESEND_FROM`, `RESEND_TEST_TO`).
- `dashboard_client.py` exists but is not the live integration path today; current runtime dashboard interactions are direct `requests` calls in [main.py](../main.py) / [job_runner.py](../job_runner.py).
- Hotfix images under `hotfix/` inject `sitecustomize.py` to patch legacy deployed jobs; see their READMEs for Cloud Build commands.
