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
            2,
            browser_flow.count("for selector, expected in ci_settings.items():"),
            "seller profile settings should be verified after draft save and again after publish",
        )
        self.assertIn('"확인 대기" in company.text', browser_flow)
        self.assertIn("assert_seller_disclosures_remain_gated(driver, private_values)", browser_flow)
        self.assertIn('visible(driver, ".ordenowa-legal-page__closed")', browser_flow)
        self.assertIn("leaked_values = [value for value in private_values if value and value in page.text]", browser_flow)
        self.assertNotIn("submitOrdenowaApproveSeller", browser_flow)

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
            2,
            browser_flow.count("for selector, expected in ci_settings.items():"),
            "localized settings should be verified after draft save and again after publish",
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

        self.assertIn('visible(driver, upload_selector).send_keys(str(source.resolve()))', browser_flow)
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
        self.assertIn("visible(driver, upload_selector).send_keys(str(source.resolve()))", helper)
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
        self.assertIn("SEO_TITLE = \"ORDENOWA CI QA\"", browser_flow)
        self.assertIn("SEO_DESCRIPTION = \"ORDENOWA CI SEO description\"", browser_flow)

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
            ('results["assetLinks"], "icon", OFFICIAL_UPLOADS["favicon_symbol"], "favicon.ico"',),
            (
                'results["assetLinks"], "apple-touch-icon", OFFICIAL_UPLOADS["pwa_icon"], "apple-touch-icon.png"',
            ),
            ('results["og"], OFFICIAL_UPLOADS["primary_logo"], "og-brand.png"',),
            ('icon_url["src"], OFFICIAL_UPLOADS["pwa_icon"], filename',),
            ('("email-logo.png", "primary_logo")',),
        )
        for binding in source_bindings:
            with self.subTest(binding=binding):
                for assertion in binding:
                    self.assertIn(assertion, browser_flow)

        self.assertIn('for filename in ("favicon-16.png", "favicon-32.png"):', browser_flow)
        self.assertIn('results["assetLinks"], "icon", OFFICIAL_UPLOADS["favicon_symbol"], filename', browser_flow)
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
