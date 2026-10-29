from pathlib import Path
import os
import shutil
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("native_mbo_error_authenticated.php").read_text(encoding="utf-8")
BOOTSTRAP = Path(__file__).with_name("prepare_test_browserkit.sh").read_text(encoding="utf-8")


class AuthenticatedNativeMboErrorContract(unittest.TestCase):
    def test_project_inventory_uses_actual_native_module_without_optional_xml(self):
        php = os.environ.get('ORDENOWA_TEST_PHP') or shutil.which('php')
        if not php:
            self.skipTest('PHP required for actual module metadata regression')
        for name in ('module_inventory_behavior.php', 'native_admin_kernel_browser_behavior.php',
                     'native_admin_private_snapshot_behavior.php', 'native_admin_http_login_behavior.php'):
            env = os.environ.copy()
            env.setdefault('ORDENOWA_TEST_REPO_ROOT', str(ROOT))
            # Linux loads DOM from the configured XML extension; -n disables it.
            # The real HTML/token behavior requires DOM and must still fail if absent.
            php_options = [] if name == 'native_admin_http_login_behavior.php' else ['-n']
            result = subprocess.run([php, *php_options, str(Path(__file__).with_name(name))],
                                    capture_output=True, text=True, timeout=20, env=env)
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
        self.assertIn("self::extractNativeBodyToken", helper)
        self.assertIn("NativeAdminMboRoute::nativeTargetUri($nativeSessionToken)", SOURCE)
        self.assertIn("NativeAdminMboRoute::canonicalizeGeneratedUri($catalogPath, $nativeSessionToken)", SOURCE)
        self.assertIn("$_SERVER['QUERY_STRING'] = '_token=' . rawurlencode($nativeSessionToken)", SOURCE)
        self.assertIn("$_GET = ['_token' => $nativeSessionToken]", SOURCE)
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
        for assertion in (
            'native_mbo_response_status_not_503', 'native_mbo_injected_header_missing',
            'native_mbo_content_type_not_html', 'native_mbo_document_language_not_korean',
            'native_mbo_korean_message_occurrences_insufficient', 'native_mbo_english_source_message_present',
            'native_mbo_provider_invocation_count_invalid', 'native_mbo_session_csrf_probe_count_invalid',
            'native_mbo_session_csrf_not_verified',
        ):
            self.assertIn(assertion, SOURCE)
        self.assertNotIn("getMessage()", SOURCE)
        self.assertNotIn("getTraceAsString()", SOURCE)

    def test_failed_native_assertion_has_only_allowlisted_facts_and_private_capture(self):
        self.assertIn("$failedAssertion = $reason", SOURCE)
        self.assertIn("$failureFacts = [", SOURCE)
        self.assertIn("'scope' => 'mbo_native_error_assertion_failure'", SOURCE)
        self.assertIn("'body_base64' => base64_encode($body)", SOURCE)
        self.assertIn("persistNativeAdminSnapshot(\n                    'mbo-auth-landing'", SOURCE)
        self.assertIn("assert_authenticated_korean_error", Path(__file__).with_name('ci_authenticated_mbo.sh').read_text(encoding='utf-8'))
        self.assertIn("MBO_FAILURE_ASSERTIONS", Path(__file__).with_name('safe_authenticated_outcome.py').read_text(encoding='utf-8'))

    def test_native_token_is_private_and_route_is_module_prefixed(self):
        helper = Path(__file__).with_name('native_admin_http_login.php').read_text(encoding='utf-8')
        route_helper = Path(__file__).with_name('native_admin_mbo_route.php').read_text(encoding='utf-8')
        self.assertIn("query('/html/body')", helper)
        self.assertIn("getAttribute('data-token')", helper)
        self.assertIn("[A-Za-z0-9_-]{1,32}\\.[A-Za-z0-9_-]{43}\\.[A-Za-z0-9_-]{43,256}", helper)
        self.assertIn("'/modules/mbo/themes/catalog/'", route_helper)
        self.assertIn("'/admin-kuranea/index.php/modules/mbo/themes/catalog/'", route_helper)
        self.assertIn("'?_token=' . rawurlencode($nativeSessionToken)", route_helper)
        outcome_start = SOURCE.index("    $outcome = [")
        outcome_end = SOURCE.index("    $emitSafeOutcome($outcome);", outcome_start)
        self.assertNotIn('native_body_token', SOURCE[outcome_start:outcome_end])
        self.assertNotIn('nativeSessionToken', SOURCE[outcome_start:outcome_end])


if __name__ == "__main__":
    unittest.main()
