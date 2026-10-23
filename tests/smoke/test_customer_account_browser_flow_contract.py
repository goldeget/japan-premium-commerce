"""Lock in the ordered customer account browser flow without Docker."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse


ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_FLOW = ROOT / "tests" / "e2e" / "verify_customer_account_browser.py"


def stage_blocks(source: str) -> tuple[list[str], dict[str, str]]:
    """Return the source blocks delimited by run_viewport's stage assignments."""
    tree = ast.parse(source)
    run_viewport = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_viewport"
    )
    stages: list[tuple[int, str]] = []
    for node in ast.walk(run_viewport):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id != "stage" or not isinstance(node.value, ast.Constant):
            continue
        if isinstance(node.value.value, str):
            stages.append((node.lineno, node.value.value))

    stages.sort()
    lines = source.splitlines(keepends=True)
    blocks: dict[str, str] = {}
    for index, (line_number, stage) in enumerate(stages):
        end_line = stages[index + 1][0] - 1 if index + 1 < len(stages) else run_viewport.end_lineno
        blocks[stage] = "".join(lines[line_number - 1 : end_line])
    return [stage for _, stage in stages], blocks


class CustomerAccountBrowserFlowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ACCOUNT_FLOW.read_text(encoding="utf-8")
        cls.stages, cls.blocks = stage_blocks(cls.source)

    def test_registration_profile_email_login_and_reset_are_ordered(self) -> None:
        required_stages = (
            "registration_submit",
            "registration_post_submit",
            "profile_update_route",
            "profile_update_persist_wait",
            "email_login",
            "password_reset_request",
            "password_reset",
            "password_reset_old_password_rejected",
            "password_reset_login",
        )
        positions = [self.stages.index(stage) for stage in required_stages]
        self.assertEqual(positions, sorted(positions))

        registration = self.blocks["registration_post_submit"]
        self.assertIn("wait_for_registration_success(driver)", registration)
        self.assertIn('assert_my_page(driver, "CI")', registration)

        profile_route = self.blocks["profile_update_route"]
        self.assertIn('driver.get(f"{BASE}/index.php?controller=identity")', profile_route)
        self.assertIn('assert_canonical_static_route(driver, "identity")', profile_route)

        profile_save = self.blocks["profile_update_persist_wait"]
        self.assertIn("expected_first_name", profile_save)

    def test_email_login_and_logout_check_authenticated_and_signed_out_states(self) -> None:
        email_login = self.blocks["email_login"]
        self.assertIn("logout(driver)", email_login)
        self.assertIn('#login-form input[name="email"]', email_login)
        self.assertIn('get_attribute("type") != "email"', email_login)
        self.assertIn("assert_my_page(driver, f\"CI-{label.title()}\")", email_login)

        reset_request = self.blocks["password_reset_request"]
        self.assertIn("logout(driver)", reset_request)
        self.assertIn("reset_link_for(account_email, recovery_route_path)", reset_request)

        logout = self.source.split("def logout", 1)[1].split("def run_viewport", 1)[0]
        self.assertIn("visible_signout_link(driver)", logout)
        self.assertIn("driver.get(account_url)", logout)
        self.assertIn('#login-form input[name="email"]', logout)
        self.assertIn('By.ID, "identity_main_link"', logout)

    def test_registration_link_wait_has_its_own_failure_stage_after_korean_check(self) -> None:
        korean_check = self.blocks["korean_email_login_label"]
        self.assertIn("assert_korean_email_login_form(driver, korean_login_state)", korean_check)
        self.assertNotIn('driver.get(f"{BASE}/index.php?controller=authentication")', korean_check)
        registration = self.blocks["registration_link_load"]
        self.assertNotIn("driver.get(", registration)
        self.assertIn('visible(driver, \'a[data-link-action="display-register-form"]\')', registration)
        self.assertIn('set_registration_control(failure_control, "display-register-form", "anchor")', registration)
        validation = self.blocks["registration_link_validation"]
        self.assertIn('registration_link.get_attribute("href")', validation)
        self.assertIn("registration_location.hostname != base_location.hostname", validation)
        self.assertIn("click_centered(driver, registration_link)", self.blocks["registration_link_click"])

    def test_login_reuses_the_current_generated_route_without_direct_authentication_gets(self) -> None:
        self.assertNotIn('driver.get(f"{BASE}/index.php?controller=authentication")', self.source)
        self.assertNotIn('driver.get(f"{BASE}/index.php?controller=password")', self.source)
        for helper_name in ("submit_login", "assert_login_rejected"):
            helper = self.source.split(f"def {helper_name}", 1)[1].split("\n\ndef ", 1)[0]
            self.assertNotIn("driver.get(", helper)
            self.assertIn("fill(driver, '#login-form input[name=\"email\"]'", helper)
        old_password = self.blocks["password_reset_old_password_rejected"]
        self.assertLess(old_password.index("assert_my_page(driver,"), old_password.index("logout(driver)"))
        self.assertLess(old_password.index("logout(driver)"), old_password.index("assert_login_rejected(driver,"))

    def test_reset_email_matching_uses_the_rendered_localized_password_route(self) -> None:
        helper_nodes = [
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef) and node.name == "reset_link_matches_route"
        ]
        self.assertEqual(len(helper_nodes), 1)
        namespace = {
            "BASE": "https://shop.example.test",
            "parse_qs": parse_qs,
            "unquote": unquote,
            "urljoin": urljoin,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=helper_nodes, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )
        matches = namespace["reset_link_matches_route"]

        self.assertTrue(
            matches(
                "https://shop.example.test/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0"
                "?token=secure-key&reset_token=reset-secret&id_customer=12",
                "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
            )
        )
        self.assertFalse(
            matches(
                "https://shop.example.test/password-reset?token=secure-key&reset_token=reset-secret",
                "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
            )
        )
        self.assertFalse(
            matches(
                "https://attacker.example.test/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0"
                "?reset_token=reset-secret",
                "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
            )
        )
        self.assertFalse(
            matches(
                "https://shop.example.test/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
                "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0",
            )
        )

    def test_route_path_assertion_accepts_the_generated_encoded_locale_path(self) -> None:
        helper_nodes = [
            node
            for node in ast.parse(self.source).body
            if isinstance(node, ast.FunctionDef) and node.name == "assert_route_path_matches"
        ]
        self.assertEqual(len(helper_nodes), 1)
        namespace = {
            "BASE": "https://shop.example.test",
            "unquote": unquote,
            "urljoin": urljoin,
            "urlparse": urlparse,
        }
        exec(
            compile(ast.Module(body=helper_nodes, type_ignores=[]), str(ACCOUNT_FLOW), "exec"),
            namespace,
        )

        class FakeDriver:
            def __init__(self, current_url: str) -> None:
                self.current_url = current_url

        assert_route = namespace["assert_route_path_matches"]
        generated_path = "/%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8-%EC%B0%BE%EA%B8%B0"
        assert_route(
            FakeDriver("https://shop.example.test/비밀번호-찾기/"),
            generated_path,
            "password recovery",
        )
        with self.assertRaises(AssertionError):
            assert_route(
                FakeDriver("https://shop.example.test/password-reset"),
                generated_path,
                "password recovery",
            )
        with self.assertRaises(AssertionError):
            assert_route(
                FakeDriver("https://attacker.example.test/비밀번호-찾기"),
                generated_path,
                "password recovery",
            )

    def test_password_recovery_assertions_compare_against_the_generated_href_path(self) -> None:
        self.assertIn('recovery_route_path = urlparse(recovery_url).path', self.source)
        reset_request = self.blocks["password_reset_request"]
        self.assertIn('assert_route_path_matches(driver, recovery_route_path, "password recovery")', reset_request)
        self.assertIn("reset_link_for(account_email, recovery_route_path)", reset_request)
        reset = self.blocks["password_reset"]
        self.assertIn('assert_route_path_matches(driver, recovery_route_path, "password reset")', reset)
        self.assertNotIn('assert_canonical_static_route(driver, "password-reset")', self.source)

    def test_mailpit_reset_checks_captured_link_and_password_change_with_separate_logo_qa(self) -> None:
        reset_request = self.blocks["password_reset_request"]
        self.assertIn("reset_link_for(account_email, recovery_route_path)", reset_request)
        self.assertIn('visible(driver, "#login-form a[href]")', reset_request)
        self.assertIn('recovery_link.get_attribute("href")', reset_request)
        self.assertIn("recovery_location.hostname != base_location.hostname", reset_request)
        self.assertIn("click_centered(driver, recovery_link)", reset_request)
        self.assertIn('assert_route_path_matches(driver, recovery_route_path, "password recovery")', reset_request)
        self.assertNotIn('"cid:shop_logo"', reset_request)
        self.assertNotIn("ContentID", reset_request)
        self.assertNotIn("hashlib.sha256", reset_request)
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        self.assertLess(
            workflow.index("tests/e2e/verify_reset_email_brand_browser.py"),
            workflow.index("tests/e2e/verify_customer_account_browser.py"),
        )

        mailpit_helper = self.source.split("def reset_link_for", 1)[1].split("def visible", 1)[0]
        self.assertIn("/api/v1/messages?", mailpit_helper)
        self.assertIn("/api/v1/message/", mailpit_helper)
        route_matcher = self.source.split("def reset_link_matches_route", 1)[1].split("def reset_link_for", 1)[0]
        self.assertIn("same_shop_origin", route_matcher)
        self.assertIn("actual_path == expected_path", route_matcher)
        self.assertIn("has_reset_token", route_matcher)

        reset = self.blocks["password_reset"]
        self.assertIn("driver.get(reset_url)", reset)
        self.assertIn('assert_route_path_matches(driver, recovery_route_path, "password reset")', reset)
        self.assertIn('#field-password[name="passwd"]', reset)
        self.assertIn('#field-confirmation-passwd[name="confirmation"]', reset)

        old_password = self.blocks["password_reset_old_password_rejected"]
        self.assertIn("assert_login_rejected(driver, account_email, initial_password)", old_password)

        reset_login = self.blocks["password_reset_login"]
        self.assertIn("submit_login(driver, account_email, reset_password)", reset_login)
        self.assertIn("assert_my_page(driver, f\"CI-{label.title()}\")", reset_login)
        self.assertIn("logout(driver)", reset_login)

    def test_browser_flow_runs_on_desktop_and_mobile_viewports(self) -> None:
        self.assertIn('(1440, 960, "desktop")', self.source)
        self.assertIn('(390, 844, "mobile")', self.source)

    def test_profile_update_accepts_both_required_disclosures_before_valid_submit(self) -> None:
        required_stages = (
            "profile_update_current_password",
            "profile_update_required_disclosures",
            "profile_update_submit",
        )
        positions = [self.stages.index(stage) for stage in required_stages]
        self.assertEqual(positions, sorted(positions))

        disclosure_stage = self.blocks["profile_update_required_disclosures"]
        self.assertIn("accept_profile_update_disclosures(driver)", disclosure_stage)
        self.assertIn("assert_native_form_valid(driver, profile_form", disclosure_stage)

        disclosure_helper = self.source.split("def accept_profile_update_disclosures", 1)[1].split(
            "def assert_native_form_valid", 1
        )[0]
        self.assertIn('("customer_privacy", "psgdpr_consent_checkbox")', disclosure_helper)
        self.assertIn("checkbox.is_displayed()", disclosure_helper)
        self.assertIn("checkbox.is_enabled()", disclosure_helper)
        self.assertIn("if not checkbox.is_selected()", disclosure_helper)
        self.assertIn("checkbox.click()", disclosure_helper)
        self.assertIn("WebDriverWait(driver, 5, poll_frequency=0.1)", disclosure_helper)
        self.assertIn("lambda _browser: checkbox.is_selected()", disclosure_helper)
        self.assertIn("checkbox.send_keys(Keys.SPACE)", disclosure_helper)
        self.assertIn("if not checkbox.is_selected()", disclosure_helper)

        label_interaction = self.source.split("def click_required_checkbox_label", 1)[1].split(
            "def prepare_required_registration_fields", 1
        )[0]
        self.assertIn('form.find_elements(By.CSS_SELECTOR, "label[for]")', label_interaction)
        self.assertIn("candidate.get_attribute(\"for\") == checkbox_id", label_interaction)
        self.assertIn("label.click()", label_interaction)
        self.assertIn("checkbox.send_keys(Keys.SPACE)", label_interaction)

        customer_field_template = (
            ROOT / "themes" / "hummingbird" / "templates" / "_partials" / "form-fields.tpl"
        ).read_text(encoding="utf-8")
        self.assertIn('name="{$field.name}"', customer_field_template)
        self.assertIn('for="{$id_prefix}field-{$field.name}"', customer_field_template)
        psgdpr_template = (
            ROOT
            / "themes"
            / "hummingbird"
            / "modules"
            / "psgdpr"
            / "views"
            / "templates"
            / "hook"
            / "displayGDPRConsent.tpl"
        ).read_text(encoding="utf-8")
        self.assertIn('name="psgdpr_consent_checkbox"', psgdpr_template)
        self.assertIn('for="psgdpr_consent_checkbox_{$psgdpr_id_module|escape:', psgdpr_template)

        validity_helper = self.source.split("def assert_native_form_valid", 1)[1].split(
            "def submit_login", 1
        )[0]
        self.assertIn('find_elements(By.CSS_SELECTOR, ":invalid")', validity_helper)
        self.assertIn("arguments[0].checkValidity()", validity_helper)

        submit_stage = self.blocks["profile_update_submit"]
        self.assertIn("click_centered(driver, submit_button)", submit_stage)


if __name__ == "__main__":
    unittest.main()
