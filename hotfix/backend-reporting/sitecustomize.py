import os
import re
import time
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


_HOTFIX_LOGGED = False


def _log_once(msg: str) -> None:
    global _HOTFIX_LOGGED
    if _HOTFIX_LOGGED:
        return
    _HOTFIX_LOGGED = True
    logging.getLogger().warning(msg)


def _safe_tz_name(value: str, default: str = "America/New_York") -> str:
    value = (value or "").strip()
    if not value:
        return default
    if not re.fullmatch(r"[A-Za-z0-9_./+-]{1,64}", value):
        return default
    return value


def _patch_budget_pacer() -> None:
    try:
        from jobs.optimization import budget_pacer as bp
    except Exception:
        return

    original = getattr(bp, "_fetch_campaigns_today", None)
    if not callable(original):
        return

    def _fetch_campaigns_today_tz():
        tz_name = _safe_tz_name(os.getenv("PACING_TIMEZONE"), "America/New_York")
        query = f"""
        WITH perf AS (
          SELECT
            CAST(cp.campaign_id AS STRING) AS campaign_id,
            SUM(cp.cost) AS spend_today,
            SAFE_DIVIDE(SUM(cp.cost), NULLIF(SUM(cp.conversion_value), 0)) AS acos,
            SAFE_DIVIDE(SUM(cp.conversions), NULLIF(SUM(cp.clicks), 0)) AS cvr
          FROM `{bp.PROJECT_ID}.{bp.DATASET}.campaign_performance` cp
          WHERE cp.date = CURRENT_DATE(\"{tz_name}\")
          GROUP BY cp.campaign_id
        )
        SELECT
          c.campaign_id,
          c.campaign_name,
          c.state,
          c.daily_budget,
          COALESCE(p.spend_today, 0.0) AS spend_today,
          COALESCE(p.acos, 0.0) AS acos,
          COALESCE(p.cvr, 0.0) AS cvr
        FROM `{bp.PROJECT_ID}.{bp.DATASET}.campaigns` c
        LEFT JOIN perf p
          ON CAST(c.campaign_id AS STRING) = p.campaign_id
        """
        started = time.time()
        rows = list(bp.bq_client.query(query).result())
        elapsed = round(time.time() - started, 3)

        # Diagnostic breadcrumbs: Cloud Run Jobs can "succeed" (exit 0) while
        # effectively doing nothing if upstream BQ tables are empty or the date
        # filter is misaligned with the reporting timezone.
        logger.warning(
            "budget_pacer hotfix: tz=%s fetched %d campaign rows in %ss",
            tz_name,
            len(rows),
            elapsed,
        )
        if not rows:
            logger.warning(
                "budget_pacer hotfix: no campaign rows for CURRENT_DATE(\"%s\"); "
                "verify BigQuery freshness (see scripts/verify_budget_pacer_inputs.sh) and PACING_TIMEZONE",
                tz_name,
            )
            fail_on_empty = (os.getenv("BUDGET_PACER_FAIL_ON_EMPTY") or "").strip().lower() in {
                "1",
                "true",
                "t",
                "yes",
                "y",
                "on",
            }
            if fail_on_empty:
                raise RuntimeError(
                    f"budget_pacer fetched 0 campaign rows for CURRENT_DATE(\"{tz_name}\"); failing due to BUDGET_PACER_FAIL_ON_EMPTY"
                )
        return rows

    bp._fetch_campaigns_today = _fetch_campaigns_today_tz
    _log_once("backend hotfix active: budget_pacer uses timezone-aware CURRENT_DATE")


def _patch_ads_reporting() -> None:
    try:
        from jobs.data_sync.amazon_ads_sync import AmazonAdsSync
    except Exception:
        return

    def _report_spec(name: str, group_by: Any, columns: Any) -> Dict[str, Any]:
        name_l = (name or "").lower()

        # Defaults that match observed API validation errors.
        if "campaign" in name_l:
            return {
                "reportTypeId": os.getenv("AMZ_REPORT_TYPE_CAMPAIGN", "spCampaigns"),
                "groupBy": ["campaign"],
                "columns": [
                    "date",
                    "impressions",
                    "clicks",
                    "cost",
                    "purchases14d",
                    "sales14d",
                ],
            }

        if "keyword" in name_l:
            return {
                "reportTypeId": os.getenv("AMZ_REPORT_TYPE_KEYWORD", "spKeywords"),
                "groupBy": ["adGroup"],
                "columns": [
                    "date",
                    "keywordId",
                    "impressions",
                    "clicks",
                    "cost",
                    "purchases14d",
                    "sales14d",
                ],
            }

        # Fallback for any unknown call site.
        group_by = list(group_by) if isinstance(group_by, (list, tuple, set)) else []
        columns = list(columns) if isinstance(columns, (list, tuple, set)) else []
        return {
            "reportTypeId": os.getenv("AMZ_REPORT_TYPE_DEFAULT", "spKeywords"),
            "groupBy": group_by,
            "columns": columns,
        }

    def _post_with_diagnostics(self: Any, path: str, payload: Dict[str, Any]):
        import requests

        last_status: Optional[int] = None
        last_text: Optional[str] = None
        last_url: Optional[str] = None
        last_exc: Optional[Exception] = None

        for base in getattr(self, "api_bases", []):
            url = f"{base}{path}"
            last_url = url
            for attempt in range(4):
                try:
                    headers = self._headers(include_scope=True)
                    resp = requests.post(url, headers=headers, json=payload, timeout=30)
                    last_status = resp.status_code
                    if resp.status_code == 401 and attempt == 0:
                        logger.warning("401 Unauthorized on report POST; refreshing token and retrying once")
                        self.get_access_token()
                        continue
                    if resp.status_code in (429, 503):
                        delay = self._get_rate_limit_delay(resp)
                        logger.warning(
                            "Rate limited (%s) on report POST %s; sleeping %ss (attempt %s/4)",
                            resp.status_code,
                            url,
                            delay,
                            attempt + 1,
                        )
                        time.sleep(delay)
                        continue

                    if resp.status_code in (400, 403):
                        body = (resp.text or "")[:1200]
                        last_text = body
                        logger.warning("Report POST failed %s status=%s body=%s", url, resp.status_code, body)

                    if resp.status_code == 404:
                        break

                    resp.raise_for_status()
                    # success
                    self.api_base = base
                    return resp
                except Exception as exc:
                    last_exc = exc
                    break

        err = f"Report POST failed across bases; url={last_url}; status={last_status}; exc={last_exc}; body={last_text}"
        raise RuntimeError(err)

    def _create_report_hotfix(
        self: Any,
        name: str,
        group_by: list,
        columns: list,
        start_date: str,
        end_date: str,
    ) -> str:
        # Prefer /reporting/reports with v3-ish schema
        spec = _report_spec(name, group_by, columns)
        report_type_id = spec["reportTypeId"]
        group_by = spec["groupBy"]
        columns = spec["columns"]
        candidates = []

        candidates.append(
            (
                "/reporting/reports",
                {
                    "name": name,
                    "startDate": start_date,
                    "endDate": end_date,
                    "configuration": {
                        "adProduct": "SPONSORED_PRODUCTS",
                        "reportTypeId": report_type_id,
                        "groupBy": group_by,
                        "columns": columns,
                        "timeUnit": "DAILY",
                        "format": os.getenv("AMZ_REPORT_FORMAT", "GZIP_JSON"),
                    },
                },
            )
        )

        # Fallback: tolerate legacy enum values
        candidates.append(
            (
                "/reporting/reports",
                {
                    "name": name,
                    "startDate": start_date,
                    "endDate": end_date,
                    "configuration": {
                        "adProduct": "SP",
                        "reportTypeId": report_type_id,
                        "groupBy": group_by,
                        "columns": columns,
                        "timeUnit": "DAILY",
                        "format": os.getenv("AMZ_REPORT_FORMAT", "GZIP_JSON"),
                    },
                },
            )
        )

        last_err: Optional[Exception] = None
        for path, payload in candidates:
            try:
                resp = _post_with_diagnostics(self, path, payload)
                rep = resp.json() if hasattr(resp, "json") else {}
                rid = None
                if isinstance(rep, dict):
                    rid = rep.get("reportId") or rep.get("id")
                if rid:
                    self.reporting_base = f"{self.api_base}/reporting/reports"
                    _log_once("backend hotfix active: Amazon Ads reporting payload fallback enabled")
                    return rid
            except Exception as exc:
                last_err = exc
                continue

        raise RuntimeError(f"Report request failed; last_error={last_err}")

    def _create_placement_report_hotfix(self: Any, start_date: str, end_date: str) -> str:
        # Placement report: treat as keyword report with placement in groupBy/columns.
        name = "SP Keyword Placement Performance"
        return _create_report_hotfix(
            self,
            name=name,
            group_by=["adGroup"],
            columns=["date", "keywordId", "impressions", "clicks", "cost", "purchases14d", "sales14d"],
            start_date=start_date,
            end_date=end_date,
        )

    def _parse_report_records(data_bytes: bytes, content_type: str, url: str):
        import csv
        import gzip
        import io
        import json
        import zipfile

        payload_bytes = data_bytes or b""
        content_type_l = (content_type or "").lower()
        url_l = (url or "").lower()

        # Auto-detect compression by headers, URL suffix, or magic bytes.
        is_gzip = (
            "gzip" in content_type_l
            or url_l.endswith(".gz")
            or payload_bytes.startswith(b"\x1f\x8b")
        )
        is_zip = payload_bytes.startswith(b"PK")

        if is_gzip:
            with gzip.GzipFile(fileobj=io.BytesIO(payload_bytes)) as gz:
                payload_bytes = gz.read()
        elif is_zip:
            with zipfile.ZipFile(io.BytesIO(payload_bytes)) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                if names:
                    payload_bytes = zf.read(names[0])

        text = payload_bytes.decode("utf-8", errors="replace")

        # JSON (array/dict)
        try:
            obj = json.loads(text)
            if isinstance(obj, list):
                return obj
            if isinstance(obj, dict):
                data = obj.get("data")
                if isinstance(data, list):
                    return data
                return [obj]
        except Exception:
            pass

        # NDJSON
        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
        if records:
            return records

        # CSV fallback
        try:
            reader = csv.DictReader(io.StringIO(text))
            return list(reader)
        except Exception as exc:
            snippet = text[:800].replace("\n", "\\n")
            logger.warning(
                "Report parse failed (not JSON/NDJSON; CSV error=%s). content_type=%s url=%s snippet=%s",
                exc,
                content_type,
                url,
                snippet,
            )
            return []

    def _sync_campaign_performance_hotfix(self: Any):
        import requests
        from datetime import datetime, timedelta, timezone
        from google.cloud import bigquery

        logger.info("Syncing campaign performance (14d metrics)...")
        end = datetime.utcnow().date()
        start = (end - timedelta(days=14))
        start_s = start.strftime("%Y-%m-%d")
        end_s = end.strftime("%Y-%m-%d")

        try:
            rid = self._create_report(
                name="SP Campaign Performance",
                group_by=["campaignId"],
                columns=["date"],
                start_date=start_s,
                end_date=end_s,
            )
            url = self._poll_report(rid)
        except Exception as exc:
            logger.warning(f"Campaign performance report not available: {exc}")
            return

        r = requests.get(url)
        r.raise_for_status()
        records = _parse_report_records(r.content, r.headers.get("Content-Type", ""), url)

        created_at = datetime.now(timezone.utc).isoformat()
        rows = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            try:
                rows.append(
                    {
                        "date": rec.get("date") or rec.get("startDate"),
                        "campaign_id": str(rec.get("campaignId") or rec.get("campaign") or ""),
                        "impressions": int(rec.get("impressions") or 0),
                        "clicks": int(rec.get("clicks") or 0),
                        "cost": float(rec.get("cost") or rec.get("spend") or 0.0),
                        "conversions": int(rec.get("purchases14d") or rec.get("purchases") or 0),
                        "conversion_value": float(rec.get("sales14d") or rec.get("sales") or 0.0),
                        "created_at": created_at,
                    }
                )
            except Exception:
                continue

        rows = [row for row in rows if row.get("campaign_id")]
        if not rows:
            logger.info("No campaign performance rows parsed")
            return

        table_id = f"{self.project_id}.{self.dataset}.campaign_performance"
        table = self.bq_client.get_table(table_id)
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema=table.schema,
            ignore_unknown_values=True,
            max_bad_records=10,
        )
        job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()
        logger.info(f"✓ Loaded {len(rows)} campaign performance rows into BigQuery")

    def _sync_keyword_performance_hotfix(self: Any):
        import requests
        from datetime import datetime, timedelta, timezone
        from google.cloud import bigquery

        logger.info("Syncing keyword performance (14d metrics)...")
        end = datetime.utcnow().date()
        start = (end - timedelta(days=14))
        start_s = start.strftime("%Y-%m-%d")
        end_s = end.strftime("%Y-%m-%d")

        try:
            rid = self._create_report(
                name="SP Keyword Performance",
                group_by=["keywordId"],
                columns=["date"],
                start_date=start_s,
                end_date=end_s,
            )
            url = self._poll_report(rid)
        except Exception as exc:
            logger.warning(f"Keyword performance report not available: {exc}")
            return

        r = requests.get(url)
        r.raise_for_status()
        records = _parse_report_records(r.content, r.headers.get("Content-Type", ""), url)

        created_at = datetime.now(timezone.utc).isoformat()
        rows = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            try:
                impressions = int(rec.get("impressions") or 0)
                clicks = int(rec.get("clicks") or 0)
                cost = float(rec.get("cost") or rec.get("spend") or 0.0)
                conversion_value = float(rec.get("sales14d") or rec.get("sales") or 0.0)
                ctr = (clicks / impressions) if impressions else None
                cpc = (cost / clicks) if clicks else None
                acos = (cost / conversion_value) if conversion_value else None
                rows.append(
                    {
                        "date": rec.get("date") or rec.get("startDate"),
                        "keyword_id": str(rec.get("keywordId") or ""),
                        "campaign_id": str(rec.get("campaignId")) if rec.get("campaignId") else None,
                        "ad_group_id": str(rec.get("adGroupId")) if rec.get("adGroupId") else None,
                        "impressions": impressions,
                        "clicks": clicks,
                        "cost": cost,
                        "conversions": int(rec.get("purchases14d") or rec.get("purchases") or 0),
                        "conversion_value": conversion_value,
                        "ctr": ctr,
                        "acos": acos,
                        "cpc": cpc,
                        "created_at": created_at,
                    }
                )
            except Exception:
                continue

        rows = [row for row in rows if row.get("keyword_id")]
        if not rows:
            logger.info("No keyword performance rows parsed")
            return

        table_id = f"{self.project_id}.{self.dataset}.keyword_performance"
        table = self.bq_client.get_table(table_id)
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
            schema=table.schema,
            ignore_unknown_values=True,
            max_bad_records=10,
        )
        job = self.bq_client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()
        logger.info(f"✓ Loaded {len(rows)} keyword performance rows into BigQuery")

    AmazonAdsSync._create_report = _create_report_hotfix
    AmazonAdsSync._create_placement_report = _create_placement_report_hotfix
    AmazonAdsSync.sync_campaign_performance = _sync_campaign_performance_hotfix
    AmazonAdsSync.sync_keyword_performance = _sync_keyword_performance_hotfix


def _apply_hotfixes() -> None:
    _patch_budget_pacer()
    _patch_ads_reporting()


_apply_hotfixes()
