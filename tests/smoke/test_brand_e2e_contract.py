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
            ('icon_url, OFFICIAL_UPLOADS["pwa_icon"], filename',),
            ('("email-logo.png", "primary_logo")',),
        )
        for binding in source_bindings:
            with self.subTest(binding=binding):
                for assertion in binding:
                    self.assertIn(assertion, browser_flow)


if __name__ == "__main__":
    unittest.main()
