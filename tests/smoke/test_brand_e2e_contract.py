"""Guard the real-browser contract for published official brand derivatives."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRAND_E2E = ROOT / "tests" / "e2e" / "verify_brand_admin_browser.py"
BRAND_PACK = ROOT / "assets" / "brand" / "ordenowa"


class BrandE2EContractTests(unittest.TestCase):
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
        self.assertIn('if "확인 대기" not in driver.find_element(By.ID, "ordenowa-company").text:', browser_flow)
        self.assertIn("assert_seller_disclosures_remain_gated(driver, private_values)", browser_flow)
        self.assertIn('visible(driver, ".ordenowa-legal-page__closed")', browser_flow)
        self.assertIn("leaked_values = [value for value in private_values if value and value in page.text]", browser_flow)
        self.assertNotIn("submitOrdenowaApproveSeller", browser_flow)

    def test_browser_replaces_and_restores_the_primary_logo_in_draft(self) -> None:
        browser_flow = BRAND_E2E.read_text(encoding="utf-8")
        preview_check = 'asset_preview_url_for_field(driver, "ordenowa-brand-assets-header_desktop")'
        baseline = browser_flow.index("public_before_draft = public_brand_snapshot(driver)")
        temporary_upload = browser_flow.index('replacement_logo.send_keys(str(OFFICIAL_UPLOADS["pwa_icon"].resolve()))')
        unchanged_check = browser_flow.index('stage = "public_brand_unchanged_after_replacement_draft"')
        restore = browser_flow.index('restored_logo.send_keys(str(OFFICIAL_UPLOADS["primary_logo"].resolve()))')
        private_preview = browser_flow.index('stage = "private_admin_preview"')

        self.assertIn('replacement_logo.send_keys(str(OFFICIAL_UPLOADS["pwa_icon"].resolve()))', browser_flow)
        self.assertIn('restored_logo.send_keys(str(OFFICIAL_UPLOADS["primary_logo"].resolve()))', browser_flow)
        self.assertEqual(2, browser_flow[:private_preview].count(preview_check))
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


if __name__ == "__main__":
    unittest.main()
