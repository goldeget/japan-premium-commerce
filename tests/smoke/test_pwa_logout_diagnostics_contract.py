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

    def test_logout_diagnostic_includes_the_selected_link_and_both_redirect_paths(self) -> None:
        metadata = {
            "final_route_class": "other",
            "final_document_status": 404,
            "login_form_count": 0,
            "login_form_visible": False,
            "email_field_count": 0,
            "email_field_visible": False,
            "ready_state": "complete",
            "selected_signout": {
                "container": "account_menu",
                "element_id": "signout_link",
                "target": {"path": "/ja/index.php", "query_keys": ["mylogout"]},
            },
            "logout_trace": {
                "observed": True,
                "method": "GET",
                "initial_target": {"path": "/ja/index.php", "query_keys": ["mylogout"]},
                "redirects": [
                    {
                        "status": 302,
                        "target": {"path": "/ja/identity", "query_keys": []},
                        "from_service_worker": False,
                        "from_disk_cache": False,
                    }
                ],
                "final": {
                    "status": 200,
                    "target": {"path": "/ja/identity", "query_keys": []},
                    "from_service_worker": True,
                    "from_disk_cache": False,
                },
            },
            "protected_pwa_trace": {
                "observed": True,
                "method": "GET",
                "initial_target": {"path": "/ja/identity", "query_keys": []},
                "redirects": [
                    {
                        "status": 302,
                        "target": {
                            "path": "/ja/authentication",
                            "query_keys": ["back", "token"],
                            "controller": "authentication",
                            "back": "my-account",
                        },
                        "from_service_worker": True,
                        "from_disk_cache": False,
                    }
                ],
                "final": {
                    "status": 404,
                    "target": {
                        "path": "/ja/authentication",
                        "query_keys": ["back", "token"],
                        "controller": "authentication",
                        "back": "my-account",
                    },
                    "from_service_worker": True,
                    "from_disk_cache": False,
                },
            },
            "protected_network_trace": {
                "observed": True,
                "method": "GET",
                "initial_target": {"path": "/ja/identity", "query_keys": []},
                "redirects": [
                    {
                        "status": 302,
                        "target": {
                            "path": "/ja/authentication",
                            "query_keys": ["back"],
                            "controller": "authentication",
                            "back": "my-account",
                        },
                        "from_service_worker": False,
                        "from_disk_cache": False,
                    }
                ],
                "final": {
                    "status": 404,
                    "target": {
                        "path": "/ja/authentication",
                        "query_keys": ["back"],
                        "controller": "authentication",
                        "back": "my-account",
                    },
                    "from_service_worker": False,
                    "from_disk_cache": False,
                },
            },
            "private_value": "private-token-sentinel",
        }

        diagnostic = pwa_browser.format_logout_wait_diagnostic(metadata)

        self.assertIn("selected_signout=account_menu#signout_link", diagnostic)
        self.assertIn("logout_trace=GET /ja/index.php?keys=mylogout", diagnostic)
        self.assertIn("302->/ja/identity", diagnostic)
        self.assertIn("protected_pwa_trace=GET /ja/identity", diagnostic)
        self.assertIn("302->/ja/authentication", diagnostic)
        self.assertIn("final=404:/ja/authentication;service_worker=true;disk_cache=false", diagnostic)
        self.assertIn("protected_network_trace=GET /ja/identity", diagnostic)
        self.assertIn("final=404:/ja/authentication;service_worker=false;disk_cache=false", diagnostic)
        self.assertIn("query_keys=back,token", diagnostic)
        self.assertNotIn("private-token-sentinel", diagnostic)

    def test_document_navigation_trace_correlates_main_frame_redirects_and_cache_provenance(self) -> None:
        trace_builder = getattr(pwa_browser, "safe_document_navigation_trace", None)
        self.assertTrue(callable(trace_builder), "safe main-frame navigation trace is missing")

        shop_url = "http://localhost:18080"
        requested_url = shop_url + "/ja/identity"
        target_url = (
            shop_url
            + "/ja/authentication?back=my-account&token=private-token-sentinel"
        )
        redirect = {
            "url": requested_url,
            "status": 302,
            "headers": {"Location": target_url},
            "fromServiceWorker": False,
            "fromDiskCache": False,
        }
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "main-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "request": {"url": requested_url, "method": "GET"},
                },
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "main-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "response": redirect,
                },
            },
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "main-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "redirectResponse": redirect,
                    "request": {"url": target_url, "method": "GET"},
                },
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "main-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "response": {
                        "url": target_url,
                        "status": 404,
                        "headers": {"Cache-Control": "no-store"},
                        "fromServiceWorker": True,
                        "fromDiskCache": False,
                    },
                },
            },
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "iframe-request",
                    "loaderId": "iframe-loader",
                    "frameId": "child-frame",
                    "type": "Document",
                    "request": {
                        "url": shop_url + "/ja/private-iframe",
                        "method": "GET",
                    },
                },
            },
        ]

        trace = trace_builder(
            events,
            requested_url,
            shop_url,
            "main-frame",
            sensitive_values=("private-token-sentinel",),
        )

        self.assertEqual("/ja/identity", trace["initial_target"]["path"])
        self.assertEqual(1, len(trace["redirects"]))
        self.assertEqual(302, trace["redirects"][0]["status"])
        self.assertEqual(
            "/ja/authentication",
            trace["redirects"][0]["target"]["path"],
        )
        self.assertEqual("authentication", trace["redirects"][0]["target"]["controller"])
        self.assertEqual(["back", "token"], trace["redirects"][0]["target"]["query_keys"])
        self.assertFalse(trace["redirects"][0]["from_service_worker"])
        self.assertEqual(404, trace["final"]["status"])
        self.assertTrue(trace["final"]["from_service_worker"])
        self.assertFalse(trace["final"]["from_disk_cache"])
        self.assertNotIn("private-token-sentinel", repr(trace))
        self.assertNotIn("private-request-id", repr(trace))

    def test_document_navigation_trace_redacts_off_origin_targets_and_keeps_unknown_provenance_unknown(self) -> None:
        trace_builder = getattr(pwa_browser, "safe_document_navigation_trace", None)
        self.assertTrue(callable(trace_builder), "safe main-frame navigation trace is missing")

        shop_url = "http://localhost:18080"
        requested_url = shop_url + "/ja/identity"
        external_url = "https://external.invalid/private?token=private-token-sentinel"
        redirect = {"url": requested_url, "status": 302, "headers": {"Location": external_url}}
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "request-one",
                    "frameId": "main-frame",
                    "type": "Document",
                    "request": {"url": requested_url, "method": "GET"},
                },
            },
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "request-one",
                    "frameId": "main-frame",
                    "type": "Document",
                    "redirectResponse": redirect,
                    "request": {"url": external_url, "method": "GET"},
                },
            },
        ]

        trace = trace_builder(events, requested_url, shop_url, "main-frame")

        self.assertEqual("<off-origin>", trace["redirects"][0]["target"]["path"])
        self.assertIsNone(trace["final"]["from_service_worker"])
        self.assertIsNone(trace["final"]["from_disk_cache"])
        self.assertNotIn("external.invalid", repr(trace))
        self.assertNotIn("private-token-sentinel", repr(trace))

    def test_document_navigation_trace_rejects_loader_mismatch_and_does_not_keep_provisional_redirect_as_final(self) -> None:
        trace_builder = getattr(pwa_browser, "safe_document_navigation_trace", None)
        self.assertTrue(callable(trace_builder))
        shop_url = "http://localhost:18080"
        requested_url = shop_url + "/ja/identity"
        redirected_url = shop_url + "/ja/authentication?back=my-account"
        redirect = {
            "url": requested_url,
            "status": 302,
            "headers": {"Location": redirected_url},
            "fromServiceWorker": True,
            "fromDiskCache": False,
        }
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "internal-id",
                    "loaderId": "expected-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "request": {"url": requested_url, "method": "GET"},
                },
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "internal-id",
                    "loaderId": "expected-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "response": redirect,
                },
            },
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "internal-id",
                    "loaderId": "expected-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "redirectResponse": redirect,
                    "request": {"url": redirected_url, "method": "GET"},
                },
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "internal-id",
                    "loaderId": "wrong-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "response": {
                        "url": redirected_url,
                        "status": 404,
                        "fromServiceWorker": False,
                        "fromDiskCache": False,
                    },
                },
            },
        ]

        trace = trace_builder(events, requested_url, shop_url, "main-frame")

        self.assertEqual(1, len(trace["redirects"]))
        self.assertIsNone(trace["final"]["status"])
        self.assertIsNone(trace["final"]["from_service_worker"])
        self.assertIsNone(trace["final"]["from_disk_cache"])
        self.assertNotIn("internal-id", repr(trace))

    def test_document_navigation_trace_accepts_optional_response_frame_and_records_cache_events(self) -> None:
        shop_url = "http://localhost:18080"
        requested_url = shop_url + "/ja/identity"
        destination = shop_url + "/ja/authentication?back=my-account"
        redirect = {
            "url": requested_url,
            "status": 302.0,
            "headers": {"Location": destination},
            "fromServiceWorker": True,
            "fromDiskCache": False,
        }
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "",
                    "frameId": "main-frame",
                    "type": "Document",
                    "request": {"url": requested_url, "method": "GET"},
                },
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "",
                    "frameId": "main-frame",
                    "type": "Document",
                    "response": redirect,
                },
            },
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "",
                    "frameId": "main-frame",
                    "type": "Document",
                    "redirectResponse": redirect,
                    "request": {"url": destination, "method": "GET"},
                },
            },
            {
                "method": "Network.requestServedFromCache",
                "params": {"requestId": "private-request-id"},
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "",
                    "type": "Document",
                    "response": {
                        "url": destination,
                        "status": 200.0,
                        "fromServiceWorker": True,
                        "fromDiskCache": False,
                        "serviceWorkerResponseSource": "network",
                    },
                },
            },
        ]

        trace = pwa_browser.safe_document_navigation_trace(
            events, requested_url, shop_url, "main-frame"
        )

        self.assertEqual(302, trace["redirects"][0]["status"])
        self.assertTrue(trace["final"]["request_served_from_cache"])
        self.assertTrue(pwa_browser.navigation_trace_has_cache_hit(trace))
        trace["final"]["status"] = 404
        trace["final"]["request_served_from_cache"] = False
        with self.assertRaisesRegex(AssertionError, "HTTP 200"):
            pwa_browser.validate_logged_out_navigation_trace(trace, service_worker_expected=True)
        trace["final"]["status"] = 200
        trace["final"]["request_served_from_cache"] = True
        with self.assertRaisesRegex(AssertionError, "browser or service-worker cache"):
            pwa_browser.validate_logged_out_navigation_trace(trace, service_worker_expected=True)

    def test_safe_navigation_target_handles_malformed_and_japanese_routes_without_losing_slashes(self) -> None:
        shop_url = "http://localhost:18080"
        self.assertEqual(
            {"path": "<off-origin>", "query_keys": []},
            pwa_browser.safe_navigation_target(None, shop_url),
        )
        self.assertEqual(
            "/ja//ログイン/",
            pwa_browser.safe_navigation_target(
                shop_url + "/ja//%E3%83%AD%E3%82%B0%E3%82%A4%E3%83%B3/", shop_url
            )["path"],
        )
        safe = pwa_browser.safe_navigation_target(
            shop_url + "/ja/%E3%83%90%E3%83%AC%E3%81%9F?private-token-sentinel=value",
            shop_url,
        )
        self.assertEqual("/ja/<other>", safe["path"])
        self.assertEqual([], safe["query_keys"])
        self.assertNotIn("private-token-sentinel", repr(safe))

    def test_pwa_logout_keeps_normal_and_bypassed_account_assertions_and_restores_worker(self) -> None:
        browser_source = Path(pwa_browser.__file__).read_text(encoding="utf-8")
        start = browser_source.index("def verify_logout_protection(")
        end = browser_source.find("\ndef run_viewport(", start)
        logout = browser_source[start:end]

        self.assertIn('account_response.get("status") != 302', logout)
        self.assertIn("wait_for_logout_login_form(driver, shop_url)", logout)
        self.assertIn('"bypass": True', logout)
        self.assertIn('"bypass": False', logout)
        self.assertIn('"logged-out account without service worker"', logout)
        self.assertIn("assert_empty_cache_storage(driver, \"logged-out protected account route\")", logout)
        self.assertIn("verify_logged_out_private_routes(", logout)
        self.assertIn("exposes_test_identity(body_text, first_name, last_name, email)", logout)
        self.assertLess(
            logout.index("exposes_test_identity(pwa_body_text, first_name, last_name, email)"),
            logout.index('driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": True})'),
        )
        self.assertIn("validate_logged_out_navigation_trace(", logout)


if __name__ == "__main__":
    unittest.main()
