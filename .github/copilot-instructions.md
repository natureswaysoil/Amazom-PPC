## Purpose

Short, actionable guidance for AI coding agents working on the Amazon PPC Optimizer
project. Focus is on the runtime architecture, configuration resolution, developer
workflows (local + deploy), and project-specific conventions an agent should
follow when making code changes.

## Big-picture architecture (what to know first)
- Entry points: `main.run_optimizer` (Cloud Function runner) and
  `main.run_health_check` (health endpoint). See `main.py`.
- Core logic lives in `optimizer_core.py` (PPCAutomation, API client, audit,
  feature-runner). Treat `optimizer_core` as the single source of truth for
  feature execution and Amazon Ads integration.
- External integrations:
  - Amazon Advertising API: handled by `AmazonAdsAPI` in `optimizer_core.py`.
  - Dashboard: `dashboard_client.py` implements non-blocking updates and retries.
  - Email (Resend) and GitHub Actions health-checks are used for alerts.
- Deployment targets: Google Cloud Functions (Gen2 / Cloud Run URL) — see
  `DEPLOYMENT_GUIDE.md` and the README deployment section.

## Configuration resolution (critical)
- Priority order used at runtime (follow the code in `main.py`):
  1. `config` object included in the incoming JSON request
  2. `config_path` in the request
  3. `PPC_CONFIG_PATH` env var (path to YAML/JSON)
  4. `PPC_CONFIG` env var (JSON/YAML string)
  5. Bundled `config.json` in the repository
- Important env vars used across the codebase:
  - `AMAZON_CLIENT_ID`, `AMAZON_CLIENT_SECRET`, `AMAZON_REFRESH_TOKEN`
  - `AMAZON_PROFILE_ID` / `PPC_PROFILE_ID`
  - `PPC_CONFIG`, `PPC_CONFIG_PATH`
  - `PPC_DRY_RUN`, `PPC_FEATURES` (comma-separated),
    `PPC_VERIFY_CONNECTION`, `PPC_VERIFY_SAMPLE_SIZE`
  - Dashboard: `DASHBOARD_URL`, `DASHBOARD_API_KEY`

## Developer workflows & quick commands (examples)
- Local verification (lightweight):
  python optimizer_core.py --config sample_config.yaml --profile-id <PROFILE> --verify-connection
- Run the service locally (health endpoint):
  python main.py
  or build the Docker image and run (Dockerfile uses gunicorn bound to 8080):
  docker build -t ppc-optimizer .
  docker run -p 8080:8080 -e PPC_CONFIG='{"amazon_api":{...}}' ppc-optimizer
- Deploy (production, uses Secret Manager): see README for the gcloud example which
  uses `--set-secrets` and `--no-allow-unauthenticated` (Gen2 Cloud Functions).
- Triggering optimization remotely (POST JSON or query params):
  - Health check: GET <FUNCTION_URL>?health=true
  - Run: POST <FUNCTION_URL> with JSON {"profile_id":"...","dry_run":true}
  - Verify via function: <FUNCTION_URL>?verify_connection=true&verify_sample_size=10

## Project-specific code conventions & patterns
- Dry-run pattern: functions accept `dry_run` (param/env `PPC_DRY_RUN`) and the
  code records actions to audit CSVs but avoids applying changes when dry-run is true.
- Feature selection: features may be passed as a comma-separated string or list
  (`PPC_FEATURES` or request `features`). Use `_normalize_features` in `main.py`
  as the canonical parser.
- Token management: `AmazonAdsAPI` automatically refreshes access tokens before
  each request (`_refresh_auth_if_needed`). Do not duplicate token refresh logic.
- Rate limiting & retries:
  - Global limit set by `MAX_REQUESTS_PER_SECOND` / `RateLimiter` in
    `optimizer_core.py`.
  - Dashboard client uses exponential backoff via `retry_with_backoff` in
    `dashboard_client.py` and is intentionally non-blocking (failures shouldn't
    stop optimization runs).
- Fatal errors: config or auth problems call `sys.exit()` in `optimizer_core.py`.
  When making changes that could raise these errors, prefer returning descriptive
  exceptions that the Cloud Function handler can convert to JSON responses.

## Where to change or add features
- New optimization features should be added inside `optimizer_core.py` or as a
  sibling module and wired into PPCAutomation.run so they are callable by name
  from the `features` list. Mirror the existing naming used in the config
  (e.g., `bid_optimization`, `dayparting`). Update `sample_config.yaml`.
- For dashboard payload changes, update `dashboard_client.py::_build_results_payload`
  to ensure the enhanced payload remains backward-compatible with the dashboard.

## Important files to inspect when editing
- `main.py` — Cloud Function handlers, config resolution, request coercion.
- `optimizer_core.py` — core automation, Amazon client, rate limiting, audit.
- `dashboard_client.py` — dashboard integration, retries, payload format.
- `sample_config.yaml` / `config.json` — canonical config shape and defaults.
- `Dockerfile`, `requirements.txt` — runtime and packaging details used by CI/CD.
- `.github/workflows/health-check.yml` — health-check behavior after deploy.

## Tests, linting, and validation notes
- There are no automated unit tests in the repo. Before submitting changes:
  - Run `pip install -r requirements.txt` in a virtualenv
  - Run the verify command above to validate Amazon API connectivity (use
    test credentials or the `--verify-connection` flag)
  - Validate config parsing by exercising `main._resolve_config_path` with
    different environment and request payload combinations.

## Examples to copy/paste (from code)
- Normalize features (use this exact behavior):
  - Input: `"bid_optimization,dayparting"` -> `['bid_optimization','dayparting']`
  - Function to call: `_normalize_features` in `main.py`
- Respect the non-blocking dashboard contract: use `dashboard_client.send_results`
  and **do not** fail the run if dashboard returns non-200 responses.

---
If any of these sections are unclear or you need more detail about one module,
tell me which area to expand (architecture, feature wiring, or deployment).
