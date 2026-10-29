from pathlib import Path
import os
import shutil
import subprocess
import unittest


SOURCE = Path(__file__).with_name("native_mbo_error_authenticated.php").read_text(encoding="utf-8")
BOOTSTRAP = Path(__file__).with_name("prepare_test_browserkit.sh").read_text(encoding="utf-8")


class AuthenticatedNativeMboErrorContract(unittest.TestCase):
    def test_project_inventory_uses_actual_native_module_without_optional_xml(self):
        php = os.environ.get('ORDENOWA_TEST_PHP') or shutil.which('php')
        if not php:
            self.skipTest('PHP required for actual module metadata regression')
        result = subprocess.run([php, '-n', str(Path(__file__).with_name('module_inventory_behavior.php'))],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_uses_production_kernel_and_real_login_form(self):
        self.assertIn("new AdminKernel('prod', false)", SOURCE)
        self.assertIn("new KernelBrowser($kernel", SOURCE)
        self.assertIn("Symfony\\Component\\BrowserKit\\AbstractBrowser::class", SOURCE)
        self.assertIn("Symfony\\Component\\DomCrawler\\Crawler::class", SOURCE)
        self.assertIn("Symfony\\Component\\CssSelector\\CssSelectorConverter::class", SOURCE)
        self.assertIn("$browser->disableReboot()", SOURCE)
        self.assertIn("$browser->request('POST', $loginTarget, $loginFields)", SOURCE)
        self.assertIn("$browser->request('GET', $catalogUri)", SOURCE)
        self.assertIn("generate('admin_mbo_catalog_theme')", SOURCE)
        self.assertNotIn("loginUser(", SOURCE)
        self.assertNotIn("ThemeCatalogController::class)->indexAction", SOURCE)
        self.assertNotIn("setLocale(", SOURCE)
        self.assertNotIn("addResource(", SOURCE)
        self.assertNotIn("liteDisplaying", SOURCE)

    def test_fake_is_installed_before_requests_and_fails_closed(self):
        self.assertIn("$container->initialized($providerId)", SOURCE)
        self.assertIn("$container->set($providerId, $injectedProvider)", SOURCE)
        self.assertIn("$container->get($providerInterfaceId) !== $injectedProvider", SOURCE)
        self.assertIn("'addons.prestashop.com'", SOURCE)
        self.assertIn("new ServiceUnavailableHttpException(", SOURCE)
        self.assertIn("'X-ORDENOWA-CI-Injected-Failure' => '1'", SOURCE)
        self.assertIn("'injected_provider_http_calls' => 0", SOURCE)
        self.assertIn("'bootstrap_network_side_effects_instrumented' => false", SOURCE)
        self.assertIn("browser_socket_requests", SOURCE)

    def test_test_dependencies_are_exact_and_stay_outside_the_shop(self):
        self.assertIn("browser_kit_commit=4f631476bb549d882a173c47bf693f3ef84c722d", BOOTSTRAP)
        self.assertIn("css_selector_commit=5484e316cd8125f5215bbf829151e2211aa6d101", BOOTSTRAP)
        self.assertIn("git -C \"$checkout\" rev-parse FETCH_HEAD", BOOTSTRAP)
        self.assertIn("git -C \"$checkout\" archive --format=tar", BOOTSTRAP)
        self.assertIn("/tmp/owned/kuranea-admin-test-deps", BOOTSTRAP)
        self.assertIn("/tmp/owned/kuranea-admin-test-deps", SOURCE)
        self.assertIn("Composer\\InstalledVersions::getReference('symfony/dom-crawler')", SOURCE)
        self.assertNotIn("composer install", BOOTSTRAP.lower())
        self.assertNotIn("/var/www/html/vendor", BOOTSTRAP)

    def test_authenticated_korean_error_assertions_are_strict(self):
        self.assertIn("$response->getStatusCode() === 503", SOURCE)
        self.assertIn("$response->headers->get('X-ORDENOWA-CI-Injected-Failure') === '1'", SOURCE)
        self.assertIn("preg_match('/\\Ako(?:[-_]|\\z)/i', $documentLanguage) === 1", SOURCE)
        self.assertIn("$koreanOccurrences >= 2", SOURCE)
        self.assertIn("!str_contains($body, $sourceMessage)", SOURCE)
        self.assertIn("$injectedProvider->calls === 1", SOURCE)
        self.assertIn("hash_equals($expectedAdminEmail, $adminEmail)", SOURCE)
        self.assertIn("'authentication_session_or_audit_writes_possible' => true", SOURCE)
        self.assertNotIn("getMessage()", SOURCE)
        self.assertNotIn("getTraceAsString()", SOURCE)


if __name__ == "__main__":
    unittest.main()
