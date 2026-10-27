"""Keep the live sitemap check scoped to the disposable local shop."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/fresh-install.yml'
PHP_FIXTURE = ROOT / 'tests/business_profile/verify_ci_sitemap_runtime_fixture.php'
HTTP_CHECK = ROOT / 'tests/e2e/verify_ci_sitemap_routes.py'


class SitemapHttpAcceptanceContractTests(unittest.TestCase):
    def test_runtime_fixture_is_isolated_read_only_and_guest_scoped(self) -> None:
        source = PHP_FIXTURE.read_text(encoding='utf-8')
        for required in (
            "getenv('KURANEA_ISOLATED_CI') !== '1'",
            "getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1'",
            'new ConfiguredShopUrlProvider()',
            'Tools::getRobotsContent()',
            "!is_array($robotsContent)",
            "$robotsContent['Allow']",
            "$robotsContent['Directories']",
            "$robotsContent['Files']",
            "$robotsContent['GB']",
            'Tools::getDomains()',
            "@file_get_contents(_PS_ROOT_DIR_ . '/robots.txt')",
            "Language::getLanguages(true, $shopId)",
            'new PublishedProfileProvider(new VersionedProfileRepository())',
            'PublishedProfileProvider::localeForIso($iso)',
            'CommerceGate::isEnabled(',
            'Group::isFeatureActive()',
            'category_group',
            'product_shop',
            'robots_core_directive_sha256',
            'robots_core_sitemap_sha256',
            "'enabled_profile_locales' => $enabledProfileLocales",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        for forbidden in (
            'Configuration::updateValue',
            'INSERT INTO',
            'UPDATE ',
            'DELETE ',
            "$_SERVER['HTTP_HOST']",
            "getenv('HTTP_HOST')",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_http_check_is_loopback_only_and_logs_no_response_text(self) -> None:
        source = HTTP_CHECK.read_text(encoding='utf-8')
        for required in (
            "parts.hostname == 'localhost'",
            'parts.port == 18080',
            'urlopen(request, timeout=10)',
            "fetch(base_url, 'robots.txt', 'text/plain')",
            "fetch(base_url, 'sitemap.xml', 'application/xml')",
            "f'sitemap-{locale}-1.xml'",
            'ElementTree.fromstring(body)',
            "fixture.get('enabled_profile_locales') == ['ja', 'en', 'ko']",
            'pending seller authorization exposed sitemap index entries',
            'PrestaShop Allow/Disallow directives were not preserved',
            'PrestaShop sitemap directives were not preserved',
            "'result': 'success'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertNotIn('print(robots_text', source)
        self.assertNotIn('print(index_body', source)

    def test_workflow_waits_for_published_locales_and_product_fixtures(self) -> None:
        source = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('tests.e2e.test_ci_sitemap_routes_contract', source)
        marker = '- name: Verify pending-gate sitemap and robots over local HTTP'
        self.assertIn(marker, source)
        step = source.split(marker, 1)[1].split('      - name:', 1)[0]
        for required in (
            'id: seo_sitemap_http',
            'continue-on-error: true',
            "steps.compose_up.outcome == 'success'",
            "steps.shipping_product_fixture.outcome == 'success'",
            "steps.brand_browser_qa.outcome == 'success'",
            "steps.product_admin_browser_qa.outcome == 'success'",
            "env.ORDENOWA_ADMIN_QA_FOCUS != 'true'",
            'CI_TEST_PRODUCT_ID=',
            'verify_ci_sitemap_runtime_fixture.php',
            'verify_ci_sitemap_routes.py',
        ):
            with self.subTest(required=required):
                self.assertIn(required, step)
        self.assertIn('steps.seo_sitemap_http.outcome', source)
        self.assertIn('SEO_SITEMAP_HTTP_OUTCOME', source)
        self.assertIn('seo_sitemap_http=$SEO_SITEMAP_HTTP_OUTCOME', source)
        self.assertIn(
            'if [[ "$BRAND_BROWSER_QA_OUTCOME" == success',
            source,
        )
        self.assertIn(
            '&& "$SHIPPING_PRODUCT_FIXTURE_OUTCOME" == success',
            source,
        )
        self.assertIn(
            '&& "$PRODUCT_ADMIN_BROWSER_QA_OUTCOME" == success',
            source,
        )
        self.assertIn(
            '&& "$SEO_SITEMAP_HTTP_OUTCOME" != success ]]',
            source,
        )
        self.assertLess(
            source.index('id: shipping_product_fixture'),
            source.index(marker),
        )
        self.assertLess(source.index('id: brand_browser_qa'), source.index(marker))
        self.assertLess(source.index('id: product_admin_browser_qa'), source.index(marker))
        self.assertLess(source.index(marker), source.index('Enable exact run synthetic catalog import adapter'))


if __name__ == '__main__':
    unittest.main()
