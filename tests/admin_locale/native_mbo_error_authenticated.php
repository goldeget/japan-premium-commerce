<?php

declare(strict_types=1);

use PrestaShop\Module\Mbo\Service\ExternalContentProvider\ExternalContentProvider;
use PrestaShop\Module\Mbo\Service\ExternalContentProvider\ExternalContentProviderInterface;
use Symfony\Bundle\FrameworkBundle\KernelBrowser;
use Symfony\Component\HttpKernel\Exception\ServiceUnavailableHttpException;

ini_set('display_errors', '0');
ini_set('log_errors', '0');
$probeBufferLevel = ob_get_level();
ob_start();
$emitSafeOutcome = static function (array $outcome) use ($probeBufferLevel): void {
    while (ob_get_level() > $probeBufferLevel) { ob_end_clean(); }
    echo json_encode($outcome, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . PHP_EOL;
};

$stage = 'ci_guard';
$moduleInventory = [];
$testDependencySources = [];
$injectedProvider = null;
$nativeHttpTransport = null;
$nativeHttpLoginResult = null;
$nativeLoginCookies = [];
$nativeLoopbackHttpRequestCount = 0;
$shopRoot = dirname(__DIR__, 2);

/** Fail with a fixed stage only; exception text and request data can carry secrets. */
$require = static function (bool $condition, string $reason): void {
    if (!$condition) {
        throw new RuntimeException($reason);
    }
};

/**
 * Resolve a same-origin admin URI. Redirects and form actions may never send
 * the test client to another host or escape the installed admin path.
 */
$localAdminUri = static function (string $candidate, string $baseUri): string {
    if ($candidate === '') {
        $candidate = $baseUri;
    }

    $parts = parse_url($candidate);
    if (!is_array($parts) || isset($parts['user']) || isset($parts['pass']) || isset($parts['fragment'])) {
        throw new RuntimeException('unsafe_local_uri');
    }
    if (isset($parts['scheme']) || isset($parts['host'])) {
        if (($parts['scheme'] ?? '') !== 'http'
            || strtolower((string) ($parts['host'] ?? '')) !== 'localhost'
            || (int) ($parts['port'] ?? 80) !== 18081) {
            throw new RuntimeException('non_local_uri');
        }
    }

    $path = (string) ($parts['path'] ?? '');
    if ($path === '') {
        $baseParts = parse_url($baseUri);
        $path = is_array($baseParts) ? (string) ($baseParts['path'] ?? '') : '';
    } elseif (!str_starts_with($path, '/')) {
        $baseParts = parse_url($baseUri);
        $basePath = is_array($baseParts) ? (string) ($baseParts['path'] ?? '/') : '/';
        $baseDirectory = str_ends_with($basePath, '/') ? rtrim($basePath, '/') : dirname($basePath);
        $path = rtrim($baseDirectory, '/') . '/' . $path;
    }

    if (str_contains($path, '\\') || preg_match('~(?:\A|/)\.\.?(/|\z)|%2e|%2f|%5c~i', $path)
        || !preg_match('~\A/admin-kuranea(?:/|\z)~D', $path)) {
        throw new RuntimeException('admin_uri_out_of_scope');
    }

    $query = isset($parts['query']) && $parts['query'] !== '' ? '?' . $parts['query'] : '';
    return $path . $query;
};

$parseLoginForm = static function (string $html): ?array {
    $previousLibxmlState = libxml_use_internal_errors(true);
    try {
        $document = new DOMDocument();
        if (!$document->loadHTML($html, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING)) {
            return null;
        }
        $xpath = new DOMXPath($document);
        $forms = $xpath->query('//form[@id="login_form"]');
        if ($forms === false || $forms->length !== 1) {
            return null;
        }
        $form = $forms->item(0);
        if (!$form instanceof DOMElement || strtolower($form->getAttribute('method') ?: 'get') !== 'post') {
            return null;
        }

        $fields = [];
        $emailName = null;
        $passwordName = null;
        foreach ($xpath->query('.//input[@name]', $form) ?: [] as $input) {
            if (!$input instanceof DOMElement) {
                continue;
            }
            $name = $input->getAttribute('name');
            $type = strtolower($input->getAttribute('type') ?: 'text');
            if ($type === 'hidden') {
                if (array_key_exists($name, $fields)) {
                    return null;
                }
                $fields[$name] = $input->getAttribute('value');
            } elseif ($name === 'email' && in_array($type, ['text', 'email'], true)) {
                $emailName = $name;
            } elseif (in_array($name, ['passwd', 'password'], true) && $type === 'password') {
                $passwordName = $name;
            }
        }
        if ($emailName === null || $passwordName === null) {
            return null;
        }

        return [
            'action' => $form->getAttribute('action'),
            'fields' => $fields,
            'email_name' => $emailName,
            'password_name' => $passwordName,
        ];
    } finally {
        libxml_clear_errors();
        libxml_use_internal_errors($previousLibxmlState);
    }
};

$hasLoginForm = static function (string $html) use ($parseLoginForm): bool {
    return $parseLoginForm($html) !== null;
};

$readModule = static function (string $name, bool $mustBeActive, array $installed, array $active, string $modulesRoot): array {
    if (!in_array($name, $installed, true)) {
        throw new RuntimeException('module_not_installed');
    }
    $isActive = in_array($name, $active, true);
    if ($mustBeActive && !$isActive) {
        throw new RuntimeException('module_not_active');
    }

    $modulePath = realpath($modulesRoot . DIRECTORY_SEPARATOR . $name);
    if ($modulePath === false || dirname($modulePath) !== $modulesRoot || basename($modulePath) !== $name) {
        throw new RuntimeException('module_path_invalid');
    }
    // Project modules keep their authoritative version in the native Module
    // instance; config.xml is optional in PrestaShop and is absent here.
    if ($name === 'kuraneabackoffice') {
        $module = Module::getInstanceByName($name);
        if (!$module instanceof Module || $module->name !== $name
            || realpath((new ReflectionClass($module))->getFileName()) !== $modulePath . DIRECTORY_SEPARATOR . $name . '.php') {
            throw new RuntimeException('project_module_instance_mismatch');
        }
        $version = (string) $module->version;
        if (!preg_match('/\A[0-9][A-Za-z0-9.+_-]{0,31}\z/D', $version)) {
            throw new RuntimeException('module_version_invalid');
        }
        return ['installed' => true, 'active' => $isActive, 'version' => $version];
    }
    $configPath = $modulePath . DIRECTORY_SEPARATOR . 'config.xml';
    if (!is_file($configPath)) {
        throw new RuntimeException('module_config_missing');
    }

    libxml_use_internal_errors(true);
    libxml_clear_errors();
    $xml = @simplexml_load_file($configPath, SimpleXMLElement::class, LIBXML_NONET | LIBXML_NOBLANKS);
    libxml_clear_errors();
    if (!$xml instanceof SimpleXMLElement || $xml->getName() !== 'module' || trim((string) $xml->name) !== $name) {
        throw new RuntimeException('module_config_invalid');
    }

    $version = trim((string) $xml->version);
    if (!preg_match('/\A[0-9][A-Za-z0-9.+_-]{0,31}\z/D', $version)) {
        throw new RuntimeException('module_version_invalid');
    }
    return ['installed' => true, 'active' => $isActive, 'version' => $version];
};

try {
    $runId = getenv('GITHUB_RUN_ID') ?: '';
    $runAttempt = getenv('GITHUB_RUN_ATTEMPT') ?: '';
    $expectedProject = 'ordenowa-procurement-ci-' . $runId . '-' . $runAttempt;
    $adminEmail = getenv('ADMIN_MAIL') ?: '';
    $adminPassword = getenv('ADMIN_PASSWD') ?: '';
    $expectedAdminEmail = 'procurement-admin-' . $runId . '-' . $runAttempt . '@example.invalid';
    $require(
        getenv('KURANEA_ISOLATED_CI') === '1'
        && getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && preg_match('/\A[0-9]{1,20}\z/D', $runId) === 1
        && preg_match('/\A[0-9]{1,8}\z/D', $runAttempt) === 1
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject
        && getenv('PS_DOMAIN') === 'localhost:18081'
        && hash_equals($expectedAdminEmail, $adminEmail)
        && preg_match('/\A[A-Za-z0-9_-]{32,128}\z/D', $adminPassword) === 1,
        'isolated_ci_auth_guard'
    );

    $stage = 'admin_bootstrap_path';
    $adminRoot = realpath($shopRoot . '/admin-kuranea');
    $shopRootReal = realpath($shopRoot);
    $require(
        $adminRoot !== false && $shopRootReal !== false && dirname($adminRoot) === $shopRootReal
        && is_file($adminRoot . '/index.php') && is_dir($adminRoot . '/themes'),
        'native_admin_path_missing'
    );
    if (!defined('_PS_ADMIN_DIR_')) {
        define('_PS_ADMIN_DIR_', $adminRoot);
    } elseif (realpath(_PS_ADMIN_DIR_) !== $adminRoot) {
        throw new RuntimeException('native_admin_path_mismatch');
    }
    require_once __DIR__ . '/native_admin_http_login.php';
    $nativeTargetUri = '/admin-kuranea/index.php/mbo/themes/catalog';
    $stage = 'native_login_get';
    $nativeHttpTransport = new NativeAdminHttpCurlTransport();
    $nativeHttpLoginResult = NativeAdminHttpLogin::authenticate(
        '/admin-kuranea/',
        $adminEmail,
        $adminPassword,
        static fn (string $method, string $uri, ?array $fields): array => $nativeHttpTransport->request($method, $uri, $fields),
        static fn (): array => $nativeHttpTransport->cookies(),
        $parseLoginForm,
        $hasLoginForm,
        $localAdminUri,
        static function (string $nextStage) use (&$stage): void { $stage = $nextStage; }
    );
    $nativeLoginCookies = NativeAdminHttpLogin::validateCookies($nativeHttpLoginResult['cookies'] ?? null);
    $nativeLoopbackHttpRequestCount = $nativeHttpTransport->requestCount();
    $nativeHttpTransport->close();
    $nativeHttpTransport = null;
    $require(
        ($nativeHttpLoginResult['login_form_posted'] ?? false) === true
        && is_string($nativeHttpLoginResult['final_uri'] ?? null)
        && $nativeLoopbackHttpRequestCount >= 3 && $nativeLoopbackHttpRequestCount <= 14
        && count($nativeLoginCookies) >= 1 && count($nativeLoginCookies) <= NativeAdminHttpLogin::MAX_COOKIES,
        'native_http_login_proof_invalid'
    );

    $_SERVER['HTTP_HOST'] = 'localhost:18081';
    $_SERVER['SERVER_NAME'] = 'localhost';
    $_SERVER['SERVER_PORT'] = '18081';
    $_SERVER['SERVER_PROTOCOL'] = 'HTTP/1.1';
    $_SERVER['REQUEST_SCHEME'] = 'http';
    $_SERVER['REQUEST_METHOD'] = 'GET';
    $_SERVER['REMOTE_ADDR'] = '127.0.0.1';
    $_SERVER['REQUEST_URI'] = $nativeTargetUri;
    $_SERVER['QUERY_STRING'] = '';
    $_SERVER['SCRIPT_NAME'] = '/admin-kuranea/index.php';
    $_SERVER['PHP_SELF'] = '/admin-kuranea/index.php';
    $_SERVER['SCRIPT_FILENAME'] = $adminRoot . '/index.php';
    $_SERVER['REQUEST_METHOD'] = 'GET';
    $_GET = [];
    $_POST = [];
    $_FILES = [];
    $_COOKIE = NativeAdminHttpLogin::globalsForUri($nativeLoginCookies, $nativeTargetUri);
    $_REQUEST = $_COOKIE;

    $stage = 'bootstrap';
    $baseVendorAutoload = $shopRoot . '/vendor/autoload.php';
    if (!is_file($baseVendorAutoload)) {
        throw new RuntimeException('base_autoloader_missing');
    }
    $baseLoader = require_once $baseVendorAutoload;
    if (!$baseLoader instanceof \Composer\Autoload\ClassLoader) {
        throw new RuntimeException('base_composer_loader_unavailable');
    }

    $stage = 'test_only_dependency_bootstrap';
    $testDependencyRoot = '/tmp/owned/kuranea-admin-test-deps';
    $sourceRoot = realpath($testDependencyRoot . '/source');
    $manifestPath = $testDependencyRoot . '/source-revisions.json';
    if ($sourceRoot === false || $sourceRoot !== $testDependencyRoot . '/source' || !is_file($manifestPath)
        || is_dir($testDependencyRoot . '/source/browser-kit/.git')
        || is_dir($testDependencyRoot . '/source/css-selector/.git')) {
        throw new RuntimeException('test_only_dependencies_missing');
    }
    $manifestBytes = file_get_contents($manifestPath);
    $dependencyManifest = is_string($manifestBytes) ? json_decode($manifestBytes, true) : null;
    $expectedManifest = [
        'symfony/browser-kit' => [
            'version' => '6.4.44',
            'source_commit' => '4f631476bb549d882a173c47bf693f3ef84c722d',
        ],
        'symfony/css-selector' => [
            'version' => '6.4.45',
            'source_commit' => '5484e316cd8125f5215bbf829151e2211aa6d101',
        ],
        'symfony/dom-crawler' => [
            'version' => '6.4.44',
            'source_commit' => '998855f6c3699f148b54096d1d7d2b8b0b0fc298',
        ],
    ];
    if (!is_array($dependencyManifest)) {
        throw new RuntimeException('test_only_dependency_manifest_invalid');
    }
    foreach ($expectedManifest as $package => $expected) {
        $actual = $dependencyManifest[$package] ?? null;
        if (!is_array($actual) || ($actual['version'] ?? null) !== $expected['version']
            || ($actual['source_commit'] ?? null) !== $expected['source_commit']) {
            throw new RuntimeException('test_only_dependency_revision_mismatch');
        }
        if (isset($actual['archive_sha256'])
            && preg_match('/\A[a-f0-9]{64}\z/D', (string) $actual['archive_sha256']) !== 1) {
            throw new RuntimeException('test_only_dependency_digest_invalid');
        }
        $testDependencySources[$package] = [
            'version' => $expected['version'],
            'source_commit' => $expected['source_commit'],
            'archive_sha256' => $actual['archive_sha256'] ?? null,
        ];
    }

    $browserKitRoot = realpath($sourceRoot . '/browser-kit');
    $cssSelectorRoot = realpath($sourceRoot . '/css-selector');
    if ($browserKitRoot !== $sourceRoot . '/browser-kit' || $cssSelectorRoot !== $sourceRoot . '/css-selector'
        || !is_file($browserKitRoot . '/AbstractBrowser.php')
        || !is_file($cssSelectorRoot . '/CssSelectorConverter.php')) {
        throw new RuntimeException('test_only_dependency_source_invalid');
    }
    if (!class_exists(\Composer\InstalledVersions::class)
        || \Composer\InstalledVersions::getPrettyVersion('symfony/dom-crawler') !== 'v6.4.44'
        || \Composer\InstalledVersions::getReference('symfony/dom-crawler') !== $expectedManifest['symfony/dom-crawler']['source_commit']) {
        throw new RuntimeException('production_dom_crawler_version_mismatch');
    }
    // Register only the two official Symfony PSR-4 roots that are require-dev
    // in PrestaShop 9.2.0. The production vendor tree remains untouched.
    $baseLoader->addPsr4('Symfony\\Component\\BrowserKit\\', $browserKitRoot);
    $baseLoader->addPsr4('Symfony\\Component\\CssSelector\\', $cssSelectorRoot);

    require_once $shopRoot . '/autoload.php';
    require_once $shopRoot . '/config/config.inc.php';
    require_once $shopRoot . '/app/AppKernel.php';
    require_once $shopRoot . '/app/AdminKernel.php';
    if (defined('_PS_APP_ID_') && _PS_APP_ID_ !== AdminKernel::APP_ID) {
        throw new RuntimeException('native_admin_app_id_mismatch');
    }
    if (!defined('_PS_APP_ID_')) {
        define('_PS_APP_ID_', AdminKernel::APP_ID);
    }

    if (!defined('_PS_BO_ALL_THEMES_DIR_') || realpath(_PS_BO_ALL_THEMES_DIR_) !== realpath($adminRoot . '/themes')) {
        throw new RuntimeException('native_admin_theme_constant_missing');
    }

    $stage = 'admin_kernel_boot';
    $kernel = new AdminKernel('prod', false);
    $kernel->boot();
    $container = $kernel->getContainer();

    $stage = 'module_inventory';
    $installedModules = $container->getParameter('prestashop.installed_modules');
    $activeModules = $container->getParameter('prestashop.active_modules');
    if (!is_array($installedModules) || !is_array($activeModules)) {
        throw new RuntimeException('module_readback_unavailable');
    }
    $modulesRoot = realpath(_PS_MODULE_DIR_);
    if ($modulesRoot === false) {
        throw new RuntimeException('module_directory_unavailable');
    }
    $moduleInventory['ps_mbo'] = $readModule('ps_mbo', true, $installedModules, $activeModules, $modulesRoot);
    if ($moduleInventory['ps_mbo']['version'] !== '5.3.2') {
        throw new RuntimeException('mbo_version_mismatch');
    }
    $moduleInventory['kuraneabackoffice'] = $readModule('kuraneabackoffice', true, $installedModules, $activeModules, $modulesRoot);

    $stage = 'native_route_services';
    if (!class_exists(KernelBrowser::class)
        || !class_exists(\Symfony\Component\BrowserKit\AbstractBrowser::class)
        || !class_exists(\Symfony\Component\DomCrawler\Crawler::class)
        || !class_exists(\Symfony\Component\CssSelector\CssSelectorConverter::class)
        || !class_exists(ExternalContentProvider::class)
        || !interface_exists(ExternalContentProviderInterface::class)) {
        throw new RuntimeException('native_browser_dependencies_or_mbo_provider_unavailable');
    }
    $providerId = ExternalContentProvider::class;
    $providerInterfaceId = ExternalContentProviderInterface::class;
    if (!method_exists($container, 'initialized') || !method_exists($container, 'set')
        || !$container->has($providerId) || !$container->has($providerInterfaceId)) {
        throw new RuntimeException('native_provider_override_unsupported');
    }

    $stage = 'install_test_only_provider';
    $injectedProvider = new class implements ExternalContentProviderInterface {
        public int $calls = 0;

        public function getContent(string $url, array $options = []): string
        {
            ++$this->calls;
            $parts = parse_url($url);
            if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https'
                || strtolower((string) ($parts['host'] ?? '')) !== 'addons.prestashop.com'
                || isset($parts['user']) || isset($parts['pass'])) {
                throw new RuntimeException('unexpected_mbo_destination');
            }
            throw new ServiceUnavailableHttpException(
                null,
                'Synthetic isolated-CI transport failure',
                null,
                0,
                ['X-ORDENOWA-CI-Injected-Failure' => '1']
            );
        }
    };

    if ($container->initialized($providerId) || $container->initialized($providerInterfaceId)) {
        throw new RuntimeException('native_provider_already_initialized');
    }
    $container->set($providerId, $injectedProvider);
    if ($container->get($providerInterfaceId) !== $injectedProvider) {
        throw new RuntimeException('native_provider_override_not_effective');
    }

    $nativeSessionCsrfVerified = false;
    $nativeSessionCsrfProbeCount = 0;
    $container->get('event_dispatcher')->addListener(
        \Symfony\Component\HttpKernel\KernelEvents::RESPONSE,
        static function (\Symfony\Component\HttpKernel\Event\ResponseEvent $event) use (
            $container, &$nativeSessionCsrfVerified, &$nativeSessionCsrfProbeCount
        ): void {
            if (!$event->isMainRequest()
                || $event->getRequest()->attributes->get('_route') !== 'admin_mbo_catalog_theme') {
                return;
            }
            ++$nativeSessionCsrfProbeCount;
            $html = $event->getResponse()->getContent();
            if (!is_string($html)) return;
            $oldLibxml = libxml_use_internal_errors(true);
            try {
                $document = new DOMDocument();
                if (!$document->loadHTML($html, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING)) return;
                $bodies = (new DOMXPath($document))->query('/html/body');
                if ($bodies === false || $bodies->length !== 1 || !$bodies->item(0) instanceof DOMElement) return;
                $nativeToken = $bodies->item(0)->getAttribute('data-token');
                $validator = $container->get(\Kuranea\Backoffice\Admin\AdminPostTokenValidator::class);
                $nativeSessionCsrfVerified = $nativeToken !== ''
                    && $validator instanceof \Kuranea\Backoffice\Admin\AdminPostTokenValidator
                    && $validator->valid($nativeToken)
                    && !$validator->valid(str_repeat('a', 64));
            } finally {
                libxml_clear_errors();
                libxml_use_internal_errors($oldLibxml);
            }
        },
        -16
    );

    require_once __DIR__ . '/native_admin_kernel_browser.php';
    \Symfony\Component\HttpFoundation\Request::enableHttpMethodParameterOverride();
    $stage = 'native_authenticated_error_route';
    $browser = new NativeAdminKernelBrowser($kernel, [
        'HTTP_HOST' => 'localhost:18081',
        'SERVER_NAME' => 'localhost',
        'SERVER_PORT' => '18081',
        'SERVER_PROTOCOL' => 'HTTP/1.1',
        'REQUEST_SCHEME' => 'http',
        'HTTPS' => 'off',
        'SCRIPT_NAME' => '/admin-kuranea/index.php',
        'PHP_SELF' => '/admin-kuranea/index.php',
        'SCRIPT_FILENAME' => $adminRoot . '/index.php',
        'REMOTE_ADDR' => '127.0.0.1',
        'HTTP_ACCEPT' => 'text/html,application/xhtml+xml',
        'HTTP_USER_AGENT' => 'ORDENOWA-isolated-ci-kernel-browser',
    ]);
    $browser->disableReboot();
    NativeAdminHttpLogin::installInBrowserKit($browser->getCookieJar(), $nativeLoginCookies);
    if ($container->get($providerInterfaceId) !== $injectedProvider) {
        throw new RuntimeException('native_provider_override_lost');
    }

    $catalogPath = $container->get('router')->generate('admin_mbo_catalog_theme');
    if ($catalogPath !== '/mbo/themes/catalog') {
        throw new RuntimeException('native_mbo_route_contract_mismatch');
    }
    $catalogUri = '/admin-kuranea/index.php' . $catalogPath;
    if ($catalogUri !== $nativeTargetUri) {
        throw new RuntimeException('native_mbo_target_uri_mismatch');
    }
    $browser->request('GET', $catalogUri);
    $require($browser->nativeRequestCount === 1, 'native_kernel_browser_target_request_count_invalid');
    $response = $browser->getResponse();
    $body = $response->getContent();
    if (!is_string($body)) {
        throw new RuntimeException('native_mbo_response_body_missing');
    }

    $stage = 'assert_authenticated_korean_error';
    $sourceMessage = 'It looks like we have trouble connecting to Addons. Please refresh the page or check your firewall configuration.';
    $koreanMessage = 'Addons에 연결하는 데 문제가 있는 것 같습니다. 페이지를 새로고침하거나 방화벽 설정을 확인해 주세요.';
    $contentType = strtolower((string) $response->headers->get('Content-Type', ''));
    $documentLanguage = '';
    $previousLibxmlState = libxml_use_internal_errors(true);
    try {
        $document = new DOMDocument();
        if ($document->loadHTML($body, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING)) {
            $htmlNodes = (new DOMXPath($document))->query('/html');
            if ($htmlNodes !== false && $htmlNodes->length === 1 && $htmlNodes->item(0) instanceof DOMElement) {
                $documentLanguage = strtolower($htmlNodes->item(0)->getAttribute('lang'));
            }
        }
    } finally {
        libxml_clear_errors();
        libxml_use_internal_errors($previousLibxmlState);
    }

    $koreanOccurrences = substr_count($body, $koreanMessage);
    $require(
        $response->getStatusCode() === 503
        && $response->headers->get('X-ORDENOWA-CI-Injected-Failure') === '1'
        && str_contains($contentType, 'text/html')
        && preg_match('/\Ako(?:[-_]|\z)/i', $documentLanguage) === 1
        && $koreanOccurrences >= 2
        && !str_contains($body, $sourceMessage)
        && $injectedProvider->calls === 1
        && $nativeSessionCsrfVerified && $nativeSessionCsrfProbeCount === 1,
        'authenticated_korean_error_assertions_failed'
    );

    require_once __DIR__ . '/native_admin_private_snapshot.php';
    persistNativeAdminSnapshot('mbo', $body, '/tmp/owned/kuranea-admin-test-deps', $expectedProject);

    $outcome = [
        'schema' => 1,
        'passed' => true,
        'test_dependency_sources' => $testDependencySources,
        'module_inventory' => $moduleInventory,
        'mbo_error_render' => [
            'mode' => 'authenticated_production_kernel_browserkit_request',
            'actual_admin_login_form_post' => $nativeHttpLoginResult['login_form_posted'] === true,
            'native_login_transport' => 'loopback_http_native_front_controller',
            'native_login_loopback_http_requests' => $nativeLoopbackHttpRequestCount,
            'native_login_cookie_count' => count($nativeLoginCookies),
            'kernel_browser_target_request_count' => $browser->nativeRequestCount,
            'private_response_snapshot_sha256' => hash('sha256', $body),
            'native_session_csrf_verified' => $nativeSessionCsrfVerified,
            'native_session_csrf_probe_count' => $nativeSessionCsrfProbeCount,
            'native_route' => 'admin_mbo_catalog_theme',
            'controller' => 'ThemeCatalogController::indexAction',
            'response_status' => 503,
            'injected_header_verified' => true,
            'full_native_layout' => true,
            'korean_document_language' => true,
            'korean_message_occurrences' => $koreanOccurrences,
            'english_source_absent' => true,
            'injected_provider_invocations' => $injectedProvider->calls,
            'injected_provider_http_calls' => 0,
            'browser_socket_requests' => 0,
            'script_initiated_business_mutations' => false,
            'authentication_session_or_audit_writes_possible' => true,
            'bootstrap_database_side_effects_instrumented' => false,
            'bootstrap_network_side_effects_instrumented' => false,
        ],
    ];
    $emitSafeOutcome($outcome);
    exit(0);
} catch (Throwable $error) {
    if ($nativeHttpTransport instanceof NativeAdminHttpCurlTransport) {
        $nativeHttpTransport->close();
    }
    fwrite(STDERR, 'FAIL authenticated native MBO error stage=' . $stage . PHP_EOL);
    $outcome = [
        'schema' => 1,
        'passed' => false,
        'failed_stage' => $stage,
        'exception_class' => preg_match('/\A[A-Za-z0-9_\\\\]{1,160}\z/D', get_class($error)) === 1
            ? get_class($error)
            : 'redacted',
        'injected_provider_invocations' => $injectedProvider === null ? 0 : $injectedProvider->calls,
        'injected_provider_http_calls' => 0,
        'browser_socket_requests' => 0,
        'script_initiated_business_mutations' => false,
        'authentication_session_or_audit_writes_possible' => true,
        'bootstrap_database_side_effects_instrumented' => false,
        'bootstrap_network_side_effects_instrumented' => false,
        'test_dependency_sources' => $testDependencySources,
        'module_inventory' => $moduleInventory,
    ];
    if ($error instanceof Twig\Error\Error) {
        $sourceName = $error->getSourceContext()?->getName() ?? '';
        if (preg_match('~\A@(?:PrestaShop/Admin|PrestaShopCore|Modules/ps_mbo)/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.twig\z~D', $sourceName)) {
            $outcome['twig_template'] = $sourceName;
        }
        $line = $error->getTemplateLine();
        if (is_int($line) && $line > 0 && $line <= 100000) {
            $outcome['twig_template_line'] = $line;
        }
    }
    $cause = $error;
    for ($depth = 0; $depth < 6 && $cause->getPrevious() !== null; ++$depth) $cause = $cause->getPrevious();
    $causeClass = get_class($cause);
    if (preg_match('/\A[A-Za-z0-9_\\\\]{1,160}\z/D', $causeClass)) $outcome['cause_class'] = $causeClass;
    $outcome['failure_trace'] = [];
    foreach (array_slice($cause->getTrace(), 0, 8) as $frame) {
        $class = (string) ($frame['class'] ?? '');
        $function = (string) ($frame['function'] ?? '');
        $file = basename(str_replace('\\', '/', (string) ($frame['file'] ?? '')));
        $line = $frame['line'] ?? 0;
        if (strlen($class) <= 160 && preg_match('/\A[A-Za-z0-9_\\\\]{1,160}\z/D', $class)
            && preg_match('/\A[A-Za-z_][A-Za-z0-9_]{0,79}\z/D', $function)
            && preg_match('/\A[A-Za-z0-9_.-]{1,120}\.php\z/D', $file)
            && is_int($line) && $line > 0 && $line <= 1000000) {
            $outcome['failure_trace'][] = ['class' => $class, 'function' => $function, 'source' => $file . ':' . $line];
        }
    }
    $sourceBase = basename(str_replace('\\', '/', $cause->getFile()));
    if (preg_match('/\A[A-Za-z0-9_.-]{1,180}\.php\z/D', $sourceBase)
        && $cause->getLine() > 0 && $cause->getLine() <= 1000000) {
        $outcome['failure_source'] = $sourceBase . ':' . $cause->getLine();
    }
    $emitSafeOutcome($outcome);
    exit(1);
}
