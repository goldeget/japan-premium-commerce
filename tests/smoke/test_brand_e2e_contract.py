"""Guard the real-browser contract for published official brand derivatives."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRAND_E2E = ROOT / "tests" / "e2e" / "verify_brand_admin_browser.py"
BRAND_PACK = ROOT / "assets" / "brand" / "ordenowa"
ADMIN_PROFILE_FORM = ROOT / "modules" / "kuraneabusinessprofile" / "src" / "Admin" / "AdminProfileForm.php"


class BrandE2EContractTests(unittest.TestCase):
    def test_browser_rejects_legacy_brand_in_rendered_customer_and_admin_pages(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        helper_start = browser_flow.index("def assert_no_legacy_brand_in_rendered_page(")
        helper_end = browser_flow.index("\ndef ", helper_start + 1)
        helper = browser_flow[helper_start:helper_end]
        published_assets = browser_flow.split("def assert_public_brand_assets(", 1)[1].split(
            "def assert_seller_disclosures_remain_gated", 1
        )[0]
        admin_login = browser_flow.split('stage = "admin_login_after_publish"', 1)[1].split(
            'print("PASS:', 1
        )[0]

        self.assertIn("document.body?.innerText", helper)
        self.assertIn("document.title", helper)
        self.assertIn("KURANEA", helper)
        self.assertIn("collect(visibleBody, 'visible_body')", helper)
        self.assertIn("assert_no_legacy_brand_in_rendered_page(driver, label + \" storefront\")", published_assets)
        self.assertIn('assert_no_legacy_brand_in_rendered_page(driver, "admin login")', admin_login)

    def test_customer_visible_legacy_brand_failure_reports_bounded_sanitized_matches(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        helper_start = browser_flow.index("def assert_no_legacy_brand_in_rendered_page(")
        helper_end = browser_flow.index("\ndef ", helper_start + 1)
        helper = browser_flow[helper_start:helper_end]
        sanitizer = browser_flow.split("def sanitize_brand_diagnostic_text(", 1)[1].split(
            "\ndef ", 1
        )[0]

        self.assertIn("document.title", helper)
        self.assertIn("document.body?.innerText", helper)
        self.assertIn("/kuranea/gi", helper)
        self.assertIn("matches", helper)
        self.assertIn("sanitize_brand_diagnostic_text", helper)
        self.assertIn("ORDENOWA_LEGACY_BRAND_MATCH=", helper)
        self.assertIn("::error title=ORDENOWA legacy brand visible text::", helper)
        self.assertIn("BRAND_DIAGNOSTIC_MAX_MATCHES", helper)
        self.assertIn("BRAND_DIAGNOSTIC_CONTEXT_CHARS", helper)
        self.assertIn("BRAND_DIAGNOSTIC_SNIPPET_CHARS", sanitizer)
        self.assertIn("[email]", sanitizer)
        self.assertIn("[url]", sanitizer)
        self.assertIn("[number]", sanitizer)

    def test_published_brand_assertions_report_distinct_failure_stages(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        published_assets = browser_flow.split("def assert_public_brand_assets(", 1)[1].split(
            "def assert_seller_disclosures_remain_gated", 1
        )[0]
        run_flow = browser_flow.split("def run()", 1)[1]

        self.assertIn('set_assertion_stage("header_logo_src_decode")', published_assets)
        self.assertIn('set_assertion_stage("visible_brand_text")', published_assets)
        self.assertIn('set_assertion_stage("public_asset_decode")', published_assets)
        self.assertIn('set_assertion_stage("public_asset_derivative_paths")', published_assets)
        self.assertIn('set_assertion_stage("metadata_contract")', published_assets)
        self.assertIn("def set_brand_assertion_stage(", run_flow)
        self.assertIn("nonlocal stage", run_flow)
        self.assertIn('stage_prefix="published_desktop_customer_brand"', run_flow)
        self.assertIn('stage_prefix="published_mobile_customer_brand"', run_flow)
        self.assertIn('stage_prefix="published_korean_customer_brand"', run_flow)

    def test_browser_validates_initial_approved_assets_before_upload(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        self.assertIn("def assert_initial_official_brand_assets(", browser_flow)
        initial_assertion = browser_flow.split("def assert_initial_official_brand_assets(", 1)[1].split(
            "\ndef ", 1
        )[0]
        run_flow = browser_flow.split("def run()", 1)[1]

        self.assertIn("assert_uploaded_derivative_url(", initial_assertion)
        self.assertIn("APPROVED_DERIVED_ASSETS", initial_assertion)
        self.assertIn("verify_browser_asset_bytes(", initial_assertion)
        for official_derivative in (
            "official-header-desktop.png",
            "official-header-mobile.png",
            "official-admin-login.png",
            "official-favicon.ico",
            "official-favicon-16.png",
            "official-favicon-32.png",
            "official-apple-touch-icon.png",
            "official-pwa-192.png",
            "official-pwa-512.png",
            "official-pwa-maskable-512.png",
            "official-og-brand.png",
        ):
            with self.subTest(official_derivative=official_derivative):
                self.assertIn(official_derivative, initial_assertion)

        baseline = run_flow.index('stage = "public_brand_baseline_before_draft"')
        assertion = run_flow.index("assert_initial_official_brand_assets(", baseline)
        upload = run_flow.index('stage = "official_asset_upload"', baseline)
        self.assertLess(assertion, upload)

    def test_browser_asserts_served_manifest_identity_and_launch_scope(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        public_snapshot = browser_flow.split("def public_brand_snapshot(", 1)[1].split(
            "def public_brand_slot_urls(", 1
        )[0]
        published_assets = browser_flow.split("def assert_public_brand_assets(", 1)[1].split(
            "def restore_approved_brand_icon_after_failure(", 1
        )[0]
        self.assertIn("def assert_manifest_base_path(", browser_flow)
        manifest_assertion = browser_flow.split("def assert_manifest_base_path(", 1)[1].split(
            "\ndef ", 1
        )[0]

        for field in ("id", "start_url", "scope"):
            with self.subTest(field=field):
                self.assertIn(f"{field}: manifest.{field} || ''", public_snapshot)
                self.assertIn(field, manifest_assertion)
        self.assertIn("urlparse(BASE).path", manifest_assertion)
        self.assertIn('for field in ("id", "start_url", "scope"):', manifest_assertion)
        self.assertIn("if manifest.get(field) != expected_path:", manifest_assertion)
        self.assertIn("assert_manifest_base_path(results[\"manifest\"])", published_assets)

    def test_browser_persists_seller_profile_fields_without_opening_disclosures(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")

        seller_profile_fields = (
            "profile[seller][legal_name][ja-JP]",
            "profile[seller][legal_name][en-US]",
            "profile[seller][legal_name][ko-KR]",
            "profile[seller][corporate_number]",
            "profile[seller][address][ja-JP]",
            "profile[seller][address][en-US]",
            "profile[seller][address][ko-KR]",
            "profile[seller][representative][ja-JP]",
            "profile[seller][representative][en-US]",
            "profile[seller][representative][ko-KR]",
            "profile[seller][responsible_person][ja-JP]",
            "profile[seller][responsible_person][en-US]",
            "profile[seller][responsible_person][ko-KR]",
            "profile[seller][support][phone]",
            "profile[seller][support][email]",
        )
        for field in seller_profile_fields:
            with self.subTest(field=field):
                self.assertIn(f'input[name="{field}"]', browser_flow, msg=f"missing browser coverage for {field}")

        self.assertEqual(
            3,
            browser_flow.count("for selector, expected in ci_settings.items():"),
            "seller profile settings should be verified after draft save, draft reload, and publish",
        )
        self.assertIn('"확인 대기" in company.text', browser_flow)
        self.assertIn("assert_seller_disclosures_remain_gated(driver, private_values)", browser_flow)
        self.assertIn('visible(driver, ".ordenowa-legal-page__closed")', browser_flow)
        self.assertIn("leaked_values = [value for value in private_values if value and value in page.text]", browser_flow)
        self.assertNotIn("submitOrdenowaApproveSeller", browser_flow)

    def test_browser_persists_korean_company_profile_and_checks_preview_and_closed_storefront(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        ci_settings = browser_flow.split("ci_settings = {", 1)[1].split(
            "\n        }\n        for selector, value in ci_settings.items():", 1
        )[0]
        run_flow = browser_flow.split("def run()", 1)[1]
        self.assertIn('stage = "company_profile_draft_reload"', run_flow)
        draft_reload = run_flow.split('stage = "company_profile_draft_reload"', 1)[1].split(
            'stage = "replace_logo_in_saved_draft"', 1
        )[0]
        private_preview = run_flow.split('stage = "private_admin_preview"', 1)[1].split(
            'publish_selector =', 1
        )[0]
        gated_page = browser_flow.split("def assert_seller_disclosures_remain_gated(", 1)[1].split(
            "\ndef run()", 1
        )[0]

        company_profile_selector = 'textarea[name="profile[content][company_profile][ko-KR]"]'
        self.assertIn(company_profile_selector, ci_settings)
        self.assertIn('company_profile_ko = "ORDENOWA CI 한국어 회사소개"', browser_flow)
        self.assertIn('driver.get(settings_url)', draft_reload)
        self.assertIn("visible(driver, company_profile_selector).get_attribute(\"value\")", draft_reload)
        self.assertIn("company_profile_ko", draft_reload)
        self.assertIn("for selector, expected in ci_settings.items():", draft_reload)
        self.assertIn('visible(driver, selector).get_attribute("value") != expected', draft_reload)
        self.assertIn("did not persist after reloading its draft", draft_reload)
        self.assertIn("company_profile_ja", private_preview)
        self.assertIn("company_profile_ko", private_preview)
        self.assertIn("if expected not in preview.text:", private_preview)
        self.assertIn('customer_url = urljoin(BASE + "/", "ko/")', gated_page)
        self.assertIn('visible(driver, ".ordenowa-legal-page__closed")', gated_page)
        self.assertIn("leaked_values = [value for value in private_values if value and value in page.text]", gated_page)
        self.assertIn('"company_profile"', browser_flow)

        preview_renderer = ADMIN_PROFILE_FORM.read_text(encoding="utf-8").split(
            "public static function renderPreview", 1
        )[1].split("private static function renderField", 1)[0]
        self.assertIn("'회사소개' => $profile['content']['company_profile'][$locale] ?? ''", preview_renderer)

    def test_browser_persists_localized_brand_and_operating_settings_for_every_locale(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        ci_settings = browser_flow.split("ci_settings = {", 1)[1].split(
            "\n        }\n        for selector, value in ci_settings.items():", 1
        )[0]
        localized_fields = (
            ("input", "brand", "name"),
            ("input", "brand", "description"),
            ("input", "brand", "slogan"),
            ("input", "company_reference", "name"),
            ("input", "customer_support", "hours"),
            ("textarea", "shipping", ""),
            ("textarea", "refund", ""),
            ("input", "seo", "title"),
            ("textarea", "seo", "description"),
            ("input", "pwa", "name"),
            ("input", "pwa", "short_name"),
        )

        for element, section, field in localized_fields:
            for locale in ("ja-JP", "en-US", "ko-KR"):
                profile_path = f"[{section}][{field}][{locale}]" if field else f"[{section}][{locale}]"
                selector = f'{element}[name="profile{profile_path}"]'
                with self.subTest(field=selector):
                    self.assertIn(selector, ci_settings, msg=f"missing localized draft and publish coverage for {selector}")

        self.assertEqual(
            3,
            browser_flow.count("for selector, expected in ci_settings.items():"),
            "localized settings should be verified after draft save, draft reload, and publish",
        )
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", ci_settings)
        self.assertTrue(emails, "the browser fixture should retain synthetic email values")
        self.assertTrue(all(email.endswith(".invalid") for email in emails), "browser test emails must use the reserved .invalid domain")

    def test_browser_replaces_and_restores_the_primary_logo_in_draft(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        baseline = browser_flow.index("public_before_draft = public_brand_snapshot(driver)")
        temporary_upload = browser_flow.index(
            'replace_primary_logo_in_saved_draft(\n            driver,\n            settings_url,\n            OFFICIAL_UPLOADS["pwa_icon"]'
        )
        unchanged_check = browser_flow.index('stage = "public_brand_unchanged_after_replacement_draft"')
        restore_start = browser_flow.index('stage = "restore_approved_logo_in_saved_draft"')
        restore_stage = browser_flow[restore_start:].split('stage = "private_admin_preview"', 1)[0]
        restore_call = "replace_primary_logo_in_saved_draft("
        self.assertIn(restore_call, restore_stage)
        restore = restore_stage.index(restore_call) + restore_start
        private_preview = browser_flow.index('stage = "private_admin_preview"')

        self.assertIn("upload_input = visible(driver, upload_selector)", browser_flow)
        self.assertIn("upload_input.send_keys(str(source.resolve()))", browser_flow)
        self.assertIn('OFFICIAL_UPLOADS["pwa_icon"]', browser_flow[temporary_upload:unchanged_check])
        run_before_preview = browser_flow.split("def run()", 1)[1].split('stage = "private_admin_preview"', 1)[0]
        self.assertEqual(2, run_before_preview.count("replace_primary_logo_in_saved_draft("))
        self.assertIn('OFFICIAL_UPLOADS["primary_logo"]', restore_stage)
        self.assertIn('"restored approved draft logo"', restore_stage)
        self.assertNotIn("send_keys", restore_stage)
        self.assertNotIn("submitOrdenowaSaveDraft", restore_stage)
        self.assertIn('driver.save_screenshot(str(DEST / "brand-admin-uploaded-draft-restored.png"))', restore_stage)
        self.assertLess(baseline, temporary_upload)
        self.assertLess(temporary_upload, unchanged_check)
        self.assertLess(unchanged_check, restore)
        self.assertLess(restore, private_preview)
        self.assertIn('public_after_replacement = public_brand_snapshot(driver)', browser_flow)
        self.assertIn('if public_after_replacement != public_before_draft:', browser_flow)
        for key in ("logo", "title", "description", "themeColor", "icons", "ogImage", "manifest"):
            with self.subTest(snapshot_key=key):
                self.assertIn(f"{key}:", browser_flow)
        self.assertIn('"temporary replacement draft logo"', browser_flow[:private_preview])
        self.assertIn('"restored approved draft logo"', browser_flow[:private_preview])
        self.assertIn('driver.save_screenshot(str(DEST / "brand-customer-unpublished-replacement.png"))', browser_flow)
        self.assertIn('driver.save_screenshot(str(DEST / "brand-admin-replacement-draft.png"))', browser_flow)
        self.assertIn('driver.save_screenshot(str(DEST / "brand-admin-uploaded-draft-restored.png"))', browser_flow)

    def test_browser_replaces_previews_publishes_and_restores_favicon_and_pwa_assets(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        run_flow = browser_flow.split("def run()", 1)[1].split("if __name__ ==", 1)[0]

        self.assertIn("def replace_publish_restore_brand_icon(", browser_flow)
        self.assertIn("def replace_brand_asset_in_saved_draft(", browser_flow)
        self.assertIn("def preview_current_draft_brand_assets(", browser_flow)
        self.assertIn("def public_brand_slot_urls(", browser_flow)
        slot_url_helper = browser_flow.split("def public_brand_slot_urls(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('if slot == "favicon_symbol":', slot_url_helper)
        self.assertIn('if slot == "pwa_icon":', slot_url_helper)

        for slot, replacement, approved, field_id, form_preview_filename, preview_files in (
            (
                "favicon_symbol",
                'OFFICIAL_UPLOADS["pwa_icon"]',
                'OFFICIAL_UPLOADS["favicon_symbol"]',
                "ordenowa-brand-assets-favicon",
                "favicon.ico",
                ("favicon-32.png",),
            ),
            (
                "pwa_icon",
                'OFFICIAL_UPLOADS["favicon_symbol"]',
                'OFFICIAL_UPLOADS["pwa_icon"]',
                "ordenowa-brand-assets-pwa_512",
                "pwa-512.png",
                ("apple-touch-icon.png", "pwa-512.png"),
            ),
        ):
            with self.subTest(slot=slot):
                stage = f'stage = "{slot}_replacement_publish_restore"'
                self.assertIn(stage, run_flow)
                call_start = run_flow.index("replace_publish_restore_brand_icon(", run_flow.index(stage))
                call = run_flow[call_start:].split("\n        )", 1)[0]
                self.assertIn(f'slot="{slot}"', call)
                self.assertIn(f"replacement_source={replacement}", call)
                self.assertIn(f"approved_source={approved}", call)
                self.assertIn(f'preview_field_id="{field_id}"', call)
                self.assertIn(f'form_preview_filename="{form_preview_filename}"', call)
                for filename in preview_files:
                    self.assertIn(f'"{filename}"', call)

        replacement_helper = browser_flow.split("def replace_publish_restore_brand_icon(", 1)[1].split(
            "def ", 1
        )[0]
        self.assertIn("form_preview_filename: str", replacement_helper)
        self.assertIn("replacement_source,\n            form_preview_filename,", replacement_helper)
        self.assertIn("approved_source,\n            form_preview_filename,", replacement_helper)
        self.assertNotIn("replacement_previews[0][0]", replacement_helper)
        self.assertNotIn("approved_previews[0][0]", replacement_helper)
        self.assertIn("form_preview_filename=form_preview_filename", replacement_helper)
        self.assertIn("restore_approved_brand_icon_after_failure(", replacement_helper)
        self.assertIn("approved_source=approved_source", replacement_helper)
        self.assertIn("stage_callback=lambda cleanup_assertion_stage: cleanup_stage.update(", replacement_helper)
        self.assertIn("except Exception as cleanup_error:", replacement_helper)
        self.assertIn(
            '"ORDENOWA_BRAND_ICON_RESTORE_CLEANUP=failed at "',
            replacement_helper,
        )
        self.assertIn('cleanup_stage["value"][:96]', replacement_helper)
        self.assertIn("raise\n", replacement_helper)
        self.assertIn("public_brand_snapshot(driver)", replacement_helper)
        self.assertIn("replace_brand_asset_in_saved_draft(", replacement_helper)
        self.assertIn("preview_current_draft_brand_assets(", replacement_helper)
        self.assertIn("publish_saved_brand_draft(", replacement_helper)
        self.assertIn("assert_public_brand_assets(", replacement_helper)
        self.assertIn("public_brand_slot_urls(", replacement_helper)
        self.assertEqual(2, replacement_helper.count("replace_brand_asset_in_saved_draft("))
        self.assertEqual(2, replacement_helper.count("preview_current_draft_brand_assets("))
        self.assertEqual(2, replacement_helper.count("publish_saved_brand_draft("))
        self.assertEqual(2, replacement_helper.count("assert_public_brand_assets("))
        self.assertIn("public_before_draft", replacement_helper)
        self.assertIn('if public_after_replacement_draft != public_before_draft:', replacement_helper)
        self.assertIn("public_after_replacement", replacement_helper)
        self.assertIn(
            'if public_brand_slot_urls(public_after_replacement, slot) == public_brand_slot_urls(public_before_draft, slot):',
            replacement_helper,
        )
        self.assertIn('if public_after_restore_draft != public_after_replacement:', replacement_helper)
        self.assertIn("public_after_restore", replacement_helper)
        self.assertIn(
            'if public_brand_slot_urls(public_after_restore, slot) != public_brand_slot_urls(public_before_draft, slot):',
            replacement_helper,
        )

        cleanup_helper = browser_flow.split("def restore_approved_brand_icon_after_failure(", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertIn("form_preview_filename: str", cleanup_helper)
        self.assertIn("replace_brand_asset_in_saved_draft(", cleanup_helper)
        self.assertIn("approved_source,\n        form_preview_filename,", cleanup_helper)
        self.assertIn("publish_saved_brand_draft(", cleanup_helper)
        self.assertIn("assert_public_brand_assets(", cleanup_helper)
        self.assertIn(
            "public_brand_slot_urls(restored, slot) != public_brand_slot_urls(public_before_draft, slot)",
            cleanup_helper,
        )

    def test_icon_cleanup_recovers_login_and_publishes_before_optional_preview(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        cleanup = browser_flow.split("def restore_approved_brand_icon_after_failure(", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertIn("restore_admin_session(", cleanup)
        self.assertIn("settings_url = business_profile_settings_url(driver)", cleanup)
        self.assertLess(cleanup.index("restore_admin_session("), cleanup.index("replace_brand_asset_in_saved_draft("))
        publication = cleanup.index("publish_saved_brand_draft(")
        preview = cleanup.find("preview_current_draft_brand_assets(")
        self.assertTrue(preview == -1 or publication < preview,
                        "private preview must not block safety publication")
        self.assertLess(publication, cleanup.index("assert_public_brand_assets("))

    def test_draft_history_wait_returns_false_until_row_appears(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        self.assertIn("def current_draft_history_row(", browser_flow)
        helper = browser_flow.split("def current_draft_history_row(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("return False", helper)
        self.assertEqual(2, browser_flow.count("until(current_draft_history_row)"))

    def test_public_draft_snapshot_checks_mobile_independently(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        helper = browser_flow.split("def public_brand_snapshot(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("driver.set_window_size(390, 844)", helper)
        self.assertIn('snapshot["mobile"] = public_brand_snapshot(driver, include_mobile=False)', helper)
        self.assertIn('driver.set_window_size(original_size["width"], original_size["height"])', helper)

    def test_later_logo_replacement_draft_does_not_publish_before_click(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        replacement = browser_flow.split('stage = "replace_published_logo_in_saved_draft"', 1)[1].split(
            'stage = "publish_replacement_logo"', 1
        )[0]
        self.assertIn("public_before_logo_draft = public_brand_snapshot(driver)", replacement)
        self.assertLess(replacement.index("public_before_logo_draft = public_brand_snapshot(driver)"),
                        replacement.index("replace_primary_logo_in_saved_draft("))
        self.assertIn("if public_brand_snapshot(driver) != public_before_logo_draft:", replacement)
        self.assertIn("driver.get(settings_url)", replacement)

    def test_replacement_upload_requeries_stale_elements_and_verifies_saved_derivative(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        self.assertIn("def replace_primary_logo_in_saved_draft(", browser_flow)
        helper_start = browser_flow.index("def replace_primary_logo_in_saved_draft(")
        helper_end = browser_flow.index("\ndef ", helper_start + 1)
        helper = browser_flow[helper_start:helper_end]
        replacement_stage = browser_flow.split('stage = "replace_logo_in_saved_draft"', 1)[1].split(
            'stage = "public_brand_unchanged_after_replacement_draft"', 1
        )[0]

        self.assertIn("for attempt in range(1, BRAND_DRAFT_REPLACEMENT_ATTEMPTS + 1):", helper)
        self.assertIn('upload_selector = \'input[name="brand_uploads[primary_logo]"]\'', helper)
        self.assertIn("upload_input = visible(driver, upload_selector)", helper)
        self.assertIn("upload_input.send_keys(str(source.resolve()))", helper)
        self.assertIn("except StaleElementReferenceException as error:", helper)
        self.assertIn("continue", helper)
        self.assertIn("wait_for_draft_save_confirmation(driver)", helper)
        saved_logo_check = "assert_saved_primary_logo(driver, source, role)"
        self.assertEqual(2, helper.count(saved_logo_check), "the derivative is checked before and after reloading the draft")
        self.assertLess(helper.index("wait_for_draft_save_confirmation(driver)"), helper.index(saved_logo_check))
        saved_logo_helper = browser_flow.split("def assert_saved_primary_logo(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("assert_uploaded_derivative_url(", saved_logo_helper)
        self.assertLess(helper.index(saved_logo_check), helper.rindex("return"))
        self.assertIn(
            'OFFICIAL_UPLOADS["pwa_icon"],\n            "temporary replacement draft logo",',
            replacement_stage,
        )

    def test_published_logo_replacement_reports_internal_draft_stages(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        helper_start = browser_flow.index("def replace_primary_logo_in_saved_draft(")
        helper_end = browser_flow.index("\ndef ", helper_start + 1)
        helper = browser_flow[helper_start:helper_end]
        run_flow = browser_flow.split("def run()", 1)[1]
        replacement_start = run_flow.index('stage = "replace_published_logo_in_saved_draft"')
        replacement_end = run_flow.index('stage = "publish_replacement_logo"', replacement_start)
        replacement_call = run_flow[replacement_start:replacement_end]

        expected_stages = (
            'report("initial_reload")',
            'wait_for_settings_form("draft_form_wait")',
            'report(f"upload_input_wait_attempt_{attempt}")',
            'report(f"upload_attempt_{attempt}")',
            'report(f"save_button_wait_attempt_{attempt}")',
            'report(f"save_attempt_{attempt}")',
            'report(f"save_confirmation_attempt_{attempt}")',
            'report(f"saved_derivative_requery_attempt_{attempt}")',
            'report("persisted_draft_reload")',
            'wait_for_settings_form("persisted_form_wait")',
            'report("persisted_derivative_requery")',
        )
        for stage in expected_stages:
            with self.subTest(stage=stage):
                self.assertIn(stage, helper)
        positions = [helper.find(stage) for stage in expected_stages]
        self.assertEqual(sorted(positions), positions, "replacement diagnostics should follow the browser flow")
        self.assertIn("stage_callback: Callable[[str], None] | None = None", helper)
        self.assertIn('stage_prefix: str = "replacement_draft"', helper)
        self.assertIn("stage_callback=set_brand_assertion_stage", replacement_call)
        self.assertIn('stage_prefix="replace_published_logo_in_saved_draft"', replacement_call)

    def test_replacement_form_timeout_emits_safe_settings_diagnostics(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        helper_start = browser_flow.index("def replace_primary_logo_in_saved_draft(")
        helper_end = browser_flow.index("\ndef ", helper_start + 1)
        helper = browser_flow[helper_start:helper_end]
        form_wait_start = helper.index("def wait_for_settings_form(")
        form_wait_end = helper.index("\n    # Reload", form_wait_start)
        form_wait = helper[form_wait_start:form_wait_end]

        self.assertIn("except TimeoutException:", form_wait)
        self.assertIn("emit_brand_settings_diagnostics(driver)", form_wait)
        self.assertIn("except Exception:", form_wait)
        self.assertIn("raise", form_wait)
        self.assertIn('wait_for_settings_form("draft_form_wait")', helper)
        self.assertIn('wait_for_settings_form("persisted_form_wait")', helper)

    def test_public_storefront_assertions_reuse_captured_admin_settings_url(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        run_flow = browser_flow.split("def run()", 1)[1].split("if __name__ ==", 1)[0]
        first_admin_lookup = run_flow.index("settings_url = business_profile_settings_url(driver)")

        for stage_name in (
            "published_desktop_customer_brand",
            "published_mobile_customer_brand",
            "published_korean_customer_brand",
        ):
            start = run_flow.index(f'stage = "{stage_name}"')
            next_stage = run_flow.find('\n        stage = "', start + 1)
            stage_block = run_flow[start:next_stage if next_stage >= 0 else len(run_flow)]
            with self.subTest(stage=stage_name):
                self.assertLess(first_admin_lookup, start)
                self.assertIn("assert_public_brand_assets(", stage_block)
                self.assertNotIn("business_profile_settings_url(driver)", stage_block)

    def test_browser_publishes_replacement_logo_then_restores_and_publishes_approved_logo(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        self.assertIn("def assert_published_logo_source(", browser_flow)
        self.assertIn("def publish_saved_brand_draft(", browser_flow)
        self.assertIn("def restore_admin_session(", browser_flow)
        logo_assertion = browser_flow.split("def assert_published_logo_source(", 1)[1].split(
            "\ndef ", 1
        )[0]
        publish_helper = browser_flow.split("def publish_saved_brand_draft(", 1)[1].split(
            "\ndef ", 1
        )[0]
        session_restore = browser_flow.split("def restore_admin_session(", 1)[1].split(
            "\ndef ", 1
        )[0]
        run_flow = browser_flow.split("def run()", 1)[1]
        initial_restore = run_flow.split('stage = "admin_login_after_publish"', 1)[1].split(
            'stage = "record_official_published_header_logo"', 1
        )[0]

        replacement_upload = run_flow.index('stage = "replace_published_logo_in_saved_draft"')
        replacement = run_flow.index('stage = "publish_replacement_logo"', replacement_upload)
        replacement_assertion = run_flow.index('stage = "published_replacement_logo"', replacement)
        restore = run_flow.index('stage = "restore_approved_logo_after_replacement_publish"', replacement_assertion)
        restore_publish = run_flow.index('stage = "publish_restored_approved_logo"', restore)
        restored_assertion = run_flow.index('stage = "published_restored_approved_logo"', restore_publish)

        self.assertLess(replacement, replacement_assertion)
        self.assertLess(replacement_assertion, restore)
        self.assertLess(restore, restore_publish)
        self.assertLess(restore_publish, restored_assertion)
        self.assertIn('OFFICIAL_UPLOADS["pwa_icon"]', run_flow[replacement_upload:replacement])
        self.assertIn('OFFICIAL_UPLOADS["primary_logo"]', run_flow[restore:restore_publish])
        self.assertIn('"replacement_publish"', run_flow[replacement:replacement_assertion])
        self.assertIn('"restored_publish"', run_flow[restore_publish:restored_assertion])
        self.assertIn("expected_previous_header_logos=", run_flow[replacement_assertion:restore])
        self.assertIn("expected_previous_admin_login_logo=", run_flow[replacement_assertion:restore])
        self.assertIn("expected_previous_header_logos=", run_flow[restored_assertion:])
        self.assertIn("expected_previous_admin_login_logo=", run_flow[restored_assertion:])
        self.assertIn('expected_previous_header_logos[viewport]', logo_assertion)

        self.assertIn('image_is_rendered(driver, "picture img.kuranea-brand__image")', logo_assertion)
        self.assertIn('image_is_rendered(driver, ".ordenowa-admin-login-brand img")', logo_assertion)
        self.assertIn("driver.delete_all_cookies()", logo_assertion)
        self.assertIn('restore_admin_session(driver, stage_callback, stage_prefix + "_admin_session_restore")', logo_assertion)
        self.assertIn("restore_admin_session(", initial_restore)
        self.assertIn('"official_publish_admin_session_restore"', initial_restore)
        self.assertIn("def business_profile_settings_url(", browser_flow)
        self.assertIn('parse_qs(urlparse(href).query).get("controller", []) == ["AdminBusinessProfile"]', browser_flow)
        self.assertIn('settings_location.path.startswith("/admin-kuranea/")', browser_flow)
        for reauthentication_stage in (
            "published_replacement_logo",
            "published_restored_approved_logo",
        ):
            stage_block = run_flow.split(f'stage = "{reauthentication_stage}"', 1)[1].split(
                'driver.save_screenshot', 1
            )[0]
            with self.subTest(reauthentication_stage=reauthentication_stage):
                self.assertIn("settings_url = business_profile_settings_url(driver)", stage_block)
        self.assertIn("email_fields[0].send_keys(ADMIN_EMAIL)", session_restore)
        self.assertIn("password_fields[0].send_keys(ADMIN_PASSWORD)", session_restore)
        self.assertIn("stage_callback(stage_name)", session_restore)
        self.assertIn('assert_uploaded_derivative_url(', logo_assertion)
        self.assertIn('"header-desktop.png"', logo_assertion)
        self.assertIn('"header-mobile.png"', logo_assertion)
        self.assertIn('"admin-login.png"', logo_assertion)
        self.assertIn('logo["src"] == expected_previous_header_logos[viewport]', logo_assertion)
        self.assertIn('login_logo["src"] == expected_previous_admin_login_logo', logo_assertion)
        self.assertIn('def publish_saved_brand_draft(', browser_flow)
        self.assertIn('stage_callback(stage_prefix + "_button_find")', publish_helper)
        self.assertIn('stage_callback(stage_prefix + "_button_click")', publish_helper)
        self.assertIn('stage_callback(stage_prefix + "_confirmation")', publish_helper)

    def test_replacement_browser_flow_restores_approved_logo_after_failure_without_cache(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        restore_helper = browser_flow.split("def restore_approved_logo_after_failure", 1)[1].split(
            "def wait_for_draft_save_confirmation", 1
        )[0]
        run_flow = browser_flow.split("def run()", 1)[1].split("if __name__ ==", 1)[0]
        cleanup = run_flow.split("finally:", 1)[1]

        self.assertIn('driver.execute_cdp_cmd("Network.enable", {})', run_flow)
        self.assertIn(
            'driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})',
            run_flow,
        )
        self.assertIn("replacement_publish_started = True", run_flow)
        self.assertIn("replacement_publish_started = False", run_flow)
        self.assertIn("if replacement_publish_started and settings_url:", cleanup)
        self.assertIn("restore_approved_logo_after_failure(driver, settings_url", cleanup)
        self.assertIn('"failure cleanup restore approved logo"', restore_helper)
        self.assertIn('"replacement_failure_cleanup_publish"', restore_helper)
        self.assertIn('stage_prefix="replacement_failure_cleanup_verify"', restore_helper)

    def test_browser_asserts_published_open_graph_text_matches_seo_settings(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        public_snapshot = browser_flow.split("def public_brand_snapshot", 1)[1].split("def click_centered", 1)[0]
        published_assets = browser_flow.split("def assert_public_brand_assets", 1)[1].split(
            "def assert_seller_disclosures_remain_gated", 1
        )[0]

        self.assertIn('ogTitle: document.querySelector(\'meta[property="og:title"]\')?.content || \'\'', public_snapshot)
        self.assertIn(
            'ogDescription: document.querySelector(\'meta[property="og:description"]\')?.content || \'\'',
            public_snapshot,
        )
        self.assertIn('const ogTitle = document.querySelector(\'meta[property="og:title"]\')?.content || \'\';', published_assets)
        self.assertIn(
            'const ogDescription = document.querySelector(\'meta[property="og:description"]\')?.content || \'\';',
            published_assets,
        )
        self.assertIn('seo_title: str = SEO_TITLE', published_assets)
        self.assertIn('seo_description: str = SEO_DESCRIPTION', published_assets)
        self.assertIn('if results["ogTitle"] != seo_title:', published_assets)
        self.assertIn('if results["ogDescription"] != seo_description:', published_assets)
        self.assertIn(
            'SEO_TITLE = \'ORDENOWA CI QA " </title><meta id="ordenowa-seo-title-inert-sentinel">\'',
            browser_flow,
        )
        self.assertIn(
            'SEO_DESCRIPTION = \'ORDENOWA CI SEO description \"><meta id="ordenowa-seo-description-inert-sentinel">\'',
            browser_flow,
        )

    def test_publish_stale_click_is_instrumented_without_retry_or_sensitive_dom_data(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        find_stage = browser_flow.index('stage = "publish_button_find"')
        click_stage = browser_flow.index('stage = "publish_button_click"')
        confirmation_stage = browser_flow.index('stage = "publish_confirmation"')
        stale_handler = browser_flow.index("except StaleElementReferenceException:", click_stage)
        failure_stage = browser_flow.index('stage = "published_desktop_customer_brand"')

        self.assertLess(find_stage, click_stage)
        self.assertLess(click_stage, confirmation_stage)
        self.assertLess(confirmation_stage, failure_stage)
        self.assertIn("emit_publish_target_diagnostics(driver, publish_selector)", browser_flow[stale_handler:confirmation_stage])
        self.assertIn("raise", browser_flow[stale_handler:confirmation_stage])
        self.assertNotIn("retry", browser_flow[click_stage:confirmation_stage].lower())

        helper_start = browser_flow.index("def emit_publish_target_diagnostics(")
        helper_end = browser_flow.index("\ndef image_is_rendered", helper_start)
        helper = browser_flow[helper_start:helper_end]
        for metadata_field in ("selector", "present", "connected", "tag", "id", "class"):
            with self.subTest(metadata_field=metadata_field):
                self.assertIn(f"{metadata_field}", helper)
        for sensitive_dom_field in (".value", "innerText", "textContent", "outerHTML"):
            with self.subTest(sensitive_dom_field=sensitive_dom_field):
                self.assertNotIn(sensitive_dom_field, helper)
        self.assertIn("ORDENOWA_PUBLISH_STALE_TARGET=", helper)

    def test_publish_confirmation_retries_stale_dom_polls_without_replaying_publish(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        confirmation = browser_flow.split("def wait_for_publish_confirmation", 1)[1].split(
            "def assert_saved_primary_logo", 1
        )[0]
        publish_stage = browser_flow.split('stage = "publish_confirmation"', 1)[1].split(
            'stage = "published_desktop_customer_brand"', 1
        )[0]
        click_stage = browser_flow.split('stage = "publish_button_click"', 1)[1].split(
            'stage = "publish_confirmation"', 1
        )[0]

        self.assertIn('find_elements(By.CSS_SELECTOR, ".alert.alert-success")', confirmation)
        self.assertIn("except StaleElementReferenceException:", confirmation)
        self.assertIn("return False", confirmation)
        self.assertIn("변경사항을 게시했습니다.", confirmation)
        self.assertIn('find_element(By.ID, "ordenowa-company")', confirmation)
        self.assertIn('"확인 대기" in company.text', confirmation)
        self.assertIn("wait_for_publish_confirmation(driver)", publish_stage)
        self.assertNotIn('find_element(By.TAG_NAME, "body")', publish_stage)
        self.assertNotIn("retry", click_stage.lower())

    def test_browser_checks_published_derivatives_from_uploaded_official_sources(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        manifest = json.loads((BRAND_PACK / "asset-manifest.json").read_text(encoding="utf-8"))

        self.assertIn('for slot, source in OFFICIAL_UPLOADS.items():', browser_flow)
        self.assertIn("hashlib.sha256(source.read_bytes()).hexdigest()", browser_flow)
        self.assertIn('f"/img/ordenowa/versions/{source_hash}/{filename}"', browser_flow)
        self.assertIn("urlparse(url).path.endswith(expected_path)", browser_flow)
        self.assertIn("urlparse(item[\"href\"]).path.endswith(expected_path)", browser_flow)
        self.assertIn("def find_asset_url(items: list[dict], rel: str, source: Path, filename: str)", browser_flow)

        upload_sources = {
            "primary_logo": "ORDENOWA-logo.png",
            "favicon_symbol": "ORDENOWA-favicon-source.png",
            "pwa_icon": "ORDENOWA-pwa-icon-source.png",
        }
        for slot, source_name in upload_sources.items():
            with self.subTest(slot=slot):
                self.assertIn(f'"{slot}": SOURCES / "{source_name}"', browser_flow)

        for source_name, expected_hash in manifest["sources_sha256"].items():
            with self.subTest(source=source_name):
                source = BRAND_PACK / "official_originals" / source_name
                self.assertEqual(expected_hash, hashlib.sha256(source.read_bytes()).hexdigest())
                self.assertIn(source_name, browser_flow)

        for derivative in (
            "header-desktop.png",
            "header-mobile.png",
            "admin-login.png",
            "email-logo.png",
            "favicon-32.png",
            "favicon.ico",
            "apple-touch-icon.png",
            "og-brand.png",
            "pwa-192.png",
            "pwa-512.png",
            "pwa-maskable-512.png",
        ):
            with self.subTest(derivative=derivative):
                self.assertIn(derivative, browser_flow)

        source_bindings = (
            ('results["assetLinks"], "icon", favicon_source, "favicon.ico"',),
            (
                'results["assetLinks"], "apple-touch-icon", pwa_source, "apple-touch-icon.png"',
            ),
            ('results["og"], OFFICIAL_UPLOADS["primary_logo"], "og-brand.png"',),
            ('icon_url["src"], pwa_source, filename',),
            ('("email-logo.png", "primary_logo")',),
        )
        for binding in source_bindings:
            with self.subTest(binding=binding):
                for assertion in binding:
                    self.assertIn(assertion, browser_flow)

        self.assertIn('for filename in ("favicon-16.png", "favicon-32.png"):', browser_flow)
        self.assertIn('results["assetLinks"], "icon", favicon_source, filename', browser_flow)
        self.assertIn('favicon_source = favicon_source or OFFICIAL_UPLOADS["favicon_symbol"]', browser_flow)
        self.assertIn('pwa_source = pwa_source or OFFICIAL_UPLOADS["pwa_icon"]', browser_flow)
        self.assertIn('("pwa-192.png", "192x192", "any", 192, 192)', browser_flow)
        self.assertIn('("pwa-512.png", "512x512", "any", 512, 512)', browser_flow)
        self.assertIn('("pwa-maskable-512.png", "512x512", "maskable", 512, 512)', browser_flow)
        self.assertIn('(icon_url["sizes"], icon_url["purpose"], icon_url["width"], icon_url["height"])', browser_flow)

    def test_browser_checks_published_brand_metadata_and_images_on_korean_customer_route(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")

        self.assertIn('SEO_TITLE_KO = "ORDENOWA CI SEO TITLE KO"', browser_flow)
        self.assertIn('SEO_DESCRIPTION_KO = "ORDENOWA CI SEO DESCRIPTION KO"', browser_flow)
        self.assertIn('customer_url = urljoin(BASE + "/", locale_path.lstrip("/"))', browser_flow)
        self.assertIn('driver.get(customer_url)', browser_flow)
        self.assertIn('expected_html_lang="ko-KR"', browser_flow)
        self.assertIn('htmlLang: document.documentElement.lang', browser_flow)
        self.assertIn(
            'assert_public_brand_assets(\n'
            '            driver,\n'
            '            "Korean",\n'
            '            "header-desktop.png",\n'
            '            locale_path="/ko/",\n'
            '            expected_html_lang="ko-KR",\n'
            '            seo_title=SEO_TITLE_KO,\n'
            '            seo_description=SEO_DESCRIPTION_KO,\n'
            '            jsonld_brand_name="ORDENOWA CI BRAND KO",\n'
            '            pwa_name="ORDENOWA CI APP KO",\n'
            '            pwa_short_name="ORDENOWA KO",\n'
            '            stage_prefix="published_korean_customer_brand",\n'
            '            stage_callback=set_brand_assertion_stage,\n'
            '        )',
            browser_flow,
        )
        self.assertIn('driver.save_screenshot(str(DEST / "brand-korean-published.png"))', browser_flow)


if __name__ == "__main__":
    unittest.main()
