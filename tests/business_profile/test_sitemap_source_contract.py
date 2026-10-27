from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "modules/kuraneabusinessprofile"


class SitemapSourceContractTests(unittest.TestCase):
    def test_routes_and_robots_hook_are_registered_for_install_and_upgrade(self):
        source = (MODULE / "kuraneabusinessprofile.php").read_text()
        upgrade = (MODULE / "upgrade/upgrade-1.0.6.php").read_text()
        self.assertIn("'moduleRoutes'", source)
        self.assertIn("'actionAdminMetaAfterWriteRobotsFile'", source)
        self.assertIn("function hookModuleRoutes", source)
        self.assertIn("'sitemap.xml'", source)
        self.assertIn("'sitemap-{iso}-{page}.xml'", source)
        self.assertIn("'moduleRoutes'", upgrade)
        self.assertIn("'actionAdminMetaAfterWriteRobotsFile'", upgrade)
        self.assertIn("return (bool) $module->refreshRobotsSitemapDirective()", upgrade)
        uninstall = source.split("public function uninstall()", 1)[1].split("public function hookModuleRoutes", 1)[0]
        self.assertIn("rewriteExistingFile(_PS_ROOT_DIR_ . '/robots.txt', null)", uninstall)
        install = source.split("public function install()", 1)[1].split("public function uninstall()", 1)[0]
        self.assertIn("return $this->refreshRobotsSitemapDirective()", install)
        refresh = source.split("public function refreshRobotsSitemapDirective()", 1)[1].split(
            "private function urlRewritingEnabled()", 1
        )[0]
        self.assertIn("return RobotsSitemapDirective::rewriteExistingFile($robotsPath, $sitemapUrl)", refresh)
        self.assertIn("return is_file($robotsPath)", refresh)
        self.assertIn("&& RobotsSitemapDirective::rewriteExistingFile($robotsPath, $sitemapUrl)", refresh)

    def test_catalog_query_is_same_shop_locale_active_indexable_and_visible(self):
        source = (MODULE / "src/Infrastructure/PublicSitemapRepository.php").read_text()
        self.assertIn("cs.id_shop = \" . $shopId", source)
        self.assertIn("cl.id_shop = \" . $shopId . \" AND cl.id_lang = \" . $langId", source)
        self.assertIn("ps.id_shop = \" . $shopId", source)
        self.assertIn("pl.id_shop = \" . $shopId . \" AND pl.id_lang = \" . $langId", source)
        self.assertIn("c.active = 1", source)
        self.assertIn("p.active = 1 AND ps.active = 1 AND ps.indexed = 1", source)
        self.assertIn("ps.visibility IN ('both', 'catalog') AND ps.show_price = 1", source)
        self.assertIn("TRIM(pl.name) <> '' AND TRIM(pl.link_rewrite) <> ''", source)
        self.assertIn("c.id_category NOT IN", source)
        self.assertIn("category_group", source)
        self.assertIn("cg.id_group = ' . $guestGroupId", source)
        self.assertIn("cp.id_product = ps.id_product", source)
        self.assertNotIn("_DB_PREFIX_ . 'customer", source)
        self.assertNotIn("_DB_PREFIX_ . 'orders", source)

    def test_pending_commerce_gate_returns_empty_sitemaps(self):
        source = (MODULE / "src/Customer/XmlSitemapService.php").read_text()
        self.assertIn("CommerceGate::isEnabled($profile, getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1')", source)
        self.assertIn("return self::response(200, $emptyXml)", source)
        self.assertIn("enabled_locales", source)
        self.assertIn("Language::getLanguages(true, $shopId)", source)
        self.assertIn("PS_UNIDENTIFIED_GROUP", source)
        self.assertIn("AnonymousGroupPolicy::resolve", source)
        self.assertNotIn("PS_CUSTOMER_GROUP", source)
        self.assertIn("return self::response(200, SitemapXmlRenderer::index([]) ?? '')", source)
        self.assertIn("return self::response(200, $emptyXml)", source)
        self.assertIn("Configuration::get('PS_UNIDENTIFIED_GROUP', null, null, $shopId)", source)
        self.assertIn("isAssociatedToShop($shopId)", source)
        self.assertNotIn("Context::getContext()->customer", source)
        endpoint = (MODULE / "src/Customer/SitemapEndpoint.php").read_text()
        self.assertIn("X-Robots-Tag: noindex", endpoint)
        self.assertIn("Cache-Control: private, no-store", endpoint)

    def test_configured_origin_and_public_route_policy_fail_closed(self):
        provider = (MODULE / "src/Infrastructure/ConfiguredShopUrlProvider.php").read_text()
        policy = (MODULE / "src/Customer/SitemapUrlPolicy.php").read_text()
        self.assertIn("_DB_PREFIX_ . 'shop_url", provider)
        self.assertIn("active = 1 AND main = 1", provider)
        for source in (provider, policy):
            self.assertNotIn("$_SERVER", source)
            self.assertNotIn("HTTP_HOST", source)
            self.assertNotIn("SERVER_NAME", source)
        self.assertIn("parseUniqueQuery", policy)
        self.assertIn("canonicalizeNativeUrl", policy)
        self.assertNotIn("authentication", policy)

    def test_sitemap_limits_and_robots_core_rules_are_preserved(self):
        policy = (MODULE / "src/Customer/SitemapUrlPolicy.php").read_text()
        robots = (MODULE / "src/Customer/RobotsSitemapDirective.php").read_text()
        php_fixture = (ROOT / "tests/business_profile/sitemap_policy.php").read_text()
        self.assertIn("MAX_URLS_PER_SITEMAP = 10000", policy)
        self.assertIn("MAX_SITEMAPS_PER_INDEX = 10000", policy)
        self.assertIn("MAX_XML_BYTES = 50 * 1024 * 1024", policy)
        self.assertIn("Sitemap[ \\t]*:", robots)
        self.assertIn("OWNER_MARKER", robots)
        self.assertIn("trim((string) $lines[$index]) !== self::OWNER_MARKER", robots)
        self.assertIn("Sitemap: https://core.example.test/1_index_sitemap.xml", php_fixture)
        self.assertIn("Sitemap: https://manual.example.test/custom.xml", php_fixture)
        self.assertIn("Sitemap: https://shop.example.test/sitemap.xml", php_fixture)
        self.assertIn("AnonymousGroupPolicy::resolve(true, 3, 3, false) === null", php_fixture)
        self.assertIn("AnonymousGroupPolicy::resolve(true, 3, 3, true) === [true, 3]", php_fixture)
        self.assertIn("MAX_URL_BYTES - strlen($urlPrefix)", php_fixture)
        self.assertIn("array_fill(0, 10000", php_fixture)
        self.assertIn("rewriteContent($content, $sitemapUrl)", robots)
        self.assertIn("PS_REWRITING_SETTINGS", (MODULE / "kuraneabusinessprofile.php").read_text())

    def test_private_content_and_untrusted_link_parameters_are_not_emitted(self):
        source = (MODULE / "src/Infrastructure/PublicSitemapRepository.php").read_text()
        policy = (MODULE / "src/Customer/SitemapUrlPolicy.php").read_text()
        self.assertNotIn("customer", source.lower())
        self.assertNotIn("authentication", source.lower())
        self.assertNotIn("cart", source.lower())
        self.assertNotIn("search", source.lower())
        self.assertIn("preview", (ROOT / "tests/business_profile/sitemap_policy.php").read_text())
        self.assertIn("str_starts_with($path, $basePath)", policy)
        self.assertIn("containsDotSegment($decodedPath)", policy)
        self.assertIn("str_contains($key, '[')", policy)


if __name__ == "__main__":
    unittest.main()
