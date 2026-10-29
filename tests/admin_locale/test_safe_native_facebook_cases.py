from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("safe_native_facebook_cases.py")
SPEC = importlib.util.spec_from_file_location("safe_native_facebook_cases", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def valid_case(case: str) -> dict:
    authenticated = case != "unauthenticated"
    positive = case == "curl_transport"
    other = case == "other_route"
    generic = case == "generic_facebook"
    denied = case == "access_denied"
    gate = int(case in {"generic_facebook", "access_denied", "curl_transport"})
    status = 503 if positive else 403 if denied else 500 if generic or other else 302
    language = "ko-kr" if positive else ""
    return {
        "schema": 2,
        "passed": True,
        "case": case,
        "module_inventory": {
            "ps_facebook": {"installed": True, "active": True, "version": "1.38.19"},
            "kuraneabackoffice": {"installed": True, "active": True, "version": "1.0.8"},
        },
        "source_sha256": {
            "facebook_http_client_sha256": "a" * 64,
            "project_subscriber_sha256": "b" * 64,
            "project_template_sha256": "c" * 64,
        },
        "facebook_case_facts": {
            "native_login_transport": "loopback_http_native_front_controller" if authenticated else "none",
            "native_login_form_posted": authenticated,
            "native_login_http_requests": 3 if authenticated else 0,
            "native_login_stages_verified": True,
            "framework_generated_legacy_link": True,
            "framework_link_has_token": authenticated,
            "unauthenticated_link_token_validity_claimed": False,
            "case": case,
            "browserkit_target_get_count": 1,
            "route": "admin_dashboard" if other else "admin_legacy_controller_route",
            "controller": "AdminDashboard" if other else "AdminPsfacebookModuleController",
            "controller_action": "not_applicable" if other else "read",
            "authenticated_read_gate_passes": gate,
            "known_facebook_request_controller_events": int(bool(gate)),
            "mismatched_facebook_route_events": 0,
            "disabled_mode_facebook_sentinels": 0,
            "other_route_exception_count": int(other),
            "generic_facebook_exception_count": int(generic),
            "access_denied_exception_count": int(denied),
            "test_transport_target": "run_owned_ipv4_loopback_bind_only",
            "stream_server_listen_used": False,
            "facebook_vendor_initContent_called_by_fixture": False,
            "script_initiated_external_transport_requests": 0,
            "installed_http_client_calls": int(positive),
            "response_status": status,
            "unauthenticated_status_not_converted": case == "unauthenticated",
            "other_route_status_not_converted": other,
            "generic_facebook_runtime_status_not_converted": generic,
            "access_denied_status_preserved": denied,
            "korean_safe_title": positive,
            "korean_safe_message": positive,
            "korean_document_language": language,
            "fixed_error_fragment_excludes_token_and_transport_details": positive,
            "native_session_csrf_verified": positive,
            "native_session_csrf_probe_count": int(positive),
            "positive_response_snapshot_sha256": "d" * 64 if positive else None,
            "script_business_data_mutations": False,
            "login_session_or_auth_audit_writes_possible": authenticated,
            "kernel_bootstrap_database_network_side_effects_instrumented": False,
        },
        "test_dependencies": {
            "symfony/browser-kit": {
                "version": "6.4.44", "source_commit": "4f631476bb549d882a173c47bf693f3ef84c722d", "archive_sha256": "e" * 64,
            },
            "symfony/css-selector": {
                "version": "6.4.45", "source_commit": "5484e316cd8125f5215bbf829151e2211aa6d101", "archive_sha256": "f" * 64,
            },
            "symfony/dom-crawler": {
                "version": "6.4.44", "source_commit": "998855f6c3699f148b54096d1d7d2b8b0b0fc298", "archive_sha256": None,
            },
        },
    }


def good_inputs() -> tuple[dict[str, bytes], dict[str, int]]:
    return ({name: json.dumps(valid_case(name), separators=(",", ":")).encode() for name in MODULE.CASES},
            {name: 0 for name in MODULE.CASES})


class SafeNativeFacebookCasesTests(unittest.TestCase):
    def test_aggregates_exact_five_fresh_process_results_and_filters_to_safe_fields(self) -> None:
        raw, statuses = good_inputs()
        result = MODULE.collect_cases(raw, statuses)
        self.assertTrue(result["passed"])
        self.assertEqual(result["execution"]["fresh_php_processes"], 5)
        self.assertEqual(result["execution"]["browserkit_target_gets"], 5)
        self.assertEqual(result["execution"]["native_login_http_requests"], 12)
        self.assertEqual(result["facebook_transport_fallback"]["response_status"], 503)
        self.assertEqual(result["facebook_transport_fallback"]["private_response_snapshot_sha256"], "d" * 64)
        serialized = json.dumps(result)
        for secret in ("ADMIN_PASSWD", "raw_html", "raw_cookie", "private/modules", "trace", "facebook_token"):
            self.assertNotIn(secret, serialized)
        self.assertEqual(set(result["cases"]), set(MODULE.CASES))

    def test_cli_writes_allowlisted_aggregate_and_refuses_overwrite(self) -> None:
        raw, _ = good_inputs()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = [sys.executable, str(SCRIPT), "--safe-output", str(root / "safe.json")]
            for name in MODULE.CASES:
                path = root / f"{name}.json"
                path.write_bytes(raw[name])
                if os.name != "nt":
                    path.chmod(0o600)
                args += ["--case-input", f"{name}={path}", "--case-status", f"{name}=0"]
            first = subprocess.run(args, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0)
            result = json.loads((root / "safe.json").read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            second = subprocess.run(args, capture_output=True, check=False)
            self.assertEqual(second.returncode, 2)
            self.assertTrue(json.loads((root / "safe.json").read_text(encoding="utf-8"))["passed"])

    def test_requires_exact_case_set_and_successful_process_statuses(self) -> None:
        raw, statuses = good_inputs()
        del raw["other_route"]
        self.assertEqual(MODULE.collect_cases(raw, statuses)["failure_code"], "case_set_mismatch")
        raw, statuses = good_inputs()
        statuses["curl_transport"] = 1
        result = MODULE.collect_cases(raw, statuses)
        self.assertFalse(result["passed"])
        self.assertEqual(result["failure_code"], "helper_nonzero")
        self.assertEqual(result["failed_case"], "curl_transport")

    def test_failed_case_reports_only_known_stage_and_symbolic_diagnostics(self) -> None:
        raw, statuses = good_inputs()
        raw['curl_transport'] = json.dumps({'schema':1,'passed':False,
            'failed_stage':'single_fresh_process_case_request','exception_class':'RuntimeException',
            'failure_source':'native_facebook_transport_fallback.php:123',
            'exception_message':'PRIVATE_COOKIE_SECRET','trace':['PRIVATE_PASSWORD']}).encode()
        statuses['curl_transport'] = 1
        result = MODULE.collect_cases(raw, statuses)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failed_stage'], 'single_fresh_process_case_request')
        self.assertEqual(result['exception_class'], 'RuntimeException')
        self.assertEqual(result['failure_source'], 'native_facebook_transport_fallback.php:123')
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_rejects_duplicate_keys_and_case_name_substitution(self) -> None:
        raw, statuses = good_inputs()
        raw["unauthenticated"] = raw["unauthenticated"].replace(b'"schema":2,', b'"schema":2,"schema":2,', 1)
        self.assertEqual(MODULE.collect_cases(raw, statuses)["failure_code"], "case_contract_mismatch")
        raw, statuses = good_inputs()
        payload = valid_case("generic_facebook")
        payload["case"] = "access_denied"
        raw["generic_facebook"] = json.dumps(payload).encode()
        self.assertEqual(MODULE.collect_cases(raw, statuses)["failure_code"], "case_contract_mismatch")

    def test_rejects_cross_process_source_or_dependency_drift(self) -> None:
        raw, statuses = good_inputs()
        payload = valid_case("access_denied")
        payload["source_sha256"]["project_template_sha256"] = "9" * 64
        raw["access_denied"] = json.dumps(payload).encode()
        self.assertEqual(MODULE.collect_cases(raw, statuses)["failure_code"], "case_source_pins_mismatch")
        raw, statuses = good_inputs()
        payload = valid_case("curl_transport")
        payload["test_dependencies"]["symfony/browser-kit"]["archive_sha256"] = "9" * 64
        raw["curl_transport"] = json.dumps(payload).encode()
        self.assertEqual(MODULE.collect_cases(raw, statuses)["failure_code"], "case_source_pins_mismatch")

    def test_fails_closed_on_unsafe_semantics(self) -> None:
        mutations = (
            ("unauthenticated", "native_login_form_posted", True),
            ("unauthenticated", "unauthenticated_link_token_validity_claimed", True),
            ("generic_facebook", "authenticated_read_gate_passes", 0),
            ("generic_facebook", "authenticated_read_gate_passes", True),
            ("curl_transport", "installed_http_client_calls", True),
            ("curl_transport", "native_session_csrf_verified", False),
            ("curl_transport", "installed_http_client_calls", 0),
            ("curl_transport", "stream_server_listen_used", True),
            ("curl_transport", "script_initiated_external_transport_requests", 1),
            ("access_denied", "response_status", 503),
        )
        for case, key, value in mutations:
            with self.subTest(case=case, key=key):
                raw, statuses = good_inputs()
                payload = valid_case(case)
                payload["facebook_case_facts"][key] = value
                raw[case] = json.dumps(payload).encode()
                self.assertFalse(MODULE.collect_cases(raw, statuses)["passed"])

    @unittest.skipIf(os.name == "nt", "POSIX private-mode checks are not available on Windows")
    def test_cli_rejects_world_readable_raw_case_input(self) -> None:
        raw, statuses = good_inputs()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            files = {}
            for name, content in raw.items():
                path = root / f"{name}.json"
                path.write_bytes(content)
                path.chmod(0o600)
                files[name] = path
            files["unauthenticated"].chmod(0o644)
            args = [sys.executable, str(SCRIPT), "--safe-output", str(root / "safe.json")]
            for name in MODULE.CASES:
                args += ["--case-input", f"{name}={files[name]}", "--case-status", f"{name}=0"]
            result = subprocess.run(args, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            safe = json.loads((root / "safe.json").read_text())
            self.assertEqual(safe["failure_code"], "private_input_invalid")
            self.assertNotIn(str(root), (root / "safe.json").read_text())


if __name__ == "__main__":
    unittest.main()
