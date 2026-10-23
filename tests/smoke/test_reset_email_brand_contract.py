"""Keep password-reset email branding independently verifiable in isolated CI."""
from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EMAIL_BROWSER = ROOT / "tests" / "e2e" / "verify_reset_email_brand_browser.py"
CUSTOMER_SEED = ROOT / "tests" / "business_profile" / "seed_reset_email_customer.php"
BRAND_MANIFEST = ROOT / "assets" / "brand" / "ordenowa" / "asset-manifest.json"
FRESH_INSTALL_WORKFLOW = ROOT / ".github" / "workflows" / "fresh-install.yml"


class ResetEmailBrandContractTests(unittest.TestCase):
    def test_run_scoped_seed_uses_current_published_logo_and_never_live_mail(self) -> None:
        self.assertTrue(CUSTOMER_SEED.is_file())
        seed = CUSTOMER_SEED.read_text(encoding="utf-8")
        for source in (
            "new Customer()",
            "Configuration::get('PS_LOGO_MAIL'",
            "PublishedProfileProvider",
            "email_logo",
            "example.invalid",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
        ):
            with self.subTest(source=source):
                self.assertIn(source, seed)

    def test_seed_requires_the_approved_original_logo_hash_for_source_and_email_derivative(self) -> None:
        manifest = json.loads(BRAND_MANIFEST.read_text(encoding="utf-8"))
        approved_hash = manifest["sources_sha256"]["ORDENOWA-logo.png"]
        seed = CUSTOMER_SEED.read_text(encoding="utf-8")
        approved_hash_literal = re.search(
            r"\$approvedPrimaryLogoHash\s*=\s*'([a-f0-9]{64})';", seed
        )

        self.assertIsNotNone(approved_hash_literal, "email seed must pin the ZIP-approved primary logo SHA")
        assert approved_hash_literal is not None
        self.assertEqual(approved_hash_literal.group(1), approved_hash)
        for source in (
            "/opt/ordenowa-brand/asset-manifest.json",
            "/opt/ordenowa-brand/official_originals/ORDENOWA-logo.png",
            "sources_sha256",
            "ORDENOWA-logo.png",
            "hash_file('sha256', $officialLogoPath)",
            "hash_equals($approvedPrimaryLogoHash, $manifestPrimaryLogoHash)",
            "hash_equals($approvedPrimaryLogoHash, $officialLogoHash)",
            "brand']['sources']['primary_logo']['sha256",
            "preg_match('~\\Aimg/ordenowa/versions/([a-f0-9]{64})/",
            "$emailLogoMatches[1]",
            "hash_equals($approvedPrimaryLogoHash, $publishedPrimaryLogoHash)",
            "hash_equals($approvedPrimaryLogoHash, $emailLogoMatches[1])",
        ):
            with self.subTest(source=source):
                self.assertIn(source, seed)

    def test_reset_email_step_is_independent_of_later_brand_browser_failure(self) -> None:
        workflow = FRESH_INSTALL_WORKFLOW.read_text(encoding="utf-8")
        email_step = workflow.split(
            "- name: Verify the published ORDENOWA password-reset email logo in Chromium", 1
        )[1].split("- name:", 1)[0]

        self.assertIn("if: always() && !cancelled()", email_step)
        self.assertIn("steps.compose_up.outcome == 'success'", email_step)
        self.assertIn("steps.mailpit_setup.outcome == 'success'", email_step)
        self.assertIn("steps.chromium_setup.outcome == 'success'", email_step)
        self.assertNotIn("steps.brand_browser_qa.outcome", email_step)

    def test_reset_email_failure_diagnostics_are_redacted_ci_annotations(self) -> None:
        workflow = FRESH_INSTALL_WORKFLOW.read_text(encoding="utf-8")
        email_step = workflow.split(
            "- name: Verify the published ORDENOWA password-reset email logo in Chromium", 1
        )[1].split("- name:", 1)[0]
        browser = EMAIL_BROWSER.read_text(encoding="utf-8")
        failure_handler = browser.split("except Exception as error:", 1)[1].split(
            "finally:", 1
        )[0]

        self.assertNotIn("safe_state_line=$(rg", email_step)
        self.assertIn("emit_reset_email_logo_safe_state(message)", failure_handler)
        self.assertIn('::error title=ORDENOWA reset-email logo state::', browser)
        self.assertIn('annotation = safe_state.replace("%", "%25").replace("\\r", "%0D").replace("\\n", "%0A")', browser)

    def test_mailpit_logo_is_byte_checked_against_published_derivative_and_rendered_in_chromium(self) -> None:
        self.assertTrue(EMAIL_BROWSER.is_file())
        browser = EMAIL_BROWSER.read_text(encoding="utf-8")
        for assertion in (
            '"cid:shop_logo"',
            'attachment.get("ContentID", "")',
            'inline_logo.get("ContentType") != "image/png"',
            "inline_sha256 = hashlib.sha256(sent_logo).hexdigest()",
            "published_sha256 = hashlib.sha256(expected_logo).hexdigest()",
            "naturalWidth",
            "is_displayed()",
            'password-reset-email-logo.png',
        ):
            with self.subTest(assertion=assertion):
                self.assertIn(assertion, browser)

    def test_mailpit_logo_assertions_report_safe_named_substages(self) -> None:
        browser = EMAIL_BROWSER.read_text(encoding="utf-8")
        assertion = browser.split("def assert_published_inline_logo(", 1)[1].split(
            "\ndef render_captured_logo", 1
        )[0]
        expected_stages = (
            'stage_callback("mailpit_html_cid")',
            'stage_callback("published_public_png")',
            'stage_callback("mailpit_inline_content_id")',
            'stage_callback("mailpit_inline_mime")',
            'stage_callback("mailpit_inline_part_identifiers")',
            'stage_callback("mailpit_inline_part_fetch")',
            'stage_callback("published_inline_hash_compare")',
            'stage_callback("mailpit_html_img_element")',
        )
        for stage in expected_stages:
            with self.subTest(stage=stage):
                self.assertIn(stage, assertion)
        positions = [assertion.index(stage) for stage in expected_stages]
        self.assertEqual(sorted(positions), positions, "email logo diagnostics should follow the assertion flow")
        self.assertIn('ORDENOWA_EMAIL_LOGO_HASH_MISMATCH=', assertion)
        self.assertIn('"published_sha256": published_sha256', assertion)
        self.assertIn('"inline_sha256": inline_sha256', assertion)
        self.assertIn('stage = "mailpit_message_lookup"', browser)
        self.assertIn("assert_published_inline_logo(message, set_logo_assertion_stage)", browser)

    def test_failure_state_reports_only_mailpit_logo_structure_booleans(self) -> None:
        browser = EMAIL_BROWSER.read_text(encoding="utf-8")
        tree = ast.parse(browser)
        safe_state_function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "reset_email_logo_safe_state"
        )
        returned_dictionary = next(
            node.value for node in ast.walk(safe_state_function)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        )
        safe_state_keys = [key.value for key in returned_dictionary.keys if isinstance(key, ast.Constant)]
        self.assertEqual(
            safe_state_keys,
            [
                "html_is_string",
                "html_nonempty",
                "html_has_shop_logo_cid",
                "inline_is_list",
                "inline_part_count",
                "shop_logo_inline_part_present",
                "shop_logo_inline_part_is_png",
            ],
            "failure annotations may report only the approved structural booleans and bounded count",
        )
        safe_state = ast.get_source_segment(browser, safe_state_function) or ""
        self.assertIn('ORDENOWA_RESET_EMAIL_SAFE_STATE=', browser)
        self.assertNotIn('"HTML":', safe_state)
        self.assertNotIn('"To":', safe_state)
        self.assertNotIn('"email"', safe_state.lower())
        emitter = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "emit_reset_email_logo_safe_state"
        )
        emitter_source = ast.get_source_segment(browser, emitter) or ""
        self.assertIn("reset_email_logo_safe_state(message)", emitter_source)
        self.assertIn("json.dumps(", emitter_source)
        self.assertIn("file=sys.stderr", emitter_source)
        self.assertIn('f"::error title=ORDENOWA reset-email logo state::{annotation}"', emitter_source)
        self.assertIn("flush=True", emitter_source)

    def test_password_reset_request_is_independent_of_the_full_account_browser(self) -> None:
        browser = EMAIL_BROWSER.read_text(encoding="utf-8")
        run_function = browser.split("def run() -> bool:", 1)[1].split("if __name__ ==", 1)[0]

        self.assertIn('driver.get(f"{BASE}/")', run_function)
        self.assertIn("shop_url_from_generated_link(driver, sign_in_link, \"customer sign-in\")", run_function)
        self.assertIn("driver.get(login_url)", run_function)
        self.assertIn("#login-form a[href]", run_function)
        self.assertIn("shop_url_from_generated_link(driver, reset_link, \"password reset\")", run_function)
        self.assertNotIn('driver.get(f"{BASE}/index.php?controller=password")', run_function)
        self.assertIn('By.CSS_SELECTOR, "#email"', run_function)
        self.assertIn('By.CSS_SELECTOR, "#send-reset-link"', run_function)
        self.assertIn("request_message_for_customer()", run_function)
        self.assertNotIn("verify_customer_account_browser.py", browser)


if __name__ == "__main__":
    unittest.main()
