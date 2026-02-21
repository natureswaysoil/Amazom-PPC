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


class TestIsGoogleOidcToken(unittest.TestCase):
    """Tests for auth_utils.is_google_oidc_token."""

    def _make_jwt(self, payload: dict) -> str:
        """Construct a minimal (unsigned) JWT string for testing."""
        import base64, json as _json
        def b64url(data: str) -> str:
            return base64.urlsafe_b64encode(data.encode()).rstrip(b'=').decode()
        header = b64url('{"alg":"RS256","typ":"JWT"}')
        body = b64url(_json.dumps(payload))
        return f"{header}.{body}.fakesig"

    def test_google_https_issuer_accepted(self):
        from auth_utils import is_google_oidc_token
        token = self._make_jwt({"iss": "https://accounts.google.com", "sub": "1234"})
        self.assertTrue(is_google_oidc_token(token))

    def test_google_plain_issuer_accepted(self):
        from auth_utils import is_google_oidc_token
        token = self._make_jwt({"iss": "accounts.google.com", "sub": "1234"})
        self.assertTrue(is_google_oidc_token(token))

    def test_non_google_issuer_rejected(self):
        from auth_utils import is_google_oidc_token
        token = self._make_jwt({"iss": "https://evil.example.com", "sub": "1234"})
        self.assertFalse(is_google_oidc_token(token))

    def test_plain_api_key_string_rejected(self):
        from auth_utils import is_google_oidc_token
        self.assertFalse(is_google_oidc_token("my-api-key-abc123"))

    def test_empty_string_rejected(self):
        from auth_utils import is_google_oidc_token
        self.assertFalse(is_google_oidc_token(""))

    def test_two_segment_string_rejected(self):
        from auth_utils import is_google_oidc_token
        self.assertFalse(is_google_oidc_token("part1.part2"))

    def test_malformed_base64_rejected(self):
        from auth_utils import is_google_oidc_token
        self.assertFalse(is_google_oidc_token("header.!!!.sig"))


class TestIsAuthorizedDashboardRequest(unittest.TestCase):
    """Tests for auth_utils.is_authorized_dashboard_request."""

    def _make_request(self, headers: dict):
        req = MagicMock()
        headers_mock = MagicMock()
        headers_mock.get = lambda key, default='': headers.get(key, headers.get(key.lower(), default))
        req.headers = headers_mock
        return req

    def test_no_api_key_allows_all(self):
        from auth_utils import is_authorized_dashboard_request
        req = self._make_request({})
        self.assertTrue(is_authorized_dashboard_request(req, ''))

    def test_matching_x_api_key_header(self):
        from auth_utils import is_authorized_dashboard_request
        req = self._make_request({'X-API-Key': 'secret'})
        self.assertTrue(is_authorized_dashboard_request(req, 'secret'))

    def test_mismatched_x_api_key_header(self):
        from auth_utils import is_authorized_dashboard_request
        req = self._make_request({'X-API-Key': 'wrong'})
        self.assertFalse(is_authorized_dashboard_request(req, 'secret'))

    def test_matching_bearer_token(self):
        from auth_utils import is_authorized_dashboard_request
        req = self._make_request({'Authorization': 'Bearer secret'})
        self.assertTrue(is_authorized_dashboard_request(req, 'secret'))

    def test_mismatched_bearer_token(self):
        from auth_utils import is_authorized_dashboard_request
        req = self._make_request({'Authorization': 'Bearer wrongkey'})
        self.assertFalse(is_authorized_dashboard_request(req, 'secret'))

    def test_google_oidc_token_accepted_on_cloud_run(self):
        """Google OIDC JWT is accepted when running on Cloud Run."""
        import base64, json as _json
        from auth_utils import is_authorized_dashboard_request

        def b64url(data: str) -> str:
            return base64.urlsafe_b64encode(data.encode()).rstrip(b'=').decode()
        payload = b64url(_json.dumps({"iss": "https://accounts.google.com", "sub": "svc"}))
        token = f"{b64url('{\"alg\":\"RS256\"}')}.{payload}.sig"

        req = self._make_request({'Authorization': f'Bearer {token}'})
        with patch.dict('os.environ', {'K_SERVICE': 'my-optimizer'}):
            self.assertTrue(is_authorized_dashboard_request(req, 'secret'))

    def test_google_oidc_token_rejected_outside_cloud_run(self):
        """Google OIDC JWT must NOT bypass auth when not on Cloud Run."""
        import base64, json as _json
        from auth_utils import is_authorized_dashboard_request

        def b64url(data: str) -> str:
            return base64.urlsafe_b64encode(data.encode()).rstrip(b'=').decode()
        payload = b64url(_json.dumps({"iss": "https://accounts.google.com", "sub": "svc"}))
        token = f"{b64url('{\"alg\":\"RS256\"}')}.{payload}.sig"

        req = self._make_request({'Authorization': f'Bearer {token}'})
        env_without_cloud = {k: '' for k in ('K_SERVICE', 'FUNCTION_TARGET', 'GAE_SERVICE', 'CLOUD_RUN_JOB')}
        with patch.dict('os.environ', env_without_cloud):
            self.assertFalse(is_authorized_dashboard_request(req, 'secret'))

    def test_fake_jwt_without_google_issuer_rejected_on_cloud_run(self):
        """A JWT-shaped token with a non-Google issuer must still be rejected."""
        import base64, json as _json
        from auth_utils import is_authorized_dashboard_request

        def b64url(data: str) -> str:
            return base64.urlsafe_b64encode(data.encode()).rstrip(b'=').decode()
        payload = b64url(_json.dumps({"iss": "https://evil.example.com", "sub": "attacker"}))
        token = f"{b64url('{\"alg\":\"RS256\"}')}.{payload}.sig"

        req = self._make_request({'Authorization': f'Bearer {token}'})
        with patch.dict('os.environ', {'K_SERVICE': 'my-optimizer'}):
            self.assertFalse(is_authorized_dashboard_request(req, 'secret'))


if __name__ == "__main__":
    unittest.main()
