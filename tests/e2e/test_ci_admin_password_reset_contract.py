"""Safety and behavior contracts for isolated Back Office recovery QA."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


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
