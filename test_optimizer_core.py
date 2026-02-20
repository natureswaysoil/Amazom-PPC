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


if __name__ == "__main__":
    unittest.main()
