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

        self.assertIn("def assert_korean_email_login_form", browser_flow)
        self.assertIn("assert_korean_email_login_form(driver)", browser_flow)
        browser_check = browser_flow.split("def assert_korean_email_login_form", 1)[1].split(
            "\n\ndef ", 1
        )[0]
        for assertion in (
            'driver.get(f"{BASE}/ko/login")',
            'assert_canonical_static_route(driver, "ko/login")',
            'visible(driver, "#login-form")',
            'visible(driver, \'#login-form input[name="email"]\')',
            'get_attribute("type") != "email"',
            'document_language.startswith("ko")',
            ".accessible_name",
            "KOREAN_EMAIL_ACCESSIBLE_NAME.search(email_accessible_name)",
            "USER_ID_LOOKUP_ACCESSIBLE_NAME.search(email_accessible_name)",
            "PASSWORD_RESET_ACCESSIBLE_NAME.search(password_reset_name)",
            "USER_ID_LOOKUP_ACCESSIBLE_NAME.search(password_reset_name)",
        ):
            self.assertIn(assertion, browser_check)
        self.assertIn("korean-login-email", browser_flow)

        self.assertIn('href="{$urls.pages.password}"', login_template)
        self.assertIn("Forgot your password?", login_template)
        self.assertNotIn("username recovery", login_template.casefold())
        self.assertNotIn("아이디 찾기", login_template)


if __name__ == "__main__":
    unittest.main()
