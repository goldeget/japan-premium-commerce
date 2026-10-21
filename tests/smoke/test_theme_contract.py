"""Regression checks for KURANEA child-theme integration contracts."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "themes" / "kuranea"


class ThemeContractTests(unittest.TestCase):
    def test_home_retains_prestashop_wrapper_hooks(self) -> None:
        template = (THEME / "templates" / "index.tpl").read_text(encoding="utf-8")
        self.assertTrue("displayContentWrapperTop" in template, "top wrapper hook is missing")
        self.assertTrue("displayContentWrapperBottom" in template, "bottom wrapper hook is missing")
        self.assertTrue("{$HOOK_HOME nofilter}" in template, "homepage module hook is missing")
        self.assertTrue('id="content" class="page-content page-content--home"' in template, "home wrapper is missing")

    def test_home_uses_generated_page_urls(self) -> None:
        template = (THEME / "templates" / "index.tpl").read_text(encoding="utf-8")
        self.assertTrue("{$urls.pages.new_products}" in template, "new-products page URL is not generated")
        self.assertTrue("{$urls.pages.search}" in template, "search page URL is not generated")
        self.assertNotIn("{$urls.base_url}new-products", template)
        self.assertNotIn("{$urls.base_url}search", template)

    def test_product_page_uses_product_image_for_open_graph(self) -> None:
        template = (THEME / "templates" / "_partials" / "head.tpl").read_text(encoding="utf-8")
        self.assertRegex(
            template,
            r"\{if \$page\.page_name != 'product'\}\s*<meta property=\"og:image\"",
        )

    def test_category_selector_matches_hummingbird_markup(self) -> None:
        css = (THEME / "assets" / "css" / "custom.css").read_text(encoding="utf-8")
        self.assertTrue(".page-category .products__selection" in css, "category sort selector misses parent markup")

    def test_mobile_navigation_yields_to_offcanvas_and_safe_area(self) -> None:
        css = (THEME / "assets" / "css" / "custom.css").read_text(encoding="utf-8")
        self.assertTrue("z-index: 1030" in css, "mobile nav must stay below Bootstrap offcanvas")
        self.assertTrue(
            "padding-bottom: calc(4.6rem + env(safe-area-inset-bottom))" in css,
            "content clearance must include the device safe area",
        )

    def test_pwa_registers_network_only_service_worker(self) -> None:
        head = (THEME / "templates" / "_partials" / "head.tpl").read_text(encoding="utf-8")
        worker_path = THEME / "assets" / "sw.js"
        self.assertTrue("pwa-register.js" in head, "PWA registration script is missing")
        self.assertTrue(worker_path.is_file(), "network-only service worker is missing")
        worker = worker_path.read_text(encoding="utf-8")
        self.assertTrue("addEventListener('fetch'" in worker, "service worker has no fetch policy")
        self.assertNotIn("caches.open", worker, "private or order pages must not be stored by the service worker")


if __name__ == "__main__":
    unittest.main()
