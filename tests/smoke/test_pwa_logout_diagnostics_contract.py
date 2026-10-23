"""Safe diagnostic contracts for logged-out PWA browser failures."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tests.e2e import verify_pwa_browser as pwa_browser


class PwaLogoutDiagnosticsTests(unittest.TestCase):
    def test_logout_diagnostics_redact_urls_and_bound_counts(self) -> None:
        secret_url = (
            "http://localhost:18080/ko/authentication"
            "?email=private-email-sentinel&token=private-token-sentinel"
        )

        class Driver:
            current_url = secret_url

            def execute_script(self, _script: str) -> dict[str, object]:
                return {
                    "navigation_same_origin": True,
                    "response_status": 302,
                    "login_form_count": 10_000,
                    "email_field_count": 10_001,
                    "login_form_visible": False,
                    "email_field_visible": True,
                    "ready_state": "complete",
                    "body_text": "private-body-sentinel",
                }

        metadata = pwa_browser.safe_logout_wait_diagnostics(
            Driver(), "http://localhost:18080"
        )
        diagnostic = pwa_browser.format_logout_wait_diagnostic(metadata)

        self.assertEqual(
            {
                "final_route_class": "authentication",
                "final_document_status": 302,
                "login_form_count": pwa_browser.MAX_PWA_DIAGNOSTIC_ELEMENT_COUNT,
                "login_form_visible": False,
                "email_field_count": pwa_browser.MAX_PWA_DIAGNOSTIC_ELEMENT_COUNT,
                "email_field_visible": True,
                "ready_state": "complete",
            },
            metadata,
        )
        for sentinel in (
            "private-email-sentinel",
            "private-token-sentinel",
            "private-body-sentinel",
            "localhost",
        ):
            self.assertNotIn(sentinel, diagnostic)
        self.assertIn("final_route_class=authentication", diagnostic)
        self.assertIn("login_form_count=20", diagnostic)
        self.assertIn("email_field_count=20", diagnostic)

    def test_logout_diagnostics_omit_status_and_dom_details_for_other_origins(self) -> None:
        class Driver:
            current_url = "https://external.invalid/authentication?token=private-token-sentinel"

            def execute_script(self, _script: str) -> dict[str, object]:
                raise AssertionError("off-origin page must not be inspected")

        metadata = pwa_browser.safe_logout_wait_diagnostics(
            Driver(), "http://localhost:18080"
        )
        diagnostic = pwa_browser.format_logout_wait_diagnostic(metadata)

        self.assertEqual(
            {
                "final_route_class": "other",
                "final_document_status": None,
                "login_form_count": None,
                "login_form_visible": None,
                "email_field_count": None,
                "email_field_visible": None,
                "ready_state": "unknown",
            },
            metadata,
        )
        self.assertNotIn("external.invalid", diagnostic)
        self.assertNotIn("private-token-sentinel", diagnostic)

    def test_logout_diagnostic_formatter_rejects_unbounded_or_unallowlisted_values(self) -> None:
        diagnostic = pwa_browser.format_logout_wait_diagnostic(
            {
                "final_route_class": "private-token-sentinel",
                "final_document_status": 999,
                "login_form_count": 1_000_000,
                "login_form_visible": "private-body-sentinel",
                "email_field_count": -4,
                "email_field_visible": True,
                "ready_state": ["private-body-sentinel"],
                "url": "http://localhost:18080/?token=private-token-sentinel",
            }
        )

        self.assertEqual(
            "; final_route_class=other; final_document_status=unavailable"
            "; login_form_count=20; login_form_visible=unknown"
            "; email_field_count=0; email_field_visible=true; ready_state=unknown",
            diagnostic,
        )
        self.assertNotIn("private-token-sentinel", diagnostic)
        self.assertNotIn("private-body-sentinel", diagnostic)

    def test_logout_form_timeout_retains_original_exception_and_attaches_safe_metadata(self) -> None:
        secret_url = (
            "http://localhost:18080/index.php?controller=authentication"
            "&token=private-token-sentinel"
        )

        class Driver:
            current_url = secret_url

            def execute_script(self, _script: str) -> dict[str, object]:
                return {
                    "navigation_same_origin": True,
                    "response_status": 200,
                    "login_form_count": 1,
                    "login_form_visible": True,
                    "email_field_count": 1,
                    "email_field_visible": True,
                    "ready_state": "complete",
                }

        timeout = pwa_browser.TimeoutException("private-token-sentinel")
        with patch.object(pwa_browser, "wait_visible", side_effect=timeout):
            with self.assertRaises(pwa_browser.TimeoutException) as raised:
                pwa_browser.wait_for_logout_login_form(Driver(), "http://localhost:18080")

        self.assertIs(raised.exception, timeout)
        self.assertEqual(
            {
                "final_route_class": "authentication",
                "final_document_status": 200,
                "login_form_count": 1,
                "login_form_visible": True,
                "email_field_count": 1,
                "email_field_visible": True,
                "ready_state": "complete",
            },
            timeout.pwa_logout_diagnostics,
        )
        self.assertNotIn("private-token-sentinel", pwa_browser.format_logout_wait_diagnostic(
            timeout.pwa_logout_diagnostics
        ))

    def test_logout_wait_timeout_keeps_the_error_and_emits_only_allowlisted_fields(self) -> None:
        browser_source = Path(pwa_browser.__file__).read_text(encoding="utf-8")
        self.assertIn("wait_for_logout_login_form(driver, shop_url)", browser_source)
        self.assertGreaterEqual(browser_source.count("wait_for_logout_login_form(driver, shop_url)"), 2)
        self.assertIn("format_logout_wait_diagnostic(logout_diagnostics)", browser_source)
        self.assertNotIn("str(error)", browser_source)


if __name__ == "__main__":
    unittest.main()
