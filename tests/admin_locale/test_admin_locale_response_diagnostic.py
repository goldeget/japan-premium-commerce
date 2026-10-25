from __future__ import annotations

import unittest

from tests.e2e.admin_locale_diagnostics import parse_admin_locale_response_diagnostic


class AdminLocaleResponseDiagnosticTests(unittest.TestCase):
    def test_missing_response_header_is_distinct_from_malformed_header(self) -> None:
        self.assertEqual(
            parse_admin_locale_response_diagnostic(None),
            "unavailable:missing_header",
        )
        self.assertEqual(
            parse_admin_locale_response_diagnostic("missing"),
            "unavailable:missing_header",
        )
        self.assertEqual(
            parse_admin_locale_response_diagnostic("unexpected response header"),
            "unavailable:invalid_diagnostic",
        )

    def test_navigation_and_follow_up_dom_metadata_are_bounded(self) -> None:
        navigation = parse_admin_locale_response_diagnostic(
            "missing;navigation_status=200;navigation_route_match=true;navigation_url_exact=true;"
            "navigation_from_service_worker=false;navigation_from_disk_cache=false;"
            "navigation_from_prefetch_cache=false;document_lang=other;"
            "document_sw_controlled=false;navigation_worker_used=false"
        )
        self.assertEqual(
            "unavailable:missing_header;navigation_status=200;navigation_route_match=true;"
            "navigation_url_exact=true;navigation_from_service_worker=false;"
            "navigation_from_disk_cache=false;navigation_from_prefetch_cache=false;"
            "document_lang=other;document_sw_controlled=false;navigation_worker_used=false",
            navigation,
        )

        follow_up = parse_admin_locale_response_diagnostic(
            "missing;browser_status=200;browser_type=basic;browser_redirected=false;"
            "browser_same_route=true;browser_url_exact=true;document_lang=other;"
            "response_html_lang=korean;document_sw_controlled=false;navigation_worker_used=false;"
            "navigation_status=200"
        )
        self.assertEqual(
            "unavailable:missing_header;browser_status=200;browser_type=basic;browser_redirected=false;"
            "browser_same_route=true;browser_url_exact=true;document_lang=other;"
            "response_html_lang=korean;document_sw_controlled=false;navigation_worker_used=false;"
            "navigation_status=200",
            follow_up,
        )

        unsafe = parse_admin_locale_response_diagnostic(
            "missing;browser_status=https://private.invalid/?token=secret;browser_type=basic;"
            "browser_redirected=false;browser_same_route=true;browser_url_exact=true;"
            "document_lang=https://private.invalid/?token=secret;response_html_lang=korean;"
            "document_sw_controlled=false;navigation_worker_used=false;navigation_status=200"
        )
        self.assertEqual(
            "unavailable:missing_header;browser_status=unknown;browser_type=basic;browser_redirected=false;"
            "browser_same_route=true;browser_url_exact=true;document_lang=unavailable;"
            "response_html_lang=korean;document_sw_controlled=false;navigation_worker_used=false;"
            "navigation_status=200",
            unsafe,
        )
        self.assertNotIn("private.invalid", unsafe)
        self.assertNotIn("secret", unsafe)

if __name__ == "__main__":
    unittest.main()
