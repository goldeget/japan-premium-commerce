<?php

declare(strict_types=1);

define('_PS_VERSION_', '9.2.0');
define('_DB_PREFIX_', 'ps_');

require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/vendor/autoload.php';

final class EmployeeProfileAuditFakeDatabase
{
    /** @var array<int, int> */
    public array $employeeProfiles = [];
    /** @var list<array{id_event:int,id_shop:int,actor_employee_id:?int,target_employee_id:int,old_profile_id:int,new_profile_id:int,changed_at_utc:string}> */
    public array $events = [];
    /** @var list<string> */
    public array $queries = [];

    public function executeS(string $sql, bool $array = true, bool $useCache = true): array|false
    {
        $this->queries[] = $sql;
        if (str_contains($sql, 'FROM `ps_employee`')) {
            preg_match('/id_employee`\s*=\s*(\d+)/', $sql, $employeeMatch);
            $employeeId = (int) ($employeeMatch[1] ?? 0);
            return isset($this->employeeProfiles[$employeeId])
                ? [['id_profile' => $this->employeeProfiles[$employeeId]]]
                : [];
        }

        if (str_contains($sql, 'FROM `ps_kuraneabackoffice_employee_profile_audit`')) {
            preg_match('/id_shop`\s*=\s*(\d+)/', $sql, $shopMatch);
            preg_match('/LIMIT\s+(\d+)\s+OFFSET\s+(\d+)/', $sql, $windowMatch);
            $shopId = (int) ($shopMatch[1] ?? 0);
            $limit = (int) ($windowMatch[1] ?? 0);
            $offset = (int) ($windowMatch[2] ?? 0);
            $includeGlobal = str_contains($sql, 'OR `id_shop` = 0');
            $events = array_values(array_filter(
                $this->events,
                static fn (array $event): bool => $event['id_shop'] === $shopId
                    || ($includeGlobal && $event['id_shop'] === 0)
            ));
            usort($events, static fn (array $left, array $right): int => $right['id_event'] <=> $left['id_event']);

            return array_slice($events, $offset, $limit);
        }

        return [];
    }

    public function execute(string $sql): bool
    {
        $this->queries[] = $sql;
        if (str_starts_with($sql, 'CREATE TABLE IF NOT EXISTS')) {
            return true;
        }
        if (preg_match(
            "/VALUES \\(\s*(\d+),\s*(NULL|\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*'([0-9 :+-]+)'\\s*\\)\\z/",
            $sql,
            $matches
        ) !== 1) {
            return false;
        }

        $this->events[] = [
            'id_event' => count($this->events) + 1,
            'id_shop' => (int) $matches[1],
            'actor_employee_id' => $matches[2] === 'NULL' ? null : (int) $matches[2],
            'target_employee_id' => (int) $matches[3],
            'old_profile_id' => (int) $matches[4],
            'new_profile_id' => (int) $matches[5],
            'changed_at_utc' => $matches[6],
        ];

        return true;
    }
}

final class Db
{
    public static EmployeeProfileAuditFakeDatabase $instance;

    public static function getInstance(): EmployeeProfileAuditFakeDatabase
    {
        return self::$instance;
    }
}

final class Shop
{
    public const CONTEXT_SHOP = 1;
    public const CONTEXT_ALL = 2;
    public static int $context = self::CONTEXT_SHOP;

    public static function getContext(): int
    {
        return self::$context;
    }
}

final class Context
{
    public static object $instance;

    public static function getContext(): object
    {
        return self::$instance;
    }
}

final class EmployeeProfileAuditFakeSmarty
{
    public string $content = '';

    public function assign(string $name, string $value): void
    {
        if ($name === 'content') {
            $this->content = $value;
        }
    }
}

final class EmployeeProfileAuditFakeLink
{
    public function getAdminLink(string $controller): string
    {
        return '/admin/index.php?controller=' . rawurlencode($controller);
    }
}

final class Language
{
    public static function getLanguages(bool $activeOnly = false): array
    {
        return [
            ['id_lang' => 1, 'iso_code' => 'ja'],
            ['id_lang' => 2, 'iso_code' => 'en'],
            ['id_lang' => 3, 'iso_code' => 'ko'],
        ];
    }
}

final class Tab
{
    /** @var array<string, int> */
    private static array $ids = [
        'AdminParentCustomerService' => 10,
        'AdminParentEmployees' => 11,
    ];
    private static int $nextId = 100;

    public int $id = 0;
    public int $active = 0;
    public string $class_name = '';
    public string $module = '';
    public int $id_parent = 0;
    public array $name = [];

    public function __construct(int $id = 0)
    {
        $this->id = $id;
    }

    public static function getIdFromClassName(string $className): int
    {
        return self::$ids[$className] ?? 0;
    }

    public function add(): bool
    {
        $this->id = self::$nextId++;
        self::$ids[$this->class_name] = $this->id;

        return true;
    }

    public function update(): bool
    {
        self::$ids[$this->class_name] = $this->id;

        return $this->id > 0;
    }
}

class Module
{
    public string $name = '';
    public string $tab = '';
    public string $version = '';
    public string $author = '';
    public int $need_instance = 0;
    public bool $bootstrap = false;
    public array $ps_versions_compliancy = [];
    public string $displayName = '';
    public string $description = '';
    /** @var list<string> */
    public array $registeredHooks = [];

    public function __construct()
    {
    }

    public function install(): bool
    {
        return true;
    }

    /** @param list<string>|string $hooks */
    public function registerHook(array|string $hooks): bool
    {
        foreach ((array) $hooks as $hook) {
            $this->registeredHooks[] = $hook;
        }

        return true;
    }
}

class ModuleAdminController
{
    public bool $bootstrap = false;
    public string $meta_title = '';
    public string $content = '';
    public array $tabAccess = ['view' => false];
    public bool $nativeView = false;
    public object $context;

    public function __construct()
    {
        $this->context = Context::getContext();
    }

    public function viewAccess(): bool
    {
        return $this->nativeView;
    }

    public function initHeader(): void
    {
    }

    public function initContent(): void
    {
    }
}

final class Hook
{
    public static ?Kuraneabackoffice $module = null;

    public static function exec(string $hookName, array $params): void
    {
        if (self::$module === null || !in_array($hookName, self::$module->registeredHooks, true)) {
            return;
        }
        if ($hookName === 'actionObjectEmployeeUpdateBefore') {
            self::$module->hookActionObjectEmployeeUpdateBefore($params);
        } elseif ($hookName === 'actionObjectEmployeeUpdateAfter') {
            self::$module->hookActionObjectEmployeeUpdateAfter($params);
        }
    }
}

class Employee
{
    public int $id;
    public int $id_profile;

    public function __construct(int $id, int $profileId)
    {
        $this->id = $id;
        $this->id_profile = $profileId;
    }

    public function update(): bool
    {
        Hook::exec('actionObjectEmployeeUpdateBefore', ['object' => $this]);
        Db::getInstance()->employeeProfiles[$this->id] = $this->id_profile;
        Hook::exec('actionObjectEmployeeUpdateAfter', ['object' => $this]);

        return true;
    }
}

require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/kuraneabackoffice.php';
require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/controllers/admin/AdminKuraneaEmployeeProfileAuditController.php';

function employeeProfileAuditAssertSame(mixed $expected, mixed $actual, string $label): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($label . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

$db = new EmployeeProfileAuditFakeDatabase();
Db::$instance = $db;
Context::$instance = (object) [
    'shop' => (object) ['id' => 7],
    'employee' => (object) ['id' => 90],
    'smarty' => new EmployeeProfileAuditFakeSmarty(),
    'link' => new EmployeeProfileAuditFakeLink(),
];
$db->employeeProfiles[31] = 3;
$module = new Kuraneabackoffice();
Hook::$module = $module;
employeeProfileAuditAssertSame(true, $module->install(), 'A fresh module install should create the audit store and tab.');
employeeProfileAuditAssertSame(true, in_array('actionObjectEmployeeUpdateBefore', $module->registeredHooks, true), 'Fresh install should register the Employee before hook.');
employeeProfileAuditAssertSame(true, in_array('actionObjectEmployeeUpdateAfter', $module->registeredHooks, true), 'Fresh install should register the Employee after hook.');
$auditTableCreates = array_values(array_filter(
    $db->queries,
    static fn (string $sql): bool => str_contains($sql, 'kuraneabackoffice_employee_profile_audit')
));
employeeProfileAuditAssertSame(1, count($auditTableCreates), 'Fresh install should create the audit table once.');
employeeProfileAuditAssertSame(true, str_starts_with($auditTableCreates[0], 'CREATE TABLE IF NOT EXISTS'), 'Audit schema setup should be idempotent.');
employeeProfileAuditAssertSame(true, Tab::getIdFromClassName('AdminKuraneaEmployeeProfileAudit') > 0, 'Fresh install should register the native admin tab.');

require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/upgrade/upgrade-1.0.3.php';
employeeProfileAuditAssertSame(true, upgrade_module_1_0_3($module), 'The installed-module upgrade should apply the additive audit setup.');
$auditTableCreates = array_values(array_filter(
    $db->queries,
    static fn (string $sql): bool => str_contains($sql, 'kuraneabackoffice_employee_profile_audit')
));
employeeProfileAuditAssertSame(2, count($auditTableCreates), 'The additive upgrade should safely rerun CREATE TABLE IF NOT EXISTS.');
employeeProfileAuditAssertSame(true, in_array('actionObjectEmployeeUpdateBefore', $module->registeredHooks, true), 'Upgrade should retain the Employee before hook.');
employeeProfileAuditAssertSame(true, in_array('actionObjectEmployeeUpdateAfter', $module->registeredHooks, true), 'Upgrade should retain the Employee after hook.');

$employee = new Employee(31, 8);
employeeProfileAuditAssertSame(true, $employee->update(), 'Employee profile update should complete through the supported hook path.');
employeeProfileAuditAssertSame(1, count($db->events), 'A persisted profile change should append exactly one event.');
employeeProfileAuditAssertSame([
    'id_event' => 1,
    'id_shop' => 7,
    'actor_employee_id' => 90,
    'target_employee_id' => 31,
    'old_profile_id' => 3,
    'new_profile_id' => 8,
], array_intersect_key($db->events[0], array_flip([
    'id_event', 'id_shop', 'actor_employee_id', 'target_employee_id', 'old_profile_id', 'new_profile_id',
])), 'The audit event should preserve the actor, target, and old/new profile IDs.');
employeeProfileAuditAssertSame(1, preg_match('/\A\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\z/', $db->events[0]['changed_at_utc']), 'The event time should use a UTC SQL timestamp.');

$unchanged = new Employee(31, 8);
$unchanged->update();
employeeProfileAuditAssertSame(1, count($db->events), 'An unchanged Employee update must not append an event.');

Context::$instance->employee = (object) ['id' => 0];
$anonymousChange = new Employee(31, 9);
$anonymousChange->update();
employeeProfileAuditAssertSame(2, count($db->events), 'A changed profile should still be recorded when actor context is absent.');
employeeProfileAuditAssertSame(null, $db->events[1]['actor_employee_id'], 'An absent actor must remain unknown instead of being guessed.');

Shop::$context = Shop::CONTEXT_ALL;
Context::$instance->employee = (object) ['id' => 90];
$globalContextChange = new Employee(31, 10);
$globalContextChange->update();
employeeProfileAuditAssertSame(0, $db->events[2]['id_shop'], 'An all-shop profile update should retain its global context marker.');

$repository = new \Kuranea\Backoffice\Infrastructure\EmployeeProfileAuditRepository($db, 'ps_');
for ($index = 0; $index < 55; $index++) {
    $repository->appendProfileChange(7, null, 31, 9, 10);
}
$repository->appendProfileChange(8, null, 44, 9, 10);
$repository->appendProfileChange(0, null, 55, 2, 3);
$repository->appendProfileChange(7, null, 32, 1, 2);
$page = $repository->pageForShop(7, 1);
employeeProfileAuditAssertSame(50, count($page['rows']), 'The audit page should cap rows at fifty.');
employeeProfileAuditAssertSame(true, $page['has_next'], 'A lookahead row should indicate another page.');
employeeProfileAuditAssertSame(true, (bool) array_filter(
    $page['rows'],
    static fn (array $event): bool => $event['target_employee_id'] === 55
), 'A selected shop should include global-context profile changes.');
employeeProfileAuditAssertSame(true, (bool) array_filter(
    $db->queries,
    static fn (string $sql): bool => str_contains($sql, 'WHERE (`id_shop` = 7 OR `id_shop` = 0)')
        && str_contains($sql, 'LIMIT 51 OFFSET 0')
), 'The page query should be shop-scoped and bounded.');
$otherShopPage = $repository->pageForShop(8, 1);
employeeProfileAuditAssertSame(3, count($otherShopPage['rows']), 'A shop page should include its own and global events only.');
employeeProfileAuditAssertSame([55, 44, 31], array_column($otherShopPage['rows'], 'target_employee_id'), 'A shop page must not expose another shop’s events.');

$queryCount = count($db->queries);
$deniedController = new AdminKuraneaEmployeeProfileAuditController();
$deniedController->nativeView = false;
$deniedController->tabAccess['view'] = false;
$deniedController->initContent();
employeeProfileAuditAssertSame($queryCount, count($db->queries), 'A reader without native view permission must not query audit rows.');
employeeProfileAuditAssertSame(true, str_contains($deniedController->content, '조회할 권한이 없습니다.'), 'Unauthorized readers should receive a denial page.');

Shop::$context = Shop::CONTEXT_ALL;
$allShopController = new AdminKuraneaEmployeeProfileAuditController();
$allShopController->nativeView = true;
$allShopController->tabAccess['view'] = true;
$queryCount = count($db->queries);
$allShopController->initContent();
employeeProfileAuditAssertSame($queryCount, count($db->queries), 'The page should reject all-shop context before querying audit events.');
employeeProfileAuditAssertSame(true, str_contains($allShopController->content, '하나의 쇼핑몰을 선택'), 'The page should require a selected shop.');

Shop::$context = Shop::CONTEXT_SHOP;
Context::$instance->shop->id = 8;
$allowedController = new AdminKuraneaEmployeeProfileAuditController();
$allowedController->nativeView = true;
$allowedController->tabAccess['view'] = true;
$allowedController->initContent();
employeeProfileAuditAssertSame(true, str_contains($allowedController->content, '<td>44</td>'), 'A shop reader should see its own target employee ID.');
employeeProfileAuditAssertSame(true, str_contains($allowedController->content, '<td>55</td>'), 'A shop reader should see global-context changes.');
employeeProfileAuditAssertSame(true, str_contains($allowedController->content, '<td>31</td>'), 'A shop reader should see the global-context Employee update.');
employeeProfileAuditAssertSame(false, str_contains($allowedController->content, '<td>32</td>'), 'A shop reader must not see another shop’s target employee ID.');

echo "PASS: Employee profile updates append actor/target old-new UTC events, unchanged updates do not, absent actors remain null, and reads include global context without leaking other shops, capped at 50 rows.\n";
