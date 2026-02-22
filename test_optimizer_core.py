#!/usr/bin/env python3
"""
Tests for optimizer_core module.

Focuses on endpoint resolution logic to guard against regressions that caused
403 "Invalid key=value pair" errors when SP endpoints were rewritten to
unversioned paths (e.g. `/sp/keywords` instead of `/v2/sp/keywords`).
"""

import time
import unittest
from unittest.mock import MagicMock, patch


class TestUpgradeEndpoint(unittest.TestCase):
    """Tests for AmazonAdsAPI._upgrade_endpoint."""

    def _make_api(self):
        """Return a minimal AmazonAdsAPI instance with authentication mocked out."""
        from optimizer_core import AmazonAdsAPI, Auth

        fake_auth = Auth(
            access_token="fake_token",
            token_type="bearer",
            expires_at=time.time() + 3600,
        )
        with patch.object(AmazonAdsAPI, "_authenticate", return_value=fake_auth):
            api = AmazonAdsAPI(profile_id="123456789")
        return api

    # ------------------------------------------------------------------
    # SP endpoints must keep the /v2/ prefix (path-based versioning)
    # ------------------------------------------------------------------

    def test_sp_keywords_keeps_v2_prefix(self):
        """/v2/sp/keywords must NOT be rewritten to the unversioned path."""
        api = self._make_api()
        path, version = api._upgrade_endpoint("/v2/sp/keywords")
        self.assertEqual(path, "/v2/sp/keywords")
        self.assertIsNone(version)

    def test_sp_keywords_with_query_params_keeps_v2_prefix(self):
        """Path with a suffix should still keep /v2/."""
        api = self._make_api()
        path, version = api._upgrade_endpoint("/v2/sp/keywords/extended")
        self.assertEqual(path, "/v2/sp/keywords/extended")
        self.assertIsNone(version)

    def test_sp_campaigns_keeps_v2_prefix(self):
        api = self._make_api()
        path, version = api._upgrade_endpoint("/v2/sp/campaigns")
        self.assertEqual(path, "/v2/sp/campaigns")
        self.assertIsNone(version)

    def test_sp_ad_groups_keeps_v2_prefix(self):
        api = self._make_api()
        path, version = api._upgrade_endpoint("/v2/sp/adGroups")
        self.assertEqual(path, "/v2/sp/adGroups")
        self.assertIsNone(version)

    def test_sp_negative_keywords_keeps_v2_prefix(self):
        api = self._make_api()
        path, version = api._upgrade_endpoint("/v2/sp/negativeKeywords")
        self.assertEqual(path, "/v2/sp/negativeKeywords")
        self.assertIsNone(version)

    def test_sp_targets_keywords_recommendations_keeps_v2_prefix(self):
        api = self._make_api()
        path, version = api._upgrade_endpoint("/v2/sp/targets/keywords/recommendations")
        self.assertEqual(path, "/v2/sp/targets/keywords/recommendations")
        self.assertIsNone(version)

    # ------------------------------------------------------------------
    # Reports endpoint must be rewritten to /reporting/reports
    # ------------------------------------------------------------------

    def test_reports_endpoint_rewritten(self):
        """/v2/reports must be rewritten to /reporting/reports with version header."""
        from optimizer_core import REPORTS_API_VERSION
        api = self._make_api()
        path, version = api._upgrade_endpoint("/v2/reports")
        self.assertEqual(path, "/reporting/reports")
        self.assertEqual(version, REPORTS_API_VERSION)

    def test_reports_endpoint_suffix_preserved(self):
        """/v2/reports/<id>/status must become /reporting/reports/<id>/status."""
        from optimizer_core import REPORTS_API_VERSION
        api = self._make_api()
        path, version = api._upgrade_endpoint("/v2/reports/abc123/status")
        self.assertEqual(path, "/reporting/reports/abc123/status")
        self.assertEqual(version, REPORTS_API_VERSION)

    # ------------------------------------------------------------------
    # Non-/v2/ paths pass through unchanged
    # ------------------------------------------------------------------

    def test_v3_campaigns_list_passthrough(self):
        """/v3/sp/campaigns/list should be returned as-is with no version header."""
        api = self._make_api()
        path, version = api._upgrade_endpoint("/v3/sp/campaigns/list")
        self.assertEqual(path, "/v3/sp/campaigns/list")
        self.assertIsNone(version)

    def test_unversioned_sp_campaigns_passthrough(self):
        """/sp/campaigns without a version prefix passes through unchanged."""
        api = self._make_api()
        path, version = api._upgrade_endpoint("/sp/campaigns")
        self.assertEqual(path, "/sp/campaigns")
        self.assertIsNone(version)

    def test_unversioned_sp_keywords_passthrough(self):
        """/sp/keywords without a version prefix passes through unchanged."""
        api = self._make_api()
        path, version = api._upgrade_endpoint("/sp/keywords")
        self.assertEqual(path, "/sp/keywords")
        self.assertIsNone(version)

    def test_empty_endpoint(self):
        """Empty string should return empty string with no version."""
        api = self._make_api()
        path, version = api._upgrade_endpoint("")
        self.assertEqual(path, "")
        self.assertIsNone(version)

    def test_none_endpoint(self):
        """None should be treated as empty string."""
        api = self._make_api()
        path, version = api._upgrade_endpoint(None)
        self.assertEqual(path, "")
        self.assertIsNone(version)


class TestListCampaignsV3Dedup(unittest.TestCase):
    """Tests that list_campaigns_v3 skips all header/body variants on 404 for versioned endpoints."""

    def _make_api(self):
        from optimizer_core import AmazonAdsAPI, Auth

        fake_auth = Auth(
            access_token="fake_token",
            token_type="bearer",
            expires_at=time.time() + 3600,
        )
        with patch.object(AmazonAdsAPI, "_authenticate", return_value=fake_auth):
            api = AmazonAdsAPI(profile_id="123456789")
        return api

    def _make_404_response(self):
        resp = MagicMock()
        resp.status_code = 404
        resp.text = "Not Found"
        http_err = __import__("requests").exceptions.HTTPError(response=resp)
        http_err.response = resp
        return http_err

    def test_v3_endpoint_breaks_body_and_header_loops_on_404(self):
        """A 404 from /v3/sp/campaigns/list should stop trying further body AND header variants."""
        api = self._make_api()
        http_err = self._make_404_response()

        v3_call_count = 0
        total_call_count = 0

        def fake_request(method, endpoint, **kwargs):
            nonlocal v3_call_count, total_call_count
            total_call_count += 1
            if "/v3/" in endpoint:
                v3_call_count += 1
            raise http_err

        with patch.object(api, "_request", side_effect=fake_request):
            try:
                api.list_campaigns_v3(count=10, start_index=0)
            except Exception:
                pass

        # With the fix: /v3/ breaks body AND header loops on 404 → 1 call per endpoint (not 9)
        self.assertLessEqual(v3_call_count, 1,
                             f"Expected at most 1 call for /v3 endpoint on 404 (skip all variants), got {v3_call_count}")

        # Total: 1 (/v3) + 1 (/v2) + 9 (unversioned, all fail) = 11
        self.assertLessEqual(total_call_count, 11,
                             f"Expected at most 11 total calls with 404 break for versioned endpoints, got {total_call_count}")

    def test_v2_endpoint_breaks_body_and_header_loops_on_404(self):
        """Pre-existing behaviour: a 404 from /v2/sp/campaigns/list stops all header/body variants."""
        api = self._make_api()
        http_err = self._make_404_response()

        v2_call_count = 0

        def fake_request(method, endpoint, **kwargs):
            nonlocal v2_call_count
            if "/v2/" in endpoint:
                v2_call_count += 1
            raise http_err

        with patch.object(api, "_request", side_effect=fake_request):
            try:
                api.list_campaigns_v3(count=10, start_index=0)
            except Exception:
                pass

        # /v2/ should only try once per endpoint (1 call, not 3 headers × 1 body = 3)
        self.assertLessEqual(v2_call_count, 1,
                             f"Expected at most 1 call for /v2 endpoint on 404, got {v2_call_count}")


class TestGetCampaignsCachesFailure(unittest.TestCase):
    """Tests that get_campaigns caches an empty result after both primary and fallback fail."""

    def _make_api(self):
        from optimizer_core import AmazonAdsAPI, Auth

        fake_auth = Auth(
            access_token="fake_token",
            token_type="bearer",
            expires_at=time.time() + 3600,
        )
        with patch.object(AmazonAdsAPI, "_authenticate", return_value=fake_auth):
            api = AmazonAdsAPI(profile_id="123456789")
        return api

    def test_failed_fallback_caches_empty_list(self):
        """After both primary and fallback endpoints fail, subsequent calls must use the cache."""
        api = self._make_api()

        # _request always fails
        with patch.object(api, "_request", side_effect=Exception("API unavailable")):
            result1 = api.get_campaigns()

        self.assertEqual(result1, [], "Should return empty list on failure")
        self.assertIsNotNone(api._campaigns_cache,
                             "_campaigns_cache must be set even after a complete failure")
        self.assertEqual(api._campaigns_cache, [])

        # A second call must use the cache and NOT call _request again
        request_call_count = [0]

        def counting_request(*args, **kwargs):
            request_call_count[0] += 1
            raise Exception("should not be called")

        with patch.object(api, "_request", side_effect=counting_request):
            result2 = api.get_campaigns()

        self.assertEqual(result2, [], "Cached empty list should be returned")
        self.assertEqual(request_call_count[0], 0,
                         "_request must not be called again after failure cache is set")

    def test_invalidate_clears_failure_cache(self):
        """invalidate_campaigns_cache must clear the failure cache so a retry is possible."""
        api = self._make_api()

        with patch.object(api, "_request", side_effect=Exception("API unavailable")):
            api.get_campaigns()

        # Clear cache
        api.invalidate_campaigns_cache()
        self.assertIsNone(api._campaigns_cache)


class TestGetKeywordsErrorHandling(unittest.TestCase):
    """Tests for AmazonAdsAPI.get_keywords endpoint path and 403 error handling.

    Guards against a regression where get_keywords used the unversioned
    ``/sp/keywords`` path (with an ``Amazon-Advertising-API-Version: v3``
    header), causing Amazon to return 403 "Invalid key=value pair" errors for
    every campaign instead of fetching keywords normally.
    """

    def _make_api(self):
        from optimizer_core import AmazonAdsAPI, Auth

        fake_auth = Auth(
            access_token="fake_token",
            token_type="bearer",
            expires_at=time.time() + 3600,
        )
        with patch.object(AmazonAdsAPI, "_authenticate", return_value=fake_auth):
            api = AmazonAdsAPI(profile_id="123456789")
        return api

    def _make_sp_permission_403(self):
        """Return a requests.HTTPError that looks like the SP 'Invalid key=value pair' 403."""
        import requests as _requests

        resp = MagicMock()
        resp.status_code = 403
        resp.text = (
            '{"message":"Invalid key=value pair (missing equal-sign) in Authorization header"}'
        )
        http_err = _requests.exceptions.HTTPError(response=resp)
        http_err.response = resp
        return http_err

    # ------------------------------------------------------------------
    # Endpoint path correctness
    # ------------------------------------------------------------------

    def test_get_keywords_uses_v2_path(self):
        """/v2/sp/keywords must be used — never the unversioned /sp/keywords."""
        api = self._make_api()

        called_endpoints = []

        def fake_request(method, endpoint, **kwargs):
            called_endpoints.append(endpoint)
            mock_resp = MagicMock()
            mock_resp.json.return_value = []
            return mock_resp

        with patch.object(api, "_request", side_effect=fake_request):
            api.get_keywords(campaign_id="420517615314283")

        self.assertEqual(len(called_endpoints), 1)
        self.assertEqual(
            called_endpoints[0],
            "/v2/sp/keywords",
            f"get_keywords must call /v2/sp/keywords, got {called_endpoints[0]!r}",
        )

    # ------------------------------------------------------------------
    # 403 "Invalid key=value pair" — single keyword fetch
    # ------------------------------------------------------------------

    def test_get_keywords_sp_permission_403_raises_runtime_error(self):
        """403 'Invalid key=value pair' must surface as RuntimeError with a clear message."""
        api = self._make_api()
        http_err = self._make_sp_permission_403()

        with patch.object(api, "_request", side_effect=http_err):
            with self.assertRaises(RuntimeError) as ctx:
                api.get_keywords(campaign_id="420517615314283")

        self.assertIn("Sponsored Products API access denied", str(ctx.exception))

    # ------------------------------------------------------------------
    # 403 "Invalid key=value pair" — campaign loop fast-fail
    # ------------------------------------------------------------------

    def test_get_keywords_campaign_loop_fast_fails_on_sp_permission_403(self):
        """Campaign loop must abort after the first 403 SP permission error.

        Without the fix the loop silently continued to every campaign, wasting
        the entire Cloud Run Job timeout on a failure mode that cannot succeed.
        """
        api = self._make_api()
        http_err = self._make_sp_permission_403()

        keywords_call_count = [0]

        def fake_request(method, endpoint, **kwargs):
            if endpoint == "/v2/sp/campaigns":
                mock_resp = MagicMock()
                mock_resp.json.return_value = [
                    {
                        "campaignId": str(i),
                        "name": f"Camp{i}",
                        "state": "enabled",
                        "dailyBudget": 10.0,
                        "targetingType": "manual",
                    }
                    for i in range(1, 4)  # 3 campaigns
                ]
                return mock_resp
            if endpoint == "/v2/sp/keywords":
                keywords_call_count[0] += 1
                raise http_err
            raise Exception(f"Unexpected endpoint: {endpoint!r}")

        with patch.object(api, "_request", side_effect=fake_request):
            with self.assertRaises(RuntimeError) as ctx:
                api.get_keywords()  # no filter → iterates over all campaigns

        # Must abort after the very first campaign, not loop through all three.
        self.assertEqual(
            keywords_call_count[0],
            1,
            f"Expected fast-fail after 1 keyword request but got {keywords_call_count[0]}",
        )
        self.assertIn("Sponsored Products API access denied", str(ctx.exception))

    # ------------------------------------------------------------------
    # Non-SP errors are handled gracefully (no fast-fail)
    # ------------------------------------------------------------------

    def test_get_keywords_generic_error_returns_empty(self):
        """A non-SP-permission error must be caught and return an empty list."""
        api = self._make_api()

        with patch.object(api, "_request", side_effect=Exception("network error")):
            result = api.get_keywords(campaign_id="420517615314283")

        self.assertEqual(result, [])


class TestGetKeywordBidRecommendations(unittest.TestCase):
    """Tests for AmazonAdsAPI.get_keyword_bid_recommendations."""

    def _make_api(self):
        from optimizer_core import AmazonAdsAPI, Auth

        fake_auth = Auth(
            access_token="fake_token",
            token_type="bearer",
            expires_at=time.time() + 3600,
        )
        with patch.object(AmazonAdsAPI, "_authenticate", return_value=fake_auth):
            return AmazonAdsAPI(profile_id="123456789")

    def test_returns_suggested_bid_on_success(self):
        """A successful 200 response returns the suggested bid per keyword."""
        api = self._make_api()

        def fake_request(method, endpoint, **kwargs):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "keywords": [
                    {
                        "keywordId": 111,
                        "code": "SUCCESS",
                        "bid": {"suggested": 0.75, "rangeStart": 0.5, "rangeEnd": 1.0},
                    }
                ]
            }
            return mock_resp

        with patch.object(api, "_request", side_effect=fake_request):
            result = api.get_keyword_bid_recommendations(
                [{"keywordId": 111, "campaignId": 1, "adGroupId": 2, "matchType": "EXACT"}]
            )

        self.assertEqual(result.get("111"), 0.75)

    def test_non_success_code_returns_none(self):
        """A keyword with a non-SUCCESS code is mapped to None."""
        api = self._make_api()

        def fake_request(method, endpoint, **kwargs):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "keywords": [{"keywordId": 222, "code": "NOT_APPLICABLE"}]
            }
            return mock_resp

        with patch.object(api, "_request", side_effect=fake_request):
            result = api.get_keyword_bid_recommendations(
                [{"keywordId": 222, "campaignId": 1, "adGroupId": 2}]
            )

        self.assertIsNone(result.get("222"))

    def test_404_response_returns_error_tuple(self):
        """A 404 HTTP error is returned as a (404, None) tuple."""
        import requests as _requests

        api = self._make_api()

        resp = MagicMock()
        resp.status_code = 404
        resp.text = "Not Found"
        http_err = _requests.exceptions.HTTPError(response=resp)
        http_err.response = resp

        with patch.object(api, "_request", side_effect=http_err):
            result = api.get_keyword_bid_recommendations(
                [{"keywordId": 333, "campaignId": 1, "adGroupId": 2}]
            )

        self.assertEqual(result.get("333"), (404, None))

    def test_uses_bulk_bid_recommendations_endpoint(self):
        """The bulk endpoint /v2/sp/keywords/bidRecommendations must be used."""
        api = self._make_api()
        called_endpoints = []

        def fake_request(method, endpoint, **kwargs):
            called_endpoints.append(endpoint)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"keywords": []}
            return mock_resp

        with patch.object(api, "_request", side_effect=fake_request):
            api.get_keyword_bid_recommendations(
                [{"keywordId": 444, "campaignId": 5, "adGroupId": 6}]
            )

        self.assertEqual(len(called_endpoints), 1)
        self.assertEqual(called_endpoints[0], "/v2/sp/keywords/bidRecommendations")

    def test_groups_by_ad_group(self):
        """Keywords in different ad groups are sent as separate API calls."""
        api = self._make_api()
        call_count = [0]

        def fake_request(method, endpoint, **kwargs):
            call_count[0] += 1
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"keywords": []}
            return mock_resp

        keywords = [
            {"keywordId": 1, "campaignId": 10, "adGroupId": 100},
            {"keywordId": 2, "campaignId": 10, "adGroupId": 200},  # different ad group
        ]
        with patch.object(api, "_request", side_effect=fake_request):
            api.get_keyword_bid_recommendations(keywords)

        self.assertEqual(call_count[0], 2)

    def test_v2_404_falls_back_to_v3_endpoint(self):
        """A 404 from POST /v2/sp/keywords/bidRecommendations retries with
        POST /sp/keywords/bidRecommendations and returns the suggested bid."""
        import requests as _requests

        api = self._make_api()
        called_endpoints = []

        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_404.text = "Not Found"
        http_err = _requests.exceptions.HTTPError(response=resp_404)
        http_err.response = resp_404

        def fake_request(method, endpoint, **kwargs):
            called_endpoints.append(endpoint)
            if endpoint == "/v2/sp/keywords/bidRecommendations":
                raise http_err
            # v3 fallback succeeds
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "keywords": [
                    {
                        "keywordId": 555,
                        "code": "SUCCESS",
                        "bid": {"suggested": 0.80},
                    }
                ]
            }
            return mock_resp

        with patch.object(api, "_request", side_effect=fake_request):
            result = api.get_keyword_bid_recommendations(
                [{"keywordId": 555, "campaignId": 1, "adGroupId": 2}]
            )

        self.assertIn("/v2/sp/keywords/bidRecommendations", called_endpoints)
        self.assertIn("/sp/keywords/bidRecommendations", called_endpoints)
        self.assertEqual(result.get("555"), 0.80)

    def test_v2_404_v3_also_fails_returns_error_tuple(self):
        """When both v2 and v3 bid-recommendation endpoints return 404, the
        result is a (404, None) error tuple for affected keywords."""
        import requests as _requests

        api = self._make_api()

        def _make_404_err():
            resp = MagicMock()
            resp.status_code = 404
            resp.text = "Not Found"
            err = _requests.exceptions.HTTPError(response=resp)
            err.response = resp
            return err

        with patch.object(api, "_request", side_effect=_make_404_err()):
            result = api.get_keyword_bid_recommendations(
                [{"keywordId": 666, "campaignId": 1, "adGroupId": 2}]
            )

        self.assertEqual(result.get("666"), (404, None))


class TestBatchUpdateKeywordsWithFallback(unittest.TestCase):
    """Tests for AmazonAdsAPI.batch_update_keywords_with_fallback."""

    def _make_api(self):
        from optimizer_core import AmazonAdsAPI, Auth

        fake_auth = Auth(
            access_token="fake_token",
            token_type="bearer",
            expires_at=time.time() + 3600,
        )
        with patch.object(AmazonAdsAPI, "_authenticate", return_value=fake_auth):
            return AmazonAdsAPI(profile_id="123456789")

    def test_success_on_v2_endpoint(self):
        """Successful PUT /v2/sp/keywords returns correct success count."""
        api = self._make_api()

        def fake_request(method, endpoint, **kwargs):
            mock_resp = MagicMock()
            mock_resp.json.return_value = [
                {"keywordId": 1, "code": "SUCCESS"},
                {"keywordId": 2, "code": "SUCCESS"},
            ]
            return mock_resp

        with patch.object(api, "_request", side_effect=fake_request):
            result = api.batch_update_keywords_with_fallback(
                [{"keywordId": 1, "bid": 0.5}, {"keywordId": 2, "bid": 0.6}]
            )

        self.assertEqual(result["success"], 2)
        self.assertEqual(result["failed"], 0)

    def test_falls_back_to_v3_on_404(self):
        """A 404 from PUT /v2/sp/keywords triggers a retry via PUT /sp/keywords."""
        import requests as _requests

        api = self._make_api()
        called_endpoints = []

        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_404.text = "Not Found"
        http_err = _requests.exceptions.HTTPError(response=resp_404)
        http_err.response = resp_404

        def fake_request(method, endpoint, **kwargs):
            called_endpoints.append(endpoint)
            if endpoint == "/v2/sp/keywords":
                raise http_err
            # v3 fallback succeeds
            mock_resp = MagicMock()
            mock_resp.json.return_value = [{"keywordId": 1, "code": "SUCCESS"}]
            return mock_resp

        with patch.object(api, "_request", side_effect=fake_request):
            result = api.batch_update_keywords_with_fallback(
                [{"keywordId": 1, "bid": 0.5}]
            )

        self.assertIn("/v2/sp/keywords", called_endpoints)
        self.assertIn("/sp/keywords", called_endpoints)
        self.assertEqual(result["success"], 1)
        self.assertEqual(result["failed"], 0)


class TestSuggestedBidOptimizerUnit(unittest.TestCase):
    """Unit tests for SuggestedBidOptimizer."""

    def _make_optimizer(self):
        from optimizer_core import (
            AmazonAdsAPI,
            Auth,
            Config,
            AuditLogger,
            SuggestedBidOptimizer,
        )
        import tempfile, json, os

        fake_auth = Auth(
            access_token="fake_token",
            token_type="bearer",
            expires_at=time.time() + 3600,
        )

        cfg_data = {
            "api": {"region": "NA"},
            "dayparting": {
                "timezone": "UTC",
                "hour_multipliers": {str(h): 1.0 for h in range(24)},
            },
            "suggested_bid_optimization": {
                "min_bid": 0.02,
                "max_bid": 10.0,
                "max_step": 2.0,
                "min_delta": 0.01,
                "max_keywords": 2000,
                "min_orders": 1,
                "max_acos": 0.40,
            },
            "logging": {"output_dir": "/tmp"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fh:
            json.dump(cfg_data, fh)
            cfg_path = fh.name

        try:
            with patch.object(AmazonAdsAPI, "_authenticate", return_value=fake_auth):
                api = AmazonAdsAPI(profile_id="123456789")
            config = Config(cfg_path)
            audit = AuditLogger("/tmp")
            optimizer = SuggestedBidOptimizer(config, api, audit)
        finally:
            os.unlink(cfg_path)

        return optimizer, api

    def _make_keyword(self, keyword_id="1", bid=0.50, state="enabled", match_type="EXACT"):
        from optimizer_core import Keyword

        return Keyword(
            keyword_id=keyword_id,
            ad_group_id="100",
            campaign_id="10",
            keyword_text="test keyword",
            match_type=match_type,
            state=state,
            bid=bid,
        )

    def test_dry_run_does_not_call_update(self):
        """In dry-run mode, no update API calls should be made."""
        optimizer, api = self._make_optimizer()
        kw = self._make_keyword()

        with (
            patch.object(optimizer, "_load_recent_update_count", return_value=None),
            patch.object(optimizer, "_load_keyword_performance", return_value=[]),
            patch.object(optimizer, "_get_all_enabled_keywords", return_value=[kw]),
            patch.object(
                api,
                "get_keyword_bid_recommendations",
                return_value={"1": 0.75},
            ),
            patch.object(
                api, "batch_update_keywords_with_fallback"
            ) as mock_update,
        ):
            result = optimizer.optimize(dry_run=True)

        mock_update.assert_not_called()
        self.assertTrue(result.get("dry_run"))
        self.assertEqual(result["reco_summary"].get("proposed", 0), 1)

    def test_no_candidates_returns_empty_result(self):
        """When SUGGESTED_BID_FALLBACK_TO_ALL=false and no top performers,
        optimize() returns an empty result without calling the API."""
        import os

        optimizer, api = self._make_optimizer()

        with (
            patch.dict(os.environ, {"SUGGESTED_BID_FALLBACK_TO_ALL": "false"}),
            patch.object(optimizer, "_load_recent_update_count", return_value=None),
            patch.object(optimizer, "_load_keyword_performance", return_value=[]),
            patch.object(optimizer, "_select_top_performers", return_value=[]),
        ):
            result = optimizer.optimize(dry_run=True)

        self.assertEqual(result["keywords_evaluated"], 0)
        self.assertIn("message", result)

    def test_guardrail_step_cap_applied(self):
        """A suggested bid that exceeds max_step should be capped."""
        optimizer, api = self._make_optimizer()
        # Current bid $0.50; suggested bid $2.00 — max_step=2.0 means max change
        # = 0.50 * (2.0 - 1) = $0.50, so new bid should be capped at $1.00.
        kw = self._make_keyword(bid=0.50)

        with (
            patch.object(optimizer, "_load_recent_update_count", return_value=None),
            patch.object(optimizer, "_load_keyword_performance", return_value=[]),
            patch.object(optimizer, "_get_all_enabled_keywords", return_value=[kw]),
            patch.object(
                api,
                "get_keyword_bid_recommendations",
                return_value={"1": 2.00},
            ),
            patch.object(
                api,
                "batch_update_keywords_with_fallback",
                return_value={"success": 1, "failed": 0},
            ) as mock_update,
        ):
            result = optimizer.optimize(dry_run=False)

        applied_updates = mock_update.call_args[0][0]
        self.assertEqual(len(applied_updates), 1)
        # Capped new bid: 0.50 + 0.50 = 1.00
        self.assertAlmostEqual(applied_updates[0]["bid"], 1.00, places=2)
        self.assertGreater(result["guardrails"]["step_capped"], 0)

    def test_below_min_delta_skipped(self):
        """Keywords whose bid change is below min_delta must not be updated."""
        optimizer, api = self._make_optimizer()
        # Current bid $0.50; suggested $0.504 — delta=$0.004 < min_delta=$0.01.
        kw = self._make_keyword(bid=0.50)

        with (
            patch.object(optimizer, "_load_recent_update_count", return_value=None),
            patch.object(optimizer, "_load_keyword_performance", return_value=[]),
            patch.object(optimizer, "_get_all_enabled_keywords", return_value=[kw]),
            patch.object(
                api,
                "get_keyword_bid_recommendations",
                return_value={"1": 0.504},
            ),
            patch.object(
                api, "batch_update_keywords_with_fallback"
            ) as mock_update,
        ):
            result = optimizer.optimize(dry_run=False)

        mock_update.assert_not_called()
        self.assertEqual(result["reco_summary"].get("below_min_delta", 0), 1)

    def test_http_404_reco_counted_in_summary(self):
        """Keywords whose recommendation returns 404 are counted in the reco summary."""
        optimizer, api = self._make_optimizer()
        kw = self._make_keyword()

        with (
            patch.object(optimizer, "_load_recent_update_count", return_value=None),
            patch.object(optimizer, "_load_keyword_performance", return_value=[]),
            patch.object(optimizer, "_get_all_enabled_keywords", return_value=[kw]),
            patch.object(
                api,
                "get_keyword_bid_recommendations",
                return_value={"1": (404, None)},
            ),
        ):
            result = optimizer.optimize(dry_run=True)

        self.assertEqual(result["reco_summary"].get("http_404", 0), 1)
        self.assertEqual(result["reco_summary"].get("no_base", 0), 1)
        self.assertEqual(result["reco_summary"].get("unparsed", 0), 1)


class TestLoadKeywordPerformance(unittest.TestCase):
    """Tests for SuggestedBidOptimizer._load_keyword_performance."""

    def _make_optimizer(self):
        from optimizer_core import (
            AmazonAdsAPI,
            Auth,
            Config,
            AuditLogger,
            SuggestedBidOptimizer,
        )
        import tempfile, json, os

        fake_auth = Auth(
            access_token="fake_token",
            token_type="bearer",
            expires_at=time.time() + 3600,
        )

        cfg_data = {
            "api": {"region": "NA"},
            "dayparting": {
                "timezone": "UTC",
                "hour_multipliers": {str(h): 1.0 for h in range(24)},
            },
            "suggested_bid_optimization": {
                "min_bid": 0.02,
                "max_bid": 10.0,
                "max_step": 2.0,
                "min_delta": 0.01,
                "max_keywords": 2000,
                "min_orders": 1,
                "max_acos": 0.40,
            },
            "logging": {"output_dir": "/tmp"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fh:
            json.dump(cfg_data, fh)
            cfg_path = fh.name

        try:
            with patch.object(AmazonAdsAPI, "_authenticate", return_value=fake_auth):
                api = AmazonAdsAPI(profile_id="123456789")
            config = Config(cfg_path)
            audit = AuditLogger("/tmp")
            bq = MagicMock()
            optimizer = SuggestedBidOptimizer(config, api, audit, bigquery_client=bq)
        finally:
            os.unlink(cfg_path)

        return optimizer

    def test_missing_sales_field_returns_empty(self):
        """When the performance schema has no 'sales' key, _load_keyword_performance
        returns [] so the top-performance selection is skipped."""
        optimizer = self._make_optimizer()
        # Return records without 'sales' key.
        optimizer.bigquery_client.fetch_top_performing_keywords.return_value = [
            {"keyword_text": "organic soil", "clicks": 10, "cost": 5.0}
        ]
        result = optimizer._load_keyword_performance()
        self.assertEqual(result, [])

    def test_sales_none_returns_empty(self):
        """When sales is present but None for the first record, _load_keyword_performance
        returns [] so the top-performance selection is skipped."""
        optimizer = self._make_optimizer()
        optimizer.bigquery_client.fetch_top_performing_keywords.return_value = [
            {"keyword_text": "organic soil", "clicks": 10, "cost": 5.0, "sales": None}
        ]
        result = optimizer._load_keyword_performance()
        self.assertEqual(result, [])

    def test_all_zero_sales_returns_empty(self):
        """When all records have sales=0, _load_keyword_performance returns []
        to avoid a guaranteed 'Selected 0 of N' outcome."""
        optimizer = self._make_optimizer()
        optimizer.bigquery_client.fetch_top_performing_keywords.return_value = [
            {"keyword_text": "organic soil", "clicks": 10, "cost": 5.0, "sales": 0},
            {"keyword_text": "potting mix", "clicks": 3, "cost": 1.5, "sales": 0},
        ]
        result = optimizer._load_keyword_performance()
        self.assertEqual(result, [])

    def test_positive_sales_returns_keywords(self):
        """Records with positive sales are returned for top-performance selection."""
        optimizer = self._make_optimizer()
        records = [
            {"keyword_text": "organic soil", "clicks": 10, "cost": 5.0, "sales": 20.0},
            {"keyword_text": "potting mix", "clicks": 3, "cost": 1.5, "sales": 0},
        ]
        optimizer.bigquery_client.fetch_top_performing_keywords.return_value = records
        result = optimizer._load_keyword_performance()
        self.assertEqual(result, records)


class TestSelectTopPerformers(unittest.TestCase):
    """Tests for SuggestedBidOptimizer._select_top_performers."""

    def _make_optimizer(self):
        from optimizer_core import (
            AmazonAdsAPI,
            Auth,
            Config,
            AuditLogger,
            SuggestedBidOptimizer,
        )
        import tempfile, json, os

        fake_auth = Auth(
            access_token="fake_token",
            token_type="bearer",
            expires_at=time.time() + 3600,
        )

        cfg_data = {
            "api": {"region": "NA"},
            "dayparting": {
                "timezone": "UTC",
                "hour_multipliers": {str(h): 1.0 for h in range(24)},
            },
            "suggested_bid_optimization": {
                "min_bid": 0.02,
                "max_bid": 10.0,
                "max_step": 2.0,
                "min_delta": 0.01,
                "max_keywords": 2000,
                "min_orders": 1,
                "max_acos": 0.40,
            },
            "logging": {"output_dir": "/tmp"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fh:
            json.dump(cfg_data, fh)
            cfg_path = fh.name

        try:
            with patch.object(AmazonAdsAPI, "_authenticate", return_value=fake_auth):
                api = AmazonAdsAPI(profile_id="123456789")
            config = Config(cfg_path)
            audit = AuditLogger("/tmp")
            optimizer = SuggestedBidOptimizer(config, api, audit)
        finally:
            os.unlink(cfg_path)

        return optimizer, api

    def _make_keyword(self, keyword_text="organic soil", bid=0.50):
        from optimizer_core import Keyword

        return Keyword(
            keyword_id="1",
            ad_group_id="100",
            campaign_id="10",
            keyword_text=keyword_text,
            match_type="EXACT",
            state="enabled",
            bid=bid,
        )

    def test_uses_precomputed_acos_from_bigquery(self):
        """When 'acos' is present in the performance record, _select_top_performers
        uses it instead of recalculating from cost/sales."""
        optimizer, api = self._make_optimizer()
        kw = self._make_keyword("organic soil")
        # acos=0.30 (below max_acos=0.40) — should be selected.
        # cost=0 is deliberately omitted to confirm acos field takes precedence.
        kw_perf = [{"keyword_text": "organic soil", "sales": 20.0, "acos": 0.30}]
        with patch.object(api, "get_keywords", return_value=[kw]):
            result = optimizer._select_top_performers(kw_perf, min_orders=1, max_acos=0.40)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].keyword_text, "organic soil")

    def test_precomputed_acos_above_max_excluded(self):
        """Keywords with precomputed acos > max_acos are excluded even if
        recalculating from cost=0 would give acos=0."""
        optimizer, api = self._make_optimizer()
        kw = self._make_keyword("organic soil")
        # acos=0.60 (above max_acos=0.40) — should be excluded.
        kw_perf = [{"keyword_text": "organic soil", "sales": 20.0, "acos": 0.60}]
        with patch.object(api, "get_keywords", return_value=[kw]):
            result = optimizer._select_top_performers(kw_perf, min_orders=1, max_acos=0.40)
        self.assertEqual(result, [])

    def test_uses_orders_column_when_present(self):
        """When 'orders' is present in the performance record, it is used
        for the min_orders filter instead of the sales-based approximation."""
        optimizer, api = self._make_optimizer()
        kw = self._make_keyword("organic soil")
        # orders=2 satisfies min_orders=1; acos=0.25 satisfies max_acos=0.40.
        kw_perf = [{"keyword_text": "organic soil", "sales": 20.0, "orders": 2, "acos": 0.25}]
        with patch.object(api, "get_keywords", return_value=[kw]):
            result = optimizer._select_top_performers(kw_perf, min_orders=1, max_acos=0.40)
        self.assertEqual(len(result), 1)

    def test_orders_zero_excluded_when_min_orders_positive(self):
        """Keywords with orders=0 are excluded when min_orders >= 1,
        even if sales > 0."""
        optimizer, api = self._make_optimizer()
        kw = self._make_keyword("organic soil")
        # orders=0 — should fail min_orders=1 filter.
        kw_perf = [{"keyword_text": "organic soil", "sales": 20.0, "orders": 0, "acos": 0.25}]
        with patch.object(api, "get_keywords", return_value=[kw]):
            result = optimizer._select_top_performers(kw_perf, min_orders=1, max_acos=0.40)
        self.assertEqual(result, [])


class TestSitecustomizeHotfix(unittest.TestCase):
    """Tests for the sitecustomize bidRecommendations 429→404 HOTFIX.

    Because Python may have loaded a system-level sitecustomize.py before
    the project's own copy, these tests import the project file explicitly
    via importlib to guarantee they test the correct implementation.
    """

    @classmethod
    def _load_our_sitecustomize(cls):
        """Return the project's sitecustomize module, loaded via its file path."""
        import importlib.util, os

        sc_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "sitecustomize.py"
        )
        spec = importlib.util.spec_from_file_location("_project_sitecustomize", sc_path)
        sc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sc)
        return sc

    def test_hotfix_is_active(self):
        """HOTFIX_ACTIVE must be True after our sitecustomize module is loaded."""
        sc = self._load_our_sitecustomize()
        self.assertTrue(sc.HOTFIX_ACTIVE)

    def test_deprecated_429_converted_to_404(self):
        """_should_convert_to_no_reco returns True for a deprecated 429 on
        a bidRecommendations URL."""
        sc = self._load_our_sitecustomize()
        result = sc._should_convert_to_no_reco(
            response_status=429,
            url="https://advertising.amazon.com/v2/sp/keywords/bidRecommendations",
            body="deprecated resource",
        )
        self.assertTrue(result)

    def test_non_deprecated_429_not_converted(self):
        """_should_convert_to_no_reco returns False for a rate-limit 429 that
        is NOT a deprecated-resource response."""
        sc = self._load_our_sitecustomize()
        result = sc._should_convert_to_no_reco(
            response_status=429,
            url="https://advertising.amazon.com/v2/sp/keywords/bidRecommendations",
            body="Too Many Requests - rate limit exceeded",
        )
        self.assertFalse(result)

    def test_non_bid_reco_url_not_converted(self):
        """_should_convert_to_no_reco returns False for non-bidRecommendations URLs."""
        sc = self._load_our_sitecustomize()
        result = sc._should_convert_to_no_reco(
            response_status=429,
            url="https://advertising.amazon.com/v2/sp/campaigns",
            body="deprecated resource",
        )
        self.assertFalse(result)

    def test_non_429_not_converted(self):
        """_should_convert_to_no_reco returns False for non-429 status codes."""
        sc = self._load_our_sitecustomize()
        result = sc._should_convert_to_no_reco(
            response_status=200,
            url="https://advertising.amazon.com/v2/sp/keywords/bidRecommendations",
            body="deprecated resource",
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
