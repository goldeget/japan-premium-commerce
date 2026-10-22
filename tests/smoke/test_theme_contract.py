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

    def test_brand_meta_and_icons_do_not_fall_back_to_legacy_kuranea_assets(self) -> None:
        template = (THEME / "templates" / "_partials" / "head.tpl").read_text(encoding="utf-8")
        module = (ROOT / "modules" / "kuraneabusinessprofile" / "kuraneabusinessprofile.php").read_text(encoding="utf-8")
        self.assertNotIn("img/brand/og-brand.png", template)
        self.assertNotIn("img/brand/favicon.ico", template)
        self.assertIn("ordenowaSeoTitle", template)
        self.assertIn("getModuleLink($this->name, 'manifest')", module)
        self.assertIn("og:image", module)

    def test_customer_brand_copy_uses_confirmed_ordenowa_names(self) -> None:
        template = (THEME / "templates" / "index.tpl").read_text(encoding="utf-8")
        header = (THEME / "templates" / "_partials" / "header.tpl").read_text(encoding="utf-8")
        self.assertIn("ORDENOWA", template)
        self.assertIn("$copyBrandName", template)
        self.assertIn("$copyBrandDescription", template)
        self.assertIn("ordenowaBrandName", header)
        self.assertNotIn("KURANEA", template)
        self.assertNotIn("kuranea-logo-", header)

    def test_home_uses_published_brand_name_description_and_slogan(self) -> None:
        template = (THEME / "templates" / "index.tpl").read_text(encoding="utf-8")

        self.assertIn("$ordenowaBrandName", template)
        self.assertIn("$ordenowaBrandDescription", template)
        self.assertIn("$ordenowaBrandSlogan", template)
        self.assertNotIn("ORDENOWA / オーデノワ", template)
        self.assertNotIn("企業と商品をつなぐ、次世代のB2B調達プラットフォーム", template)

    def test_featured_catalog_heading_uses_published_brand_name(self) -> None:
        template = (THEME / "modules" / "ps_featuredproducts" / "views" / "templates" / "hook" / "ps_featuredproducts.tpl").read_text(encoding="utf-8")

        self.assertIn("$ordenowaBrandName", template)
        self.assertIn("{$catalogHeading|escape:'htmlall':'UTF-8'}", template)
        self.assertNotIn("ORDENOWAの商品カタログ", template)
        self.assertNotIn("ORDENOWA 상품 카탈로그", template)
        self.assertNotIn("ORDENOWA product catalog", template)

    def test_footer_brand_descriptions_use_published_brand_name(self) -> None:
        template = (THEME / "modules" / "ps_linklist" / "views" / "templates" / "hook" / "linkblock.tpl").read_text(encoding="utf-8")

        self.assertIn("$ordenowaBrandName", template)
        self.assertIn("$footerBrandName", template)
        self.assertIn("{$footerLinkDescription|escape:'htmlall':'UTF-8'}", template)
        self.assertNotIn("ORDENOWAのご利用規約です。", template)
        self.assertNotIn("ORDENOWA 이용약관을 확인하세요.", template)
        self.assertNotIn("ORDENOWA's terms of use.", template)

    def test_visible_theme_palette_matches_ordenowa_blue_cyan_silver_artwork(self) -> None:
        css = (THEME / "assets" / "css" / "custom.css").read_text(encoding="utf-8").lower()

        self.assertIn("--ordenowa-navy: #071b3d", css)
        self.assertIn("--ordenowa-blue: #0755b8", css)
        self.assertIn("--ordenowa-cyan: #00bbd4", css)
        self.assertIn("--ordenowa-silver: #b8c3ce", css)
        self.assertNotIn("#b49a61", css)
        self.assertNotIn("#d4b874", css)

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

    def test_mobile_navigation_color_overrides_footer_link_color(self) -> None:
        css = (THEME / "assets" / "css" / "custom.css").read_text(encoding="utf-8")
        self.assertIn("#footer .kuranea-mobile-nav__item", css)
        self.assertIn("color: var(--kuranea-ink)", css)

    def test_searchbar_override_provides_store_locale_labels(self) -> None:
        override = THEME / "modules" / "ps_searchbar" / "ps_searchbar.tpl"
        self.assertTrue(override.is_file(), "KURANEA search bar override is missing")
        template = override.read_text(encoding="utf-8")
        self.assertIn("商品名・キーワードで検索", template)
        self.assertIn("Search products...", template)
        self.assertIn("상품명 또는 키워드 검색", template)
        self.assertIn("name=\"s\"", template)

    def test_empty_featured_collection_has_localized_manual_discovery_state(self) -> None:
        template_path = (
            THEME
            / "modules"
            / "ps_featuredproducts"
            / "views"
            / "templates"
            / "hook"
            / "ps_featuredproducts.tpl"
        )
        self.assertTrue(template_path.is_file(), "KURANEA featured-products override is missing")
        template = template_path.read_text(encoding="utf-8")
        for message in (
            "ただいま、セレクションを準備しています。",
            "We're preparing our first collection.",
            "첫 컬렉션을 준비하고 있습니다.",
        ):
            self.assertIn(message, template)
        self.assertIn("{if $products}", template)
        self.assertIn("catalog/_partials/productlist.tpl", template)
        self.assertIn("{$urls.pages.search}", template)
        self.assertIn('role="status"', template)
        self.assertNotIn("Our special products", template)

        home = (THEME / "templates" / "index.tpl").read_text(encoding="utf-8")
        for message in (
            "ただいま、セレクションを準備しています。",
            "We're preparing our first collection.",
            "첫 컬렉션을 준비하고 있습니다.",
        ):
            self.assertIn(message, home)
        self.assertIn("kuranea-catalog-empty--home", home)

        css = (THEME / "assets" / "css" / "custom.css").read_text(encoding="utf-8")
        self.assertIn(
            ".kuranea-featured:has(.ps-featuredproducts .module-products__list) .kuranea-catalog-empty--home",
            css,
            "the home empty state should yield to real featured product cards",
        )

    def test_pwa_registers_network_only_service_worker(self) -> None:
        head = (THEME / "templates" / "_partials" / "head.tpl").read_text(encoding="utf-8")
        worker_path = THEME / "assets" / "sw.js"
        self.assertTrue("pwa-register.js" in head, "PWA registration script is missing")
        module = (ROOT / "modules" / "kuraneabusinessprofile" / "kuraneabusinessprofile.php").read_text(encoding="utf-8")
        self.assertIn("actionFrontControllerInitBefore", module, "sales must be gated until the seller profile is approved")
        self.assertTrue(worker_path.is_file(), "network-only service worker is missing")
        worker = worker_path.read_text(encoding="utf-8")
        self.assertTrue("addEventListener('fetch'" in worker, "service worker has no fetch policy")
        self.assertNotIn("caches.open", worker, "private or order pages must not be stored by the service worker")
        self.assertIn("ORDENOWA", worker)
        self.assertNotIn("KURANEA", worker)


if __name__ == "__main__":
    unittest.main()
