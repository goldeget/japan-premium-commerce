"""Safe diagnostic contracts for logged-out PWA browser failures."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tests.e2e import verify_pwa_browser as pwa_browser


class PwaLogoutDiagnosticsTests(unittest.TestCase):
    def test_logout_route_classifier_recognizes_japanese_and_korean_login_slugs(self) -> None:
        classifier = pwa_browser.customer_route_class

        self.assertEqual(
            "authentication",
            classifier("http://localhost:18080/ja/ログイン", "http://localhost:18080"),
        )
        self.assertEqual(
            "authentication",
            classifier("http://localhost:18080/ko/로그인", "http://localhost:18080"),
        )

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
                        "from_prefetch_cache": False,
                        "private_cache_policy": True,
                        "request_served_from_cache": False,
                        "service_worker_source": "network",
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
                    "from_prefetch_cache": False,
                    "private_cache_policy": True,
                    "request_served_from_cache": False,
                    "service_worker_source": "network",
                },
                "final_route_matches_login": False,
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
        self.assertIn("redirect1_service_worker=true", diagnostic)
        self.assertIn("redirect1_private_cache_policy=true", diagnostic)
        self.assertIn("final=404:/ja/authentication;service_worker=true;disk_cache=false", diagnostic)
        self.assertIn("final_route_matches_login=false", diagnostic)
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

    def test_document_navigation_trace_matches_redirect_location_and_redacts_referrer(self) -> None:
        requested_url = "http://localhost:18080/ko/my-account"
        target_url = "http://localhost:18080/ko/authentication?back=my-account&token=private-token-sentinel"
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "main-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "request": {
                        "url": requested_url + "?token=request-token-sentinel",
                        "method": "GET",
                        "headers": {
                            "Referer": requested_url + "?email=private-email-sentinel",
                        },
                    },
                },
            },
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "main-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "redirectResponse": {
                        "url": requested_url,
                        "status": 302,
                        "headers": {"Location": target_url},
                    },
                    "request": {"url": target_url, "method": "GET"},
                },
            },
        ]

        trace = pwa_browser.safe_document_navigation_trace(
            events,
            requested_url + "?token=request-token-sentinel",
            "http://localhost:18080",
            "main-frame",
            expected_final_url="http://localhost:18080/ko/authentication",
        )

        self.assertEqual("/ko/my-account", trace.get("navigation_referrer", {}).get("path"))
        self.assertTrue(trace.get("redirects", [{}])[0].get("location_matches_next_request"))
        self.assertEqual(
            "/ko/authentication",
            trace.get("redirects", [{}])[0].get("location_target", {}).get("path"),
        )
        self.assertTrue(trace.get("redirects", [{}])[0].get("location_matches_expected_login"))
        formatted = pwa_browser._format_navigation_trace(trace)
        self.assertIn(";navigation_referrer=/ko/my-account", formatted)
        self.assertIn("redirect1_location_match=true", formatted)
        self.assertIn("redirect1_login_match=true", formatted)
        for secret in ("private-token-sentinel", "request-token-sentinel", "private-email-sentinel", "private-request-id"):
            self.assertNotIn(secret, repr(trace))
            self.assertNotIn(secret, formatted)

        events[1]["params"]["request"]["url"] = "http://localhost:18080/ko/other?back=my-account"
        mismatched_trace = pwa_browser.safe_document_navigation_trace(
            events,
            requested_url + "?token=request-token-sentinel",
            "http://localhost:18080",
            "main-frame",
        )
        self.assertFalse(mismatched_trace["redirects"][0]["location_matches_next_request"])

    def test_redirect_location_is_checked_against_login_route_even_when_browser_follows_it(self) -> None:
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "request-one",
                    "loaderId": "loader-one",
                    "frameId": "main-frame",
                    "type": "Document",
                    "request": {
                        "url": "http://localhost:18080/ko/?mylogout",
                        "method": "GET",
                        "headers": {"Referer": "http://localhost:18080/ko/my-account"},
                    },
                },
            },
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "request-one",
                    "loaderId": "loader-one",
                    "frameId": "main-frame",
                    "type": "Document",
                    "redirectResponse": {
                        "url": "http://localhost:18080/ko/?mylogout",
                        "status": 302,
                        "headers": {"Location": "/ko/unexpected?token=secret"},
                    },
                    "request": {
                        "url": "http://localhost:18080/ko/unexpected?token=secret",
                        "method": "GET",
                    },
                },
            },
        ]
        trace = pwa_browser.safe_document_navigation_trace(
            events,
            "http://localhost:18080/ko/?mylogout",
            "http://localhost:18080",
            "main-frame",
            expected_final_url="http://localhost:18080/ko/authentication",
        )

        redirect = trace.get("redirects", [{}])[0]
        self.assertTrue(redirect.get("location_matches_next_request"))
        self.assertFalse(redirect.get("location_matches_expected_login"))
        self.assertNotIn("secret", repr(trace))
        self.assertNotIn("unexpected", pwa_browser._format_navigation_trace(trace))

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

    def test_generated_login_match_is_bound_to_the_captured_final_response_url(self) -> None:
        shop_url = "http://localhost:18080"
        requested_url = shop_url + "/ko/my-account"
        expected_login_url = (
            shop_url + "/index.php?controller=authentication&token=expected-secret"
        )
        actual_wrong_url = (
            shop_url + "/index.php?controller=category&token=actual-secret"
        )
        actual_login_url = (
            shop_url + "/index.php?back=my-account&controller=authentication&token=actual-secret"
        )
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "private-loader-id",
                    "frameId": "main-frame",
                    "type": "Document",
                    "request": {"url": requested_url, "method": "GET"},
                },
            },
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "private-loader-id",
                    "frameId": "main-frame",
                    "type": "Document",
                    "redirectResponse": {
                        "url": requested_url,
                        "status": 302,
                        "headers": {"Cache-Control": "private, no-store"},
                        "fromServiceWorker": False,
                        "fromDiskCache": False,
                        "fromPrefetchCache": False,
                    },
                    "request": {"url": actual_wrong_url, "method": "GET"},
                },
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "private-request-id",
                    "loaderId": "private-loader-id",
                    "frameId": "main-frame",
                    "type": "Document",
                    "response": {
                        "url": actual_wrong_url,
                        "status": 200,
                        "headers": {"Cache-Control": "private, no-store"},
                        "fromServiceWorker": False,
                        "fromDiskCache": False,
                    },
                },
            },
        ]

        trace = pwa_browser.safe_document_navigation_trace(
            events,
            requested_url,
            shop_url,
            "main-frame",
            expected_final_url=expected_login_url,
        )

        self.assertFalse(trace["final_route_matches_login"])
        self.assertNotIn("expected-secret", repr(trace))
        self.assertNotIn("actual-secret", repr(trace))
        self.assertNotIn("private-request-id", repr(trace))
        with self.assertRaisesRegex(AssertionError, "authentication route"):
            pwa_browser.validate_logged_out_navigation_trace(
                trace,
                service_worker_expected=False,
            )

        events[1]["params"]["request"]["url"] = actual_login_url
        events[2]["params"]["response"]["url"] = actual_login_url
        matching_trace = pwa_browser.safe_document_navigation_trace(
            events,
            requested_url,
            shop_url,
            "main-frame",
            expected_final_url=expected_login_url,
        )
        self.assertTrue(matching_trace["final_route_matches_login"])
        pwa_browser.validate_logged_out_navigation_trace(
            matching_trace,
            service_worker_expected=False,
        )

    def test_logout_trace_requires_a_successful_login_destination_after_redirect(self) -> None:
        validator = getattr(pwa_browser, "validate_logout_navigation_trace", None)
        self.assertTrue(callable(validator))
        trace = {
            "observed": True,
            "redirects_truncated": False,
            "redirects": [{
                "status": 302,
                "location_matches_next_request": True,
                "location_matches_expected_login": True,
                "private_cache_policy": True,
                "from_service_worker": False,
            }],
            "final": {
                "status": 200,
                "private_cache_policy": True,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": "network",
                "from_service_worker": False,
            },
            "final_route_matches_login": True,
        }

        validator(trace)
        trace["redirects"][0]["location_matches_next_request"] = False
        with self.assertRaisesRegex(AssertionError, "Location did not match"):
            validator(trace)
        trace["redirects"][0]["location_matches_next_request"] = True
        trace["redirects"][0]["location_matches_expected_login"] = False
        with self.assertRaisesRegex(AssertionError, "generated sign-in route"):
            validator(trace)
        trace["redirects"][0]["location_matches_expected_login"] = True
        trace["final"]["status"] = 404
        with self.assertRaisesRegex(AssertionError, "HTTP 200"):
            validator(trace)
        trace["final"]["status"] = 200
        trace["final_route_matches_login"] = False
        with self.assertRaisesRegex(AssertionError, "authentication route"):
            validator(trace)

    def test_logout_trace_rejects_a_service_worker_intercepted_redirect(self) -> None:
        trace = {
            "observed": True,
            "redirects_truncated": False,
            "redirects": [{
                "status": 302,
                "location_matches_next_request": True,
                "location_matches_expected_login": True,
                "from_service_worker": True,
            }],
            "final": {
                "status": 200,
                "private_cache_policy": True,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": "network",
                "from_service_worker": False,
            },
            "final_route_matches_login": True,
        }

        with self.assertRaisesRegex(AssertionError, "service worker"):
            pwa_browser.validate_logout_navigation_trace(trace)

    def test_logout_trace_accepts_network_fetched_service_worker_redirects_after_native_logout(self) -> None:
        trace = {
            "observed": True,
            "redirects_truncated": False,
            "redirects": [
                {
                    "status": 302,
                    "location_matches_next_request": True,
                    "location_matches_expected_login": False,
                    "private_cache_policy": True,
                    "from_service_worker": False,
                },
                {
                    "status": 302,
                    "location_matches_next_request": True,
                    "location_matches_expected_login": True,
                    "private_cache_policy": True,
                    "from_service_worker": True,
                    "service_worker_source": "network",
                },
            ],
            "final": {
                "status": 200,
                "private_cache_policy": True,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": "network",
                "from_service_worker": True,
            },
            "final_route_matches_login": True,
        }

        pwa_browser.validate_logout_navigation_trace(trace)
        trace["final"]["service_worker_source"] = "cache-storage"
        with self.assertRaisesRegex(AssertionError, "browser or service-worker cache"):
            pwa_browser.validate_logout_navigation_trace(trace)

    def test_logout_trace_rejects_a_cacheable_redirect_response(self) -> None:
        trace = {
            "observed": True,
            "redirects_truncated": False,
            "redirects": [{
                "status": 302,
                "location_matches_next_request": True,
                "location_matches_expected_login": True,
                "private_cache_policy": False,
                "from_service_worker": False,
            }],
            "final": {
                "status": 200,
                "private_cache_policy": True,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": "network",
                "from_service_worker": False,
            },
            "final_route_matches_login": True,
        }

        with self.assertRaisesRegex(AssertionError, "no-store cache policy"):
            pwa_browser.validate_logout_navigation_trace(trace)

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

        trace = trace_builder(
            events,
            requested_url,
            shop_url,
            "main-frame",
            expected_final_url=shop_url + "/ja/authentication?token=expected-secret",
        )

        self.assertEqual(1, len(trace["redirects"]))
        self.assertIsNone(trace["final"]["status"])
        self.assertIsNone(trace["final_route_matches_login"])
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
            "headers": {
                "Location": destination,
                "Cache-Control": "private, no-store",
            },
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
                        "headers": {"Cache-Control": "private, no-store"},
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

        trace["final"]["request_served_from_cache"] = False
        trace["final"]["target"]["path"] = "/ja/category"
        trace["final"]["target"].pop("controller", None)
        with self.assertRaisesRegex(AssertionError, "authentication route"):
            pwa_browser.validate_logged_out_navigation_trace(trace, service_worker_expected=True)
        trace["final"]["target"]["path"] = "/ja/authentication"
        trace["final"]["private_cache_policy"] = False
        with self.assertRaisesRegex(AssertionError, "no-store"):
            pwa_browser.validate_logged_out_navigation_trace(trace, service_worker_expected=True)

    def test_document_navigation_trace_rejects_redirect_chains_beyond_the_observed_limit(self) -> None:
        shop_url = "http://localhost:18080"
        requested_url = shop_url + "/ja/identity"
        current_url = requested_url
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "long-chain",
                    "loaderId": "long-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "request": {"url": requested_url, "method": "GET"},
                },
            }
        ]
        for index in range(9):
            next_url = shop_url + f"/ja/authentication?step={index + 1}"
            events.append(
                {
                    "method": "Network.requestWillBeSent",
                    "params": {
                        "requestId": "long-chain",
                        "loaderId": "long-loader",
                        "frameId": "main-frame",
                        "type": "Document",
                        "redirectResponse": {
                            "url": current_url,
                            "status": 302,
                            "headers": {"Cache-Control": "private, no-store"},
                            "fromServiceWorker": True,
                            "fromDiskCache": index == 8,
                        },
                        "request": {"url": next_url, "method": "GET"},
                    },
                }
            )
            current_url = next_url
        events.append(
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "long-chain",
                    "loaderId": "long-loader",
                    "frameId": "main-frame",
                    "type": "Document",
                    "response": {
                        "url": current_url,
                        "status": 200,
                        "headers": {"Cache-Control": "private, no-store"},
                        "fromServiceWorker": True,
                        "fromDiskCache": False,
                        "serviceWorkerResponseSource": "network",
                    },
                },
            }
        )

        trace = pwa_browser.safe_document_navigation_trace(
            events, requested_url, shop_url, "main-frame"
        )

        with self.assertRaisesRegex(AssertionError, "redirect chain is incomplete"):
            pwa_browser.validate_logged_out_navigation_trace(
                trace, service_worker_expected=True
            )

    def test_logout_snapshot_failure_preserves_an_existing_primary_failure(self) -> None:
        helper = getattr(pwa_browser, "capture_logout_snapshot_preserving_error", lambda *_args, **_kwargs: ({}, None))

        primary_error = pwa_browser.TimeoutException("login form timeout")
        with patch.object(
            pwa_browser,
            "safe_logout_wait_diagnostics",
            side_effect=RuntimeError("diagnostic snapshot unavailable"),
        ):
            snapshot, reported_error = helper(
                object(),
                "http://localhost:18080",
                prior_error=primary_error,
            )

        self.assertEqual({}, snapshot)
        self.assertIs(primary_error, reported_error)

    def test_original_network_failure_stage_survives_service_worker_restore_checks(self) -> None:
        helper = getattr(pwa_browser, "prefer_primary_failure_substage", lambda *_args: "")
        primary_error = AssertionError("network comparison failed")

        self.assertEqual(
            "request_network_account_login_form",
            helper(
                primary_error,
                "request_network_account_login_form",
                "request_restored_account_final_response",
            ),
        )

    def test_bypass_failure_keeps_the_original_error_and_attempts_to_restore_the_worker(self) -> None:
        class FakeElement:
            def __init__(self, owner: "FakeDriver") -> None:
                self.owner = owner

            def is_displayed(self) -> bool:
                return True

            def is_enabled(self) -> bool:
                return True

            def get_attribute(self, name: str) -> str:
                return {
                    "id": "signout_link",
                    "href": "/ja/index.php?mylogout",
                }.get(name, "")

            def click(self) -> None:
                self.owner.signed_out = True

        class FakeBody:
            text = "Sign in"

        class FakeDriver:
            current_url = "http://localhost:18080/ja/identity"

            def __init__(self) -> None:
                self.signed_out = False
                self.bypass_calls: list[bool] = []
                self.events: list[str] = []
                self.signout = FakeElement(self)

            def find_elements(self, by: str, selector: str) -> list[FakeElement]:
                if selector == "a.account-menu__link--signout" and not self.signed_out:
                    return [self.signout]
                if selector == "#login-form input[name='email']" and self.signed_out:
                    return [self.signout]
                return []

            def find_element(self, by: str, selector: str) -> FakeBody:
                return FakeBody()

            def execute_script(self, _script: str) -> str:
                return "complete"

            def get_log(self, _name: str) -> list[dict[str, object]]:
                return []

            def execute_cdp_cmd(self, method: str, parameters: dict[str, object]) -> dict[str, object]:
                if method == "Network.setBypassServiceWorker":
                    bypass = parameters.get("bypass") is True
                    self.bypass_calls.append(bypass)
                    self.events.append("bypass-on" if bypass else "bypass-off")
                    if bypass:
                        raise RuntimeError("network comparison failed")
                return {}

            def save_screenshot(self, _path: str) -> bool:
                return True

        class ImmediateWait:
            def __init__(self, driver: FakeDriver, *_args: object, **_kwargs: object) -> None:
                self.driver = driver

            def until(self, predicate, message: str | None = None):
                result = predicate(self.driver)
                if not result:
                    raise pwa_browser.TimeoutException(message or "condition did not match")
                return result

        class FakeBy:
            CSS_SELECTOR = "css selector"
            TAG_NAME = "tag name"
            ID = "id"

        driver = FakeDriver()
        navigation_count = 0

        def navigate(*_args: object, **_kwargs: object) -> dict[str, object]:
            nonlocal navigation_count
            navigation_count += 1
            driver.events.append(f"navigation-{navigation_count}")
            return {"status": 302, "navigation_trace": valid_trace}

        def wait_for_worker(_driver: object) -> dict[str, str]:
            driver.events.append("worker-ready")
            return {"activeState": "activated"}

        valid_trace = {
            "observed": True,
            "redirects_truncated": False,
            "method": "GET",
            "initial_target": {"path": "/ja/identity", "query_keys": []},
            "redirects": [
                {
                    "status": 302,
                    "target": {"path": "/ja/authentication", "controller": "authentication"},
                    "location_matches_next_request": True,
                    "location_matches_expected_login": True,
                    "private_cache_policy": True,
                    "from_service_worker": True,
                    "from_disk_cache": False,
                    "from_prefetch_cache": False,
                    "request_served_from_cache": False,
                    "service_worker_source": "network",
                }
            ],
            "final": {
                "status": 200,
                "target": {"path": "/ja/authentication", "controller": "authentication"},
                "private_cache_policy": True,
                "from_service_worker": True,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": "network",
            },
        }
        network_logout_trace = {
            "observed": True,
            "redirects_truncated": False,
            "redirects": [
                {
                    "status": 302,
                    "target": {"path": "/ja/authentication", "controller": "authentication"},
                    "location_matches_next_request": True,
                    "location_matches_expected_login": True,
                    "private_cache_policy": True,
                    "from_service_worker": False,
                    "from_disk_cache": False,
                    "from_prefetch_cache": False,
                    "request_served_from_cache": False,
                    "service_worker_source": "network",
                }
            ],
            "final": {
                "status": 200,
                "target": {"path": "/ja/authentication", "controller": "authentication"},
                "private_cache_policy": True,
                "from_service_worker": False,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": "network",
            },
            "final_route_matches_login": True,
        }

        def navigation_trace(_events: object, requested_url: str, *_args: object, **_kwargs: object):
            return network_logout_trace if "mylogout" in requested_url else valid_trace

        with (
            patch.object(pwa_browser, "WebDriverWait", ImmediateWait),
            patch.object(pwa_browser, "By", FakeBy),
            patch.object(pwa_browser, "current_main_frame_id", return_value="main-frame"),
            patch.object(pwa_browser, "safe_document_navigation_trace", side_effect=navigation_trace),
            patch.object(pwa_browser, "navigate_private_document", side_effect=navigate),
            patch.object(pwa_browser, "wait_for_logout_login_form"),
            patch.object(pwa_browser, "wait_for_service_worker", side_effect=wait_for_worker),
            patch.object(pwa_browser, "assert_empty_cache_storage"),
            patch.object(pwa_browser, "safe_logout_wait_diagnostics", return_value={}),
        ):
            with self.assertRaisesRegex(RuntimeError, "network comparison failed"):
                pwa_browser.verify_logout_protection(
                    driver,
                    "http://localhost:18080/ja/identity",
                    "http://localhost:18080",
                    "Pwa",
                    "Session",
                    "qa@example.invalid",
                    Path("/tmp/pwa-logged-out.png"),
                    set_substage=lambda _stage: None,
                )

        self.assertEqual([True, False], driver.bypass_calls)
        self.assertLess(driver.events.index("bypass-off"), driver.events.index("navigation-2"))
        self.assertLess(driver.events.index("navigation-2"), driver.events.index("worker-ready"))

    def test_pwa_browser_matrix_includes_each_locale_at_each_viewport(self) -> None:
        matrix = getattr(pwa_browser, "pwa_browser_cases", lambda: ())()

        self.assertEqual(
            (
                ("desktop", "ja", 1440, 960, "desktop-ja"),
                ("desktop", "en", 1440, 960, "desktop-en"),
                ("desktop", "ko", 1440, 960, "desktop-ko"),
                ("mobile", "ja", 390, 844, "mobile-ja"),
                ("mobile", "en", 390, 844, "mobile-en"),
                ("mobile", "ko", 390, 844, "mobile-ko"),
            ),
            matrix,
        )

    def test_generated_language_destination_is_used_and_restricted_to_shop_origin(self) -> None:
        resolver = getattr(pwa_browser, "resolve_storefront_locale_url", lambda *_args: "")
        shop_url = "http://localhost:18080"

        self.assertEqual(
            "http://localhost:18080/generated/language?locale=ko",
            resolver(
                [
                    {"iso_code": "ja", "value": "http://localhost:18080/generated/language?locale=ja"},
                    {"iso_code": "ko", "value": "http://localhost:18080/generated/language?locale=ko"},
                ],
                "ko",
                shop_url,
            ),
        )
        with self.assertRaisesRegex(AssertionError, "language selector changed the isolated shop origin"):
            resolver([{"iso_code": "ko", "value": "https://external.invalid/ko"}], "ko", shop_url)

    def test_generated_signin_route_matches_unknown_localized_slugs_without_exposing_urls(self) -> None:
        matcher = getattr(pwa_browser, "same_storefront_route", lambda *_args: False)
        shop_url = "http://localhost:18080"

        self.assertTrue(
            matcher(
                "http://localhost:18080/ko/로그인?back=identity",
                "http://localhost:18080/ko/로그인",
                shop_url,
            )
        )
        self.assertFalse(
            matcher(
                "http://localhost:18080/ko/my-account",
                "http://localhost:18080/ko/로그인",
                shop_url,
            )
        )
        self.assertFalse(
            matcher(
                "http://localhost:18080/index.php?controller=category",
                "http://localhost:18080/index.php?controller=authentication",
                shop_url,
            )
        )
        self.assertTrue(
            matcher(
                "http://localhost:18080/index.php?controller=authentication&back=my-account&token=actual-token",
                "http://localhost:18080/index.php?controller=authentication&token=expected-token",
                shop_url,
            )
        )
        self.assertTrue(
            matcher(
                "http://localhost:18080/ko/%EB%A1%9C%EA%B7%B8%EC%9D%B8?lang=KO&isolang=KO&controller=authentication&back=identity",
                "http://localhost:18080/ko/로그인?controller=authentication&isolang=ko&lang=ko",
                shop_url,
            )
        )
        for candidate_url, expected_url in (
            (
                "http://localhost:18080/index.php?controller=authentication&id_lang=2",
                "http://localhost:18080/index.php?controller=authentication&id_lang=1",
            ),
            (
                "http://localhost:18080/index.php?controller=authentication&isolang=en",
                "http://localhost:18080/index.php?controller=authentication&isolang=ja",
            ),
            (
                "http://localhost:18080/index.php?controller=authentication&lang=en",
                "http://localhost:18080/index.php?controller=authentication&lang=ja",
            ),
            (
                "http://localhost:18080/index.php?controller=authentication&lang=",
                "http://localhost:18080/index.php?controller=authentication",
            ),
        ):
            with self.subTest(candidate_url=candidate_url):
                self.assertFalse(matcher(candidate_url, expected_url, shop_url))
        trace = {
            "observed": True,
            "redirects": [
                {
                    "status": 302,
                    "private_cache_policy": True,
                    "from_service_worker": True,
                    "from_disk_cache": False,
                    "from_prefetch_cache": False,
                    "request_served_from_cache": False,
                    "service_worker_source": "network",
                }
            ],
            "final": {
                "status": 200,
                "target": {"path": "/ko/<other>"},
                "private_cache_policy": True,
                "from_service_worker": True,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": "network",
            },
            "final_route_matches_login": True,
        }
        pwa_browser.validate_logged_out_navigation_trace(
            trace,
            service_worker_expected=True,
        )
        trace["final_route_matches_login"] = False
        with self.assertRaisesRegex(AssertionError, "authentication route"):
            pwa_browser.validate_logged_out_navigation_trace(
                trace,
                service_worker_expected=True,
            )

    def test_safe_navigation_target_classifies_private_back_urls_without_exposing_them(self) -> None:
        shop_url = "http://localhost:18080"
        friendly = pwa_browser.safe_navigation_target(
            "http://localhost:18080/ko/?back=%2Fko%2Fmy-account",
            shop_url,
        )
        controller = pwa_browser.safe_navigation_target(
            "http://localhost:18080/ko/?back=%2Findex.php%3Fcontroller%3Dorder-detail",
            shop_url,
        )
        external = pwa_browser.safe_navigation_target(
            "http://localhost:18080/ko/?back=https%3A%2F%2Fother.example%2Fko%2Fmy-account",
            shop_url,
        )
        public = pwa_browser.safe_navigation_target(
            "http://localhost:18080/ko/?back=%2Fko%2Fsearch",
            shop_url,
        )

        self.assertIs(friendly.get("back_is_private_route"), True)
        self.assertIs(controller.get("back_is_private_route"), True)
        self.assertIs(external.get("back_is_private_route"), False)
        self.assertIs(public.get("back_is_private_route"), False)
        for metadata in (friendly, controller, external, public):
            self.assertNotIn("my-account", repr(metadata))
            self.assertNotIn("order-detail", repr(metadata))
            self.assertNotIn("other.example", repr(metadata))

    def test_safe_navigation_target_marks_private_customer_route_without_exposing_it(self) -> None:
        shop_url = "http://localhost:18080"
        private = pwa_browser.safe_navigation_target(
            shop_url + "/ko/identity?customer=private-customer-id",
            shop_url,
        )
        public = pwa_browser.safe_navigation_target(shop_url + "/ko/category", shop_url)
        near_match = pwa_browser.safe_navigation_target(shop_url + "/ko/identity-help", shop_url)
        encoded_separator = pwa_browser.safe_navigation_target(
            shop_url + "/ko%2Fidentity", shop_url
        )
        external = pwa_browser.safe_navigation_target(
            "https://other.example/ko/identity?customer=private-customer-id",
            shop_url,
        )

        self.assertIs(private.get("private_customer_route"), True)
        self.assertIs(public.get("private_customer_route"), False)
        self.assertIs(near_match.get("private_customer_route"), False)
        self.assertIs(encoded_separator.get("private_customer_route"), False)
        self.assertNotIn("private-customer-id", repr(private))
        self.assertIs(external.get("private_customer_route"), False)

    def test_document_trace_marks_private_initial_route_without_exposing_urls(self) -> None:
        shop_url = "http://localhost:18080"
        requested_url = shop_url + "/ko/identity?customer=private-customer-id"
        events = [{
            "method": "Network.requestWillBeSent",
            "params": {
                "requestId": "private-request-id",
                "loaderId": "private-loader-id",
                "frameId": "main-frame",
                "type": "Document",
                "request": {"url": requested_url, "method": "GET"},
            },
        }]

        trace = pwa_browser.safe_document_navigation_trace(
            events, requested_url, shop_url, "main-frame"
        )

        self.assertIs(trace["initial_target"].get("private_customer_route"), True)
        self.assertNotIn("private-customer-id", repr(trace))
        self.assertNotIn("http://localhost:18080", repr(trace))
        self.assertNotIn("private-request-id", repr(trace))
        self.assertIn("private_customer_route=true", pwa_browser._format_navigation_trace(trace))

    def test_logged_out_pwa_navigation_accepts_native_hops_for_private_initial_route(self) -> None:
        trace = {
            "observed": True,
            "initial_target": {"path": "/<other>", "private_customer_route": True},
            "redirects_truncated": False,
            "redirects": [{
                "status": 302,
                "target": {"path": "/ko/ログイン", "query_keys": ["back"]},
                "private_cache_policy": True,
                "from_service_worker": False,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": None,
            }],
            "final": {
                "status": 200,
                "target": {"path": "/ko/ログイン"},
                "private_cache_policy": True,
                "from_service_worker": True,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": "network",
            },
            "final_route_matches_login": True,
        }

        pwa_browser.validate_logged_out_navigation_trace(trace, service_worker_expected=True)

        trace["initial_target"]["private_customer_route"] = False
        with self.assertRaisesRegex(AssertionError, "native redirect hop"):
            pwa_browser.validate_logged_out_navigation_trace(trace, service_worker_expected=True)

    def test_logged_out_pwa_navigation_allows_native_network_hop_after_private_redirect(self) -> None:
        trace = {
            "observed": True,
            "redirects_truncated": False,
            "redirects": [{
                "status": 302,
                "target": {
                    "path": "/ko/<other>",
                    "query_keys": ["back"],
                    "back_is_private_route": True,
                },
                "private_cache_policy": True,
                "from_service_worker": True,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": "network",
            }],
            "final": {
                "status": 200,
                "target": {"path": "/ko/로그인"},
                "private_cache_policy": True,
                "from_service_worker": False,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": None,
            },
            "final_route_matches_login": True,
        }

        pwa_browser.validate_logged_out_navigation_trace(trace, service_worker_expected=True)

        trace["redirects"][0]["target"]["back_is_private_route"] = False
        with self.assertRaisesRegex(AssertionError, "native redirect hop"):
            pwa_browser.validate_logged_out_navigation_trace(trace, service_worker_expected=True)

    def test_private_initial_route_does_not_allow_native_auth_response_without_private_back(self) -> None:
        trace = {
            "observed": True,
            "initial_target": {"path": "/<other>", "private_customer_route": True},
            "redirects_truncated": False,
            "redirects": [{
                "status": 302,
                "target": {"path": "/ko/authentication", "query_keys": []},
                "private_cache_policy": True,
                "from_service_worker": False,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": None,
            }],
            "final": {
                "status": 200,
                "target": {"path": "/ko/authentication"},
                "private_cache_policy": True,
                "from_service_worker": False,
                "from_disk_cache": False,
                "from_prefetch_cache": False,
                "request_served_from_cache": False,
                "service_worker_source": None,
            },
            "final_route_matches_login": True,
        }

        with self.assertRaisesRegex(AssertionError, "native redirect hop"):
            pwa_browser.validate_logged_out_navigation_trace(trace, service_worker_expected=True)

    def test_offline_fallback_must_match_the_requested_locale_and_language(self) -> None:
        helper = getattr(pwa_browser, "assert_offline_fallback_content", lambda *_args: None)

        class FakeBy:
            TAG_NAME = "tag name"

        class FakeElement:
            def __init__(self, *, language: str = "", text: str = "") -> None:
                self.language = language
                self.text = text

            def get_attribute(self, name: str) -> str:
                return self.language if name == "lang" else ""

        class FakeDriver:
            def __init__(self, language: str, body: str) -> None:
                self.html = FakeElement(language=language)
                self.body = FakeElement(text=body)

            def find_element(self, _by: str, name: str) -> FakeElement:
                return self.html if name == "html" else self.body

        with patch.object(pwa_browser, "By", FakeBy):
            with self.assertRaisesRegex(AssertionError, "expected storefront locale"):
                helper(
                    FakeDriver("ja", "インターネットに接続できません"),
                    "ko",
                )
            with self.assertRaisesRegex(AssertionError, "expected Korean offline fallback"):
                helper(FakeDriver("ko", "インターネットに接続できません"), "ko")
            helper(FakeDriver("ko", "연결을 확인해 주세요"), "ko")

    def test_browser_locale_profile_sets_a_deterministic_accept_language(self) -> None:
        profile = getattr(pwa_browser, "browser_locale_profile", lambda _locale: {})

        self.assertEqual(
            {"browser_tag": "ja-JP", "accept_language": "ja-JP,ja;q=0.9"},
            profile("ja"),
        )
        self.assertEqual(
            {"browser_tag": "en-US", "accept_language": "en-US,en;q=0.9"},
            profile("en"),
        )
        self.assertEqual(
            {"browser_tag": "ko-KR", "accept_language": "ko-KR,ko;q=0.9"},
            profile("ko"),
        )

    def test_safe_navigation_target_handles_malformed_and_japanese_routes_without_losing_slashes(self) -> None:
        shop_url = "http://localhost:18080"
        self.assertEqual(
            {"path": "<off-origin>", "query_keys": [], "private_customer_route": False},
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
