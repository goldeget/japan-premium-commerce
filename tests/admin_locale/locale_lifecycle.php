<?php

declare(strict_types=1);

// Run with: php locale_lifecycle.php /path/to/prestashop/vendor/autoload.php /path/to/prestashop
// Only repository boundaries are fixtures; request dispatch, language context
// building, legacy context synchronization and translation use upstream code.
require $argv[1];
$shopRoot = $argv[2] ?? dirname(__DIR__, 2);
if (!defined('_PS_ROOT_DIR_')) {
    define('_PS_ROOT_DIR_', $shopRoot);
}
require $shopRoot . '/modules/kuraneabackoffice/src/AdminLocaleSubscriber.php';

use Kuranea\Backoffice\AdminLocaleSubscriber;
use PrestaShop\PrestaShop\Adapter\ContextStateManager;
use PrestaShop\PrestaShop\Adapter\LegacyContext;
use PrestaShop\PrestaShop\Adapter\SymfonyContainer;
use PrestaShop\PrestaShop\Core\Context\Employee;
use PrestaShop\PrestaShop\Core\Context\EmployeeContext;
use PrestaShop\PrestaShop\Core\Context\LanguageContextBuilder;
use PrestaShop\PrestaShop\Core\Domain\Configuration\ShopConfigurationInterface;
use PrestaShop\PrestaShop\Core\Domain\Language\ValueObject\LanguageId;
use PrestaShop\PrestaShop\Core\Domain\Shop\ValueObject\ShopConstraint;
use PrestaShop\PrestaShop\Core\Language\LanguageInterface;
use PrestaShop\PrestaShop\Core\Language\LanguageRepositoryInterface;
use PrestaShop\PrestaShop\Core\Localization\Locale;
use PrestaShopBundle\EventListener\Admin\Context\LanguageContextSubscriber;
use PrestaShopBundle\EventListener\Admin\Context\LegacyContextSubscriber;
use PrestaShopBundle\EventListener\Admin\UserLocaleSubscriber;
use PrestaShopBundle\Security\Admin\SessionEmployeeInterface;
use PrestaShopBundle\Security\Admin\SessionEmployeeProvider;
use PrestaShopBundle\Translation\TranslatorComponent;
use PrestaShopBundle\Translation\TranslatorLanguageLoader;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\DependencyInjection\Container;
use Symfony\Component\EventDispatcher\EventDispatcher;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\RequestStack;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Controller\ControllerReference;
use Symfony\Component\HttpKernel\Event\ControllerEvent;
use Symfony\Component\HttpKernel\Event\RequestEvent;
use Symfony\Component\HttpKernel\EventListener\LocaleAwareListener;
use Symfony\Component\HttpKernel\Fragment\InlineFragmentRenderer;
use Symfony\Component\HttpKernel\HttpKernelInterface;
use Symfony\Component\HttpKernel\KernelEvents;
use Symfony\Component\Security\Core\Authentication\Token\Storage\TokenStorage;
use Symfony\Component\Security\Core\Authentication\Token\UsernamePasswordToken;
use Symfony\Component\Security\Core\User\UserInterface;

// Avoid ObjectModel's database bootstrap while retaining the real context code.
class ObjectModel { public int $id; }
class Language extends ObjectModel implements LanguageInterface
{
    public string $locale;
    public function __construct(int $id) { $this->id = $id; $this->locale = [1 => 'en-US', 2 => 'ko-KR', 3 => 'ja-JP'][$id]; }
    public function getId(): int { return $this->id; }
    public function getName(): string { return $this->locale; }
    public function getIsoCode(): string { return substr($this->locale, 0, 2); }
    public function getLocale(): string { return $this->locale; }
    public function getLanguageCode(): string { return $this->locale; }
    public function isRTL(): bool { return false; }
    public function getDateFormat(): string { return 'Y-m-d'; }
    public function getDateTimeFormat(): string { return 'Y-m-d H:i:s'; }
    public function getActive(): bool { return true; }
}
require (getenv('PRESTASHOP_SOURCE') ?: $shopRoot) . '/classes/Context.php';
class Context extends ContextCore {}

function same(mixed $expected, mixed $actual, string $label): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($label . ': expected ' . json_encode($expected) . ', got ' . json_encode($actual));
    }
}

$repository = new class implements LanguageRepositoryInterface {
    public function find($id) { return new Language((int) $id); }
    public function findAll() { return [new Language(1), new Language(2), new Language(3)]; }
    public function findBy(array $criteria, ?array $orderBy = null, ?int $limit = null, ?int $offset = null) { return []; }
    public function findOneBy(array $criteria) { return null; }
    public function getClassName() { return Language::class; }
    public function getOneByLocale($locale) { return $this->getOneByLocaleOrIsoCode($locale); }
    public function getOneByIsoCode($isoCode) { return $this->getOneByLocaleOrIsoCode($isoCode); }
    public function getOneByLocaleOrIsoCode($locale) { return str_starts_with($locale, 'ko') ? new Language(2) : null; }
};
$locales = new class implements \PrestaShop\PrestaShop\Core\Localization\Locale\RepositoryInterface {
    public function getLocale($localeCode) {
        $locale = (new ReflectionClass(Locale::class))->newInstanceWithoutConstructor();
        (new ReflectionProperty(Locale::class, 'code'))->setValue($locale, $localeCode);
        return $locale;
    }
};
$legacyRepository = new class extends \PrestaShop\PrestaShop\Adapter\Language\Repository\LanguageRepository {
    public function get(LanguageId $languageId): Language { return new Language($languageId->getValue()); }
};
$configuration = new class implements \PrestaShop\PrestaShop\Core\ConfigurationInterface {
    public function get($key) { return 3; }
    public function set($key, $value) {}
};
$shopConfiguration = new class implements ShopConfigurationInterface {
    public function get($key, $default = null, ?ShopConstraint $shopConstraint = null) { return 3; }
    public function set($key, $value, ?ShopConstraint $shopConstraint = null) { return $this; }
    public function has($key, ?ShopConstraint $shopConstraint = null) { return true; }
    public function remove($key) { return $this; }
    public function keys() { return []; }
};
$kernel = new class implements HttpKernelInterface {
    public function handle(Request $request, int $type = self::MAIN_REQUEST, bool $catch = true): \Symfony\Component\HttpFoundation\Response { throw new LogicException('No HTTP server is used.'); }
};

foreach ([
    ['admin_orders_index', ['kuraneabackoffice'], 1, 'ko-KR', '주문'],
    ['admin_orders_index', ['kuraneabackoffice'], 2, 'ko-KR', '주문'],
    ['admin_login', ['kuraneabackoffice'], null, 'ko-KR', '주문'],
    ['shop_index', ['kuraneabackoffice'], null, 'ja-JP', 'Orders'],
    ['admin_orders_index', [], 1, 'en-US', 'Orders'],
] as [$route, $activeModules, $employeeLanguageId, $expectedLocale, $expectedOrders]) {
    $translator = new TranslatorComponent('en-US');
    $translator->addLoader('xlf', new \Symfony\Component\Translation\Loader\XliffFileLoader());
    // Keep base catalogues in memory: this regression needs no DB resources.
    $translator->getCatalogue('ko-KR');
    $container = new Container();
    $container->set(\PrestaShopBundle\Translation\TranslatorInterface::class, $translator);
    (new ReflectionProperty(SymfonyContainer::class, 'instance'))->setValue(null, $container);
    $context = new Context();
    $context->language = new Language(3);
    (new ReflectionProperty(ContextCore::class, 'translator'))->setValue($context, $translator);
    $requestStack = new RequestStack();
    $securityContainer = new Container();
    $tokenStorage = new TokenStorage();
    if ($employeeLanguageId !== null) {
        $sessionEmployee = new class($employeeLanguageId) implements SessionEmployeeInterface, UserInterface {
            private string $locale;
            public function __construct(int $languageId) { $this->locale = [1 => 'en-US', 2 => 'ko-KR'][$languageId]; }
            public function getId(): int { return 1; }
            public function getUserIdentifier(): string { return 'fixture@example.invalid'; }
            public function getPassword(): string { return ''; }
            public function getProfileId(): int { return 1; }
            public function getDefaultLocale(): string { return $this->locale; }
            public function getRoles(): array { return []; }
            public function eraseCredentials(): void {}
        };
        $tokenStorage->setToken(new UsernamePasswordToken($sessionEmployee, 'main', []));
    }
    $securityContainer->set('security.token_storage', $tokenStorage);
    $security = new Security($securityContainer);
    $userLocaleSubscriber = new UserLocaleSubscriber(
        $shopConfiguration,
        $repository,
        $security,
        new SessionEmployeeProvider($requestStack)
    );
    $localeAwareListener = new LocaleAwareListener([$translator], $requestStack);
    $legacyContext = new class($context) extends LegacyContext {
        public function __construct(private Context $context) {}
        public function getContext() { return $this->context; }
    };
    $builder = new LanguageContextBuilder($repository, $locales, new ContextStateManager($legacyContext), $legacyRepository);
    $employee = $employeeLanguageId === null ? null : new Employee(1, 1, $employeeLanguageId, 'Test', 'Employee', 'fixture@example.invalid', '', '', 1, 1, [1], [1]);
    $coreLanguage = new LanguageContextSubscriber($builder, new EmployeeContext($employee, [1]), $configuration);
    // The module loader must not reach DB: the Korean catalogue already exists.
    $loader = (new ReflectionClass(TranslatorLanguageLoader::class))->newInstanceWithoutConstructor();
    $module = new AdminLocaleSubscriber($repository, $builder, $translator, $loader, $requestStack, $shopRoot . '/modules/kuraneabackoffice', $activeModules);
    $dispatcher = new EventDispatcher();
    $dispatcher->addSubscriber($coreLanguage);
    $dispatcher->addSubscriber($module);
    $dispatcher->addSubscriber(new LegacyContextSubscriber([$builder]));
    $request = Request::create('/');
    $request->attributes->set('_route', $route);
    $requestStack->push($request);
    $mainRequestEvent = new RequestEvent($kernel, $request, HttpKernelInterface::MAIN_REQUEST);
    $userLocaleSubscriber->onKernelRequest($mainRequestEvent);
    $localeAwareListener->onKernelRequest($mainRequestEvent);
    $dispatcher->dispatch($mainRequestEvent, KernelEvents::REQUEST);
    $dispatcher->dispatch(new ControllerEvent($kernel, static function () {}, $request, HttpKernelInterface::MAIN_REQUEST), KernelEvents::CONTROLLER);

    // An explicit Korean translation proves domain registration independently
    // of the current locale. Default translation exposes later locale resets.
    if ($activeModules !== [] && str_starts_with($route, 'admin_')) {
        same('주문', $translator->trans('Orders', [], 'Admin.Navigation.Menu', 'ko-KR'), $route . ' explicit Korean catalogue');
        same('배송사', $translator->trans('Carriers', [], 'Admin.Navigation.Menu', 'ko-KR'), $route . ' explicit Korean carrier navigation');
        same('결제 수단', $translator->trans('Payment Methods', [], 'Admin.Navigation.Menu', 'ko-KR'), $route . ' explicit Korean payment menu title');
        same('결제 수단', $translator->trans('Payment methods', [], 'Admin.Navigation.Menu', 'ko-KR'), $route . ' explicit Korean payment menu label');
        same('결제 방법', $translator->trans('Payment method', [], 'Admin.Orderscustomers.Feature', 'ko-KR'), $route . ' explicit Korean payment method label');
        same('데모 모드', $translator->trans('Demo mode', [], 'Admin.Dashboard.Feature', 'ko-KR'), $route . ' explicit Korean demo mode label');
        if ($route === 'admin_orders_index') {
            same('평균 주문 금액', $translator->trans('Average Order Value', [], 'Admin.Global', 'ko-KR'), $route . ' explicit Admin.Global KPI translation');
        }
    }
    $context->getTranslator();
    same($expectedOrders, $translator->trans('Orders', [], 'Admin.Navigation.Menu'), $route . ' Orders title');
    if ($activeModules !== [] && str_starts_with($route, 'admin_')) {
        same('결제 수단', $translator->trans('Payment Methods', [], 'Admin.Navigation.Menu'), $route . ' default Korean payment menu title');
        same('결제 수단', $translator->trans('Payment methods', [], 'Admin.Navigation.Menu'), $route . ' default Korean payment menu label');
        same('데모 모드', $translator->trans('Demo mode', [], 'Admin.Dashboard.Feature'), $route . ' default Korean demo mode label');
    }
    if ($activeModules !== [] && $route === 'admin_orders_index') {
        same('평균 주문 금액', $translator->trans('Average Order Value', [], 'Admin.Global'), $route . ' default Admin.Global KPI translation');

        $fragmentKernel = new class($requestStack, $userLocaleSubscriber, $localeAwareListener, $module, $translator) implements HttpKernelInterface {
            public ?Request $lastRequest = null;
            public function __construct(
                private RequestStack $requestStack,
                private UserLocaleSubscriber $userLocaleSubscriber,
                private LocaleAwareListener $localeAwareListener,
                private AdminLocaleSubscriber $adminLocaleSubscriber,
                private TranslatorComponent $translator
            ) {}
            public function handle(Request $request, int $type = self::MAIN_REQUEST, bool $catch = true): Response
            {
                $this->lastRequest = $request;
                $this->requestStack->push($request);
                try {
                    $event = new RequestEvent($this, $request, $type);
                    $this->userLocaleSubscriber->onKernelRequest($event);
                    $this->localeAwareListener->onKernelRequest($event);
                    $this->adminLocaleSubscriber->onKernelRequest($event);
                    return new Response($this->translator->trans('Average Order Value', [], 'Admin.Global'));
                } finally {
                    $this->requestStack->pop();
                }
            }
        };
        $controllerReference = new ControllerReference(
            'PrestaShopBundle\\Controller\\Admin\\CommonController::renderKpiRowAction'
        );
        $fragmentRenderer = new InlineFragmentRenderer($fragmentKernel);
        $response = $fragmentRenderer->render($controllerReference, $request);
        $kpiSubrequest = $fragmentKernel->lastRequest;
        if (!$kpiSubrequest instanceof Request) {
            throw new RuntimeException($route . ' KPI fragment request was not dispatched');
        }

        same('ko-KR', $kpiSubrequest->attributes->get('_locale'), $route . ' generated KPI fragment locale');
        same('ko-KR', $kpiSubrequest->getLocale(), $route . ' KPI fragment locale');
        same(
            '평균 주문 금액',
            $response->getContent(),
            $route . ' rendered KPI fragment translation'
        );
    }
    same($expectedLocale, $builder->build()->getLocale(), $route . ' final language context');
    same($expectedLocale, $context->language->locale, $route . ' legacy language');
    same($expectedLocale, $translator->getLocale(), $route . ' translator locale');
    if ($employee !== null) {
        same($employeeLanguageId, $employee->getLanguageId(), $route . ' employee preference');
    }
}
echo "PASS: Korean Orders and its KPI fragment preserve the admin locale; storefront and employee preferences are preserved.\n";
