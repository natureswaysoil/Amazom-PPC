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
    """Tests that list_campaigns_v3 stops trying body variants on 404 for versioned endpoints."""

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

    def test_v3_endpoint_breaks_body_loop_on_404(self):
        """A 404 from /v3/sp/campaigns/list should stop trying further body variants."""
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

        # With the fix: /v3/ breaks body loop on 404 → 3 headers × 1 body = 3 calls (not 9)
        self.assertLessEqual(v3_call_count, 3,
                             f"Expected at most 3 calls for /v3 endpoint on 404 (one per header), got {v3_call_count}")

        # Total without fix: 9 (/v3) + 3 (/v2) + 9 (unversioned) = 21
        # Total with fix:    3 (/v3) + 3 (/v2) + 9 (unversioned)  = 15
        self.assertLessEqual(total_call_count, 15,
                             f"Expected at most 15 total calls with 404 break for versioned endpoints, got {total_call_count}")

    def test_v2_endpoint_breaks_body_loop_on_404(self):
        """Pre-existing behaviour: a 404 from /v2/sp/campaigns/list stops further body variants."""
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

        # /v2/ should only try one body per header set (3 headers × 1 body = 3)
        self.assertLessEqual(v2_call_count, 3,
                             f"Expected at most 3 calls for /v2 endpoint on 404, got {v2_call_count}")


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


if __name__ == "__main__":
    unittest.main()
