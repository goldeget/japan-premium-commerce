from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("safe_native_facebook_outcome.py")
SPEC = importlib.util.spec_from_file_location("safe_native_facebook_outcome", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def valid_payload() -> dict:
    return {
        "schema": 1,
        "passed": True,
        "module_inventory": {
            "ps_facebook": {"installed": True, "active": True, "version": "1.38.19", "module_path": "/private/modules/ps_facebook"},
            "kuraneabackoffice": {"installed": True, "active": True, "version": "1.0.8", "module_path": "/private/modules/kuraneabackoffice"},
        },
        "source_sha256": {
            "facebook_http_client_sha256": "a" * 64,
            "project_subscriber_sha256": "b" * 64,
            "project_template_sha256": "c" * 64,
        },
        "facebook_error_fallback": {
            "mode": "authenticated_native_admin_kernel_browserkit",
            "native_admin_login_posted": True,
            "native_session_csrf_verified": True,
            "native_session_csrf_probe_count": 1,
            "native_authenticated_read_gate_verified": True,
            "framework_generated_legacy_link": True,
            "route": "admin_legacy_controller_route",
            "controller": "AdminPsfacebookModuleController",
            "controller_action": "read",
            "positive_failure_source": "installed_ps_facebook_HttpClient_cURL_exception",
            "actual_http_client_source_trace_verified_by_fallback": True,
            "known_facebook_request_controller_events": 3,
            "mismatched_facebook_route_events": 0,
            "disabled_mode_facebook_sentinels": 0,
            "test_transport_target": "run_owned_ipv4_loopback_bind_only",
            "stream_server_listen_used": False,
            "facebook_vendor_initContent_called_by_fixture": False,
            "script_initiated_external_transport_requests": 0,
            "installed_http_client_calls": 1,
            "response_status": 503,
            "korean_safe_title": True,
            "korean_safe_message": True,
            "korean_document_language": "ko-KR",
            "fixed_error_fragment_excludes_token_and_transport_details": True,
            "unauthenticated_status_not_converted": True,
            "other_route_status_not_converted": True,
            "generic_facebook_runtime_status_not_converted": True,
            "access_denied_status_preserved": True,
            "script_business_data_mutations": False,
            "login_session_or_auth_audit_writes_possible": True,
            "kernel_bootstrap_database_network_side_effects_instrumented": False,
            "raw_exception_message": "PRIVATE_CURL_MESSAGE",
        },
        "test_dependencies": {
            "symfony/browser-kit": {
                "version": "6.4.44",
                "source_commit": "4f631476bb549d882a173c47bf693f3ef84c722d",
                "archive_sha256": "d" * 64,
            },
            "symfony/css-selector": {
                "version": "6.4.45",
                "source_commit": "5484e316cd8125f5215bbf829151e2211aa6d101",
                "archive_sha256": "e" * 64,
            },
            "symfony/dom-crawler": {
                "version": "6.4.44",
                "source_commit": "998855f6c3699f148b54096d1d7d2b8b0b0fc298",
                "archive_sha256": None,
            },
        },
        "facebook_token": "PRIVATE_TOKEN",
        "raw_html": "PRIVATE_HTML",
        "trace": "PRIVATE_TRACE",
    }


def raw_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class SafeNativeFacebookOutcomeTests(unittest.TestCase):
    def test_success_rebuilds_allowlisted_output_and_discards_raw_values(self) -> None:
        result = MODULE.collect_safe_outcome(raw_json(valid_payload()), 0)
        self.assertTrue(result["passed"])
        self.assertEqual(result["modules"]["ps_facebook"]["version"], "1.38.19")
        self.assertEqual(result["modules"]["kuraneabackoffice"]["version"], "1.0.8")
        self.assertTrue(result["facebook_error_fallback"]["native_session_csrf_verified"])
        self.assertEqual(result["facebook_error_fallback"]["korean_document_language"], "ko-kr")
        serialized = json.dumps(result, ensure_ascii=False)
        for secret in ("PRIVATE_CURL_MESSAGE", "PRIVATE_TOKEN", "PRIVATE_HTML", "PRIVATE_TRACE", "/private/modules"):
            self.assertNotIn(secret, serialized)
        self.assertNotIn("module_inventory", result)
        self.assertNotIn("trace", result)

    def test_duplicate_json_keys_are_rejected_at_all_levels(self) -> None:
        raw = raw_json(valid_payload())
        variants = (
            raw.replace('"schema":1,', '"schema":1,"schema":1,', 1),
            raw.replace('"native_session_csrf_verified":true,', '"native_session_csrf_verified":true,"native_session_csrf_verified":false,', 1),
            raw.replace('"archive_sha256":"' + "d" * 64 + '"', '"archive_sha256":"' + "d" * 64 + '","archive_sha256":"' + "f" * 64 + '"', 1),
        )
        for variant in variants:
            with self.subTest(prefix=variant[:40]):
                result = MODULE.collect_safe_outcome(variant, 0)
                self.assertFalse(result["passed"])
                self.assertEqual(result["failure_code"], "invalid_helper_json")

    def test_nonzero_exit_status_overrides_helper_passed_flag_and_hides_raw_diagnostics(self) -> None:
        payload = valid_payload()
        payload.update({"passed": True, "failed_stage": "actual_installed_curl_failure_positive", "exception_class": "RuntimeException", "exception_message": "PRIVATE_MESSAGE", "trace": "PRIVATE_STACK"})
        result = MODULE.collect_safe_outcome(raw_json(payload), 1)
        self.assertEqual(result["failure_code"], "helper_exit_nonzero")
        self.assertEqual(result["failed_stage"], "actual_installed_curl_failure_positive")
        self.assertEqual(result["exception_class"], "RuntimeException")
        encoded = json.dumps(result)
        for secret in ("PRIVATE_MESSAGE", "PRIVATE_STACK", "trace", "exception_message"):
            self.assertNotIn(secret, encoded)

    def test_invalid_output_is_fail_closed_without_echoing_input(self) -> None:
        for raw in (
            "<html>PRIVATE_HTML</html>",
            "PRIVATE_STDOUT\n" + raw_json(valid_payload()),
            "not JSON PRIVATE_RAW",
            "[" * 1200 + "0" + "]" * 1200,
            json.dumps({"schema": 1, "passed": True}) + " " * MODULE.MAX_INPUT_BYTES,
        ):
            result = MODULE.collect_safe_outcome(raw, 0)
            self.assertFalse(result["passed"])
            self.assertEqual(result["failure_code"], "invalid_helper_json")
            self.assertNotIn("PRIVATE_", json.dumps(result))

    def test_missing_invalid_or_unverified_auth_and_csrf_flags_fail_closed(self) -> None:
        cases = (
            ("native_admin_login_posted", False),
            ("native_admin_login_posted", 1),
            ("native_session_csrf_verified", False),
            ("native_session_csrf_verified", 1),
            ("native_session_csrf_probe_count", 0),
            ("native_session_csrf_probe_count", True),
            ("native_authenticated_read_gate_verified", False),
            ("framework_generated_legacy_link", False),
        )
        for field, value in cases:
            payload = valid_payload()
            payload["facebook_error_fallback"][field] = value
            with self.subTest(field=field, value=value):
                result = MODULE.collect_safe_outcome(raw_json(payload), 0)
                self.assertFalse(result["passed"])
                self.assertEqual(result["failure_code"], "outcome_contract_mismatch")

        payload = valid_payload()
        del payload["facebook_error_fallback"]["native_session_csrf_verified"]
        result = MODULE.collect_safe_outcome(raw_json(payload), 0)
        self.assertEqual(result["failure_code"], "outcome_contract_mismatch")
        payload = valid_payload()
        del payload["facebook_error_fallback"]["native_authenticated_read_gate_verified"]
        result = MODULE.collect_safe_outcome(raw_json(payload), 0)
        self.assertEqual(result["failure_code"], "outcome_contract_mismatch")

    def test_only_expected_module_versions_and_dependency_revisions_are_accepted(self) -> None:
        cases = []
        payload = valid_payload()
        payload["module_inventory"]["ps_facebook"]["version"] = "1.38.20"
        cases.append(payload)
        payload = valid_payload()
        payload["module_inventory"]["kuraneabackoffice"]["active"] = False
        cases.append(payload)
        payload = valid_payload()
        payload["test_dependencies"]["symfony/browser-kit"]["source_commit"] = "0" * 40
        cases.append(payload)
        payload = valid_payload()
        payload["test_dependencies"]["symfony/css-selector"]["archive_sha256"] = "short"
        cases.append(payload)
        payload = valid_payload()
        del payload["test_dependencies"]["symfony/browser-kit"]["archive_sha256"]
        cases.append(payload)
        payload = valid_payload()
        payload["test_dependencies"]["symfony/dom-crawler"]["archive_sha256"] = "f" * 64
        cases.append(payload)
        payload = valid_payload()
        del payload["test_dependencies"]["symfony/dom-crawler"]
        cases.append(payload)
        for payload in cases:
            result = MODULE.collect_safe_outcome(raw_json(payload), 0)
            self.assertFalse(result["passed"])
            self.assertEqual(result["failure_code"], "outcome_contract_mismatch")

    def test_runtime_fallback_facts_are_strictly_typed_and_bounded(self) -> None:
        cases = (
            ("response_status", 200),
            ("response_status", True),
            ("installed_http_client_calls", 2),
            ("script_initiated_external_transport_requests", False),
            ("known_facebook_request_controller_events", 2),
            ("known_facebook_request_controller_events", True),
            ("mismatched_facebook_route_events", 1),
            ("disabled_mode_facebook_sentinels", 1),
            ("stream_server_listen_used", 0),
            ("facebook_vendor_initContent_called_by_fixture", True),
            ("korean_safe_message", 1),
            ("korean_document_language", "en"),
            ("login_session_or_auth_audit_writes_possible", False),
        )
        for field, value in cases:
            payload = valid_payload()
            payload["facebook_error_fallback"][field] = value
            with self.subTest(field=field, value=value):
                result = MODULE.collect_safe_outcome(raw_json(payload), 0)
                self.assertFalse(result["passed"])
                self.assertEqual(result["failure_code"], "outcome_contract_mismatch")

    def test_failure_source_allows_only_the_bounded_probe_filename_and_line(self) -> None:
        payload = {'schema': 1, 'passed': False, 'failure_source': 'native_facebook_transport_fallback.php:432'}
        result = MODULE.collect_safe_outcome(raw_json(payload), 1)
        self.assertEqual(result['failure_source'], payload['failure_source'])
        for source in ('/private/native_facebook_transport_fallback.php:432', 'private.php:432',
                       'native_facebook_transport_fallback.php:1000000', 'TOKEN_SECRET'):
            payload['failure_source'] = source
            self.assertNotIn('failure_source', MODULE.collect_safe_outcome(raw_json(payload), 1))

    def test_source_hashes_must_have_exact_keys_and_sha256_syntax(self) -> None:
        payload = valid_payload()
        payload["source_sha256"]["unexpected"] = "f" * 64
        result = MODULE.collect_safe_outcome(raw_json(payload), 0)
        self.assertEqual(result["failure_code"], "outcome_contract_mismatch")
        payload = valid_payload()
        payload["source_sha256"]["project_subscriber_sha256"] = "invalid"
        result = MODULE.collect_safe_outcome(raw_json(payload), 0)
        self.assertEqual(result["failure_code"], "outcome_contract_mismatch")

    def test_cli_reads_private_input_writes_only_safe_json_and_returns_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private_input = root / "private.stdout.json"
            safe_output = root / "qa-safe.json"
            payload = valid_payload()
            payload["facebook_token"] = "CLI_PRIVATE_TOKEN"
            private_input.write_text(raw_json(payload), encoding="utf-8")
            if os.name == "posix":
                private_input.chmod(0o600)
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "--private-input", str(private_input), "--safe-output", str(safe_output), "--helper-exit-status", "0"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout, "")
            safe_text = safe_output.read_text(encoding="utf-8")
            self.assertNotIn("CLI_PRIVATE_TOKEN", safe_text)
            self.assertTrue(json.loads(safe_text)["passed"])
            if os.name == "posix":
                self.assertEqual(safe_output.stat().st_mode & 0o777, 0o600)

    def test_cli_rejects_input_output_alias_and_private_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private_input = root / "private.json"
            private_input.write_text(raw_json(valid_payload()), encoding="utf-8")
            if os.name == "posix":
                private_input.chmod(0o600)
            same_path = subprocess.run(
                [sys.executable, str(SCRIPT), "--private-input", str(private_input), "--safe-output", str(private_input), "--helper-exit-status", "0"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(same_path.returncode, 64)
            if hasattr(os, "symlink"):
                alias = root / "private-link.json"
                try:
                    alias.symlink_to(private_input)
                except OSError:
                    return
                safe_output = root / "safe.json"
                linked = subprocess.run(
                    [sys.executable, str(SCRIPT), "--private-input", str(alias), "--safe-output", str(safe_output), "--helper-exit-status", "0"],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(linked.returncode, 1)
                self.assertEqual(json.loads(safe_output.read_text(encoding="utf-8"))["failure_code"], "private_input_unavailable")

    @unittest.skipUnless(os.name == "posix", "private mode check applies on POSIX runners")
    def test_cli_rejects_world_readable_private_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private_input = root / "private.json"
            safe_output = root / "qa-safe.json"
            private_input.write_text(raw_json(valid_payload()), encoding="utf-8")
            private_input.chmod(0o644)
            run = subprocess.run(
                [sys.executable, str(SCRIPT), "--private-input", str(private_input), "--safe-output", str(safe_output), "--helper-exit-status", "0"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(run.returncode, 1)
            outcome = json.loads(safe_output.read_text(encoding="utf-8"))
            self.assertEqual(outcome["failure_code"], "private_input_unavailable")
            self.assertNotIn("PRIVATE_", json.dumps(outcome))


if __name__ == "__main__":
    unittest.main()
