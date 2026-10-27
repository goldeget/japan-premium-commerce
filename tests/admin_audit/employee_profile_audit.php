<?php

declare(strict_types=1);

use PrestaShop\PrestaShop\Core\Security\Permission;

define('_PS_VERSION_', '9.2.0');
define('_DB_PREFIX_', 'ps_');

require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/vendor/autoload.php';

final class EmployeeProfileAuditFakePermission
{
    public const PREFIX_TAB = 'ROLE_MOD_TAB_';
}

class_alias(EmployeeProfileAuditFakePermission::class, 'PrestaShop\\PrestaShop\\Core\\Security\\Permission');

final class Access
{
    /** @var array<string, bool> */
    public static array $grants = [];

    public static function isGranted(string $permission, int $profileId): bool
    {
        return self::$grants[$permission . ':' . $profileId] ?? false;
    }
}

final class EmployeeProfileAuditFakeDatabase
{
    /** @var array<int, int> */
    public array $employeeProfiles = [];
    /** @var list<array{id_event:int,id_shop:int,actor_employee_id:?int,target_employee_id:int,old_profile_id:int,new_profile_id:int,changed_at_utc:string}> */
    public array $events = [];
    /** @var list<array{id_order_history:int,id_order:int,id_shop:int,reference:string,id_order_state:int,state_name:string,id_employee:?int,date_add:string}> */
    public array $orderHistory = [];
    /** @var list<array<string, mixed>> */
    public array $activityFeedEvents = [];
    /** @var list<string> */
    public array $queries = [];

    public function executeS(string $sql, bool $array = true, bool $useCache = true): array|false
    {
        $this->queries[] = $sql;
        if (str_contains($sql, ') `audit_feed`')) {
            preg_match_all("/'([a-z_]+)' AS `event_source`/", $sql, $sourceMatches);
            preg_match('/LIMIT\s+(\d+)\s+OFFSET\s+(\d+)/', $sql, $windowMatch);
            $authorizedSources = array_fill_keys($sourceMatches[1] ?? [], true);
            $limit = (int) ($windowMatch[1] ?? 0);
            $offset = (int) ($windowMatch[2] ?? 0);
            $shopMatch = preg_match('/`id_shop`\s*=\s*(\d+)/', $sql, $shopCapture);
            $shopId = $shopMatch === 1 ? (int) $shopCapture[1] : 0;
            $events = array_values(array_filter(
                $this->activityFeedEvents,
                static fn (array $event): bool => isset($authorizedSources[$event['event_source'] ?? ''])
                    && ((int) ($event['id_shop'] ?? -1) === $shopId
                        || (($event['event_source'] ?? '') === 'employee_profile' && (int) ($event['id_shop'] ?? -1) === 0))
            ));
            usort($events, static fn (array $left, array $right): int =>
                strcmp((string) $right['event_at'], (string) $left['event_at'])
                ?: strcmp((string) $left['event_source'], (string) $right['event_source'])
                ?: ((int) $right['event_id'] <=> (int) $left['event_id']));

            return array_slice($events, $offset, $limit);
        }

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

        if (str_contains($sql, 'FROM `ps_order_history` oh')) {
            preg_match('/o\.`id_shop`\s*=\s*(\d+)/', $sql, $shopMatch);
            preg_match('/LIMIT\s+51\s+OFFSET\s+(\d+)/', $sql, $windowMatch);
            $shopId = (int) ($shopMatch[1] ?? 0);
            $offset = (int) ($windowMatch[1] ?? 0);
            $rows = array_values(array_filter(
                $this->orderHistory,
                static fn (array $row): bool => $row['id_shop'] === $shopId
            ));
            usort($rows, static fn (array $left, array $right): int => $right['date_add'] <=> $left['date_add']
                ?: $right['id_order_history'] <=> $left['id_order_history']);

            return array_slice($rows, $offset, 51);
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

    public function initHeader()
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
    'employee' => (object) ['id' => 90, 'id_profile' => 2],
    'language' => (object) ['id' => 3],
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
require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/upgrade/upgrade-1.0.5.php';
employeeProfileAuditAssertSame(true, upgrade_module_1_0_3($module), 'The installed-module upgrade should apply the additive audit setup.');
employeeProfileAuditAssertSame(true, upgrade_module_1_0_5($module), 'The installed-module upgrade should rename the existing audit tab.');
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

for ($index = 1; $index <= 51; $index++) {
    $db->orderHistory[] = [
        'id_order_history' => $index,
        'id_order' => 100 + $index,
        'id_shop' => 7,
        'reference' => 'CI-ORDER-' . $index,
        'id_order_state' => 2,
        'state_name' => '결제 대기',
        'id_employee' => 90,
        'date_add' => '2026-10-26 12:00:00',
    ];
}
$db->orderHistory[] = [
    'id_order_history' => 52,
    'id_order' => 200,
    'id_shop' => 8,
    'reference' => 'OTHER-SHOP-ORDER',
    'id_order_state' => 2,
    'state_name' => '결제 대기',
    'id_employee' => 90,
    'date_add' => '2026-10-26 12:00:00',
];
$orderHistoryRepository = new \Kuranea\Backoffice\Infrastructure\OrderHistoryAuditRepository($db, 'ps_');
$orderHistoryPage = $orderHistoryRepository->pageForShop(7, 3, 1);
employeeProfileAuditAssertSame(50, count($orderHistoryPage['rows']), 'Order audit pages should cap rows at fifty.');
employeeProfileAuditAssertSame(true, $orderHistoryPage['has_next'], 'An order audit lookahead row should indicate another page.');
employeeProfileAuditAssertSame(51, $orderHistoryPage['rows'][0]['id_order_history'], 'Order history should be sorted newest-first with an ID tie-breaker.');
employeeProfileAuditAssertSame(false, (bool) array_filter(
    $orderHistoryPage['rows'],
    static fn (array $row): bool => $row['reference'] === 'OTHER-SHOP-ORDER'
), 'Order history must not expose a different shop.');
employeeProfileAuditAssertSame(true, (bool) array_filter(
    $db->queries,
    static fn (string $sql): bool => str_contains($sql, 'INNER JOIN `ps_orders`')
        && str_contains($sql, 'LEFT JOIN `ps_order_state_lang`')
        && str_contains($sql, 'WHERE o.`id_shop` = 7')
        && str_contains($sql, 'LIMIT 51 OFFSET 0')
), 'Order audit must read native history, localize the status, and constrain the selected shop.');
employeeProfileAuditAssertSame(1, preg_match('/\A\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\z/', $orderHistoryPage['rows'][0]['date_add']),
    'Order audit should preserve the native history timestamp.');
try {
    $orderHistoryRepository->pageForShop(7, 3, 0);
    throw new RuntimeException('An invalid order audit page was accepted.');
} catch (InvalidArgumentException $expected) {
}

$activityRepository = new \Kuranea\Backoffice\Infrastructure\AdminAuditEventRepository($db, 'ps_');
$db->activityFeedEvents = [];
for ($index = 1; $index <= 51; $index++) {
    $db->activityFeedEvents[] = [
        'event_source' => 'order_history',
        'event_id' => $index,
        'event_at' => '2026-10-26 12:00:00',
        'time_basis' => 'stored',
        'actor_employee_id' => 90,
        'action_key' => 'order_status_changed',
        'target_type' => 'order',
        'target_id' => 100 + $index,
        'id_shop' => 7,
    ];
}
$activityPageOne = $activityRepository->pageForShop(7, 1, ['order_history', 'order_history']);
employeeProfileAuditAssertSame(50, count($activityPageOne['rows']), 'The combined activity feed should cap rows at fifty.');
employeeProfileAuditAssertSame(true, $activityPageOne['has_next'], 'The combined feed lookahead should indicate another page.');
employeeProfileAuditAssertSame(51, $activityPageOne['rows'][0]['event_id'], 'Equal timestamps should use a stable descending event ID tie-breaker.');
$activityPageTwo = $activityRepository->pageForShop(7, 2, ['order_history']);
employeeProfileAuditAssertSame(1, count($activityPageTwo['rows']), 'The combined feed should return the remaining row on page two.');
employeeProfileAuditAssertSame(false, $activityPageTwo['has_next'], 'The final combined feed page should not report a next page.');
employeeProfileAuditAssertSame(1, $activityPageTwo['rows'][0]['event_id'], 'Global feed pages should not repeat rows.');
$activityQueries = array_values(array_filter(
    $db->queries,
    static fn (string $sql): bool => str_contains($sql, ') `audit_feed`')
));
$lastActivityQuery = $activityQueries[array_key_last($activityQueries)] ?? '';
employeeProfileAuditAssertSame(true, str_contains($lastActivityQuery, 'ORDER BY `event_at` DESC, `event_source` ASC, `event_id` DESC'),
    'The combined feed should order timestamp ties deterministically across sources.');
employeeProfileAuditAssertSame(true, str_contains($lastActivityQuery, 'LIMIT 51 OFFSET 50'),
    'The combined feed should use one globally bounded offset page.');

$db->activityFeedEvents = [
    [
        'event_source' => 'employee_profile', 'event_id' => 7, 'event_at' => '2026-10-26 12:00:00',
        'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'employee_profile_changed',
        'target_type' => 'employee', 'target_id' => 31, 'id_shop' => 7,
        'profile_json' => 'PRIVATE-PROFILE', 'email' => 'PRIVATE-EMAIL',
    ],
    [
        'event_source' => 'employee_profile', 'event_id' => 8, 'event_at' => '2026-10-26 12:00:01',
        'time_basis' => 'UTC', 'actor_employee_id' => null, 'action_key' => 'employee_profile_changed',
        'target_type' => 'employee', 'target_id' => 55, 'id_shop' => 0,
    ],
    [
        'event_source' => 'order_history', 'event_id' => 9, 'event_at' => '2026-10-26 12:00:00',
        'time_basis' => 'stored', 'actor_employee_id' => 90, 'action_key' => 'order_status_changed',
        'target_type' => 'order', 'target_id' => 201, 'id_shop' => 7,
        'reference' => 'PRIVATE-ORDER-REF', 'message' => 'PRIVATE-MESSAGE',
    ],
    [
        'event_source' => 'support_assignment', 'event_id' => 10, 'event_at' => '2026-10-26 12:00:00',
        'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'support_reassigned',
        'target_type' => 'support_thread', 'target_id' => 301, 'id_shop' => 7,
        'email' => 'PRIVATE-CONTACT', 'message' => 'PRIVATE-THREAD',
    ],
    [
        'event_source' => 'bank_transfer_instruction', 'event_id' => 11, 'event_at' => '2026-10-26 12:00:00',
        'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'bank_transfer_instruction_issued',
        'target_type' => 'order', 'target_id' => 401, 'id_shop' => 7,
        'bank_account_id' => 'PRIVATE-ACCOUNT-ID', 'order_reference' => 'PRIVATE-ORDER-REF',
    ],
    [
        'event_source' => 'bank_transfer_receipt', 'event_id' => 12, 'event_at' => '2026-10-26 12:00:00',
        'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'bank_transfer_receipt_confirmed',
        'target_type' => 'order', 'target_id' => 401, 'id_shop' => 7,
        'receipt_reference_sha256' => 'PRIVATE-REFERENCE-DIGEST', 'received_amount' => '999999',
    ],
];
$allSources = ['employee_profile', 'order_history', 'support_assignment', 'bank_transfer_instruction', 'bank_transfer_receipt'];
$mixedFeed = $activityRepository->pageForShop(7, 1, $allSources);
employeeProfileAuditAssertSame(
    ['employee_profile', 'bank_transfer_instruction', 'bank_transfer_receipt', 'employee_profile', 'order_history', 'support_assignment'],
    array_column($mixedFeed['rows'], 'source'),
    'The combined feed should merge source events newest-first with a stable source tie-breaker.'
);
employeeProfileAuditAssertSame(
    ['source', 'event_id', 'event_at', 'time_basis', 'actor_employee_id', 'action', 'target_type', 'target_id'],
    array_keys($mixedFeed['rows'][2]),
    'The activity view model should contain only allowlisted source/action/actor/time/target identifiers.'
);
employeeProfileAuditAssertSame(true, (bool) array_filter(
    $mixedFeed['rows'],
    static fn (array $event): bool => $event['source'] === 'employee_profile' && $event['target_id'] === 55
), 'A global employee profile event should remain visible with the selected shop audit page.');

$db->activityFeedEvents = [
    ['event_source' => 'employee_profile', 'event_id' => 101, 'event_at' => '2026-10-26 12:00:05', 'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'employee_profile_changed', 'target_type' => 'employee', 'target_id' => 44, 'id_shop' => 8],
    ['event_source' => 'employee_profile', 'event_id' => 102, 'event_at' => '<script>alert(1)</script>', 'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'employee_profile_changed', 'target_type' => 'employee', 'target_id' => 31, 'id_shop' => 0],
    ['event_source' => 'employee_profile', 'event_id' => 103, 'event_at' => '2026-10-26 12:00:03', 'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'employee_profile_changed', 'target_type' => 'employee', 'target_id' => 32, 'id_shop' => 7],
    ['event_source' => 'employee_profile', 'event_id' => 104, 'event_at' => '2026-10-26 12:00:02', 'time_basis' => 'UTC', 'actor_employee_id' => null, 'action_key' => 'employee_profile_changed', 'target_type' => 'employee', 'target_id' => 55, 'id_shop' => 0],
    ['event_source' => 'order_history', 'event_id' => 201, 'event_at' => '2026-10-26 12:00:01', 'time_basis' => 'stored', 'actor_employee_id' => 90, 'action_key' => 'order_status_changed', 'target_type' => 'order', 'target_id' => 202, 'id_shop' => 8, 'reference' => 'PRIVATE-ORDER-REF'],
    ['event_source' => 'support_assignment', 'event_id' => 301, 'event_at' => '2026-10-26 12:00:01', 'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'support_assigned', 'target_type' => 'support_thread', 'target_id' => 303, 'id_shop' => 8, 'email' => 'PRIVATE-CONTACT', 'message' => 'PRIVATE-THREAD'],
    ['event_source' => 'bank_transfer_instruction', 'event_id' => 401, 'event_at' => '2026-10-26 12:00:01', 'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'bank_transfer_instruction_issued', 'target_type' => 'order', 'target_id' => 404, 'id_shop' => 8, 'bank_account_id' => 'PRIVATE-ACCOUNT-ID', 'order_reference' => 'PRIVATE-ORDER-REF'],
    ['event_source' => 'bank_transfer_receipt', 'event_id' => 501, 'event_at' => '2026-10-26 12:00:01', 'time_basis' => 'UTC', 'actor_employee_id' => 90, 'action_key' => 'bank_transfer_receipt_confirmed', 'target_type' => 'order', 'target_id' => 404, 'id_shop' => 8, 'receipt_reference_sha256' => 'PRIVATE-REFERENCE-DIGEST', 'received_amount' => '999999'],
];

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
Context::$instance->employee = (object) ['id' => 90, 'id_profile' => 2];
$orderHistoryQueryCount = count(array_filter(
    $db->queries,
    static fn (string $sql): bool => str_contains($sql, 'FROM `ps_order_history` oh')
));
$profileAuditReader = new AdminKuraneaEmployeeProfileAuditController();
$profileAuditReader->nativeView = true;
$profileAuditReader->tabAccess['view'] = true;
$profileAuditReader->initContent();
employeeProfileAuditAssertSame($orderHistoryQueryCount, count(array_filter(
    $db->queries,
    static fn (string $sql): bool => str_contains($sql, 'FROM `ps_order_history` oh')
)), 'An audit-only reader without native Orders READ must not query order history.');
employeeProfileAuditAssertSame(false, str_contains($db->queries[array_key_last($db->queries)] ?? '', 'FROM `ps_kuraneabackoffice_support_assignment_history`'),
    'An audit-only reader must not query support assignment history.');
employeeProfileAuditAssertSame(false, str_contains($db->queries[array_key_last($db->queries)] ?? '', 'kuraneabusinessprofile_bank_transfer_'),
    'An audit-only reader must not query bank transfer history.');
employeeProfileAuditAssertSame(false, str_contains($profileAuditReader->content, 'OTHER-SHOP-ORDER'), 'An audit-only reader must not see order references.');

Access::$grants[Permission::PREFIX_TAB . 'ADMINORDERS_READ:2'] = true;
$ordersReadRole = Permission::PREFIX_TAB . 'ADMINORDERS_READ';
$profileId = (int) Context::$instance->employee->id_profile;
employeeProfileAuditAssertSame(true, Access::isGranted($ordersReadRole, $profileId),
    'The fixture should grant native role ' . $ordersReadRole . ' to profile ' . $profileId . '.');
$allowedController = new AdminKuraneaEmployeeProfileAuditController();
$allowedController->nativeView = true;
$allowedController->tabAccess['view'] = true;
$allowedController->initContent();
$orderHistoryQueries = array_values(array_filter(
    $db->queries,
    static fn (string $sql): bool => str_contains($sql, 'FROM `ps_order_history` oh')
));
employeeProfileAuditAssertSame($orderHistoryQueryCount + 1, count($orderHistoryQueries),
    'Orders READ should permit exactly one order-history query for profile ' . $profileId . '.');
$allowedOrderQuery = $orderHistoryQueries[array_key_last($orderHistoryQueries)] ?? '';
employeeProfileAuditAssertSame(true, str_contains($allowedOrderQuery, 'WHERE o.`id_shop` = 8'),
    'The authorized order-history query should use the selected shop.');
employeeProfileAuditAssertSame(true, str_contains($allowedController->content, '관리자 #44'), 'A shop reader should see its own target employee ID.');
employeeProfileAuditAssertSame(true, str_contains($allowedController->content, '관리자 #55'), 'A shop reader should see global-context changes.');
employeeProfileAuditAssertSame(true, str_contains($allowedController->content, '관리자 #31'), 'A shop reader should see the global-context Employee update.');
employeeProfileAuditAssertSame(false, str_contains($allowedController->content, '관리자 #32'), 'A shop reader must not see another shop’s target employee ID.');
employeeProfileAuditAssertSame(true, str_contains($allowedController->content, '주문 #202'), 'An Orders READ reader should see the selected-shop order target ID.');
employeeProfileAuditAssertSame(false, str_contains($allowedController->content, 'PRIVATE-ORDER-REF'), 'The feed must not expose order references.');
employeeProfileAuditAssertSame(false, str_contains($allowedController->content, '문의 #303'), 'Orders READ must not grant support assignment access.');
employeeProfileAuditAssertSame(false, str_contains($allowedController->content, '입금 안내'), 'Orders READ must not grant bank transfer access.');

Access::$grants[Permission::PREFIX_TAB . 'ADMINKURANEASUPPORTASSIGNMENTS_READ:2'] = true;
$supportReadController = new AdminKuraneaEmployeeProfileAuditController();
$supportReadController->nativeView = true;
$supportReadController->tabAccess['view'] = true;
$supportReadController->initContent();
$supportReadQuery = $db->queries[array_key_last($db->queries)] ?? '';
employeeProfileAuditAssertSame(true, str_contains($supportReadQuery, 'FROM `ps_kuraneabackoffice_support_assignment_history`'),
    'Support READ should add the shop-scoped assignment source.');
employeeProfileAuditAssertSame(false, str_contains($supportReadQuery, 'kuraneabusinessprofile_bank_transfer_'),
    'Support READ must not grant bank transfer history.');
employeeProfileAuditAssertSame(true, str_contains($supportReadController->content, '문의 #303'),
    'A support reader should see the selected-shop thread target ID.');
employeeProfileAuditAssertSame(false, str_contains($supportReadController->content, 'PRIVATE-CONTACT'),
    'The common feed must not expose support contact details.');
employeeProfileAuditAssertSame(false, str_contains($supportReadController->content, 'PRIVATE-THREAD'),
    'The common feed must not expose support message content.');

Access::$grants[Permission::PREFIX_TAB . 'ADMINBUSINESSPROFILETRANSFERS_READ:2'] = true;
$bankReadController = new AdminKuraneaEmployeeProfileAuditController();
$bankReadController->nativeView = true;
$bankReadController->tabAccess['view'] = true;
$bankReadController->initContent();
$bankReadQuery = $db->queries[array_key_last($db->queries)] ?? '';
employeeProfileAuditAssertSame(true, str_contains($bankReadQuery, 'FROM `ps_kuraneabusinessprofile_bank_transfer_instruction`'),
    'Transfer READ should add the shop-scoped instruction source.');
employeeProfileAuditAssertSame(true, str_contains($bankReadQuery, 'FROM `ps_kuraneabusinessprofile_bank_transfer_receipt`'),
    'Transfer READ should add the shop-scoped receipt source.');
employeeProfileAuditAssertSame(true, str_contains($bankReadController->content, '입금 안내 발급'),
    'A transfer reader should see safe instruction action metadata.');
employeeProfileAuditAssertSame(true, str_contains($bankReadController->content, '입금 확인 기록'),
    'A transfer reader should see safe receipt action metadata.');
foreach (['PRIVATE-ACCOUNT-ID', 'PRIVATE-REFERENCE-DIGEST', '999999', 'PRIVATE-ORDER-REF'] as $secret) {
    employeeProfileAuditAssertSame(false, str_contains($bankReadController->content, $secret),
        'The common feed must not expose bank or order secret ' . $secret . '.');
}
employeeProfileAuditAssertSame(true, str_contains($bankReadController->content, '&lt;script&gt;alert(1)&lt;/script&gt;'),
    'Timestamp output should be escaped before rendering.');
employeeProfileAuditAssertSame(false, str_contains($bankReadController->content, '<script>alert(1)</script>'),
    'Raw timestamp markup must not reach the page.');

echo "PASS: The read-only admin activity feed preserves independent ACLs, shop scope, bounded ordering, and safe fields across existing event sources.\n";
