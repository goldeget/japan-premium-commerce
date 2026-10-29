<?php

declare(strict_types=1);

use Symfony\Bundle\FrameworkBundle\KernelBrowser;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Event\ControllerEvent;
use Symfony\Component\HttpKernel\KernelEvents;

ini_set('display_errors', '0');
ini_set('log_errors', '0');
$probeBufferLevel = ob_get_level();
ob_start();
$emitSafeOutcome = static function (array $value) use ($probeBufferLevel): void {
    while (ob_get_level() > $probeBufferLevel) ob_end_clean();
    echo json_encode($value, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . PHP_EOL;
};

require_once __DIR__ . '/native_admin_http_login.php';

$stage = 'ci_guard';
$shopRoot = dirname(__DIR__, 2);
$moduleInventory = [];
$dependencySources = [];
$outcome = [];
$caseName = getenv('ORDENOWA_FACEBOOK_CASE') ?: '';
$caseModes = [
    'unauthenticated' => 'disabled',
    'other_route' => 'other_route_runtime',
    'generic_facebook' => 'generic_facebook_runtime',
    'access_denied' => 'facebook_access_denied',
    'curl_transport' => 'curl_transport',
];
$mode = $caseModes[$caseName] ?? 'invalid';
$nativeLogin = null;
$nativeCookies = [];
$nativeHttpBodyToken = null;
$nativeHttpBodyTokenApplied = false;
$isolatedCiGuardPassed = false;
$nativeLoginRequests = 0;
$nativeLoginStages = [];
$injectionCounts = [
    'target_controller_events' => 0,
    'known_facebook_request_controller_events' => 0,
    'mismatched_facebook_route_events' => 0,
    'disabled_mode_facebook_sentinels' => 0,
    'http_client_requests' => 0,
    'generic_facebook_exceptions' => 0,
    'facebook_access_denied_exceptions' => 0,
    'other_route_exceptions' => 0,
];
$nativeSessionCsrfVerified = false;
$nativeSessionCsrfProbeCount = 0;
$authenticatedReadGatePasses = 0;
$observedFacebookControllerEvent = false;
$observedDashboardControllerEvent = false;
$observedDashboardRouteName = 'not_observed';
$dashboardUri = null;
$heldSockets = [];

$require = static function (bool $condition, string $reason): void {
    if (!$condition) {
        throw new RuntimeException($reason);
    }
};

$readModule = static function (
    string $name,
    array $installed,
    array $active,
    string $modulesRoot,
    bool $readModuleRuntimeMetadata = false
): array {
    if (!in_array($name, $installed, true)) {
        throw new RuntimeException('module_not_installed');
    }
    $modulePath = realpath($modulesRoot . DIRECTORY_SEPARATOR . $name);
    if ($modulePath === false || dirname($modulePath) !== $modulesRoot || basename($modulePath) !== $name) {
        throw new RuntimeException('module_path_invalid');
    }
    if ($readModuleRuntimeMetadata) {
        $module = \Module::getInstanceByName($name);
        $moduleClassFile = $module instanceof \Module
            ? realpath((new ReflectionClass($module))->getFileName())
            : false;
        $expectedModuleClassFile = realpath($modulePath . DIRECTORY_SEPARATOR . $name . '.php');
        if (!$module instanceof \Module || $module->name !== $name
            || $moduleClassFile === false || $moduleClassFile !== $expectedModuleClassFile) {
            throw new RuntimeException('project_module_instance_mismatch');
        }
        $version = trim((string) $module->version);
    } else {
        $configPath = $modulePath . DIRECTORY_SEPARATOR . 'config.xml';
        if (!is_file($configPath)) {
            throw new RuntimeException('module_config_missing');
        }

        libxml_use_internal_errors(true);
        libxml_clear_errors();
        $xml = @simplexml_load_file($configPath, SimpleXMLElement::class, LIBXML_NONET | LIBXML_NOBLANKS);
        libxml_clear_errors();
        if (!$xml instanceof SimpleXMLElement || $xml->getName() !== 'module'
            || trim((string) $xml->name) !== $name) {
            throw new RuntimeException('module_config_invalid');
        }
        $version = trim((string) $xml->version);
    }
    if (preg_match('/\A[0-9][A-Za-z0-9.+_-]{0,31}\z/D', $version) !== 1) {
        throw new RuntimeException('module_version_invalid');
    }

    return [
        'installed' => true,
        'active' => in_array($name, $active, true),
        'version' => $version,
        'module_path' => $modulePath,
    ];
};

$localAdminUri = static function (string $candidate, string $baseUri): string {
    if ($candidate === '') {
        $candidate = $baseUri;
    }
    $parts = parse_url($candidate);
    if (!is_array($parts) || isset($parts['user']) || isset($parts['pass']) || isset($parts['fragment'])) {
        throw new RuntimeException('unsafe_admin_uri');
    }
    if (isset($parts['scheme']) || isset($parts['host'])) {
        if (($parts['scheme'] ?? '') !== 'http' || strtolower((string) ($parts['host'] ?? '')) !== 'localhost'
            || (int) ($parts['port'] ?? 80) !== 18081) {
            throw new RuntimeException('non_local_admin_uri');
        }
    }
    $path = (string) ($parts['path'] ?? '');
    if ($path === '') {
        $baseParts = parse_url($baseUri);
        $path = is_array($baseParts) ? (string) ($baseParts['path'] ?? '') : '';
    } elseif (!str_starts_with($path, '/')) {
        $baseParts = parse_url($baseUri);
        $basePath = is_array($baseParts) ? (string) ($baseParts['path'] ?? '/') : '/';
        $path = rtrim(dirname($basePath), '/') . '/' . $path;
    }
    if (str_contains($path, '\\') || preg_match('~(?:\A|/)\.\.?(/|\z)|%2e|%2f|%5c~i', $path) === 1
        || !preg_match('~\A/admin-kuranea(?:/|\z)~D', $path)) {
        throw new RuntimeException('admin_uri_out_of_scope');
    }
    return $path . (isset($parts['query']) && $parts['query'] !== '' ? '?' . $parts['query'] : '');
};

$applyNativeHttpBodyToken = static function (
    string $generatedUri,
    string $nativeBodyToken,
    string $baseUri
) use ($localAdminUri): string {
    if (!class_exists(NativeAdminHttpLogin::class)
        || !NativeAdminHttpLogin::isSymfonyUriSafeToken($nativeBodyToken)) {
        throw new RuntimeException('native_http_body_token_invalid');
    }
    $uri = $localAdminUri($generatedUri, $baseUri);
    $parts = parse_url($uri);
    if (!is_array($parts) || !isset($parts['path']) || !isset($parts['query']) || $parts['query'] === '') {
        throw new RuntimeException('native_generated_admin_token_field_missing');
    }

    $queryParts = explode('&', (string) $parts['query']);
    $tokenIndexes = ['token' => null, '_token' => null];
    foreach ($queryParts as $index => $queryPart) {
        if ($queryPart === '') {
            throw new RuntimeException('native_generated_admin_query_invalid');
        }
        $separator = strpos($queryPart, '=');
        $rawName = $separator === false ? $queryPart : substr($queryPart, 0, $separator);
        $rawValue = $separator === false ? '' : substr($queryPart, $separator + 1);
        $name = urldecode($rawName);
        if (!array_key_exists($name, $tokenIndexes)) {
            continue;
        }
        if ($tokenIndexes[$name] !== null) {
            throw new RuntimeException('native_generated_admin_token_field_ambiguous');
        }
        $generatedToken = urldecode($rawValue);
        if ($generatedToken !== '' && !NativeAdminHttpLogin::isSymfonyUriSafeToken($generatedToken)) {
            throw new RuntimeException('native_generated_admin_token_invalid');
        }
        $tokenIndexes[$name] = $index;
        $queryParts[$index] = $rawName . '=' . rawurlencode($nativeBodyToken);
    }
    if ($tokenIndexes['token'] === null && $tokenIndexes['_token'] === null) {
        throw new RuntimeException('native_generated_admin_token_field_missing');
    }

    return (string) $parts['path'] . '?' . implode('&', $queryParts);
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
        if ($forms === false || $forms->length !== 1 || !$forms->item(0) instanceof DOMElement) {
            return null;
        }
        $form = $forms->item(0);
        if (strtolower($form->getAttribute('method') ?: 'get') !== 'post') {
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

$hasLoginForm = static fn (string $html): bool => $parseLoginForm($html) !== null;

$isLocalAdminLoginRedirect = static function (mixed $location, string $baseUri) use ($localAdminUri): bool {
    if (!is_string($location) || $location === '') {
        return false;
    }

    try {
        $target = $localAdminUri($location, $baseUri);
    } catch (Throwable) {
        return false;
    }
    $parts = parse_url($target);
    if (!is_array($parts)) {
        return false;
    }

    $query = [];
    parse_str((string) ($parts['query'] ?? ''), $query);
    if (($query['controller'] ?? null) === 'AdminLogin') {
        return true;
    }

    return preg_match(
        '~\\A/admin-kuranea/(?:login|index\\.php/login)(?:/|\\z)~D',
        (string) ($parts['path'] ?? '')
    ) === 1;
};

$classifyUnauthenticatedResponse = static function (
    int $status,
    mixed $location,
    bool $hasLoginForm,
    string $baseUri
) use ($isLocalAdminLoginRedirect): string {
    if ($status === 401) {
        return 'http_401';
    }
    if ($status === 403) {
        return 'http_403';
    }
    if ($status === 200 && $hasLoginForm) {
        return 'local_admin_login_form';
    }
    if (in_array($status, [301, 302, 303, 307, 308], true)
        && $isLocalAdminLoginRedirect($location, $baseUri)) {
        return 'local_admin_login_redirect';
    }

    return 'not_proven';
};

$safeControllerEventTarget = static function (Request $request): bool {
    return $request->getMethod() === 'GET'
        && $request->attributes->get('_route') === 'admin_legacy_controller_route'
        && $request->attributes->get('_controller')
            === 'PrestaShopBundle\\Controller\\Admin\\LegacyController::legacyPageAction'
        && $request->attributes->get('_legacy_controller_name') === 'AdminPsfacebookModule'
        && $request->attributes->get('_legacy_controller_class') === 'AdminPsfacebookModuleController'
        && $request->attributes->get('_legacy_controller_action') === 'read'
        && $request->attributes->get('_legacy_controller_is_module') === true
        && $request->attributes->get('_anonymous_controller') === false
        && is_object($request->attributes->get('_legacy_controller_instance'))
        && get_class($request->attributes->get('_legacy_controller_instance')) === 'AdminPsfacebookModuleController';
};

try {
    $runId = getenv('GITHUB_RUN_ID') ?: '';
    $runAttempt = getenv('GITHUB_RUN_ATTEMPT') ?: '';
    $expectedProject = 'ordenowa-procurement-ci-' . $runId . '-' . $runAttempt;
    $adminEmail = $caseName === 'unauthenticated' ? '' : (getenv('ADMIN_MAIL') ?: '');
    $adminPassword = $caseName === 'unauthenticated' ? '' : (getenv('ADMIN_PASSWD') ?: '');
    $expectedAdminEmail = 'procurement-admin-' . $runId . '-' . $runAttempt . '@example.invalid';
    $require(
        getenv('KURANEA_ISOLATED_CI') === '1'
        && getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && preg_match('/\A[0-9]{1,20}\z/D', $runId) === 1
        && preg_match('/\A[0-9]{1,8}\z/D', $runAttempt) === 1
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject
        && getenv('PS_DOMAIN') === 'localhost:18081'
        && ($caseName === 'unauthenticated'
            || (hash_equals($expectedAdminEmail, $adminEmail)
                && preg_match('/\A[A-Za-z0-9_-]{32,128}\z/D', $adminPassword) === 1)),
        'isolated_ci_auth_guard'
    );
    $require(array_key_exists($caseName, $caseModes), 'isolated_facebook_case_guard');
    $isolatedCiGuardPassed = true;

    $stage = 'admin_bootstrap_path';
    $adminRoot = realpath($shopRoot . '/admin-kuranea');
    $shopRootReal = realpath($shopRoot);
    $require($adminRoot !== false && $shopRootReal !== false && dirname($adminRoot) === $shopRootReal
        && is_file($adminRoot . '/index.php') && is_dir($adminRoot . '/themes'), 'native_admin_path_missing');

    // Each invocation is one fresh PHP process. Authenticated cases perform
    // real HTTP login before configuration/session bootstrap.
    if ($caseName !== 'unauthenticated') {
        $stage = 'native_http_admin_login';
        $transport = new NativeAdminHttpCurlTransport();
        try {
            $nativeLogin = NativeAdminHttpLogin::authenticate(
                '/admin-kuranea/',
                $adminEmail,
                $adminPassword,
                [$transport, 'request'],
                [$transport, 'cookies'],
                $parseLoginForm,
                $hasLoginForm,
                $localAdminUri,
                static function (string $loginStage) use (&$nativeLoginStages): void {
                    $nativeLoginStages[] = $loginStage;
                }
            );
            if (!method_exists($transport, 'requestCount')) {
                throw new RuntimeException('native_http_request_counter_unavailable');
            }
            $nativeLoginRequests = $transport->requestCount();
            if (!is_int($nativeLoginRequests) || $nativeLoginRequests < 2 || $nativeLoginRequests > 20) {
                throw new RuntimeException('native_http_request_count_invalid');
            }
            if ($nativeLoginStages !== [
                'native_login_get', 'native_login_get_redirects', 'native_login_post', 'native_login_post_redirects',
            ]) {
                throw new RuntimeException('native_http_login_stage_sequence_invalid');
            }
            $nativeCookies = $nativeLogin['cookies'];
            $nativeHttpBodyToken = $nativeLogin['native_body_token'] ?? null;
            if (!is_string($nativeHttpBodyToken)
                || !NativeAdminHttpLogin::isSymfonyUriSafeToken($nativeHttpBodyToken)) {
                throw new RuntimeException('native_http_login_body_token_missing');
            }
            $_COOKIE = NativeAdminHttpLogin::globalsForUri($nativeCookies, $nativeLogin['final_uri']);
        } finally {
            $transport->close();
        }
    } else {
        $_COOKIE = [];
    }
    if (!defined('_PS_ADMIN_DIR_')) {
        define('_PS_ADMIN_DIR_', $adminRoot);
    } elseif (realpath(_PS_ADMIN_DIR_) !== $adminRoot) {
        throw new RuntimeException('native_admin_path_mismatch');
    }
    $_SERVER['HTTP_HOST'] = 'localhost:18081';
    $_SERVER['SERVER_NAME'] = 'localhost';
    $_SERVER['SERVER_PORT'] = '18081';
    $_SERVER['SERVER_PROTOCOL'] = 'HTTP/1.1';
    $_SERVER['REQUEST_SCHEME'] = 'http';
    $_SERVER['REQUEST_METHOD'] = 'GET';
    $_SERVER['REMOTE_ADDR'] = '127.0.0.1';
    $_SERVER['REQUEST_URI'] = '/admin-kuranea/';
    $_SERVER['SCRIPT_NAME'] = '/admin-kuranea/index.php';
    $_SERVER['PHP_SELF'] = '/admin-kuranea/index.php';
    $_SERVER['SCRIPT_FILENAME'] = $adminRoot . '/index.php';

    $stage = 'bootstrap';
    $baseVendorAutoload = $shopRoot . '/vendor/autoload.php';
    if (!is_file($baseVendorAutoload)) {
        throw new RuntimeException('base_autoloader_missing');
    }
    $baseLoader = require_once $baseVendorAutoload;
    if (!$baseLoader instanceof Composer\Autoload\ClassLoader) {
        throw new RuntimeException('base_composer_loader_unavailable');
    }

    $stage = 'test_only_dependency_bootstrap';
    $testDependencyRoot = '/tmp/owned/kuranea-admin-test-deps';
    $sourceRoot = realpath($testDependencyRoot . '/source');
    $manifestPath = $testDependencyRoot . '/source-revisions.json';
    if ($sourceRoot !== $testDependencyRoot . '/source' || !is_file($manifestPath)
        || is_dir($sourceRoot . '/browser-kit/.git') || is_dir($sourceRoot . '/css-selector/.git')) {
        throw new RuntimeException('test_only_dependencies_missing');
    }
    $manifestRaw = file_get_contents($manifestPath);
    $manifest = is_string($manifestRaw) ? json_decode($manifestRaw, true) : null;
    $expectedDependencies = [
        'symfony/browser-kit' => [
            'version' => '6.4.44', 'source_commit' => '4f631476bb549d882a173c47bf693f3ef84c722d', 'archive_required' => true,
        ],
        'symfony/css-selector' => [
            'version' => '6.4.45', 'source_commit' => '5484e316cd8125f5215bbf829151e2211aa6d101', 'archive_required' => true,
        ],
        'symfony/dom-crawler' => [
            'version' => '6.4.44', 'source_commit' => '998855f6c3699f148b54096d1d7d2b8b0b0fc298', 'archive_required' => false,
        ],
    ];
    foreach ($expectedDependencies as $name => $expected) {
        $actual = is_array($manifest) ? ($manifest[$name] ?? null) : null;
        if (!is_array($actual) || ($actual['version'] ?? null) !== $expected['version']
            || ($actual['source_commit'] ?? null) !== $expected['source_commit']) {
            throw new RuntimeException('test_dependency_revision_mismatch');
        }
        $archiveSha256 = $actual['archive_sha256'] ?? null;
        if ($expected['archive_required']
            ? (!is_string($archiveSha256) || preg_match('/\A[a-f0-9]{64}\z/D', $archiveSha256) !== 1)
            : ($archiveSha256 !== null)) {
            throw new RuntimeException('test_dependency_archive_digest_mismatch');
        }
        $dependencySources[$name] = [
            'version' => $expected['version'],
            'source_commit' => $expected['source_commit'],
            'archive_sha256' => $archiveSha256,
        ];
    }
    if (!class_exists(Composer\InstalledVersions::class)
        || Composer\InstalledVersions::getPrettyVersion('symfony/dom-crawler') !== 'v6.4.44'
        || Composer\InstalledVersions::getReference('symfony/dom-crawler') !== $expectedDependencies['symfony/dom-crawler']['source_commit']) {
        throw new RuntimeException('production_dom_crawler_version_mismatch');
    }
    $browserKitRoot = realpath($sourceRoot . '/browser-kit');
    $cssSelectorRoot = realpath($sourceRoot . '/css-selector');
    if ($browserKitRoot !== $sourceRoot . '/browser-kit' || $cssSelectorRoot !== $sourceRoot . '/css-selector'
        || !is_file($browserKitRoot . '/AbstractBrowser.php') || !is_file($cssSelectorRoot . '/CssSelectorConverter.php')) {
        throw new RuntimeException('test_dependency_source_invalid');
    }
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

    $stage = 'read_only_module_inventory';
    $installed = $container->getParameter('prestashop.installed_modules');
    $active = $container->getParameter('prestashop.active_modules');
    if (!is_array($installed) || !is_array($active)) {
        throw new RuntimeException('module_inventory_unavailable');
    }
    $modulesRoot = realpath(_PS_MODULE_DIR_);
    if ($modulesRoot === false) {
        throw new RuntimeException('module_directory_unavailable');
    }
    $moduleInventory['ps_facebook'] = $readModule('ps_facebook', $installed, $active, $modulesRoot);
    // The project module has no config.xml; read its declared version through
    // the native Module API instead of adding false metadata to its package.
    $moduleInventory['kuraneabackoffice'] = $readModule('kuraneabackoffice', $installed, $active, $modulesRoot, true);
    if (!$moduleInventory['ps_facebook']['active'] || $moduleInventory['ps_facebook']['version'] !== '1.38.19'
        || !$moduleInventory['kuraneabackoffice']['active'] || $moduleInventory['kuraneabackoffice']['version'] !== '1.0.8') {
        throw new RuntimeException('module_version_or_active_state_mismatch');
    }

    $stage = 'native_facebook_api_and_subscriber_contract';
    $httpClientClass = 'PrestaShop\\Module\\PrestashopFacebook\\Http\\HttpClient';
    $subscriberClass = 'Kuranea\\Backoffice\\AdminFacebookTransportExceptionSubscriber';
    $facebookAutoload = realpath($moduleInventory['ps_facebook']['module_path'] . '/vendor/autoload.php');
    if ($facebookAutoload === false
        || !str_starts_with($facebookAutoload, $moduleInventory['ps_facebook']['module_path'] . DIRECTORY_SEPARATOR)) {
        throw new RuntimeException('facebook_module_autoloader_missing');
    }
    require_once $facebookAutoload;
    if (!class_exists($httpClientClass) || !class_exists($subscriberClass)
        || !class_exists(KernelBrowser::class) || !class_exists(Symfony\Component\DomCrawler\Crawler::class)
        || !class_exists(Symfony\Component\CssSelector\CssSelectorConverter::class)) {
        throw new RuntimeException('native_test_classes_missing');
    }
    $httpClientReflection = new ReflectionClass($httpClientClass);
    $httpClientFile = realpath((string) $httpClientReflection->getFileName());
    $expectedHttpClientFile = realpath($moduleInventory['ps_facebook']['module_path'] . '/classes/Http/HttpClient.php');
    if ($httpClientReflection->getName() !== $httpClientClass || $httpClientFile === false
        || $httpClientFile !== $expectedHttpClientFile) {
        throw new RuntimeException('facebook_http_client_source_mismatch');
    }
    $constructor = $httpClientReflection->getConstructor();
    $getMethod = $httpClientReflection->getMethod('get');
    $requestMethod = $httpClientReflection->getMethod('request');
    if ($constructor === null || count($constructor->getParameters()) !== 1
        || $constructor->getDeclaringClass()->getName() !== $httpClientClass
        || (string) $constructor->getParameters()[0]->getType() !== 'string'
        || count($getMethod->getParameters()) !== 2 || (string) $getMethod->getParameters()[0]->getType() !== 'string'
        || (string) $getMethod->getParameters()[1]->getType() !== 'array'
        || count($requestMethod->getParameters()) < 2 || (string) $requestMethod->getParameters()[0]->getType() !== 'string'
        || (string) $requestMethod->getParameters()[1]->getType() !== 'string') {
        throw new RuntimeException('facebook_http_client_signature_mismatch');
    }
    $sourceHash = hash_file('sha256', $httpClientFile);
    if (!is_string($sourceHash) || !preg_match('/\A[a-f0-9]{64}\z/D', $sourceHash)) {
        throw new RuntimeException('facebook_http_client_hash_failed');
    }
    $dispatcher = $container->get('event_dispatcher');
    $exceptionListeners = [];
    foreach ($dispatcher->getListeners(KernelEvents::EXCEPTION) as $listener) {
        if (is_array($listener) && isset($listener[0], $listener[1]) && is_object($listener[0])
            && get_class($listener[0]) === $subscriberClass && $listener[1] === 'onKernelException') {
            $exceptionListeners[] = $listener;
        }
    }
    if (count($exceptionListeners) !== 1) {
        throw new RuntimeException('facebook_exception_subscriber_not_registered');
    }
    $exceptionSubscriber = $exceptionListeners[0][0];
    if (!method_exists($exceptionSubscriber, 'isAuthenticatedFacebookReadForIsolatedTest')) {
        throw new RuntimeException('test_only_security_bridge_unavailable');
    }

    require_once __DIR__ . '/native_admin_kernel_browser.php';
    \Symfony\Component\HttpFoundation\Request::enableHttpMethodParameterOverride();
    $stage = 'native_admin_kernel_browser_fixture';
    $browserServer = [
        'HTTP_HOST' => 'localhost:18081', 'SERVER_NAME' => 'localhost', 'SERVER_PORT' => '18081',
        'SERVER_PROTOCOL' => 'HTTP/1.1', 'REQUEST_SCHEME' => 'http', 'HTTPS' => false,
        'SCRIPT_NAME' => '/admin-kuranea/index.php', 'PHP_SELF' => '/admin-kuranea/index.php',
        'SCRIPT_FILENAME' => $adminRoot . '/index.php', 'REMOTE_ADDR' => '127.0.0.1',
        'HTTP_ACCEPT' => 'text/html,application/xhtml+xml', 'HTTP_USER_AGENT' => 'ORDENOWA-isolated-ci-kernel-browser',
    ];
    $browser = new NativeAdminKernelBrowser($kernel, $browserServer);
    $browser->disableReboot();
    if ($caseName !== 'unauthenticated') {
        if (($nativeLogin['login_form_posted'] ?? false) !== true || $nativeCookies === []) {
            throw new RuntimeException('native_http_login_contract_mismatch');
        }
        NativeAdminHttpLogin::installInBrowserKit($browser->getCookieJar(), $nativeCookies);
    }

    $stage = 'framework_generated_facebook_admin_link';
    $context = Context::getContext();
    if (!is_object($context->link) || !method_exists($context->link, 'getAdminLink')) {
        throw new RuntimeException('native_admin_link_unavailable');
    }
    $facebookLink = $context->link->getAdminLink('AdminPsfacebookModule', true);
    if (!is_string($facebookLink) || $facebookLink === '') {
        throw new RuntimeException('framework_facebook_link_missing');
    }
    $facebookUri = $localAdminUri($facebookLink, '/admin-kuranea/index.php');
    $facebookParts = parse_url($facebookUri);
    parse_str((string) (is_array($facebookParts) ? ($facebookParts['query'] ?? '') : ''), $facebookQuery);
    if (($facebookQuery['controller'] ?? null) !== 'AdminPsfacebookModule') {
        throw new RuntimeException('framework_facebook_link_contract_mismatch');
    }
    if ($caseName !== 'unauthenticated') {
        if (!is_string($nativeHttpBodyToken)) {
            throw new RuntimeException('native_http_login_body_token_missing');
        }
        $facebookUri = $applyNativeHttpBodyToken(
            $facebookUri,
            $nativeHttpBodyToken,
            '/admin-kuranea/index.php'
        );
        $nativeHttpBodyTokenApplied = true;
        $facebookParts = parse_url($facebookUri);
        $facebookQuery = [];
        parse_str((string) (is_array($facebookParts) ? ($facebookParts['query'] ?? '') : ''), $facebookQuery);
    }
    $facebookTokenField = array_key_exists('token', $facebookQuery)
        ? 'token'
        : (array_key_exists('_token', $facebookQuery) ? '_token' : null);
    $facebookToken = $facebookTokenField !== null && is_string($facebookQuery[$facebookTokenField])
        ? $facebookQuery[$facebookTokenField]
        : '';
    $frameworkLinkHasToken = $facebookToken !== '';
    if ($caseName !== 'unauthenticated' && !$frameworkLinkHasToken) {
        throw new RuntimeException('authenticated_framework_facebook_token_missing');
    }
    if ($caseName !== 'unauthenticated' && !hash_equals((string) $nativeHttpBodyToken, $facebookToken)) {
        throw new RuntimeException('authenticated_framework_facebook_token_source_mismatch');
    }

    $stage = 'test_only_controller_listener';
    $controllerListener = static function (ControllerEvent $event) use (
        &$mode,
        &$injectionCounts,
        &$authenticatedReadGatePasses,
        &$observedFacebookControllerEvent,
        &$observedDashboardControllerEvent,
        &$observedDashboardRouteName,
        &$heldSockets,
        $exceptionSubscriber,
        $facebookUri,
        &$dashboardUri,
        $moduleInventory,
        $safeControllerEventTarget
    ): void {
        if (!$event->isMainRequest()) {
            return;
        }
        $request = $event->getRequest();
        $isFacebook = $safeControllerEventTarget($request);
        $requestController = $request->query->get('controller', $request->request->get('controller'));
        $isKnownFacebookRequest = $request->getRequestUri() === $facebookUri
            || $requestController === 'AdminPsfacebookModule';
        if ($isFacebook) {
            $observedFacebookControllerEvent = true;
            ++$injectionCounts['target_controller_events'];
            $resolvedController = $event->getController();
            $isNativeLegacyAction = is_array($resolvedController)
                && isset($resolvedController[0], $resolvedController[1])
                && is_object($resolvedController[0])
                && is_a($resolvedController[0], 'PrestaShopBundle\\Controller\\Admin\\LegacyController')
                && $resolvedController[1] === 'legacyPageAction';
            if (is_string($resolvedController)) {
                $isNativeLegacyAction = $resolvedController
                    === 'PrestaShopBundle\\Controller\\Admin\\LegacyController::legacyPageAction';
            }
            if (!$isNativeLegacyAction) {
                throw new RuntimeException('native_legacy_controller_callable_mismatch');
            }
        }

        if ($isKnownFacebookRequest || $isFacebook) {
            ++$injectionCounts['known_facebook_request_controller_events'];
            if (!$isKnownFacebookRequest || !$isFacebook) {
                ++$injectionCounts['mismatched_facebook_route_events'];
                throw new RuntimeException('native_facebook_request_route_attribute_mismatch');
            }
            if ($mode === 'disabled') {
                ++$injectionCounts['disabled_mode_facebook_sentinels'];
                throw new RuntimeException('native_facebook_target_controller_event_in_disabled_mode');
            }
            if ($mode === 'other_route_runtime') {
                throw new RuntimeException('native_facebook_target_controller_event_in_other_route_mode');
            }
        }

        if ($mode === 'other_route_runtime') {
            $routeName = $request->attributes->get('_route');
            $legacyControllerName = $request->attributes->get('_legacy_controller_name');
            $dashboardRouteNames = ['admin_dashboard', 'admin_dashboard_index', 'admin_legacy_controller_route'];
            $isDashboardController = $request->getRequestUri() === $dashboardUri
                && ($requestController === 'AdminDashboard'
                    || $legacyControllerName === 'AdminDashboard'
                    || in_array($routeName, ['admin_dashboard', 'admin_dashboard_index'], true));
            if (!$isDashboardController) {
                throw new RuntimeException('native_other_route_target_mismatch');
            }
            $observedDashboardControllerEvent = true;
            $observedDashboardRouteName = in_array($routeName, $dashboardRouteNames, true)
                ? $routeName
                : 'not_observed';
            $injectionCounts['other_route_exceptions']++;
            throw new RuntimeException('Synthetic isolated-CI unrelated-route failure');
        }
        if (!$isFacebook) {
            return;
        }

        $legacyController = $request->attributes->get('_legacy_controller_instance');
        if (!$moduleInventory['ps_facebook']['active']
            || !$exceptionSubscriber->isAuthenticatedFacebookReadForIsolatedTest($request)
            || !($legacyController instanceof AdminController)
            || !is_object(Context::getContext()->controller)
            || Context::getContext()->controller !== $legacyController) {
            throw new RuntimeException('native_facebook_auth_context_mismatch');
        }
        ++$authenticatedReadGatePasses;

        if ($mode === 'generic_facebook_runtime') {
            ++$injectionCounts['generic_facebook_exceptions'];
            throw new RuntimeException('Synthetic isolated-CI non-transport failure');
        }
        if ($mode === 'facebook_access_denied') {
            ++$injectionCounts['facebook_access_denied_exceptions'];
            throw new Symfony\Component\HttpKernel\Exception\AccessDeniedHttpException('Synthetic isolated-CI access denial');
        }
        if ($mode !== 'curl_transport') {
            throw new RuntimeException('unknown_native_test_mode');
        }

        $bindError = 0;
        $bindMessage = '';
        $socket = @stream_socket_server(
            'tcp://127.0.0.1:0',
            $bindError,
            $bindMessage,
            STREAM_SERVER_BIND
        );
        if (!is_resource($socket)) {
            throw new RuntimeException('loopback_bind_failed');
        }
        $address = stream_socket_get_name($socket, false);
        if (!is_string($address) || !preg_match('/\A127\.0\.0\.1:([1-9][0-9]{0,4})\z/D', $address, $parts)) {
            fclose($socket);
            throw new RuntimeException('loopback_bind_address_invalid');
        }
        $port = (int) $parts[1];
        if ($port < 1 || $port > 65535) {
            fclose($socket);
            throw new RuntimeException('loopback_bind_port_invalid');
        }
        // STREAM_SERVER_LISTEN is intentionally absent. Hold the bound address so no
        // other process can claim it; no socket accepts a connection.
        $heldSockets[] = $socket;

        $proxyNames = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'];
        $previousProxyValues = [];
        foreach ($proxyNames as $proxyName) {
            $oldValue = getenv($proxyName);
            $previousProxyValues[$proxyName] = $oldValue === false ? null : $oldValue;
            putenv($proxyName . '=');
        }
        $previousNoProxy = getenv('NO_PROXY');
        $previousNoProxyLower = getenv('no_proxy');
        putenv('NO_PROXY=127.0.0.1,localhost');
        putenv('no_proxy=127.0.0.1,localhost');
        try {
            $httpClientClass = 'PrestaShop\\Module\\PrestashopFacebook\\Http\\HttpClient';
            $client = new $httpClientClass('https://127.0.0.1:' . $port);
            ++$injectionCounts['http_client_requests'];
            $client->get('/');
            throw new RuntimeException('loopback_http_client_unexpected_success');
        } finally {
            foreach ($previousProxyValues as $proxyName => $oldValue) {
                putenv($oldValue === null ? $proxyName : $proxyName . '=' . $oldValue);
            }
            putenv($previousNoProxy === false ? 'NO_PROXY' : 'NO_PROXY=' . $previousNoProxy);
            putenv($previousNoProxyLower === false ? 'no_proxy' : 'no_proxy=' . $previousNoProxyLower);
        }
    };
    $dispatcher->addListener(KernelEvents::CONTROLLER, $controllerListener, PHP_INT_MIN);
    $controllerListeners = $dispatcher->getListeners(KernelEvents::CONTROLLER);
    if ($controllerListeners === [] || end($controllerListeners) !== $controllerListener) {
        throw new RuntimeException('test_listener_priority_contract_mismatch');
    }
    $dispatcher->addListener(
        KernelEvents::RESPONSE,
        static function (Symfony\Component\HttpKernel\Event\ResponseEvent $event) use (
            $container,
            &$nativeSessionCsrfVerified,
            &$nativeSessionCsrfProbeCount
        ): void {
            if (!$event->isMainRequest()
                || $event->getRequest()->attributes->get('_route') !== 'admin_legacy_controller_route'
                || $event->getRequest()->getMethod() !== 'GET'
                || $event->getResponse()->getStatusCode() !== 503) {
                return;
            }
            $activeRequestStack = $container->get('request_stack');
            if (!$activeRequestStack instanceof Symfony\Component\HttpFoundation\RequestStack
                || $activeRequestStack->getCurrentRequest() !== $event->getRequest()) {
                return;
            }
            ++$nativeSessionCsrfProbeCount;
            $html = $event->getResponse()->getContent();
            if (!is_string($html)) {
                return;
            }
            $oldLibxml = libxml_use_internal_errors(true);
            try {
                $document = new DOMDocument();
                if (!$document->loadHTML($html, LIBXML_HTML_NOIMPLIED | LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING)) {
                    return;
                }
                $bodies = (new DOMXPath($document))->query('/html/body');
                if ($bodies === false || $bodies->length !== 1 || !$bodies->item(0) instanceof DOMElement) {
                    return;
                }
                $nativeToken = $bodies->item(0)->getAttribute('data-token');
                $validator = $container->get(Kuranea\Backoffice\Admin\AdminPostTokenValidator::class);
                $nativeSessionCsrfVerified = $nativeToken !== ''
                    && $validator instanceof Kuranea\Backoffice\Admin\AdminPostTokenValidator
                    && $validator->valid($nativeToken)
                    && !$validator->valid(str_repeat('a', 64));
            } finally {
                libxml_clear_errors();
                libxml_use_internal_errors($oldLibxml);
            }
        },
        -16
    );

    if ($caseName === 'other_route') {
        $dashboardLink = $context->link->getAdminLink('AdminDashboard', true);
        if (!is_string($dashboardLink) || $dashboardLink === '') {
            throw new RuntimeException('framework_dashboard_link_missing');
        }
        $dashboardUri = $localAdminUri($dashboardLink, '/admin-kuranea/index.php');
        if (!is_string($nativeHttpBodyToken)) {
            throw new RuntimeException('native_http_login_body_token_missing');
        }
        $dashboardUri = $applyNativeHttpBodyToken(
            $dashboardUri,
            $nativeHttpBodyToken,
            '/admin-kuranea/index.php'
        );
    }

    $stage = 'single_fresh_process_case_request';
    if ($caseName === 'unauthenticated') {
        if ($nativeLogin !== null || $nativeCookies !== [] || $_COOKIE !== []) {
            throw new RuntimeException('unauthenticated_case_has_auth_state');
        }
        $requestUri = $facebookUri;
    } elseif ($caseName === 'other_route') {
        $requestUri = $dashboardUri;
    } else {
        $requestUri = $facebookUri;
    }
    $require(is_string($requestUri) && $requestUri !== '', 'case_request_uri_missing');
    $browser->request('GET', $requestUri);
    $browserRequests = $browser->nativeRequestCount;
    $require($browserRequests === 1, 'one_native_target_request_required');
    $response = $browser->getResponse();
    $responseStatus = $response->getStatusCode();
    $body = $response->getContent();
    if (!is_string($body)) {
        throw new RuntimeException('case_response_body_unavailable');
    }

    $stage = 'case_specific_semantic_assertions';
    $safeTitle = 'Facebook 계정 연결을 일시적으로 사용할 수 없습니다';
    $safeMessage = 'Facebook 서비스에 연결하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.';
    $unauthenticatedAuthRejection = 'not_applicable';
    $caseChecks = [
        'unauthenticated_status_not_converted' => false,
        'other_route_status_not_converted' => false,
        'generic_facebook_status_not_converted' => false,
        'access_denied_status_preserved' => false,
        'facebook_fallback_response_safe' => false,
    ];
    $documentLanguage = '';
    $noSensitiveDetails = false;

    if ($caseName === 'unauthenticated') {
        $unauthenticatedAuthRejection = $classifyUnauthenticatedResponse(
            $responseStatus,
            $response->headers->get('Location'),
            $responseStatus === 200 && $hasLoginForm($body),
            $requestUri
        );
        $caseChecks['unauthenticated_status_not_converted'] = $responseStatus !== 503
            && !str_contains($body, $safeTitle)
            && $unauthenticatedAuthRejection !== 'not_proven'
            && !$observedFacebookControllerEvent
            && !$observedDashboardControllerEvent
            && $injectionCounts['target_controller_events'] === 0
            && $injectionCounts['known_facebook_request_controller_events'] === 0
            && $injectionCounts['mismatched_facebook_route_events'] === 0
            && $authenticatedReadGatePasses === 0
            && $injectionCounts['disabled_mode_facebook_sentinels'] === 0;
        $require($caseChecks['unauthenticated_status_not_converted'], 'unauthenticated_auth_rejection_not_proven');
    } elseif ($caseName === 'other_route') {
        $caseChecks['other_route_status_not_converted'] = $injectionCounts['other_route_exceptions'] === 1
            && $responseStatus !== 503 && !str_contains($body, $safeTitle);
        $require($caseChecks['other_route_status_not_converted'], 'unrelated_route_failure_was_converted');
    } elseif ($caseName === 'generic_facebook') {
        $caseChecks['generic_facebook_status_not_converted'] = $authenticatedReadGatePasses === 1
            && $injectionCounts['generic_facebook_exceptions'] === 1
            && $responseStatus !== 503 && !str_contains($body, $safeTitle);
        $require($caseChecks['generic_facebook_status_not_converted'], 'generic_facebook_exception_was_converted');
    } elseif ($caseName === 'access_denied') {
        $caseChecks['access_denied_status_preserved'] = $authenticatedReadGatePasses === 1
            && $injectionCounts['facebook_access_denied_exceptions'] === 1
            && $responseStatus === 403 && !str_contains($body, $safeTitle);
        $require($caseChecks['access_denied_status_preserved'], 'access_denied_was_converted_or_not_preserved');
    } elseif ($caseName === 'curl_transport') {
        if ($responseStatus !== 503 || $injectionCounts['http_client_requests'] !== 1
            || str_contains(strtolower((string) $response->headers->get('Cache-Control')), 'no-store') === false
            || strtolower((string) $response->headers->get('X-Robots-Tag')) !== 'noindex') {
            throw new RuntimeException('facebook_transport_fallback_response_mismatch');
        }
        $oldLibxmlState = libxml_use_internal_errors(true);
        $errorFragment = '';
        try {
            $document = new DOMDocument();
            if ($document->loadHTML($body, LIBXML_HTML_NOIMPLIED | LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING)) {
                $htmlNodes = (new DOMXPath($document))->query('/html');
                if ($htmlNodes !== false && $htmlNodes->length === 1 && $htmlNodes->item(0) instanceof DOMElement) {
                    $documentLanguage = strtolower($htmlNodes->item(0)->getAttribute('lang'));
                }
                $errorNodes = (new DOMXPath($document))->query('//*[@id="ordenowa-facebook-transport-error"]');
                if ($errorNodes !== false && $errorNodes->length === 1 && $errorNodes->item(0) instanceof DOMElement) {
                    $errorFragment = $errorNodes->item(0)->textContent;
                }
            }
        } finally {
            libxml_clear_errors();
            libxml_use_internal_errors($oldLibxmlState);
        }
        $noSensitiveDetails = $errorFragment !== '' && $frameworkLinkHasToken
            && !str_contains($errorFragment, $facebookToken);
        foreach (['cURL error', 'billing-api.distribution.prestashop.net', '127.0.0.1'] as $forbidden) {
            if (str_contains($body, $forbidden)) {
                $noSensitiveDetails = false;
            }
        }
        $caseChecks['facebook_fallback_response_safe'] = str_contains($body, $safeTitle)
            && str_contains($body, $safeMessage)
            && preg_match('/\Ako(?:[-_]|\z)/i', $documentLanguage) === 1
            && $response->headers->get('Content-Type') !== null
            && str_contains(strtolower((string) $response->headers->get('Content-Type')), 'text/html')
            && $noSensitiveDetails
            && $nativeSessionCsrfVerified && $nativeSessionCsrfProbeCount === 1
            && $authenticatedReadGatePasses === 1;
        $require($caseChecks['facebook_fallback_response_safe'], 'facebook_safe_html_or_csrf_assertions_failed');
    } else {
        throw new RuntimeException('unknown_isolated_facebook_case');
    }

    $sourceHashes = [
        'facebook_http_client_sha256' => $sourceHash,
        'project_subscriber_sha256' => hash_file('sha256', $moduleInventory['kuraneabackoffice']['module_path']
            . '/src/AdminFacebookTransportExceptionSubscriber.php'),
        'project_template_sha256' => hash_file('sha256', $moduleInventory['kuraneabackoffice']['module_path']
            . '/views/templates/admin/facebook_transport_error.html.twig'),
    ];
    if (!preg_match('/\A[a-f0-9]{64}\z/D', (string) $sourceHashes['project_subscriber_sha256'])
        || !preg_match('/\A[a-f0-9]{64}\z/D', (string) $sourceHashes['project_template_sha256'])) {
        throw new RuntimeException('project_fallback_source_missing');
    }

    $snapshotHash = null;
    if ($caseName === 'curl_transport') {
        if (!$nativeSessionCsrfVerified || $nativeSessionCsrfProbeCount !== 1
            || !$caseChecks['facebook_fallback_response_safe']) {
            throw new RuntimeException('facebook_private_snapshot_not_yet_proven');
        }
        require_once __DIR__ . '/native_admin_private_snapshot.php';
        $ownedDependencyRoot = '/tmp/owned/kuranea-admin-test-deps';
        persistNativeAdminSnapshot('facebook', $body, $ownedDependencyRoot, $expectedProject);
        $snapshotHash = hash('sha256', $body);
        if (!is_string($snapshotHash) || !preg_match('/\A[a-f0-9]{64}\z/D', $snapshotHash)) {
            throw new RuntimeException('facebook_private_snapshot_hash_invalid');
        }
    }

    $outcome = [
        'schema' => 4,
        'passed' => true,
        'case' => $caseName,
        'module_inventory' => [
            'ps_facebook' => ['installed' => true, 'active' => true, 'version' => $moduleInventory['ps_facebook']['version']],
            'kuraneabackoffice' => ['installed' => true, 'active' => true, 'version' => $moduleInventory['kuraneabackoffice']['version']],
        ],
        'source_sha256' => $sourceHashes,
        'facebook_case_facts' => [
            'native_login_transport' => $caseName === 'unauthenticated' ? 'none' : 'loopback_http_native_front_controller',
            'native_login_form_posted' => $caseName !== 'unauthenticated' && ($nativeLogin['login_form_posted'] ?? false) === true,
            'native_login_http_requests' => $nativeLoginRequests,
            'native_login_stages_verified' => $caseName === 'unauthenticated'
                ? $nativeLoginStages === []
                : $nativeLoginStages === [
                    'native_login_get', 'native_login_get_redirects', 'native_login_post', 'native_login_post_redirects',
                ],
            'native_http_body_token_applied' => $nativeHttpBodyTokenApplied,
            'framework_generated_legacy_link' => true,
            'framework_link_has_token' => $frameworkLinkHasToken,
            'unauthenticated_link_token_validity_claimed' => false,
            'case' => $caseName,
            'browserkit_target_get_count' => $browserRequests,
            'attempted_route' => $caseName === 'other_route' ? 'dashboard_admin_link' : 'facebook_admin_link',
            'attempted_controller' => $caseName === 'other_route' ? 'AdminDashboard' : 'AdminPsfacebookModule',
            'route_observation' => ($observedFacebookControllerEvent || $observedDashboardControllerEvent)
                ? 'controller_event'
                : 'not_observed',
            'route' => $observedFacebookControllerEvent
                ? 'admin_legacy_controller_route'
                : ($observedDashboardControllerEvent ? $observedDashboardRouteName : 'not_observed'),
            'controller' => $observedFacebookControllerEvent
                ? 'AdminPsfacebookModuleController'
                : ($observedDashboardControllerEvent ? 'AdminDashboard' : 'not_observed'),
            'controller_action' => $observedFacebookControllerEvent
                ? 'read'
                : ($observedDashboardControllerEvent ? 'not_applicable' : 'not_observed'),
            'authenticated_read_gate_passes' => $authenticatedReadGatePasses,
            'known_facebook_request_controller_events' => $injectionCounts['known_facebook_request_controller_events'],
            'mismatched_facebook_route_events' => $injectionCounts['mismatched_facebook_route_events'],
            'disabled_mode_facebook_sentinels' => $injectionCounts['disabled_mode_facebook_sentinels'],
            'other_route_exception_count' => $injectionCounts['other_route_exceptions'],
            'generic_facebook_exception_count' => $injectionCounts['generic_facebook_exceptions'],
            'access_denied_exception_count' => $injectionCounts['facebook_access_denied_exceptions'],
            'test_transport_target' => 'run_owned_ipv4_loopback_bind_only',
            'stream_server_listen_used' => false,
            'facebook_vendor_initContent_called_by_fixture' => false,
            'script_initiated_external_transport_requests' => 0,
            'installed_http_client_calls' => $injectionCounts['http_client_requests'],
            'response_status' => $responseStatus,
            'unauthenticated_status_not_converted' => $caseChecks['unauthenticated_status_not_converted'],
            'unauthenticated_auth_rejection' => $unauthenticatedAuthRejection,
            'other_route_status_not_converted' => $caseChecks['other_route_status_not_converted'],
            'generic_facebook_runtime_status_not_converted' => $caseChecks['generic_facebook_status_not_converted'],
            'access_denied_status_preserved' => $caseChecks['access_denied_status_preserved'],
            'korean_safe_title' => $caseChecks['facebook_fallback_response_safe'],
            'korean_safe_message' => $caseChecks['facebook_fallback_response_safe'],
            'korean_document_language' => $documentLanguage,
            'fixed_error_fragment_excludes_token_and_transport_details' => $caseChecks['facebook_fallback_response_safe'] && $noSensitiveDetails,
            'native_session_csrf_verified' => $nativeSessionCsrfVerified,
            'native_session_csrf_probe_count' => $nativeSessionCsrfProbeCount,
            'positive_response_snapshot_sha256' => $snapshotHash,
            'script_business_data_mutations' => false,
            'login_session_or_auth_audit_writes_possible' => $caseName !== 'unauthenticated',
            'kernel_bootstrap_database_network_side_effects_instrumented' => false,
        ],
        'test_dependencies' => $dependencySources,
    ];
    $emitSafeOutcome($outcome);
    exit(0);
} catch (Throwable $error) {
    fwrite(STDERR, 'FAIL native Facebook transport fallback stage=' . $stage . PHP_EOL);
    $errorClass = get_class($error);
    $outcome = [
        'schema' => 1,
        'passed' => false,
        'failed_stage' => $stage,
        'exception_class' => strlen($errorClass) <= 160
            && preg_match('/\A[A-Za-z_][A-Za-z0-9_]*\z/D', str_replace(chr(92), '_', $errorClass)) === 1
                ? $errorClass : 'redacted',
        'failure_source' => $error->getFile() === __FILE__
            ? 'native_facebook_transport_fallback.php:' . $error->getLine() : null,
        'injection_counts' => $injectionCounts,
        'module_inventory' => array_map(static fn (array $item): array => [
            'installed' => $item['installed'] ?? false,
            'active' => $item['active'] ?? false,
            'version' => $item['version'] ?? null,
        ], $moduleInventory),
        'script_business_data_mutations' => false,
        'native_session_csrf_verified' => $nativeSessionCsrfVerified,
        'native_session_csrf_probe_count' => $nativeSessionCsrfProbeCount,
        'login_session_or_auth_audit_writes_possible' => true,
        'kernel_bootstrap_database_network_side_effects_instrumented' => false,
    ];
    if ($error instanceof \Twig\Error\Error) {
        try {
            $sourceContext = $error->getSourceContext();
            $templateName = $sourceContext?->getName();
            $templateLine = $error->getTemplateLine();
            if (is_string($templateName) && strlen($templateName) <= 240
                && preg_match('~\A@(?:PrestaShop/Admin|PrestaShopCore|Modules/ps_facebook)/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.twig\z~D', $templateName) === 1
                && is_int($templateLine) && $templateLine >= 1 && $templateLine <= 100000) {
                $outcome['twig_template'] = $templateName;
                $outcome['twig_template_line'] = $templateLine;
            }
        } catch (Throwable) {
            // Safe template provenance is optional; never replace the original failure.
        }
    }
    if ($isolatedCiGuardPassed && $caseName === 'unauthenticated'
        && $stage === 'case_specific_semantic_assertions'
        && isset($requestUri, $responseStatus, $body)
        && is_string($requestUri) && preg_match('~\A/admin-kuranea(?:/|\z)~D', $requestUri) === 1
        && is_int($responseStatus) && $responseStatus >= 100 && $responseStatus <= 599
        && is_string($body) && strlen($body) <= 2 * 1024 * 1024) {
        try {
            $privateEnvelope = json_encode([
                'scope' => 'facebook_unauthenticated_native_target_failure',
                'status' => $responseStatus,
                'request_uri' => $requestUri,
                'body_base64' => base64_encode($body),
            ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
            require_once __DIR__ . '/native_admin_private_snapshot.php';
            persistNativeAdminSnapshot(
                'facebook-unauthenticated', $privateEnvelope,
                '/tmp/owned/kuranea-admin-test-deps', $expectedProject
            );
        } catch (Throwable) {
            // Keep the original functional failure and never expose private HTML.
        }
    }
    if (class_exists('NativeAdminHttpLogin', false)) {
        $authLanding = NativeAdminHttpLogin::safeAuthLandingFacts();
        if (is_array($authLanding)) $outcome['auth_landing'] = $authLanding;
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
} finally {
    foreach ($heldSockets as $heldSocket) {
        if (is_resource($heldSocket)) {
            fclose($heldSocket);
        }
    }
}
