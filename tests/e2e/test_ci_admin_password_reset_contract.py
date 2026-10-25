"""Safety and behavior contracts for isolated Back Office recovery QA."""

from __future__ import annotations

import importlib.util
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests" / "e2e" / "verify_ci_admin_password_reset_browser.py"


def load_script():
    if not SCRIPT.is_file():
        raise AssertionError("the isolated Back Office password recovery browser test is missing")
    spec = importlib.util.spec_from_file_location("ordenowa_admin_password_reset", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("the Back Office password recovery browser test cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdminPasswordResetContractTests(unittest.TestCase):
    def test_login_route_accepts_only_canonical_and_index_php_paths_on_admin_origin(self):
        module = load_script()
        self.assertTrue(
            hasattr(module, "is_admin_login_route"),
            "native reset completion must recognize the exact PrestaShop login route variants",
        )
        admin_url = "http://localhost:18080/admin-kuranea"
        for candidate in (
            "http://localhost:18080/admin-kuranea/login",
            "http://localhost:18080/admin-kuranea/index.php/login",
        ):
            with self.subTest(candidate=candidate):
                self.assertTrue(module.is_admin_login_route(candidate, admin_url))

        for candidate in (
            "https://localhost:18080/admin-kuranea/login",
            "http://outside.example:18080/admin-kuranea/login",
            "http://localhost:18081/admin-kuranea/login",
            "http://localhost:18080/admin-kuranea-evil/login",
            "http://localhost:18080/admin-kuranea/index.php/login/extra",
            "http://localhost:18080/admin-kuranea/unexpected/login",
        ):
            with self.subTest(candidate=candidate):
                self.assertFalse(module.is_admin_login_route(candidate, admin_url))

    def test_login_page_check_requires_visible_form_on_an_exact_login_route(self):
        module = load_script()
        self.assertTrue(
            hasattr(module, "is_admin_login_page"),
            "a route match must also require the real visible Back Office login form",
        )

        class Form:
            def __init__(self, visible):
                self.visible = visible

            def is_displayed(self):
                return self.visible

        class Driver:
            def __init__(self, current_url, visible):
                self.current_url = current_url
                self.form = Form(visible)

            def find_elements(self, by, selector):
                return [self.form] if selector == "#login_form" else []

        admin_url = "http://localhost:18080/admin-kuranea"
        self.assertTrue(
            module.is_admin_login_page(
                Driver("http://localhost:18080/admin-kuranea/index.php/login", True),
                admin_url,
            )
        )
        self.assertFalse(
            module.is_admin_login_page(
                Driver("http://localhost:18080/admin-kuranea/login", False),
                admin_url,
            )
        )
        self.assertFalse(
            module.is_admin_login_page(
                Driver("http://outside.example:18080/admin-kuranea/login", True),
                admin_url,
            )
        )

    def test_native_reset_failure_gate_accepts_assertion_and_non_assertion_errors(self):
        module = load_script()
        self.assertTrue(
            hasattr(module, "should_capture_native_reset_diagnostic"),
            "native reset form diagnostics must not filter caught failures by exception subtype",
        )
        expected_url = "http://localhost:18080/admin-kuranea/index.php/reset-password/" + ("a" * 40)
        for error in (AssertionError("safe"), ValueError("safe"), TimeoutError("safe")):
            with self.subTest(error_type=type(error).__name__):
                self.assertTrue(
                    module.should_capture_native_reset_diagnostic(
                        "native_reset_form",
                        error,
                        object(),
                        expected_url,
                    )
                )
        for stage in ("old_password_rejected", "new_password_login"):
            with self.subTest(stage=stage):
                self.assertEqual(
                    stage == "old_password_rejected",
                    module.should_capture_native_reset_diagnostic(
                        stage,
                        ValueError("safe"),
                        object(),
                        expected_url,
                    ),
                )

    def test_old_password_rejection_waits_for_a_visible_error_response(self):
        module = load_script()
        self.assertTrue(
            hasattr(module, "old_password_rejection_visible"),
            "old-password QA must wait for the submitted rejection response, not the already-visible login form",
        )

        class Element:
            def __init__(self, visible):
                self.visible = visible

            def is_displayed(self):
                return self.visible

        class Driver:
            def __init__(self, selectors, current_url="http://localhost:18080/admin-kuranea/index.php/login"):
                self.selectors = selectors
                self.current_url = current_url

            def find_elements(self, by, selector):
                return self.selectors.get(selector, [])

        self.assertFalse(
            module.old_password_rejection_visible(
                Driver({"#login_form": [Element(True)], ".alert.alert-danger": []}),
                "http://localhost:18080/admin-kuranea",
            ),
            "a visible form before the POST response must not count as old-password rejection",
        )
        self.assertTrue(
            module.old_password_rejection_visible(
                Driver({"#login_form": [Element(True)], ".alert.alert-danger": [Element(True)]}),
                "http://localhost:18080/admin-kuranea",
            ),
            "the submitted login error should prove the old password was rejected",
        )
        self.assertFalse(
            module.old_password_rejection_visible(
                Driver({"#login_form": [Element(False)], ".alert.alert-danger": []}),
                "http://localhost:18080/admin-kuranea",
            ),
            "an accepted old password must not be classified as rejected",
        )
        self.assertFalse(
            module.old_password_rejection_visible(
                Driver(
                    {"#login_form": [Element(True)], ".alert.alert-danger": [Element(True)]},
                    "http://localhost:18080/admin-kuranea/index.php/dashboard",
                ),
                "http://localhost:18080/admin-kuranea",
            ),
            "a danger alert outside the canonical Back Office login route must not count as rejection",
        )

    def test_old_password_attempt_starts_from_a_clean_page_after_its_final_navigation(self):
        module = load_script()
        self.assertTrue(
            hasattr(module, "assert_no_login_error_before_submit"),
            "old-password rejection must not be inferred from a stale alert loaded before the credential POST",
        )

        class Element:
            def __init__(self, visible):
                self.visible = visible

            def is_displayed(self):
                return self.visible

        self.assertIsNone(module.assert_no_login_error_before_submit(
            type("Driver", (), {"find_elements": lambda self, by, selector: []})()
        ))
        with self.assertRaisesRegex(AssertionError, "clean login page"):
            module.assert_no_login_error_before_submit(
                type(
                    "Driver",
                    (),
                    {"find_elements": lambda self, by, selector: [Element(True)] if selector == ".alert.alert-danger" else []},
                )()
            )

        source = SCRIPT.read_text(encoding="utf-8")
        fill_login = source.split("def fill_login(", 1)[1].split("\n\ndef write_safe_log", 1)[0]
        stage = source.split('stage = "old_password_rejected"', 1)[1].split(
            'stage = "new_password_login"', 1
        )[0]
        self.assertIn("require_clean_page", fill_login)
        self.assertIn("assert_no_login_error_before_submit(driver)", fill_login)
        self.assertIn("require_clean_page=True", stage)
        self.assertLess(fill_login.index("driver.get("), fill_login.index("assert_no_login_error_before_submit(driver)"))
        self.assertLess(fill_login.index("password_input.send_keys(password)"), fill_login.index("assert_no_login_error_before_submit(driver)"))
        self.assertLess(fill_login.index("assert_no_login_error_before_submit(driver)"), fill_login.index(".click()"))

    def test_failure_screenshot_is_saved_only_after_all_sensitive_form_fields_are_cleared(self):
        module = load_script()
        self.assertTrue(
            hasattr(module, "clear_sensitive_form_values_before_screenshot"),
            "password reset failure captures must clear both login and reset-form password values",
        )

        class Driver:
            current_url = "http://localhost:18080/admin-kuranea/index.php/login"

            def __init__(self, mask_result):
                self.mask_result = mask_result
                self.mask_script = ""
                self.mask_scripts = []
                self.save_calls = 0

            def execute_script(self, script):
                if script == "return document.readyState":
                    return "complete"
                self.mask_script = script
                self.mask_scripts.append(script)
                return self.mask_result

            def find_elements(self, by, selector):
                return []

            def save_screenshot(self, filename):
                self.save_calls += 1
                Path(filename).write_bytes(b"synthetic screenshot")
                return True

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            driver = Driver(False)
            output = StringIO()
            with redirect_stdout(output):
                state = module.capture_native_reset_failure_diagnostic(
                    driver,
                    "http://localhost:18080/admin-kuranea",
                    directory,
                )
            self.assertEqual(driver.save_calls, 0)
            self.assertEqual(state["screenshot_saved"], "false")
            self.assertFalse((directory / "admin-password-reset-failure.png").exists())
            self.assertIn("ORDENOWA_ADMIN_RESET_FAILURE=", output.getvalue())

            mask_script = driver.mask_script
            for selector in (
                "#login_form input[type=\"email\"]",
                "#login_form input[type=\"password\"]",
                "form#reset_password_form input[type=\"password\"]",
            ):
                self.assertIn(selector, mask_script)
            self.assertIn("fields.length > 0", mask_script)
            self.assertIn("input.value === ''", mask_script)

    def test_native_reset_assertion_diagnostic_redacts_url_and_records_safe_state(self):
        module = load_script()
        self.assertTrue(
            hasattr(module, "capture_native_reset_failure_diagnostic"),
            "native reset form assertions must save and report bounded diagnostics before browser cleanup",
        )

        reset_token = "a" * 40

        class LoginForm:
            def is_displayed(self):
                return False

        class Driver:
            def __init__(self, screenshot_path: Path, current_url: str):
                self.screenshot_path = screenshot_path
                self.current_url = current_url
                self.credentials_masked = False
                self.credentials_masked_before_screenshot = False
                self.fields = {
                    '#login_form input[type="email"]': "customer@example.invalid",
                    '#login_form input[type="password"]': "old-secret",
                    'form#reset_password_form input[type="password"]': "new-secret",
                }

            def save_screenshot(self, filename: str) -> bool:
                self.credentials_masked_before_screenshot = self.credentials_masked
                if any(value != "" for value in self.fields.values()):
                    raise AssertionError("screenshot must wait until every sensitive field is empty")
                self.screenshot_path = Path(filename)
                self.screenshot_path.write_bytes(b"synthetic screenshot")
                return True

            def execute_script(self, script: str) -> str:
                if script == "return document.readyState":
                    self.assert_ready_query = True
                    return "complete"
                if all(
                    selector in script
                    for selector in self.fields
                ) and all(marker in script for marker in ("input.value = ''", "input.value === ''", "fields.length > 0")):
                    self.fields = {selector: "" for selector in self.fields}
                    self.credentials_masked = True
                    return True
                return False

            def find_elements(self, by: str, selector: str) -> list[LoginForm]:
                return [LoginForm()] if selector == "#login_form" else []

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            summary = directory / "step-summary.md"
            screenshot = directory / "not-used.png"
            driver = Driver(
                screenshot,
                "http://localhost:18080/admin-kuranea/index.php/login?token=query-secret&customer=private-id",
            )
            output = StringIO()
            with patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary)}), redirect_stdout(output):
                state = module.capture_native_reset_failure_diagnostic(
                    driver,
                    "http://localhost:18080/admin-kuranea",
                    directory,
                )

            expected_state = {
                "same_origin": "true",
                "pathname": "/admin-kuranea/index.php/login",
                "login_form_visible": "false",
                "document_ready": "complete",
                "login_route_match": "true",
                "dashboard_route_match": "false",
                "login_error_visible": "false",
                "screenshot": "admin-password-reset-failure.png",
                "screenshot_saved": "true",
            }
            self.assertEqual(state, expected_state)
            self.assertTrue((directory / "admin-password-reset-failure.png").is_file())
            self.assertEqual(driver.screenshot_path.name, "admin-password-reset-failure.png")
            self.assertTrue(driver.credentials_masked_before_screenshot)

            published = output.getvalue() + summary.read_text(encoding="utf-8")
            for value in (
                "same_origin=true",
                "document_ready=complete",
                "login_route_match=true",
                "dashboard_route_match=false",
                "login_error_visible=false",
            ):
                self.assertIn(value, published)
            self.assertIn("::error title=ORDENOWA native reset form diagnostics::", published)
            self.assertIn("admin-password-reset-failure.png", published)
            for secret in (reset_token, "query-secret", "private-id", "http://localhost:18080"):
                self.assertNotIn(secret, published)

    def test_native_reset_diagnostic_is_emitted_before_driver_quit(self):
        source = SCRIPT.read_text(encoding="utf-8")
        run = source.split("def run() -> bool:", 1)[1].split("\n\nif __name__", 1)[0]
        exception_handler = run[run.rindex("except Exception as error:") :].split("finally:", 1)[0]
        self.assertIn("should_capture_native_reset_diagnostic(stage, error, driver, reset_url)", exception_handler)
        capture_gate = source.split("def should_capture_native_reset_diagnostic(", 1)[1].split("\n\ndef run()", 1)[0]
        self.assertIn('stage in {"native_reset_form", "old_password_rejected"}', capture_gate)
        self.assertNotIn("isinstance(error, AssertionError)", exception_handler)
        self.assertIn("error_type = type(error).__name__", exception_handler)
        self.assertNotIn("str(error)", exception_handler)
        self.assertIn("capture_native_reset_failure_diagnostic(", exception_handler)
        self.assertLess(
            exception_handler.index("capture_native_reset_failure_diagnostic("),
            run.index("driver.quit()"),
        )

    def test_old_password_stage_waits_for_submitted_rejection_and_reports_safe_route_state(self):
        source = SCRIPT.read_text(encoding="utf-8")
        stage = source.split('stage = "old_password_rejected"', 1)[1].split(
            'stage = "new_password_login"', 1
        )[0]
        self.assertIn("old_password_rejection_visible(browser, admin_login_url)", stage)
        self.assertIn("require_clean_page=True", stage)
        self.assertNotIn("until(lambda browser: visible_login_form(browser))", stage)
        for expected in ("dashboard_route_match", "login_error_visible", "GITHUB_STEP_SUMMARY"):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_artifacts_are_confined_to_the_actions_runner_temp_directory(self):
        module = load_script()
        self.assertTrue(
            hasattr(module, "validate_artifact_directory"),
            "the browser test must fail closed before writing artifacts outside RUNNER_TEMP",
        )
        self.assertEqual(
            module.validate_artifact_directory(
                "/tmp/actions/ordenowa-browser-qa",
                "/tmp/actions",
            ),
            Path("/tmp/actions/ordenowa-browser-qa"),
        )
        for candidate in ("", "relative/path", "/tmp/elsewhere/qa"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    module.validate_artifact_directory(candidate, "/tmp/actions")

    def test_fixture_result_is_run_scoped_and_never_contains_credentials_or_tokens(self):
        module = load_script()
        result = module.parse_fixture_result(
            'ORDENOWA_ADMIN_RECOVERY_FIXTURE={"employee_id":42,"email":"ordenowa-admin-recovery-12345-2-a1b2c3d4@example.invalid"}\n',
            "ordenowa-admin-recovery-12345-2-a1b2c3d4@example.invalid",
            "12345",
            "2",
        )
        self.assertEqual(result, {"employee_id": 42, "email": "ordenowa-admin-recovery-12345-2-a1b2c3d4@example.invalid"})

        for payload in (
            {"employee_id": 1, "email": "ordenowa-admin-recovery-12345-2-a1b2c3d4@example.invalid"},
            {
                "employee_id": 42,
                "email": "ordenowa-admin-recovery-12345-2-a1b2c3d4@example.invalid",
                "password": "must-not-escape",
            },
            {"employee_id": 42, "email": "ordenowa-admin-recovery-99999-2-a1b2c3d4@example.invalid"},
        ):
            with self.subTest(payload=payload):
                line = "ORDENOWA_ADMIN_RECOVERY_FIXTURE=" + module.json.dumps(payload) + "\n"
                with self.assertRaises(ValueError):
                    module.parse_fixture_result(
                        line,
                        "ordenowa-admin-recovery-12345-2-a1b2c3d4@example.invalid",
                        "12345",
                        "2",
                    )

    def test_mailpit_reset_link_must_match_exact_recipient_and_admin_route(self):
        module = load_script()
        email = "ordenowa-admin-recovery-12345-2-a1b2c3d4@example.invalid"
        reset_url = "http://localhost:18080/admin-kuranea/index.php/reset-password/" + ("a" * 40)
        message = {
            "To": [{"Address": email, "Name": ""}],
            "HTML": f'<a href="{reset_url}">Reset password</a>',
            "Text": "",
        }
        try:
            actual_reset_url = module.reset_url_from_mailpit_message(
                message,
                email,
                "http://localhost:18080/admin-kuranea",
            )
        except ValueError as error:
            self.fail(f"the generated PrestaShop employee reset path was rejected: {error}")
        self.assertEqual(actual_reset_url, reset_url)

        wrong_recipient_message = {
            **message,
            "To": [{"Address": "ordenowa-admin-reset-12345-2-a1b2c3d5@example.invalid", "Name": ""}],
        }
        self.assertIsNone(
            module.reset_url_from_mailpit_message(
                wrong_recipient_message,
                email,
                "http://localhost:18080/admin-kuranea",
            )
        )

        for wrong_message in (
            {**message, "HTML": f'<a href="https://outside.example/admin-kuranea/index.php/reset-password/{"a" * 40}">Reset</a>'},
            {**message, "HTML": f'<a href="http://localhost:18080/admin-kuranea-evil/index.php/reset-password/{"a" * 40}">Reset</a>'},
        ):
            with self.subTest(message=wrong_message):
                with self.assertRaises(ValueError):
                    module.reset_url_from_mailpit_message(
                        wrong_message,
                        email,
                        "http://localhost:18080/admin-kuranea",
                    )

    def test_run_guard_accepts_only_the_exact_local_actions_services(self):
        module = load_script()
        env = {
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "KURANEA_ISOLATED_CI": "1",
            "GITHUB_RUN_ID": "12345",
            "GITHUB_RUN_ATTEMPT": "2",
            "CI_COMPOSE_PROJECT_NAME": "kuranea-ci-12345-2",
            "SHOP_BASE_URL": "http://localhost:18080",
            "ADMIN_LOGIN_URL": "http://localhost:18080/admin-kuranea",
            "MAILPIT_API_URL": "http://127.0.0.1:8025",
            "ADMIN_RECOVERY_EMAIL": "ordenowa-admin-recovery-12345-2-a1b2c3d4@example.invalid",
            "ADMIN_MAIL": "ci-ordenowa@example.invalid",
            "ADMIN_PASSWD": "ci-only-test-password",
        }
        self.assertEqual(module.validate_isolated_environment(env)["compose_project"], "kuranea-ci-12345-2")
        for key, value in (
            ("CI_COMPOSE_PROJECT_NAME", "shared-dev-project"),
            ("SHOP_BASE_URL", "https://shop.example.test"),
            ("MAILPIT_API_URL", "http://localhost:8026"),
            ("ADMIN_LOGIN_URL", "http://outside.example/admin-kuranea"),
        ):
            invalid = env | {key: value}
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    module.validate_isolated_environment(invalid)

    def test_browser_flow_proves_old_password_rejection_and_new_dashboard_login(self):
        source = SCRIPT.read_text(encoding="utf-8") if SCRIPT.is_file() else ""
        self.assertIn("stage = \"old_password_rejected\"", source)
        self.assertIn("stage = \"new_password_login\"", source)
        self.assertIn("AdminDashboard", source)
        self.assertIn("reset_password_form", source)
        self.assertIn("forgot_password_form", source)
        self.assertNotIn("print(reset_url", source)
        self.assertNotIn("print(new_password", source)


if __name__ == "__main__":
    unittest.main()
