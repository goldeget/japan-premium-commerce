"""Guard the rendered Korean login's email identifier and password recovery wording."""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[2]


class KoreanCustomerLoginContractTests(unittest.TestCase):
    def test_safe_url_metadata_reports_route_shape_without_query_values(self) -> None:
        browser_flow_path = ROOT / "tests" / "e2e" / "verify_customer_account_browser.py"
        syntax_tree = ast.parse(browser_flow_path.read_text(encoding="utf-8"))
        helper_nodes = [
            node
            for node in syntax_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"safe_same_origin_path", "safe_url_metadata"}
        ]
        namespace = {
            "BASE": "https://shop.example.test",
            "parse_qs": parse_qs,
            "re": re,
            "unquote": unquote,
            "urlparse": urlparse,
        }
        compiled_helpers = compile(
            ast.Module(body=helper_nodes, type_ignores=[]),
            str(browser_flow_path),
            "exec",
        )
        exec(compiled_helpers, namespace)

        metadata = namespace["safe_url_metadata"](
            "https://shop.example.test/ログイン?controller=authentication&id_lang=3&token=secret-token&email=private%40example.test"
        )
        self.assertTrue(metadata["same_origin"])
        self.assertTrue(metadata["id_lang_present"])
        self.assertTrue(metadata["controller_present"])
        self.assertTrue(metadata["path_has_non_ascii"])
        self.assertEqual(metadata["path"], "/<redacted>")
        self.assertEqual(metadata["query_key_names"], ["controller", "id_lang"])
        self.assertNotIn("secret-token", repr(metadata))
        self.assertNotIn("private@example.test", repr(metadata))
        self.assertEqual(
            namespace["safe_same_origin_path"]("https://shop.example.test/a7"),
            "/<redacted>",
        )
        self.assertEqual(
            namespace["safe_same_origin_path"]("https://shop.example.test/ko/identity"),
            "/ko/identity",
        )
        self.assertFalse(
            namespace["safe_url_metadata"]("https://other.example.test/login")["same_origin"]
        )

    def test_account_browser_checks_korean_email_login_and_separate_password_recovery(self) -> None:
        browser_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(
            encoding="utf-8"
        )
        login_template = (
            ROOT / "themes" / "hummingbird" / "templates" / "customer" / "_partials" / "login-form.tpl"
        ).read_text(encoding="utf-8")
        language_template = (
            ROOT / "themes" / "hummingbird" / "modules" / "ps_languageselector" / "ps_languageselector.tpl"
        ).read_text(encoding="utf-8")
        signin_template = (
            ROOT / "themes" / "hummingbird" / "modules" / "ps_customersignin" / "ps_customersignin.tpl"
        ).read_text(encoding="utf-8")
        form_fields_template = (
            ROOT / "themes" / "hummingbird" / "templates" / "_partials" / "form-fields.tpl"
        ).read_text(encoding="utf-8")

        self.assertIn("def assert_korean_email_login_form", browser_flow)
        self.assertIn("assert_korean_email_login_form(driver, korean_login_state)", browser_flow)
        browser_check = browser_flow.split("def assert_korean_email_login_form", 1)[1].split(
            "\n\ndef ", 1
        )[0]
        for assertion in (
            'driver.get(f"{BASE}/")',
            'select.js-language-selector option[data-iso-code="ko"]',
            'driver.get(korean_language_url)',
            "#_desktop_ps_customersignin a[href], #_mobile_ps_customersignin a[href]",
            'driver.get(login_url)',
            'visible(driver, "#login-form")',
            'visible(driver, \'#login-form input[type="email"]\')',
            'get_attribute("name") != "email"',
            'get_attribute("type") != "email"',
            'document_language.startswith("ko")',
            'get_attribute("aria-label")',
            'label.get_attribute("for") == email_field_id',
            "aria_label or visible_label",
            "KOREAN_EMAIL_ACCESSIBLE_NAME.search(email_accessible_name)",
            "USER_ID_LOOKUP_ACCESSIBLE_NAME.search(email_accessible_name)",
            "PASSWORD_RESET_ACCESSIBLE_NAME.search(password_reset_name)",
            "USER_ID_LOOKUP_ACCESSIBLE_NAME.search(password_reset_name)",
        ):
            self.assertIn(assertion, browser_check)
        accessible_name_pattern = browser_flow.split(
            "KOREAN_EMAIL_ACCESSIBLE_NAME = re.compile(", 1
        )[1].split(")", 1)[0]
        for korean_email_term in ("이메일", r"전자\s*우편", r"메일\s*주소"):
            self.assertIn(korean_email_term, accessible_name_pattern)
        self.assertNotIn("e[", accessible_name_pattern.casefold())
        self.assertIn("korean-login-email", browser_flow)

        self.assertIn('select class="form-select js-language-selector"', language_template)
        self.assertIn('data-iso-code="{$language.iso_code}"', language_template)
        self.assertIn('{url entity=\'language\' id=$language.id_lang}', language_template)
        self.assertIn("{$urls.pages.authentication}", signin_template)
        self.assertIn('id="login-form"', login_template)
        self.assertIn('aria-label="{$field.label}"', form_fields_template)
        self.assertIn('for="{$id_prefix}field-{$field.name}"', form_fields_template)
        self.assertNotIn('driver.get(f"{BASE}/ko/login")', browser_check)
        self.assertIn('href="{$urls.pages.password}"', login_template)
        self.assertIn("Forgot your password?", login_template)
        self.assertNotIn("username recovery", login_template.casefold())
        self.assertNotIn("아이디 찾기", login_template)

    def test_korean_login_timeout_reports_the_exact_wait_and_safe_rendered_page_state(self) -> None:
        browser_flow = (ROOT / "tests" / "e2e" / "verify_customer_account_browser.py").read_text(
            encoding="utf-8"
        )
        workflow = (ROOT / ".github" / "workflows" / "fresh-install.yml").read_text(encoding="utf-8")
        for stage in (
            "korean_storefront_home",
            "korean_language_selector",
            "korean_language_destination",
            "korean_sign_in_link",
            "korean_login_page_navigation",
            "korean_login_form",
            "korean_email_field",
            "korean_password_reset_link",
        ):
            self.assertIn(stage, browser_flow)
        self.assertIn("def emit_korean_login_diagnostics", browser_flow)
        self.assertIn("def safe_url_metadata", browser_flow)
        self.assertIn('korean_login_state: dict[str, object]', browser_flow)
        self.assertIn('for key in (\n                "document_language",', browser_flow)
        self.assertIn('"ORDENOWA_KOREAN_LOGIN_SAFE_STATE="', browser_flow)
        self.assertIn('emit_korean_login_diagnostics(driver, korean_login_state)', browser_flow)
        self.assertIn('korean_login_diagnostics=$(rg \'^ORDENOWA_KOREAN_LOGIN_SAFE_STATE=\'', workflow)
        self.assertIn("ORDENOWA_KOREAN_LOGIN_SAFE_STATE", workflow)
        for transition_fact in (
            'state["language_url_metadata"] = safe_url_metadata(korean_language_url)',
            'state["sign_in_url_metadata"] = safe_url_metadata(login_url)',
            '"final_url_metadata": safe_url_metadata',
            '"email_label_document_language"',
            '"login_navigation_document_language"',
            '"failed_stage_elapsed_ms"',
            '"reset_link_before_wait_href_present"',
            '"reset_link_before_wait_visible"',
            '"reset_link_before_wait_computed_display"',
            '"reset_link_before_wait_computed_visibility"',
            '"reset_link_before_wait_text_length"',
            '"reset_link_before_wait_aria_label_text_length"',
            '"reset_link_before_wait_url_metadata"',
            '"reset_wait_navigation_elapsed_ms"',
            '"reset_wait_navigation_url_metadata"',
            '"reset_wait_navigation_document_language"',
            '"reset_link_navigation_timeline"',
            '"document_navigation_events"',
            "addEventListener('beforeunload'",
            "addEventListener('pagehide'",
            '"performance": "ALL"',
            '"query_key_names"',
            '"id_lang_present"',
            '"path_has_non_ascii"',
        ):
            self.assertIn(transition_fact, browser_flow)
        diagnostics = browser_flow.split("def emit_korean_login_diagnostics", 1)[1].split(
            "\n\ndef ", 1
        )[0]
        for safe_field in (
            '"path": safe_same_origin_path',
            '"document_language"',
            '"korean_language_option_count"',
            '"customer_sign_in_link_count"',
            '"login_form_visible"',
            '"email_field_visible"',
            '"email_label_present"',
            '"password_reset_link_count"',
        ):
            self.assertIn(safe_field, diagnostics)
        self.assertNotIn("password_value", diagnostics)
        self.assertNotIn('"text":', diagnostics)
        self.assertNotIn('"aria_label":', diagnostics)


if __name__ == "__main__":
    unittest.main()
