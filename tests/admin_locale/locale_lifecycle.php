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
use PrestaShop\PrestaShop\Core\Domain\Language\ValueObject\LanguageId;
use PrestaShop\PrestaShop\Core\Language\LanguageInterface;
use PrestaShop\PrestaShop\Core\Language\LanguageRepositoryInterface;
use PrestaShop\PrestaShop\Core\Localization\Locale;
use PrestaShopBundle\EventListener\Admin\Context\LanguageContextSubscriber;
use PrestaShopBundle\EventListener\Admin\Context\LegacyContextSubscriber;
use PrestaShopBundle\Translation\TranslatorComponent;
use PrestaShopBundle\Translation\TranslatorLanguageLoader;
use Symfony\Component\DependencyInjection\Container;
use Symfony\Component\EventDispatcher\EventDispatcher;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Event\ControllerEvent;
use Symfony\Component\HttpKernel\Event\RequestEvent;
use Symfony\Component\HttpKernel\HttpKernelInterface;
use Symfony\Component\HttpKernel\KernelEvents;

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
    $legacyContext = new class($context) extends LegacyContext {
        public function __construct(private Context $context) {}
        public function getContext() { return $this->context; }
    };
    $builder = new LanguageContextBuilder($repository, $locales, new ContextStateManager($legacyContext), $legacyRepository);
    $employee = $employeeLanguageId === null ? null : new Employee(1, 1, $employeeLanguageId, 'Test', 'Employee', 'fixture@example.invalid', '', '', 1, 1, [1], [1]);
    $coreLanguage = new LanguageContextSubscriber($builder, new EmployeeContext($employee, [1]), $configuration);
    // The module loader must not reach DB: the Korean catalogue already exists.
    $loader = (new ReflectionClass(TranslatorLanguageLoader::class))->newInstanceWithoutConstructor();
    $module = new AdminLocaleSubscriber($repository, $builder, $translator, $loader, $shopRoot . '/modules/kuraneabackoffice', $activeModules);
    $dispatcher = new EventDispatcher();
    $dispatcher->addSubscriber($coreLanguage);
    $dispatcher->addSubscriber($module);
    $dispatcher->addSubscriber(new LegacyContextSubscriber([$builder]));
    $request = Request::create('/');
    $request->attributes->set('_route', $route);
    $dispatcher->dispatch(new RequestEvent($kernel, $request, HttpKernelInterface::MAIN_REQUEST), KernelEvents::REQUEST);
    $dispatcher->dispatch(new ControllerEvent($kernel, static function () {}, $request, HttpKernelInterface::MAIN_REQUEST), KernelEvents::CONTROLLER);

    // An explicit Korean translation proves domain registration independently
    // of the current locale. Default translation exposes later locale resets.
    if ($activeModules !== [] && str_starts_with($route, 'admin_')) {
        same('주문', $translator->trans('Orders', [], 'Admin.Navigation.Menu', 'ko-KR'), $route . ' explicit Korean catalogue');
        if ($route === 'admin_orders_index') {
            same('평균 주문 금액', $translator->trans('Average Order Value', [], 'Admin.Global', 'ko-KR'), $route . ' explicit Admin.Global KPI translation');
        }
    }
    $context->getTranslator();
    same($expectedOrders, $translator->trans('Orders', [], 'Admin.Navigation.Menu'), $route . ' Orders title');
    if ($activeModules !== [] && $route === 'admin_orders_index') {
        same('평균 주문 금액', $translator->trans('Average Order Value', [], 'Admin.Global'), $route . ' default Admin.Global KPI translation');
    }
    same($expectedLocale, $builder->build()->getLocale(), $route . ' final language context');
    same($expectedLocale, $context->language->locale, $route . ' legacy language');
    same($expectedLocale, $translator->getLocale(), $route . ' translator locale');
    if ($employee !== null) {
        same($employeeLanguageId, $employee->getLanguageId(), $route . ' employee preference');
    }
}
echo "PASS: Korean Orders survives core language initialization; storefront and employee preferences are preserved.\n";
