"""Contract checks for the isolated admin and native password-reset security flows."""

import ast
import ipaddress
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlparse


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
        self.assertGreaterEqual(source.count("assert_setting_unchanged("), 3)

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
            "bodyHasViewOnlyDenial",
            "status == 404",
            "response_url",
            "설정 초안을 수정할 권한이 없습니다.",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

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
