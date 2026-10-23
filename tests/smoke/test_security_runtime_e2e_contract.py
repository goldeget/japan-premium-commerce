"""Contract checks for the isolated admin and native password-reset security flows."""

import ast
from contextlib import redirect_stderr
from io import StringIO
import ipaddress
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
ADMIN_FLOW = ROOT / "tests" / "e2e" / "verify_admin_security_browser.py"
RESET_FLOW = ROOT / "tests" / "e2e" / "verify_customer_reset_token_browser.py"
FIXTURE = ROOT / "tests" / "business_profile" / "seed_security_fixtures.php"


def load_function(path: Path, function_name: str, namespace: dict[str, object]):
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    isolated_module = ast.Module(body=[function], type_ignores=[])
    exec(compile(isolated_module, str(path), "exec"), namespace)
    return namespace[function_name]


class SecurityRuntimeE2EContractTests(unittest.TestCase):
    def test_admin_security_flow_covers_missing_invalid_and_view_only_requests(self):
        self.assertTrue(ADMIN_FLOW.is_file(), "the isolated admin security browser flow is missing")
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        for marker in (
            '"missing"',
            '"invalid"',
            '"view_only"',
            "submitOrdenowaSaveDraft",
            "profile[brand][name][ko-KR]",
            "assert_setting_unchanged",
            "current_draft_pointer",
            "assert_draft_pointer_unchanged",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        state_assertion = source.split("def assert_setting_unchanged(", 1)[1].split("\n\ndef ", 1)[0]
        self.assertIn(
            "assert_draft_pointer_unchanged(driver, expected_draft_pointer, label)",
            state_assertion,
        )
        guarded_attempt = source.split("def verify_security_attempt_without_mutation(", 1)[1].split("\n\ndef ", 1)[0]
        self.assertIn("assert_setting_unchanged(", guarded_attempt)
        self.assertIn("assert_security_attempt_rejected(response, mode)", guarded_attempt)
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertIn("verify_security_attempt_without_mutation(", run)

    def test_admin_security_flow_guards_exact_loopback_ci_target_before_browser_creation(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        for marker in (
            "def validate_isolated_ci_project",
            "def validate_loopback_admin_targets",
            "os.environ.get(\"CI\")",
            "os.environ.get(\"GITHUB_ACTIONS\")",
            "os.environ.get(\"KURANEA_ISOLATED_CI\")",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "CI_COMPOSE_PROJECT_NAME",
            "EXPECTED_SHOP_PORT = 18080",
            "ipaddress.ip_address(host).is_loopback",
            "ADMIN_MAIL",
            "@example.invalid",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertLess(run.index("validate_isolated_ci_project()"), run.index("new_driver()"))
        self.assertLess(run.index("validate_loopback_admin_targets()"), run.index("new_driver()"))
        self.assertNotIn("save_screenshot", run)

    def test_admin_security_browser_failure_emits_safe_stage_annotation(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        handler = run.split("except Exception as error:", 1)[1].split("finally:", 1)[0]
        self.assertIn("::error title=ORDENOWA admin security browser QA::", handler)
        self.assertIn("{stage}", handler)
        self.assertIn("{error_type}", handler)
        self.assertIn("admin_security_substage", handler)
        self.assertIn("admin_security_response", handler)
        self.assertIn("admin_security_request", handler)
        self.assertIn("admin_security_state_recheck", handler)
        self.assertIn("substage={diagnostic_substage}", handler)
        self.assertIn("setting_value_mismatch", source)
        self.assertIn("draft_pointer_mismatch", source)
        self.assertIn("ORDENOWA_ADMIN_SECURITY_SUBSTAGE=", handler)
        self.assertIn("ORDENOWA_ADMIN_SECURITY_RESPONSE=", handler)
        self.assertNotIn("str(error)", handler)
        self.assertNotIn("{error}", handler)

    def test_admin_browser_cleanup_attempts_both_drivers_and_keeps_failure_redacted(self):
        namespace: dict[str, object] = {"sys": sys}
        close_drivers = load_function(ADMIN_FLOW, "close_browser_drivers", namespace)

        class FakeDriver:
            def __init__(self, fail: bool) -> None:
                self.fail = fail
                self.quit_calls = 0

            def quit(self) -> None:
                self.quit_calls += 1
                if self.fail:
                    raise RuntimeError("private browser session detail")

        admin = FakeDriver(fail=True)
        restricted = FakeDriver(fail=False)
        output = StringIO()
        with redirect_stderr(output):
            cleanup_ok = close_drivers(
                (("admin", admin), ("restricted", restricted)),
                primary_failure=False,
            )

        self.assertFalse(cleanup_ok)
        self.assertEqual(admin.quit_calls, 1)
        self.assertEqual(restricted.quit_calls, 1)
        self.assertIn("admin_chrome_shutdown", output.getvalue())
        self.assertIn("RuntimeError", output.getvalue())
        self.assertNotIn("private browser session detail", output.getvalue())

        admin = FakeDriver(fail=True)
        restricted = FakeDriver(fail=True)
        output = StringIO()
        with redirect_stderr(output):
            cleanup_ok = close_drivers(
                (("admin", admin), ("restricted", restricted)),
                primary_failure=True,
            )

        self.assertFalse(cleanup_ok)
        self.assertEqual(admin.quit_calls, 1)
        self.assertEqual(restricted.quit_calls, 1)
        self.assertIn("WARNING:", output.getvalue())
        self.assertNotIn("::error", output.getvalue())
        self.assertNotIn("private browser session detail", output.getvalue())

    def test_admin_ci_and_origin_guards_accept_only_the_matching_local_project(self):
        namespace: dict[str, object] = {
            "os": os,
            "ipaddress": ipaddress,
            "urlparse": urlparse,
            "COMPOSE_PROJECT": "kuranea-ci-123456789-2",
            "ADMIN_EMAIL": "ci-ordenowa@example.invalid",
            "VIEW_ONLY_EMAIL": "view-only@example.invalid",
            "EXPECTED_SHOP_PORT": 18080,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        load_function(ADMIN_FLOW, "_loopback_http_origin", namespace)
        validate_targets = load_function(ADMIN_FLOW, "validate_loopback_admin_targets", namespace)
        validate_project = load_function(ADMIN_FLOW, "validate_isolated_ci_project", namespace)
        valid_environment = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "KURANEA_ISOLATED_CI": "1",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_RUN_ATTEMPT": "2",
            "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-123456789-2",
        }
        with patch.dict(os.environ, valid_environment, clear=False):
            validate_project()
            validate_targets()
            for key, value in (
                ("CI", "false"),
                ("GITHUB_ACTIONS", "false"),
                ("KURANEA_ISOLATED_CI", "0"),
                ("GITHUB_RUN_ID", "run123"),
                ("GITHUB_RUN_ATTEMPT", "2 "),
                ("CI_COMPOSE_PROJECT_NAME", "kuranea-ci-123456789-3"),
            ):
                with self.subTest(variable=key, value=value), patch.dict(os.environ, {key: value}):
                    with self.assertRaises(ValueError):
                        validate_project()

        for shop_url, admin_url in (
            ("https://shop.example:18080", "https://shop.example:18080/admin-kuranea"),
            ("http://127.0.0.1:18080", "http://localhost:18080/admin-kuranea"),
            ("http://localhost:18081", "http://localhost:18081/admin-kuranea"),
        ):
            with self.subTest(shop_url=shop_url, admin_url=admin_url):
                namespace["BASE"] = shop_url
                namespace["ADMIN_LOGIN"] = admin_url
                with self.assertRaises(ValueError):
                    validate_targets()

    def test_admin_security_attempts_require_the_admin_handler_and_reject_not_found(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        for marker in (
            "responseUrl",
            "bodyHasSettingsForm",
            "bodyHasDangerAlert",
            "bodyHasAdminLoginForm",
            "bodyHasViewOnlyDenial",
            "status == 404",
            "response_url",
            "설정 초안을 수정할 권한이 없습니다.",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_admin_security_rejects_only_the_specific_prestashop_login_gate_page(self):
        namespace: dict[str, object] = {
            "re": re,
            "urlparse": urlparse,
            "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        is_login_rejection = load_function(
            ADMIN_FLOW,
            "is_prestashop_admin_login_rejection",
            namespace,
        )
        login_page = {
            "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/login",
            "bodyHasAdminLoginForm": True,
            "bodyHasSettingsForm": False,
        }
        self.assertTrue(is_login_rejection(login_page))
        self.assertTrue(
            is_login_rejection(
                {
                    **login_page,
                    "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminLogin",
                }
            )
        )

        for response in (
            {**login_page, "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard"},
            {**login_page, "responseUrl": "http://localhost:18080/admin-kuranea/another-route"},
            {**login_page, "responseUrl": "http://localhost:18080/login"},
            {**login_page, "responseUrl": "http://outside.example/admin-kuranea/login"},
            {**login_page, "status": 302},
            {**login_page, "bodyHasAdminLoginForm": False},
            {**login_page, "bodyHasSettingsForm": True},
        ):
            with self.subTest(response=response):
                self.assertFalse(is_login_rejection(response))

    def test_admin_security_response_classifier_preserves_explicit_rejections_only(self):
        namespace: dict[str, object] = {
            "re": re,
            "urlparse": urlparse,
            "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        load_function(ADMIN_FLOW, "response_summary", namespace)
        namespace["is_prestashop_compromised_token_rejection"] = load_function(
            ADMIN_FLOW,
            "is_prestashop_compromised_token_rejection",
            namespace,
        )
        namespace["is_prestashop_admin_login_rejection"] = load_function(
            ADMIN_FLOW,
            "is_prestashop_admin_login_rejection",
            namespace,
        )
        namespace["response_classification"] = load_function(
            ADMIN_FLOW,
            "response_classification",
            namespace,
        )
        namespace["raise_admin_security_response_failure"] = load_function(
            ADMIN_FLOW,
            "raise_admin_security_response_failure",
            namespace,
        )
        assert_rejected = load_function(
            ADMIN_FLOW,
            "assert_security_attempt_rejected",
            namespace,
        )

        assert_rejected(
            {
                "formPresent": True,
                "status": 200,
                "responseUrl": "http://localhost:18080/admin-kuranea/login",
                "bodyHasSettingsForm": False,
                "bodyHasDangerAlert": False,
                "bodyHasAdminLoginForm": True,
                "bodyHasViewOnlyDenial": False,
            },
            "missing",
        )
        assert_rejected(
            {
                "formPresent": True,
                "status": 403,
                "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile",
                "bodyHasSettingsForm": False,
                "bodyHasDangerAlert": False,
                "bodyHasAdminLoginForm": False,
                "bodyHasViewOnlyDenial": False,
            },
            "invalid",
        )
        assert_rejected(
            {
                "formPresent": True,
                "status": 200,
                "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile",
                "bodyHasSettingsForm": True,
                "bodyHasDangerAlert": True,
                "bodyHasAdminLoginForm": False,
                "bodyHasViewOnlyDenial": False,
            },
            "invalid",
        )

        for response in (
            {
                "formPresent": True,
                "status": 200,
                "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard",
                "bodyHasSettingsForm": False,
                "bodyHasDangerAlert": False,
                "bodyHasAdminLoginForm": True,
                "bodyHasViewOnlyDenial": False,
            },
            {
                "formPresent": True,
                "status": 200,
                "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile",
                "bodyHasSettingsForm": True,
                "bodyHasDangerAlert": False,
                "bodyHasAdminLoginForm": False,
                "bodyHasViewOnlyDenial": False,
            },
        ):
            with self.subTest(response=response), self.assertRaises(AssertionError):
                assert_rejected(response, "missing")

        secret_redirect = {
            "formPresent": True,
            "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard&token=private-token",
            "bodyHasSettingsForm": False,
            "bodyHasDangerAlert": False,
            "bodyHasAdminLoginForm": True,
            "bodyHasViewOnlyDenial": False,
        }
        with self.assertRaises(AssertionError) as failure:
            assert_rejected(secret_redirect, "missing")
        self.assertEqual(
            failure.exception.admin_security_substage,
            "missing_token_rejection_unrecognized",
        )
        self.assertIn("classification=unrecognized", failure.exception.admin_security_response)
        self.assertIn("final_path=/admin-kuranea/index.php", failure.exception.admin_security_response)
        self.assertNotIn("private-token", failure.exception.admin_security_response)

    def test_admin_security_recognizes_native_invalid_token_warning_without_accepting_generic_pages(self):
        namespace = {
            "re": re, "urlparse": urlparse, "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        for function in (
            "is_prestashop_admin_login_rejection", "is_prestashop_compromised_token_rejection", "response_classification",
            "response_summary", "raise_admin_security_response_failure",
            "assert_security_attempt_rejected",
        ):
            load_function(ADMIN_FLOW, function, namespace)
        warning = {
            "formPresent": True, "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile",
            "bodyHasSettingsForm": False, "bodyHasDangerAlert": False,
            "bodyHasAdminLoginForm": False, "bodyHasViewOnlyDenial": False,
            "bodyHasInvalidTokenPage": True,
        }
        self.assertEqual(namespace["response_classification"](warning), "prestashop_invalid_token")
        for mode in ("missing", "invalid"):
            with self.subTest(mode=mode):
                namespace["assert_security_attempt_rejected"](warning, mode)
        with self.assertRaises(AssertionError):
            namespace["assert_security_attempt_rejected"](warning, "view_only")
        for changes in (
            {"bodyHasInvalidTokenPage": False},
            {"bodyHasSettingsForm": True},
            {"bodyHasAdminLoginForm": True},
            {"responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard"},
            {"responseUrl": "http://localhost:18080/admin-kuranea/other"},
            {"responseUrl": "http://outside.example/admin-kuranea/index.php?controller=AdminBusinessProfile"},
            {"status": 302},
        ):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                namespace["assert_security_attempt_rejected"]({**warning, **changes}, "missing")

    def test_admin_security_recognizes_only_the_native_prestashop_compromised_token_route(self):
        namespace = {
            "re": re, "urlparse": urlparse, "parse_qs": parse_qs,
            "BASE": "http://localhost:18080",
            "ADMIN_LOGIN": "http://localhost:18080/admin-kuranea",
        }
        for function in (
            "is_prestashop_admin_login_rejection", "is_prestashop_compromised_token_rejection", "response_classification",
            "response_summary", "raise_admin_security_response_failure",
            "assert_security_attempt_rejected",
        ):
            load_function(ADMIN_FLOW, function, namespace)

        native = {
            "formPresent": True,
            "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/security/compromised",
            "bodyHasSettingsForm": False,
            "bodyHasDangerAlert": True,
            "bodyHasAdminLoginForm": False,
            "bodyHasViewOnlyDenial": False,
            "bodyHasNativeCompromisedPage": True,
        }
        self.assertEqual(namespace["response_classification"](native), "prestashop_compromised_token")
        for mode in ("missing", "invalid"):
            with self.subTest(mode=mode):
                namespace["assert_security_attempt_rejected"](native, mode)

        for changes in (
            {"bodyHasNativeCompromisedPage": False},
            {"bodyHasDangerAlert": False},
            {"bodyHasAdminLoginForm": True},
            {"bodyHasViewOnlyDenial": True},
            {"responseUrl": "http://localhost:18080/admin-kuranea/login"},
            {"responseUrl": "http://localhost:18080/admin-kuranea/other/security/compromised"},
            {"responseUrl": "http://outside.example/admin-kuranea/security/compromised"},
            {"status": 404},
            {"status": 302},
        ):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                namespace["assert_security_attempt_rejected"]({**native, **changes}, "missing")

        generic_danger_alert = {
            **native,
            "bodyHasNativeCompromisedPage": False,
            "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminDashboard",
        }
        with self.assertRaises(AssertionError):
            namespace["assert_security_attempt_rejected"](generic_danger_alert, "missing")

        business_profile_error = {**native, "bodyHasSettingsForm": True}
        self.assertEqual(
            namespace["response_classification"](business_profile_error),
            "business_profile_error",
        )
        self.assertNotEqual(
            namespace["response_classification"](business_profile_error),
            "prestashop_compromised_token",
        )
        namespace["assert_security_attempt_rejected"](business_profile_error, "missing")

        source = ADMIN_FLOW.read_text(encoding="utf-8")
        fixture = ROOT / "tests" / "fixtures" / "prestashop-9.2-security-compromised.html"
        self.assertTrue(fixture.is_file(), "the native PrestaShop 9.2 compromised security fixture is missing")
        markup = fixture.read_text(encoding="utf-8")
        for marker in (
            'id="security-compromised-page"',
            'class="alert alert-danger"',
            "class=\"btn btn-lg btn-outline-danger mr-3\"",
            "class=\"btn btn-lg btn-primary ml-3\"",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, markup)
        self.assertIn("#security-compromised-page", source)
        self.assertIn("verify_native_compromised_page_fixture", source)
        self.assertIn("searchParams.getAll('token')", source)
        self.assertIn("searchParams.getAll('_token')", source)
        self.assertIn('"tokenless_request_link"', source)
        self.assertIn('"tokenized_request_link"', source)
        self.assertIn('"dashboard_symfony_token"', source)
        self.assertIn('"missing_dashboard_token"', source)
        self.assertIn('"duplicate_dashboard_tokens"', source)
        self.assertIn("&& details.compromisedContinueController", source)
        self.assertNotIn("&& details.compromisedContinueTokenPresent", source)
        self.assertIn("&& details.compromisedDashboardTokenPresent", source)
        for diagnostic in (
            "compromisedPageMarker",
            "compromisedWarning",
            "compromisedContinueLink",
            "compromisedDashboardLink",
            "compromisedResponseSameOrigin",
            "compromisedResponsePath",
            "compromisedContinueSameOrigin",
            "compromisedContinuePath",
            "compromisedContinueController",
            "compromisedContinueTokenPresent",
            "compromisedDashboardSameOrigin",
            "compromisedDashboardPath",
            "compromisedDashboardController",
            "compromisedDashboardTokenPresent",
        ):
            with self.subTest(diagnostic=diagnostic):
                self.assertIn(diagnostic, source)
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertIn("verify_native_compromised_page_fixture(admin_driver)", run)

    def test_admin_security_failure_summary_exposes_only_safe_invalid_token_dom_facts(self):
        namespace = {"re": re, "urlparse": urlparse, "parse_qs": parse_qs}
        load_function(ADMIN_FLOW, "is_prestashop_compromised_token_rejection", namespace)
        load_function(ADMIN_FLOW, "is_prestashop_admin_login_rejection", namespace)
        load_function(ADMIN_FLOW, "response_classification", namespace)
        summary = load_function(ADMIN_FLOW, "response_summary", namespace)
        result = {
            "status": 200,
            "responseUrl": "http://localhost:18080/admin-kuranea/index.php?controller=AdminBusinessProfile&token=secret",
            "bodyHasSettingsForm": False,
            "bodyHasDangerAlert": False,
            "bodyHasAdminLoginForm": False,
            "bodyHasInvalidTokenPage": False,
            "bodyHasInvalidTokenWarning": True,
            "bodyHasInvalidTokenContinue": True,
            "bodyHasInvalidTokenCancel": True,
            "invalidTokenRecoverySameOrigin": True,
            "invalidTokenRecoverySamePath": True,
            "invalidTokenRecoveryController": "AdminBusinessProfile",
            "invalidTokenRecoveryTokenPresent": True,
            "compromisedPageMarker": True,
            "compromisedWarning": True,
            "compromisedContinueLink": True,
            "compromisedDashboardLink": True,
            "compromisedResponseSameOrigin": True,
            "compromisedResponsePath": True,
            "compromisedContinueSameOrigin": True,
            "compromisedContinuePath": True,
            "compromisedContinueController": True,
            "compromisedContinueTokenPresent": True,
            "compromisedDashboardSameOrigin": True,
            "compromisedDashboardPath": True,
            "compromisedDashboardController": True,
            "compromisedDashboardTokenPresent": True,
        }
        diagnostic = summary(result)
        for safe_fact in (
            "response_controller=AdminBusinessProfile",
            "invalid_token_warning=true",
            "invalid_token_continue=true",
            "invalid_token_cancel=true",
            "recovery_same_origin=true",
            "recovery_same_path=true",
            "recovery_controller=AdminBusinessProfile",
            "recovery_token_present=true",
            "invalid_token_page=false",
            "native_compromised_page=false",
            "compromised_marker=true",
            "compromised_warning=true",
            "compromised_continue=true",
            "compromised_dashboard=true",
            "compromised_response_origin=true",
            "compromised_response_path=true",
            "compromised_continue_origin=true",
            "compromised_continue_path=true",
            "compromised_continue_controller=true",
            "compromised_continue_token=true",
            "compromised_dashboard_origin=true",
            "compromised_dashboard_path=true",
            "compromised_dashboard_controller=true",
            "compromised_dashboard_token=true",
        ):
            with self.subTest(safe_fact=safe_fact):
                self.assertIn(safe_fact, diagnostic)
        self.assertIn("settings_form=false; danger_alert=false; admin_login_form=false", diagnostic)
        self.assertNotIn("secret", diagnostic)

        source = ADMIN_FLOW.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(ADMIN_FLOW))
        pattern_assignment = next(
            (
                node
                for node in module.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "SAFE_ADMIN_SECURITY_RESPONSE_PATTERN"
                    for target in node.targets
                )
            ),
            None,
        )
        self.assertIsNotNone(pattern_assignment)
        assert pattern_assignment is not None
        self.assertRegex(diagnostic, ast.literal_eval(pattern_assignment.value))

    def test_admin_security_browser_runs_native_token_dom_fixture_in_chromium(self):
        source = ADMIN_FLOW.read_text(encoding="utf-8")
        fixture = ROOT / "tests" / "fixtures" / "prestashop-9.2-invalid-token.html"
        self.assertTrue(fixture.is_file(), "the native PrestaShop invalid-token fixture is missing")
        markup = fixture.read_text(encoding="utf-8")
        self.assertIn('<img width="32px" alt="warning"', markup)
        self.assertIn('class="btn btn-continue"', markup)
        self.assertIn('class="btn btn-cancel" href="index.php"', markup)
        self.assertIn("TOKEN_DOM_DETECTOR_JS", source)
        self.assertIn("verify_native_invalid_token_dom_fixture", source)
        self.assertIn("verify_native_invalid_token_dom_fixture(admin_driver)", source)

    def test_admin_security_attempt_rechecks_state_before_classifying_a_rejection(self):
        events: list[str] = []

        def reject_unrecognized_response(response, mode):
            events.append("classification")
            error = AssertionError("unrecognized response")
            error.admin_security_substage = "missing_token_rejection_unrecognized"
            error.admin_security_response = "classification=unrecognized; status=200; final_path=/admin-kuranea/home; settings_form=false; danger_alert=false; admin_login_form=false"
            raise error

        namespace: dict[str, object] = {
            "webdriver": type("WebDriverTypes", (), {"Chrome": object}),
            "submit_settings_attempt": lambda driver, mode: events.append("request") or {"status": 200},
            "assert_setting_unchanged": lambda driver, value, pointer, label: events.append("state"),
            "assert_security_attempt_rejected": reject_unrecognized_response,
        }
        verify_attempt = load_function(
            ADMIN_FLOW,
            "verify_security_attempt_without_mutation",
            namespace,
        )
        with self.assertRaisesRegex(AssertionError, "unrecognized response") as response_failure:
            verify_attempt(object(), "missing", "original", "17", "missing-token")
        self.assertEqual(events, ["request", "state", "classification"])
        self.assertEqual(response_failure.exception.admin_security_request, "completed")
        self.assertEqual(response_failure.exception.admin_security_state_recheck, "passed")

        events.clear()
        namespace["submit_settings_attempt"] = lambda driver, mode: events.append("request") or {"status": 200}
        namespace["assert_setting_unchanged"] = lambda driver, value, pointer, label: (
            events.append("state") or (_ for _ in ()).throw(AssertionError("private setting value"))
        )
        with self.assertRaises(AssertionError) as state_failure:
            verify_attempt(object(), "missing", "original", "17", "missing-token")
        self.assertEqual(events, ["request", "state"])
        self.assertEqual(state_failure.exception.admin_security_substage, "state_recheck_failed")
        self.assertEqual(state_failure.exception.admin_security_request, "completed")
        self.assertEqual(state_failure.exception.admin_security_state_recheck, "failed:AssertionError")
        self.assertEqual(state_failure.exception.admin_security_response, "not_evaluated")
        self.assertNotIn("private setting value", str(state_failure.exception))

        events.clear()
        namespace["assert_setting_unchanged"] = lambda driver, value, pointer, label: events.append("state")
        namespace["assert_security_attempt_rejected"] = lambda response, mode: events.append("classification")
        with self.assertRaises(AssertionError) as request_failure:
            namespace["submit_settings_attempt"] = lambda driver, mode: (
                events.append("request") or (_ for _ in ()).throw(RuntimeError("browser request failed"))
            )
            verify_attempt(object(), "missing", "original", "17", "missing-token")
        self.assertEqual(events, ["request", "state"])
        self.assertEqual(request_failure.exception.admin_security_substage, "request_execution")
        self.assertEqual(request_failure.exception.admin_security_request, "failed:RuntimeError")
        self.assertEqual(request_failure.exception.admin_security_state_recheck, "passed")
        self.assertEqual(request_failure.exception.admin_security_response, "not_evaluated")

    def test_security_fixtures_create_read_only_admin_and_two_disposable_customers(self):
        self.assertTrue(FIXTURE.is_file(), "the isolated security fixture seeder is missing")
        source = FIXTURE.read_text(encoding="utf-8")
        for marker in (
            "AdminBusinessProfile",
            "AdminDashboard",
            "updateLgcAccess",
            "'view'",
            "'edit'",
            "'add'",
            "'delete'",
            "reset-token-replay",
            "reset-token-expired",
            "example.invalid",
            "getenv('CI') === 'true'",
            "getenv('GITHUB_ACTIONS') === 'true'",
            "getenv('KURANEA_ISOLATED_CI') === '1'",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "CI_COMPOSE_PROJECT_NAME",
            "FILTER_VALIDATE_EMAIL",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        guard_start = source.index("getenv('CI') === 'true'")
        bootstrap = source.index("require_once '/var/www/html/config/config.inc.php';")
        first_profile_write = source.index("new Profile();")
        self.assertLess(guard_start, bootstrap)
        self.assertLess(bootstrap, first_profile_write)

    def test_reset_token_browser_flow_replays_consumed_token_and_expires_live_fixture(self):
        self.assertTrue(RESET_FLOW.is_file(), "the isolated reset-token browser flow is missing")
        source = RESET_FLOW.read_text(encoding="utf-8")
        for marker in (
            "REPLAY_CUSTOMER_EMAIL",
            "EXPIRED_CUSTOMER_EMAIL",
            'button[type="submit"][name="submit"]',
            "expire_reset_token_in_isolated_container",
            "validate_isolated_ci_compose_project",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "KURANEA_ISOLATED_CI",
            "assert_reset_link_rejected",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        expiry = source[source.index("def expire_reset_token_in_isolated_container") :]
        self.assertLess(
            expiry.index("validate_isolated_ci_compose_project()"),
            expiry.index("subprocess.run(command"),
        )

    def test_reset_browser_guards_loopback_shop_and_mailpit_before_any_reset_request(self):
        source = RESET_FLOW.read_text(encoding="utf-8")
        for marker in (
            "EXPECTED_SHOP_PORT = 18080",
            "EXPECTED_MAILPIT_PORT = 8025",
            "def validate_loopback_endpoints",
            "ipaddress.ip_address(host).is_loopback",
            "validate_isolated_ci_compose_project()",
            "validate_loopback_endpoints()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        run = source.split("def run()", 1)[1].split("\n\nif __name__", 1)[0]
        self.assertLess(run.index("validate_isolated_ci_compose_project()"), run.index("replay_scenario()"))
        self.assertLess(run.index("validate_loopback_endpoints()"), run.index("replay_scenario()"))

    def test_reset_endpoint_guard_rejects_remote_hosts_and_wrong_ports(self):
        namespace: dict[str, object] = {"ipaddress": ipaddress, "urlparse": urlparse}
        validate_endpoint = load_function(RESET_FLOW, "_validate_loopback_endpoint", namespace)
        self.assertEqual(
            validate_endpoint("http://localhost:18080", 18080, "SHOP_BASE_URL"),
            ("http", "localhost", 18080),
        )
        self.assertEqual(
            validate_endpoint("http://127.0.0.1:8025", 8025, "MAILPIT_API_URL"),
            ("http", "127.0.0.1", 8025),
        )
        for url, expected_port in (
            ("https://localhost:18080", 18080),
            ("http://shop.example:18080", 18080),
            ("http://127.0.0.1:18081", 18080),
            ("http://user@localhost:18080", 18080),
            ("http://localhost:18080/path", 18080),
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_endpoint(url, expected_port, "test endpoint")

    def test_reset_rejection_and_replay_require_native_customer_account_state(self):
        source = RESET_FLOW.read_text(encoding="utf-8")
        for marker in (
            'form.forgotten-password .alert.alert-danger',
            "password change request expired",
            "def assert_customer_can_login_with_password",
            "a.account-menu__link--signout",
            "assert_customer_can_login_with_password(REPLAY_EMAIL, password)",
            "expected_reset_path",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        replay = source.split("def replay_scenario()", 1)[1].split("def expiry_scenario()", 1)[0]
        self.assertLess(
            replay.index("assert_customer_can_login_with_password(REPLAY_EMAIL, password)"),
            replay.index("assert_reset_link_rejected("),
        )

    def test_reset_rejection_marker_matches_native_expiry_error_not_generic_alerts(self):
        marker = load_function(RESET_FLOW, "is_native_expired_reset_message", {})
        self.assertTrue(marker("The password change request expired. You should ask for a new one."))
        self.assertTrue(marker("パスワード変更リクエストの有効期限が切れました。"))
        self.assertTrue(marker("비밀번호 변경 요청이 만료되었습니다."))
        self.assertFalse(marker("Page not found"))
        self.assertFalse(marker("Your email address is invalid."))


if __name__ == "__main__":
    unittest.main()
