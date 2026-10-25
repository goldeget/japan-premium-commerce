"""Safe, bounded contracts for PWA service-worker registration diagnostics."""
from __future__ import annotations

import inspect
from contextlib import redirect_stderr
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from tests.e2e import verify_pwa_browser as pwa_browser


class PwaRegistrationDiagnosticsTests(unittest.TestCase):
    def test_viewport_requires_initial_controller_before_locale_navigation(self) -> None:
        for controller_ready in (True, False):
            with self.subTest(controller_ready=controller_ready):
                driver = MagicMock()
                driver.current_url = "http://localhost:18080/"
                driver.execute_async_script.return_value = {
                    "phase": "complete" if controller_ready else "controller_wait",
                    "category": "none" if controller_ready else "controller_timeout",
                    "controller_present": controller_ready,
                }
                driver.get_log.return_value = []
                driver._pwa_registration_observer_installed = True
                wait = MagicMock()
                wait.until.return_value = True

                def navigate_locale(*_args: object) -> str:
                    self.assertTrue(
                        driver.execute_async_script.called,
                        "locale navigation raced the initial worker installation",
                    )
                    self.assertTrue(controller_ready)
                    raise RuntimeError("locale navigation reached after bootstrap")

                with (
                    patch.object(pwa_browser, "Options", return_value=MagicMock()),
                    patch.object(pwa_browser, "webdriver", SimpleNamespace(Chrome=lambda **_kwargs: driver)),
                    patch.object(pwa_browser, "WebDriverWait", return_value=wait),
                    patch.object(pwa_browser, "install_service_worker_registration_observer"),
                    patch.object(pwa_browser, "select_storefront_locale", side_effect=navigate_locale) as select_locale,
                    redirect_stderr(io.StringIO()),
                ):
                    expected_error = RuntimeError if controller_ready else pwa_browser.PwaDiagnosticAssertionError
                    with self.assertRaises(expected_error):
                        pwa_browser.run_viewport(
                            "http://localhost:18080", Path("/tmp"),
                            390, 844, "mobile", "ja", "mobile-ja", 1,
                        )
                if controller_ready:
                    self.assertEqual(1, select_locale.call_count)
                else:
                    self.assertFalse(select_locale.called)

    def test_registration_metadata_is_allowlisted_and_redacts_urls_and_messages(self) -> None:
        private_url = (
            "http://localhost:18080/sw.js?token=registration-secret"
            "&email=customer-secret"
        )
        metadata = pwa_browser.safe_service_worker_registration_metadata(
            {
                "phase": "controller_wait",
                "category": "controller_timeout",
                "error_name": "TimeoutError",
                "registration_error_name": "SecurityError",
                "service_worker_supported": True,
                "observer_installed": True,
                "registration_attempted": True,
                "registration_outcome": "resolved",
                "ready_resolved": True,
                "registration_found": True,
                "active_state": "activated",
                "controller_present": False,
                "controller_change_observed": False,
                "route_matches_expected": True,
                "scope_matches_expected": True,
                "script_origin_matches_expected": True,
                "script_path_matches_expected": True,
                "worker_response_status": 200,
                "worker_response_mime": "application/javascript",
                "worker_from_service_worker": False,
                "worker_from_disk_cache": True,
                "worker_from_prefetch_cache": False,
                "worker_source": "network",
                "error_message": private_url,
                "scope": private_url,
                "script_url": private_url,
            }
        )
        diagnostic = pwa_browser.format_service_worker_registration_diagnostic(metadata)

        self.assertEqual(
            {
                "phase": "controller_wait",
                "category": "controller_timeout",
                "error_name": "TimeoutError",
                "registration_error_name": "SecurityError",
                "service_worker_supported": True,
                "observer_installed": True,
                "registration_attempted": True,
                "registration_outcome": "resolved",
                "ready_resolved": True,
                "registration_found": True,
                "active_state": "activated",
                "controller_present": False,
                "controller_change_observed": False,
                "route_matches_expected": True,
                "scope_matches_expected": True,
                "script_origin_matches_expected": True,
                "script_path_matches_expected": True,
                "worker_response_status": 200,
                "worker_response_mime": "application/javascript",
                "worker_from_service_worker": False,
                "worker_from_disk_cache": True,
                "worker_from_prefetch_cache": False,
                "worker_source": "network",
            },
            metadata,
        )
        for private_value in (
            "registration-secret",
            "customer-secret",
            "localhost",
            "error_message",
        ):
            self.assertNotIn(private_value, diagnostic)
        self.assertIn("phase=controller_wait", diagnostic)
        self.assertIn("category=controller_timeout", diagnostic)
        self.assertIn("controller_change_observed=false", diagnostic)
        self.assertIn("worker_response_status=200", diagnostic)

    def test_registration_metadata_rejects_unlisted_values_and_bounds_status(self) -> None:
        diagnostic = pwa_browser.format_service_worker_registration_diagnostic(
            {
                "phase": "private-token-sentinel",
                "category": "https://localhost:18080/?token=private-token-sentinel",
                "error_name": "private-body-sentinel",
                "active_state": ["private-body-sentinel"],
                "registration_outcome": "private-token-sentinel",
                "worker_response_status": 9999,
                "worker_response_mime": "text/html;token=private-token-sentinel",
                "worker_source": "private-token-sentinel",
                "controller_present": "private-body-sentinel",
            }
        )

        self.assertEqual(
            "; phase=unknown; category=unknown; error_name=unknown"
            "; registration_error_name=unknown"
            "; service_worker_supported=unknown; observer_installed=unknown"
            "; registration_attempted=unknown; registration_outcome=unknown"
            "; ready_resolved=unknown; registration_found=unknown"
            "; active_state=unknown; controller_present=unknown"
            "; controller_change_observed=unknown; route_matches_expected=unknown"
            "; scope_matches_expected=unknown; script_origin_matches_expected=unknown"
            "; script_path_matches_expected=unknown; worker_response_status=unavailable"
            "; worker_response_mime=unknown; worker_from_service_worker=unknown"
            "; worker_from_disk_cache=unknown; worker_from_prefetch_cache=unknown"
            "; worker_source=unknown",
            diagnostic,
        )
        self.assertNotIn("private-token-sentinel", diagnostic)
        self.assertNotIn("private-body-sentinel", diagnostic)
        self.assertNotIn("localhost", diagnostic)

    def test_worker_response_diagnostics_capture_only_status_mime_and_cache_flags(self) -> None:
        private_url = (
            "http://localhost:18080/sw.js?token=registration-secret"
            "&email=customer-secret"
        )
        events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "private-request-id",
                    "type": "Script",
                    "request": {"url": private_url},
                },
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "private-request-id",
                    "type": "Script",
                    "response": {
                        "url": private_url,
                        "status": 200,
                        "mimeType": "application/javascript",
                        "fromServiceWorker": False,
                        "fromDiskCache": True,
                        "fromPrefetchCache": False,
                    },
                },
            },
        ]

        metadata = pwa_browser.service_worker_response_metadata(
            events,
            "http://localhost:18080",
            "/sw.js",
        )
        diagnostic = pwa_browser.format_service_worker_registration_diagnostic(metadata)

        self.assertEqual(200, metadata["worker_response_status"])
        self.assertEqual("application/javascript", metadata["worker_response_mime"])
        self.assertFalse(metadata["worker_from_service_worker"])
        self.assertTrue(metadata["worker_from_disk_cache"])
        self.assertFalse(metadata["worker_from_prefetch_cache"])
        self.assertEqual("http-cache", metadata["worker_source"])
        for private_value in (
            "registration-secret",
            "customer-secret",
            "private-request-id",
            "localhost",
        ):
            self.assertNotIn(private_value, diagnostic)

        no_provenance_events = [
            {
                "method": "Network.requestWillBeSent",
                "params": {
                    "requestId": "request-without-provenance",
                    "request": {"url": "http://localhost:18080/sw.js"},
                },
            },
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "request-without-provenance",
                    "response": {
                        "url": "http://localhost:18080/sw.js",
                        "status": 200,
                        "mimeType": "application/javascript",
                    },
                },
            },
        ]
        no_provenance = pwa_browser.service_worker_response_metadata(
            no_provenance_events,
            "http://localhost:18080",
            "/sw.js",
        )
        self.assertEqual("unknown", no_provenance["worker_source"])

    def test_wait_for_worker_preserves_safe_failure_phase_without_raw_js_error(self) -> None:
        private_url = (
            "http://localhost:18080/ko/identity?token=private-token-sentinel"
        )

        class Driver:
            current_url = "http://localhost:18080/ko/"

            def execute_async_script(self, _script: str, *_args: object) -> dict[str, object]:
                return {
                    "phase": "controller_wait",
                    "category": "controller_timeout",
                    "error_name": "TimeoutError",
                    "service_worker_supported": True,
                    "observer_installed": True,
                    "registration_attempted": True,
                    "registration_outcome": "resolved",
                    "ready_resolved": True,
                    "registration_found": True,
                    "active_state": "activated",
                    "controller_present": False,
                    "controller_change_observed": False,
                    "scope_matches_expected": True,
                    "script_origin_matches_expected": True,
                    "script_path_matches_expected": True,
                    "error_message": private_url,
                }

            def get_log(self, _log_type: str) -> list[dict[str, object]]:
                return []

        with self.assertRaises(pwa_browser.PwaDiagnosticAssertionError) as caught:
            pwa_browser.wait_for_service_worker(
                Driver(),
                "http://localhost:18080",
                "http://localhost:18080/ko/",
            )

        error = caught.exception
        self.assertEqual("service_worker_registration", error.diagnostic_code)
        self.assertEqual("controller_wait", error.safe_metadata["phase"])
        self.assertEqual("controller_timeout", error.safe_metadata["category"])
        self.assertEqual("unknown", error.safe_metadata["registration_error_name"])
        self.assertFalse(error.safe_metadata["controller_present"])
        self.assertTrue(error.safe_metadata["route_matches_expected"])
        self.assertTrue(error.safe_metadata["scope_matches_expected"])
        self.assertTrue(error.safe_metadata["script_origin_matches_expected"])
        self.assertTrue(error.safe_metadata["script_path_matches_expected"])
        self.assertNotIn("private-token-sentinel", str(error))
        self.assertNotIn("localhost", pwa_browser.format_service_worker_registration_diagnostic(error.safe_metadata))

    def test_original_registration_validation_matches_remain_required(self) -> None:
        for field, category in (
            ("scope_matches_expected", "scope_mismatch"),
            ("script_origin_matches_expected", "script_origin_mismatch"),
            ("script_path_matches_expected", "script_path_mismatch"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(pwa_browser.PwaDiagnosticAssertionError) as caught:
                    pwa_browser.require_service_worker_registration_match(
                        {field: False},
                        field,
                        category,
                        "service worker registration mismatch",
                    )
                self.assertEqual(category, caught.exception.safe_metadata["category"])

    def test_controller_wait_keeps_its_existing_12_second_bound_after_ready(self) -> None:
        script = pwa_browser.service_worker_registration_wait_script()

        ready_index = script.index("registration = await serviceWorker.ready")
        controller_wait_index = script.index(
            "await waitForControllerWithinDeadline(controllerChangePromise)"
        )
        self.assertLess(ready_index, controller_wait_index)
        self.assertIn("const controllerDeadline = Date.now() + 12000", script)
        self.assertIn("controller_change_observed", script)
        self.assertNotIn("String(error)", script)
        self.assertNotIn("error.message", script)

    def test_controller_change_listener_precedes_immediate_controller_recheck(self) -> None:
        wait_script = getattr(
            pwa_browser,
            "service_worker_registration_wait_script",
            pwa_browser.wait_for_service_worker,
        )
        script = inspect.getsource(wait_script)
        listener_index = script.index("addEventListener('controllerchange'")
        controller_recheck_index = script.index("if (!serviceWorker.controller)")

        self.assertLess(listener_index, controller_recheck_index)
        self.assertIn("controller_change_observed", script)

    def test_registration_observer_records_outcome_without_changing_returned_promise(self) -> None:
        script = pwa_browser.service_worker_registration_observer_script()

        self.assertIn("__pwaRegistrationObservation", script)
        self.assertIn("registration_attempted", script)
        self.assertIn("registration_outcome", script)
        self.assertIn("error_name", script)
        self.assertNotIn("error.message", script)
        self.assertNotIn("String(error)", script)
        self.assertNotIn("location.href", script)
        self.assertIn("return promise", script)


if __name__ == "__main__":
    unittest.main()
