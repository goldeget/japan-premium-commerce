<?php

declare(strict_types=1);

use PrestaShop\Module\Mbo\Addons\Provider\LinksProvider;
use PrestaShop\Module\Mbo\Controller\Admin\ThemeCatalogController;
use PrestaShop\Module\Mbo\Service\ExternalContentProvider\ExternalContentProviderInterface;
use PrestaShop\PrestaShop\Core\Translation\Storage\Normalizer\DomainNormalizer;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Exception\ServiceUnavailableHttpException;
use Symfony\Component\Translation\Loader\XliffFileLoader;

$stage = 'ci_guard';
$inventory = [];
$failureProvider = null;
$shopRoot = dirname(__DIR__, 2);

try {
    $runId = getenv('GITHUB_RUN_ID') ?: '';
    $runAttempt = getenv('GITHUB_RUN_ATTEMPT') ?: '';
    $expectedProject = 'ordenowa-procurement-ci-' . $runId . '-' . $runAttempt;
    if (
        getenv('KURANEA_ISOLATED_CI') !== '1'
        || getenv('CI') !== 'true'
        || getenv('GITHUB_ACTIONS') !== 'true'
        || !preg_match('/\A[0-9]{1,20}\z/D', $runId)
        || !preg_match('/\A[0-9]{1,8}\z/D', $runAttempt)
        || getenv('KURANEA_CI_PROJECT_NAME') !== $expectedProject
        || getenv('PS_DOMAIN') !== 'localhost:18081'
    ) {
        throw new RuntimeException('isolated_ci_guard');
    }

    $stage = 'admin_bootstrap_path';
    $adminRoot = realpath($shopRoot . '/admin-kuranea');
    if ($adminRoot === false || dirname($adminRoot) !== realpath($shopRoot)
        || !is_file($adminRoot . '/index.php') || !is_dir($adminRoot . '/themes')) {
        throw new RuntimeException('native_admin_path_missing');
    }
    if (!defined('_PS_ADMIN_DIR_')) {
        define('_PS_ADMIN_DIR_', $adminRoot);
    } elseif (realpath(_PS_ADMIN_DIR_) !== $adminRoot) {
        throw new RuntimeException('native_admin_path_mismatch');
    }
    $_SERVER['HTTP_HOST'] = 'localhost:18081';
    $_SERVER['REQUEST_URI'] = '/admin-kuranea/index.php/mbo/themes/catalog?liteDisplaying=1';
    $_SERVER['SCRIPT_NAME'] = '/admin-kuranea/index.php';

    $stage = 'bootstrap';
    require_once $shopRoot . '/autoload.php';
    require_once $shopRoot . '/config/config.inc.php';
    require_once $shopRoot . '/app/AppKernel.php';
    require_once $shopRoot . '/app/AdminKernel.php';

    if (!defined('_PS_BO_ALL_THEMES_DIR_') || realpath(_PS_BO_ALL_THEMES_DIR_) !== realpath($adminRoot . '/themes')) {
        throw new RuntimeException('native_admin_theme_constant_missing');
    }

    $stage = 'admin_kernel_boot';
    // Match native_boundaries' warmed production container exactly.
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

    $readModule = static function (string $name, bool $mustBeActive) use (
        $installedModules,
        $activeModules,
        $modulesRoot
    ): array {
        if (!in_array($name, $installedModules, true)) {
            throw new RuntimeException('module_not_installed');
        }
        $active = in_array($name, $activeModules, true);
        if ($mustBeActive && !$active) {
            throw new RuntimeException('module_not_active');
        }

        $modulePath = realpath($modulesRoot . DIRECTORY_SEPARATOR . $name);
        if ($modulePath === false || dirname($modulePath) !== $modulesRoot || basename($modulePath) !== $name) {
            throw new RuntimeException('module_path_invalid');
        }
        $configPath = $modulePath . DIRECTORY_SEPARATOR . 'config.xml';
        if (!is_file($configPath)) {
            throw new RuntimeException('module_config_missing');
        }

        libxml_use_internal_errors(true);
        libxml_clear_errors();
        $xml = @simplexml_load_file($configPath, SimpleXMLElement::class, LIBXML_NONET | LIBXML_NOBLANKS);
        if (
            !$xml instanceof SimpleXMLElement
            || $xml->getName() !== 'module'
            || trim((string) $xml->name) !== $name
        ) {
            throw new RuntimeException('module_config_invalid');
        }

        $version = trim((string) $xml->version);
        if (!preg_match('/\A[0-9][A-Za-z0-9.+_-]{0,31}\z/D', $version)) {
            throw new RuntimeException('module_version_invalid');
        }
        $configHash = hash_file('sha256', $configPath);
        if (!is_string($configHash)) {
            throw new RuntimeException('module_config_hash_failed');
        }

        return [
            'installed' => true,
            'active' => $active,
            'version' => $version,
            'config_sha256' => $configHash,
        ];
    };

    $stage = 'read_ps_mbo';
    $inventory['ps_mbo'] = $readModule('ps_mbo', true);
    $stage = 'read_ps_facebook';
    $inventory['ps_facebook'] = $readModule('ps_facebook', false);

    $stage = 'verify_mbo_source';
    $modulePath = $modulesRoot . DIRECTORY_SEPARATOR . 'ps_mbo';
    $controllerPath = $modulePath . '/src/Controller/Admin/ThemeCatalogController.php';
    $templatePath = $modulePath . '/views/templates/admin/error.html.twig';
    $overlayPath = $modulesRoot . '/kuraneabackoffice/translations/ko-KR/ModulesMboErrors.ko-KR.xlf';
    foreach ([$controllerPath, $templatePath, $overlayPath] as $sourcePath) {
        if (!is_file($sourcePath)) {
            throw new RuntimeException('required_source_missing');
        }
    }

    $controllerSource = file_get_contents($controllerPath);
    $templateSource = file_get_contents($templatePath);
    if (!is_string($controllerSource) || !is_string($templateSource)) {
        throw new RuntimeException('required_source_unreadable');
    }
    $sourceMessage = 'It looks like we have trouble connecting to Addons. Please refresh the page or check your firewall configuration.';
    $koreanMessage = 'Addons에 연결하는 데 문제가 있는 것 같습니다. 페이지를 새로고침하거나 방화벽 설정을 확인해 주세요.';
    if (
        !str_contains($controllerSource, 'ExternalContentProviderInterface')
        || !str_contains($controllerSource, '@Modules/ps_mbo/views/templates/admin/error.html.twig')
        || !str_contains($controllerSource, 'ServiceUnavailableHttpException')
        || substr_count($templateSource, $sourceMessage) !== 2
        || substr_count($templateSource, "Modules.Mbo.Errors") !== 2
    ) {
        throw new RuntimeException('installed_mbo_error_contract_mismatch');
    }

    $controllerHash = hash_file('sha256', $controllerPath);
    $templateHash = hash_file('sha256', $templatePath);
    $overlayHash = hash_file('sha256', $overlayPath);
    if (!is_string($controllerHash) || !is_string($templateHash) || !is_string($overlayHash)) {
        throw new RuntimeException('mbo_source_hash_failed');
    }

    $stage = 'validate_native_interfaces';
    if (
        !interface_exists(ExternalContentProviderInterface::class)
        || !class_exists(ThemeCatalogController::class)
        || !class_exists(LinksProvider::class)
    ) {
        throw new RuntimeException('mbo_native_classes_missing');
    }
    $providerMethod = new ReflectionMethod(ExternalContentProviderInterface::class, 'getContent');
    $providerParameters = $providerMethod->getParameters();
    if (
        count($providerParameters) !== 2
        || (string) $providerParameters[0]->getType() !== 'string'
        || (string) $providerParameters[1]->getType() !== 'array'
        || (string) $providerMethod->getReturnType() !== 'string'
        || (new ReflectionClass(LinksProvider::class))->isFinal()
    ) {
        throw new RuntimeException('mbo_provider_signature_mismatch');
    }
    $actionMethod = new ReflectionMethod(ThemeCatalogController::class, 'indexAction');
    $actionParameters = $actionMethod->getParameters();
    $expectedParameterTypes = [Request::class, LinksProvider::class, ExternalContentProviderInterface::class];
    if (count($actionParameters) !== count($expectedParameterTypes)) {
        throw new RuntimeException('mbo_controller_signature_mismatch');
    }
    foreach ($expectedParameterTypes as $index => $expectedType) {
        $parameterType = $actionParameters[$index]->getType();
        if (!$parameterType instanceof ReflectionNamedType || $parameterType->getName() !== $expectedType) {
            throw new RuntimeException('mbo_controller_signature_mismatch');
        }
    }

    $stage = 'native_translator_setup';
    if (!$container->has('translator')) {
        throw new RuntimeException('native_translator_missing');
    }
    $translator = $container->get('translator');
    if (
        !method_exists($translator, 'setLocale')
        || !method_exists($translator, 'addResource')
        || !method_exists($translator, 'getCatalogue')
    ) {
        throw new RuntimeException('native_translator_api_mismatch');
    }
    $translator->setLocale('ko-KR');
    $catalogueDomain = (new DomainNormalizer())->normalize('Modules.Mbo.Errors');
    $translator->addResource('xlf', $overlayPath, 'ko-KR', $catalogueDomain);
    $catalogue = $translator->getCatalogue('ko-KR');
    $catalogue->addCatalogue((new XliffFileLoader())->load($overlayPath, 'ko-KR', $catalogueDomain));
    $resolvedMessage = $translator->trans($sourceMessage, [], 'Modules.Mbo.Errors', 'ko-KR');
    if ($resolvedMessage !== $koreanMessage) {
        throw new RuntimeException('native_translator_resolution_failed');
    }

    $stage = 'resolve_native_controller';
    $controllerService = $container->get(ThemeCatalogController::class);
    if (!$controllerService instanceof ThemeCatalogController) {
        throw new RuntimeException('mbo_controller_service_mismatch');
    }

    // The real error template honors this native layout switch. The full Admin
    // shell needs an authenticated employee/session; this direct controller
    // fixture deliberately renders its native light layout without faking one.
    $request = Request::create(
        'http://localhost:18081/admin-kuranea/index.php/mbo/themes/catalog?liteDisplaying=1',
        'GET'
    );
    $request->attributes->set('_route', 'admin_mbo_catalog_theme');
    $request->attributes->set('_legacy_controller', 'AdminPsMboTheme');
    $request->attributes->set('_controller', ThemeCatalogController::class . '::indexAction');
    $request->setLocale('ko-KR');
    $request->setSession(new \Symfony\Component\HttpFoundation\Session\Session(new \Symfony\Component\HttpFoundation\Session\Storage\MockArraySessionStorage()));
    $requestStack = $container->get('request_stack');
    $requestStack->push($request);

    try {
        $stage = 'prepare_native_admin_contexts';
        $contextClasses = [
            'PrestaShopBundle\\EventListener\\Admin\\Context\\LanguageContextSubscriber',
            'PrestaShopBundle\\EventListener\\Admin\\Context\\ShopContextSubscriber',
            'PrestaShopBundle\\EventListener\\Admin\\Context\\CountryContextSubscriber',
            'PrestaShopBundle\\EventListener\\Admin\\Context\\CurrencyContextSubscriber',
            'PrestaShopBundle\\EventListener\\Admin\\Context\\EmployeeContextSubscriber',
            'PrestaShopBundle\\EventListener\\Admin\\Context\\LegacyControllerContextSubscriber',
            'PrestaShopBundle\\EventListener\\Admin\\Context\\LegacyContextSubscriber',
            'Kuranea\\Backoffice\\AdminLocaleSubscriber',
        ];
        $contextEvent = new \Symfony\Component\HttpKernel\Event\RequestEvent(
            $kernel,
            $request,
            \Symfony\Component\HttpKernel\HttpKernelInterface::MAIN_REQUEST
        );
        $contextListenerCalls = 0;
        $contextClassesSeen = [];
        foreach ($container->get('event_dispatcher')->getListeners(\Symfony\Component\HttpKernel\KernelEvents::REQUEST) as $listener) {
            if (!is_array($listener) || !isset($listener[0], $listener[1]) || !is_object($listener[0])) {
                continue;
            }
            $listenerClass = get_class($listener[0]);
            if (!in_array($listenerClass, $contextClasses, true)) {
                continue;
            }
            $listener($contextEvent);
            ++$contextListenerCalls;
            $contextClassesSeen[$listenerClass] = true;
            if ($contextEvent->hasResponse()) {
                throw new RuntimeException('native_context_requested_redirect');
            }
        }
        if (count($contextClassesSeen) !== count($contextClasses) || $contextListenerCalls !== 10) {
            throw new RuntimeException('native_context_listener_contract_mismatch');
        }
        $koLanguageId = (int) \Language::getIdByIso('ko', true);
        if ($koLanguageId < 1) {
            throw new RuntimeException('native_korean_language_missing');
        }
        $container->get(\PrestaShop\PrestaShop\Core\Context\ContextBuilderPreparer::class)->prepareLanguageId($koLanguageId);

        $controllerContextEvent = new \Symfony\Component\HttpKernel\Event\ControllerEvent(
            $kernel,
            [$controllerService, 'indexAction'],
            $request,
            \Symfony\Component\HttpKernel\HttpKernelInterface::MAIN_REQUEST
        );
        $legacyControllerContextCalls = 0;
        foreach ($container->get('event_dispatcher')->getListeners(\Symfony\Component\HttpKernel\KernelEvents::CONTROLLER) as $listener) {
            if (is_array($listener) && isset($listener[0], $listener[1]) && is_object($listener[0])
                && get_class($listener[0]) === 'PrestaShopBundle\\EventListener\\Admin\\Context\\LegacyContextSubscriber') {
                $listener($controllerContextEvent);
                ++$legacyControllerContextCalls;
            }
        }
        if ($legacyControllerContextCalls !== 1
            || !\Context::getContext()->controller
            || (int) \Context::getContext()->language->id !== $koLanguageId) {
            throw new RuntimeException('native_legacy_context_sync_failed');
        }


        $linksProvider = new class extends LinksProvider {
            public function __construct()
            {
            }

            public function getSelectionLink(): string
            {
                return 'https://addons.prestashop.com/ci-only-no-network';
            }
        };
        $failureProvider = new class implements ExternalContentProviderInterface {
            public int $calls = 0;

            public function getContent(string $url, array $options = []): string
            {
                ++$this->calls;
                if ($url !== 'https://addons.prestashop.com/ci-only-no-network') {
                    throw new RuntimeException('unexpected_external_content_url');
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

        $stage = 'render_native_mbo_error';
        $response = $controllerService->indexAction($request, $linksProvider, $failureProvider);
    } finally {
        $requestStack->pop();
    }

    $stage = 'assert_native_render';
    $body = $response->getContent();
    if (
        $failureProvider->calls !== 1
        || $response->getStatusCode() !== 503
        || $response->headers->get('X-ORDENOWA-CI-Injected-Failure') !== '1'
        || !is_string($body)
        || substr_count($body, $koreanMessage) < 2
        || str_contains($body, $sourceMessage)
    ) {
        throw new RuntimeException('native_mbo_error_render_assertion_failed');
    }

    $outcome = [
        'schema' => 1,
        'passed' => true,
        'script_app_mutations' => false,
        'bootstrap_database_side_effects_instrumented' => false,
        'bootstrap_network_side_effects_instrumented' => false,
        'module_inventory' => $inventory,
        'mbo_error_render' => [
            'mode' => 'direct_native_controller_call_with_test_only_provider',
            'authenticated_http_dispatch' => false,
            'request_session' => 'in_memory_fixture',
            'native_context_request_listener_calls' => $contextListenerCalls,
            'native_context_subscriber_classes' => count($contextClassesSeen),
            'native_legacy_controller_listener_calls' => $legacyControllerContextCalls,
            'native_layout_variant' => 'lightDisplaying=1',
            'route' => 'admin_mbo_catalog_theme',
            'controller' => 'ThemeCatalogController::indexAction',
            'failure_injected' => 'ServiceUnavailableHttpException',
            'response_status' => 503,
            'injected_header_verified' => true,
            'native_twig_template' => '@Modules/ps_mbo/views/templates/admin/error.html.twig',
            'korean_message_occurrences' => substr_count($body, $koreanMessage),
            'english_source_absent' => true,
            'injected_provider_invocations' => $failureProvider->calls,
            'injected_provider_http_calls' => 0,
        ],
        'sha256' => [
            'ps_mbo_controller' => $controllerHash,
            'ps_mbo_error_template' => $templateHash,
            'project_ko_xliff' => $overlayHash,
        ],
    ];

    $stage = 'emit_outcome';
    echo json_encode($outcome, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . PHP_EOL;
    exit(0);
} catch (Throwable $error) {
    fwrite(STDERR, 'FAIL native MBO error render stage=' . $stage . PHP_EOL);
    $outcome = [
        'schema' => 1,
        'passed' => false,
        'script_app_mutations' => false,
        'bootstrap_database_side_effects_instrumented' => false,
        'bootstrap_network_side_effects_instrumented' => false,
        'injected_provider_invocations' => $failureProvider === null ? 0 : $failureProvider->calls,
        'injected_provider_http_calls' => 0,
        'failed_stage' => $stage,
        'exception_class' => preg_match('/\A[A-Za-z0-9_\\\\]{1,160}\z/D', get_class($error))
            ? get_class($error)
            : 'redacted',
        'module_inventory' => $inventory,
    ];
    if ($error instanceof Twig\Error\Error) {
        $sourceName = $error->getSourceContext()?->getName() ?? '';
        if (preg_match(
            '~\A@(?:PrestaShop/Admin|PrestaShopCore|Modules/ps_mbo)/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.twig\z~D',
            $sourceName
        )) {
            $outcome['twig_template'] = $sourceName;
        }
        $templateLine = $error->getTemplateLine();
        if (is_int($templateLine) && $templateLine > 0 && $templateLine <= 100000) {
            $outcome['twig_template_line'] = $templateLine;
        }
    }
    $cause = $error;
    for ($depth = 0; $depth < 6 && $cause->getPrevious() !== null; ++$depth) {
        $cause = $cause->getPrevious();
    }
    $causeClass = get_class($cause);
    if (preg_match('/\A[A-Za-z0-9_\\\\]{1,160}\z/D', $causeClass)) {
        $outcome['cause_class'] = $causeClass;
    }
    $causeBase = basename(str_replace('\\', '/', $cause->getFile()));
    if (preg_match('/\A[A-Za-z0-9_.-]{1,180}\.php\z/D', $causeBase)) {
        $outcome['cause_basename'] = $causeBase;
        $outcome['cause_file_line'] = $cause->getLine();
    }
    $causeCall = $cause->getTrace()[0] ?? [];
    foreach (['class', 'function'] as $symbol) {
        if (isset($causeCall[$symbol]) && is_string($causeCall[$symbol])
            && preg_match('/\A[A-Za-z0-9_\\\\]{1,160}\z/D', $causeCall[$symbol])) {
            $outcome['cause_call_' . $symbol] = $causeCall[$symbol];
        }
    }
    $causeFile = str_replace('\\', '/', $cause->getFile());
    $sourceRoot = str_replace('\\', '/', $shopRoot) . '/';
    if (str_starts_with($causeFile, $sourceRoot)) {
        $relativeSource = substr($causeFile, strlen($sourceRoot));
        if (preg_match('~\A(?:src/(?:Core/Context|PrestaShopBundle/Twig|PrestaShopBundle/Security|Adapter)|vendor/symfony)/[A-Za-z0-9_./-]+\.php\z~D', $relativeSource)
            && !str_contains($relativeSource, '..')) {
            $outcome['cause_source'] = $relativeSource;
            $outcome['cause_line'] = $cause->getLine();
        }
    }
    echo json_encode($outcome, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . PHP_EOL;
    exit(1);
}

