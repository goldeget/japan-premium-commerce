"""Guard the rendered Korean login's email identifier and password recovery wording."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class KoreanCustomerLoginContractTests(unittest.TestCase):
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
        self.assertIn("assert_korean_email_login_form(driver)", browser_flow)
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


if __name__ == "__main__":
    unittest.main()
