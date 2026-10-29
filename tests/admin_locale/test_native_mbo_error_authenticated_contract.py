from pathlib import Path
import os
import shutil
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SOURCE = Path(__file__).with_name("native_mbo_error_authenticated.php").read_text(encoding="utf-8")
BOOTSTRAP = Path(__file__).with_name("prepare_test_browserkit.sh").read_text(encoding="utf-8")


class AuthenticatedNativeMboErrorContract(unittest.TestCase):
    def test_project_inventory_uses_actual_native_module_without_optional_xml(self):
        php = os.environ.get('ORDENOWA_TEST_PHP') or shutil.which('php')
        if not php:
            self.skipTest('PHP required for actual module metadata regression')
        for name in ('module_inventory_behavior.php', 'native_admin_kernel_browser_behavior.php',
                     'native_admin_private_snapshot_behavior.php', 'native_admin_http_login_behavior.php'):
            result = subprocess.run([php, '-n', str(Path(__file__).with_name(name))],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_uses_production_kernel_and_real_login_form(self):
        self.assertIn("new AdminKernel('prod', false)", SOURCE)
        self.assertIn("new NativeAdminKernelBrowser($kernel", SOURCE)
        self.assertIn("define('_PS_APP_ID_', AdminKernel::APP_ID)", SOURCE)
        self.assertIn('Request::enableHttpMethodParameterOverride()', SOURCE)
        self.assertIn("require_once __DIR__ . '/native_admin_kernel_browser.php'", SOURCE)
        self.assertIn("Symfony\\Component\\BrowserKit\\AbstractBrowser::class", SOURCE)
        self.assertIn("Symfony\\Component\\DomCrawler\\Crawler::class", SOURCE)
        self.assertIn("Symfony\\Component\\CssSelector\\CssSelectorConverter::class", SOURCE)
        self.assertIn("$browser->disableReboot()", SOURCE)
        self.assertIn("NativeAdminHttpLogin::authenticate(", SOURCE)
        self.assertNotIn("$browser->request('POST', $loginTarget, $loginFields)", SOURCE)
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

    def test_native_login_uses_real_http_then_one_authenticated_kernel_request(self):
        helper = Path(__file__).with_name('native_admin_http_login.php').read_text(encoding='utf-8')
        self.assertIn("NativeAdminHttpLogin::authenticate(", SOURCE)
        self.assertIn("NativeAdminHttpLogin::installInBrowserKit($browser->getCookieJar(), $nativeLoginCookies)", SOURCE)
        self.assertIn("$browser->nativeRequestCount === 1", SOURCE)
        self.assertIn("'native_login_transport' => 'loopback_http_native_front_controller'", SOURCE)
        self.assertIn("'native_login_loopback_http_requests' => $nativeLoopbackHttpRequestCount", SOURCE)
        self.assertIn("CURLOPT_CONNECT_TO => ['localhost:18081:127.0.0.1:80']", helper)
        self.assertIn("CURLOPT_FOLLOWLOCATION => false", helper)
        self.assertIn("CURLOPT_PROTOCOLS_STR, 'http'", helper)
        self.assertIn("$options[CURLOPT_POSTFIELDS] = null", helper)
        self.assertIn("$options[CURLOPT_HTTPGET] = true", helper)
        self.assertNotIn("$browser->request('POST', $loginTarget, $loginFields)", SOURCE)

    def test_curl_method_order_reaches_only_an_ephemeral_loopback_server(self):
        php = os.environ.get('ORDENOWA_TEST_PHP') or shutil.which('php')
        if not php:
            self.skipTest('PHP required for native cURL method regression')
        command = [php]
        extension = os.environ.get('ORDENOWA_TEST_PHP_CURL_EXTENSION')
        if extension:
            extension_path = Path(extension).resolve()
            command += ['-n', '-d', f'extension_dir={extension_path.parent}', '-d', f'extension={extension_path.name}']
        probe = subprocess.run(command + ['-r', 'exit(extension_loaded("curl") ? 0 : 1);'],
                                capture_output=True, text=True, timeout=10)
        if probe.returncode != 0:
            self.skipTest('PHP cURL extension unavailable')

        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                requests.append(('GET', self.path, body))
                self.send_response(200)
                self.send_header('Content-Length', '4')
                self.end_headers()
                self.wfile.write(b'GET:')

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                requests.append(('POST', self.path, body))
                response = b'POST:' + body
                self.send_response(200)
                self.send_header('Content-Length', str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, _format, *_args):
                return

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_address[1]}/probe'
            script = Path(__file__).with_name('native_admin_http_login_curl_behavior.php')
            run = subprocess.run(command + [str(script), url], capture_output=True, text=True, timeout=10)
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)
            self.assertEqual('native cURL request methods: ok\n', run.stdout)
            self.assertEqual([('GET', '/probe', b''), ('POST', '/probe', b'mode=probe')], requests)
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=3)

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
