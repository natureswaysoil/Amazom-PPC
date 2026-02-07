# Live Dashboard Data API (BigQuery-backed)

This repo already **pushes** optimizer run data to a dashboard via `DashboardClient`.

To power “live” dashboard views like **Overview**, **Campaigns**, **Automation**, **Discovery**, **Budget Manager**, **Dayparting**, and **Reports**, this service now also exposes **read-only** endpoints that pull from **BigQuery**.

These endpoints are served by the existing Cloud Function/Cloud Run handler in [main.py](main.py).

## Security model

- **Auth**: Requires the same shared secret as the dashboard integration:
  - Header `Authorization: Bearer <DASHBOARD_API_KEY>` **or** `X-API-Key: <DASHBOARD_API_KEY>`
- **CORS**: If the request includes `Origin`, it will only echo `Access-Control-Allow-Origin` when it matches the configured dashboard base URL (from `dashboard.url`).
- **Recommended**: Call these endpoints from your dashboard **server-side** (API route / server action) so you don’t leak the API key to browsers.

## Endpoints

All live data endpoints are accessed via query param routing:

`GET /?live=<section>`

Supported sections:

- `overview`
- `campaigns`
- `automation`
- `discovery`
- `budget`
- `dayparting`
- `reports`

### Common query parameters

- `profile_id` (optional): Filters to a single Amazon Ads profile when available
- `days` (optional, default `14`): Lookback window for aggregations
- `limit` (optional, default `200`): Max rows for list endpoints

### 1) Overview

Returns the latest run + daily aggregates.

Request:

`GET /?live=overview&days=14&profile_id=1780498399290938`

Response shape:

```json
{
  "status": "success",
  "latest": { "run_id": "...", "timestamp": "...", "summary": "..." },
  "daily": [
    { "day": "2026-02-05", "runs": 1, "total_spend": 12.34, "total_sales": 45.67, "blended_acos": 0.27 }
  ]
}
```

### 2) Campaigns

Returns top campaigns aggregated from BigQuery `campaign_details` joined to recent runs.

`GET /?live=campaigns&days=14&limit=100&profile_id=1780498399290938`

### 3) Automation

Returns recent run lifecycle events (started/completed/failed).

`GET /?live=automation&limit=200&profile_id=1780498399290938`

### 4) Discovery / Budget / Dayparting

Returns the matching feature slice from the **latest** run payload:

- `discovery` → `features.keyword_discovery`
- `budget` → `features.budget_optimization`
- `dayparting` → `features.dayparting`

Example:

`GET /?live=dayparting&profile_id=1780498399290938`

### 5) Reports

Returns the latest run payload + daily aggregates (same daily shape as Overview).

`GET /?live=reports&days=30&profile_id=1780498399290938`

## Example curl

```bash
API_BASE="https://YOUR-OPTIMIZER-SERVICE-URL"
API_KEY="YOUR_DASHBOARD_API_KEY"

curl -sS \
  -H "Authorization: Bearer $API_KEY" \
  "$API_BASE?live=overview&days=14" | jq
```

## Required configuration

- BigQuery must be enabled in config (`bigquery.enabled: true`).
- The service must have permission to read the dataset.
- `dashboard.api_key` (or env `DASHBOARD_API_KEY`) must be set for authorization.
