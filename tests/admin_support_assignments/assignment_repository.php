<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/vendor/autoload.php';

use Kuranea\Backoffice\Infrastructure\SupportAssignmentRepository;
use Kuranea\Backoffice\Infrastructure\SupportAssignmentSchema;

final class SupportAssignmentFakeDatabase
{
    /** @var array<string, bool> */
    public array $threads = [];
    /** @var array<int, array{active:bool,shops:list<int>}> */
    public array $employees = [];
    /** @var array<string, int> */
    public array $assignments = [];
    /** @var list<string> */
    public array $queries = [];
    /** @var list<array{sql:string,use_cache:bool}> */
    public array $selectCacheSettings = [];
    public bool $failHistoryInsert = false;

    public function executeS(string $sql, bool $array = true, bool $useCache = true): array|false
    {
        $this->queries[] = $sql;
        $this->selectCacheSettings[] = ['sql' => $sql, 'use_cache' => $useCache];
        if (preg_match('/\bFROM\s+`[^`]*customer_thread`(?:\s|$)/i', $sql) === 1) {
            if (str_contains($sql, 'ORDER BY t.`date_upd`')) {
                preg_match('/WHERE t\.`id_shop` = (\d+)/', $sql, $scope);
                preg_match('/LIMIT (\d+)(?: OFFSET (\d+))?/', $sql, $window);
                $ids = [];
                foreach ($this->threads as $key => $exists) {
                    [$shop, $id] = array_map('intval', explode(':', $key));
                    if ($exists && $shop === (int) ($scope[1] ?? 0)) {
                        $ids[] = $id;
                    }
                }
                rsort($ids);
                return array_map(static fn (int $id): array => [
                    'id_customer_thread' => $id, 'status' => 'open', 'date_add' => '2026-01-01 00:00:00',
                ], array_slice($ids, (int) ($window[2] ?? 0), (int) ($window[1] ?? 0)));
            }
            preg_match('/id_customer_thread`\s*=\s*(\d+)/', $sql, $threadMatch);
            preg_match('/id_shop`\s*=\s*(\d+)/', $sql, $shopMatch);
            $key = (int) ($shopMatch[1] ?? 0) . ':' . (int) ($threadMatch[1] ?? 0);
            return isset($this->threads[$key]) ? [['id_customer_thread' => (int) ($threadMatch[1] ?? 0)]] : [];
        }

        if (str_contains($sql, 'employee_shop')) {
            preg_match('/id_employee`\s*=\s*(\d+)/', $sql, $employeeMatch);
            preg_match('/id_shop`\s*=\s*(\d+)/', $sql, $shopMatch);
            $employeeId = (int) ($employeeMatch[1] ?? 0);
            $shopId = (int) ($shopMatch[1] ?? 0);
            $employee = $this->employees[$employeeId] ?? null;
            return is_array($employee)
                && $employee['active']
                && in_array($shopId, $employee['shops'], true)
                    ? [['id_employee' => $employeeId]]
                    : [];
        }

        if (preg_match('/\bFROM\s+`[^`]*employee`(?:\s|$)/i', $sql) === 1) {
            preg_match('/id_employee`\s*=\s*(\d+)/', $sql, $employeeMatch);
            $employeeId = (int) ($employeeMatch[1] ?? 0);
            return ($this->employees[$employeeId]['active'] ?? false)
                ? [['id_employee' => $employeeId]]
                : [];
        }

        if (str_contains($sql, 'support_assignment`') && str_contains($sql, 'SELECT `id_employee`')) {
            preg_match('/id_shop`\s*=\s*(\d+)/', $sql, $shopMatch);
            preg_match('/id_customer_thread`\s*=\s*(\d+)/', $sql, $threadMatch);
            $key = (int) ($shopMatch[1] ?? 0) . ':' . (int) ($threadMatch[1] ?? 0);
            return isset($this->assignments[$key])
                ? [['id_employee' => $this->assignments[$key]]]
                : [];
        }

        return [];
    }

    public function execute(string $sql): bool
    {
        $this->queries[] = $sql;
        return !($this->failHistoryInsert && str_contains($sql, 'support_assignment_history'));
    }
}

function supportAssignmentAssertSame(mixed $expected, mixed $actual, string $label): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($label . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function supportAssignmentAssertThrows(callable $operation, string $label): void
{
    try {
        $operation();
    } catch (InvalidArgumentException) {
        return;
    }
    throw new RuntimeException($label . '; expected InvalidArgumentException.');
}

$db = new SupportAssignmentFakeDatabase();
$db->threads['7:20'] = true;
$db->employees[70] = ['active' => true, 'shops' => [7]];
$db->employees[71] = ['active' => true, 'shops' => [7]];
$db->employees[90] = ['active' => true, 'shops' => [7]];
$repository = new SupportAssignmentRepository($db, 'ps_');
$result = $repository->assign(7, 20, 70, 90, true, true);
supportAssignmentAssertSame(true, $result['changed'], 'An initial assignment should be saved.');
supportAssignmentAssertSame(true, in_array('START TRANSACTION', $db->queries, true), 'Assignment writes should be transactional.');
supportAssignmentAssertSame(true, in_array('COMMIT', $db->queries, true), 'Successful assignment should commit.');
foreach ($db->selectCacheSettings as $selection) {
    if (str_contains($selection['sql'], 'FOR UPDATE')) {
        supportAssignmentAssertSame(false, $selection['use_cache'], 'Locking selects must bypass PrestaShop query cache.');
    }
}
$writes = array_values(array_filter($db->queries, static fn (string $sql): bool => str_starts_with($sql, 'INSERT INTO') || str_starts_with($sql, 'UPDATE')));
supportAssignmentAssertSame(2, count($writes), 'Current assignment and history should both be written.');
supportAssignmentAssertSame(true, str_contains($writes[0], 'ps_kuraneabackoffice_support_assignment`'), 'Current assignment should use the prefixed table.');
supportAssignmentAssertSame(true, str_contains($writes[0], '7, 20, 70, 90'), 'Current assignment should include validated shop/thread/employee/actor IDs.');
supportAssignmentAssertSame(true, str_contains($writes[1], 'ps_kuraneabackoffice_support_assignment_history`'), 'Every assignment change should append history.');
supportAssignmentAssertSame(true, str_contains($writes[1], '7, 20, NULL, 70, 90'), 'Initial history should record no previous employee and the actor.');
supportAssignmentAssertSame(true, preg_match('/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/', $writes[1]) === 1, 'History should record a UTC timestamp.');

$db = new SupportAssignmentFakeDatabase();
$db->threads['7:20'] = true;
$db->employees[70] = ['active' => true, 'shops' => [7]];
$db->employees[71] = ['active' => true, 'shops' => [7]];
$db->employees[90] = ['active' => true, 'shops' => [7]];
$db->assignments['7:20'] = 70;
$repository = new SupportAssignmentRepository($db, 'ps_');
$result = $repository->assign(7, 20, 71, 90, true, true);
supportAssignmentAssertSame(70, $result['from_employee_id'], 'Reassignment should keep the prior employee in the event.');
$historyWrites = array_values(array_filter($db->queries, static fn (string $sql): bool => str_starts_with($sql, 'INSERT INTO') && str_contains($sql, 'support_assignment_history')));
supportAssignmentAssertSame(1, count($historyWrites), 'Reassignment should append one history event.');
supportAssignmentAssertSame(true, str_contains($historyWrites[0], '7, 20, 70, 71, 90'), 'Reassignment should record old, new, and actor IDs.');

$db = new SupportAssignmentFakeDatabase();
$db->threads['7:20'] = true;
$db->employees[70] = ['active' => true, 'shops' => [7]];
$db->employees[90] = ['active' => true, 'shops' => [7]];
$db->assignments['7:20'] = 70;
$repository = new SupportAssignmentRepository($db, 'ps_');
$result = $repository->assign(7, 20, 70, 90, true, true);
supportAssignmentAssertSame(false, $result['changed'], 'Repeating the same employee should be idempotent.');
supportAssignmentAssertSame(false, (bool) array_filter($db->queries, static fn (string $sql): bool => str_starts_with($sql, 'INSERT INTO') || str_starts_with($sql, 'UPDATE')), 'An idempotent repeat should not add another history event.');

$db = new SupportAssignmentFakeDatabase();
$db->threads['7:20'] = true;
$db->employees[71] = ['active' => true, 'shops' => [8]];
$db->employees[90] = ['active' => true, 'shops' => [7]];
$repository = new SupportAssignmentRepository($db, 'ps_');
supportAssignmentAssertThrows(static fn () => $repository->assign(8, 20, 71, 90, true, true), 'A foreign-shop thread must be rejected.');
supportAssignmentAssertThrows(static fn () => $repository->assign(7, 20, 71, 90, true, true), 'An employee not associated with this shop must be rejected.');
supportAssignmentAssertSame(false, (bool) array_filter($db->queries, static fn (string $sql): bool => str_starts_with($sql, 'INSERT INTO') || str_starts_with($sql, 'UPDATE')), 'Invalid thread or employee IDs must not change assignment data.');

$db = new SupportAssignmentFakeDatabase();
$repository = new SupportAssignmentRepository($db, 'ps_');
supportAssignmentAssertThrows(static fn () => $repository->assign(0, 20, 71, 90, true, true), 'Non-positive IDs must be rejected.');
supportAssignmentAssertSame([], $db->queries, 'Invalid IDs must be rejected before opening a transaction.');

$db = new SupportAssignmentFakeDatabase();
$db->threads['7:20'] = true;
$db->employees[70] = ['active' => true, 'shops' => [7]];
$db->employees[90] = ['active' => true, 'shops' => [7]];
$db->failHistoryInsert = true;
$repository = new SupportAssignmentRepository($db, 'ps_');
try {
    $repository->assign(7, 20, 70, 90, true, true);
    throw new RuntimeException('History failure should abort assignment.');
} catch (RuntimeException $exception) {
    if ($exception->getMessage() === 'History failure should abort assignment.') {
        throw $exception;
    }
}
supportAssignmentAssertSame(true, in_array('ROLLBACK', $db->queries, true), 'History failure must roll back the current assignment write.');

$db = new SupportAssignmentFakeDatabase();
$db->threads['7:20'] = true;
$db->employees[70] = ['active' => true, 'shops' => [7]];
$db->employees[90] = ['active' => true, 'shops' => [7]];
$repository = new SupportAssignmentRepository($db, 'ps_');
supportAssignmentAssertThrows(static fn () => $repository->assign(7, 20, 70, 90, false, true), 'Create permission is required for an unassigned thread.');
supportAssignmentAssertSame(false, (bool) array_filter($db->queries, static fn (string $sql): bool => str_starts_with($sql, 'INSERT INTO') || str_starts_with($sql, 'UPDATE')), 'Missing create permission must not write.');

$db = new SupportAssignmentFakeDatabase();
$db->threads['7:20'] = true;
$db->employees[70] = ['active' => true, 'shops' => [7]];
$db->employees[71] = ['active' => true, 'shops' => [7]];
$db->employees[90] = ['active' => true, 'shops' => [7]];
$db->assignments['7:20'] = 70;
$repository = new SupportAssignmentRepository($db, 'ps_');
supportAssignmentAssertThrows(static fn () => $repository->assign(7, 20, 71, 90, true, false), 'Edit permission is required to reassign an existing thread.');
supportAssignmentAssertSame(false, (bool) array_filter($db->queries, static fn (string $sql): bool => str_starts_with($sql, 'INSERT INTO') || str_starts_with($sql, 'UPDATE')), 'Missing edit permission must not write.');

// Equal update times are broken by thread ID; the oldest same-shop thread is on page two.
$db = new SupportAssignmentFakeDatabase();
for ($id = 1; $id <= 101; ++$id) {
    $db->threads['7:' . $id] = true;
}
$db->threads['8:999'] = true;
$db->employees[70] = ['active' => true, 'shops' => [7]];
$db->employees[90] = ['active' => true, 'shops' => [7]];
$repository = new SupportAssignmentRepository($db, 'ps_');
$firstPage = $repository->threadsForShop(7, 1);
$secondPage = $repository->threadsForShop(7, 2);
supportAssignmentAssertSame([1], array_column($secondPage, 'id_customer_thread'), 'Page two must reach the older same-shop inquiry outside the first hundred.');
supportAssignmentAssertSame(101, count($firstPage), 'Page one includes one lookahead row for next-page navigation.');
supportAssignmentAssertSame(false, in_array(999, array_column($firstPage, 'id_customer_thread'), true), 'Pagination must exclude foreign-shop inquiries.');
$result = $repository->assign(7, $secondPage[0]['id_customer_thread'], 70, 90, true, true);
supportAssignmentAssertSame(true, $result['changed'], 'The older inquiry reached on page two must be assignable.');
supportAssignmentAssertSame(null, $repository->threadForShop(7, 999), 'Direct lookup must not reveal a foreign-shop inquiry.');
supportAssignmentAssertThrows(static fn () => $repository->assign(7, 999, 70, 90, true, true), 'Pagination must not permit assigning a foreign-shop inquiry.');
supportAssignmentAssertThrows(static fn () => $repository->threadsForShop(7, 0), 'Page zero must be rejected.');
supportAssignmentAssertThrows(static fn () => $repository->threadsForShop(7, PHP_INT_MAX), 'Overflowing offsets must be rejected.');

// Exercise controller rendering and parsing without booting the PrestaShop framework.
class ModuleAdminController
{
    public array $tabAccess = ['view' => true, 'add' => true, 'edit' => true];
    public function viewAccess(): bool { return true; }
    public function access(string $operation): bool { return true; }
}
require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/controllers/admin/AdminKuraneaSupportAssignmentsController.php';
$controllerClass = new ReflectionClass(AdminKuraneaSupportAssignmentsController::class);
$controller = $controllerClass->newInstanceWithoutConstructor();
supportAssignmentAssertSame(true, $controllerClass->hasMethod('requestedPage'), 'Controller must safely parse a support page.');
$parsePage = $controllerClass->getMethod('requestedPage');
foreach ([null, '', '0', '-1', '1.5', '1e2', ['2'], str_repeat('9', 40)] as $invalidPage) {
    $_GET = ['support_page' => $invalidPage];
    supportAssignmentAssertSame(1, $parsePage->invoke($controller), 'Invalid or oversized pages must fall back to page one.');
}
$_GET = ['support_page' => '2'];
supportAssignmentAssertSame(2, $parsePage->invoke($controller), 'The controller must accept page two.');
$renderPagination = $controllerClass->getMethod('renderPagination');
$baseUrl = '/admin/index.php?controller=AdminKuraneaSupportAssignments&token=synthetic';
$pageOneNav = $renderPagination->invoke($controller, $baseUrl, 1, true);
supportAssignmentAssertSame(true, str_contains($pageOneNav, 'support_page=2'), 'The first page must link to the older inquiries.');
supportAssignmentAssertSame(false, str_contains($pageOneNav, 'support_page=0'), 'The first page must not expose a zero page.');
$pageTwoNav = $renderPagination->invoke($controller, $baseUrl, 2, false);
supportAssignmentAssertSame(true, str_contains($pageTwoNav, 'support_page=1'), 'The last page must link back to the first page.');
supportAssignmentAssertSame(false, str_contains($pageTwoNav, 'support_page=3'), 'No next link may be shown without a lookahead row.');
$renderTable = $controllerClass->getMethod('renderThreadTable');
$html = $renderTable->invoke($controller, $secondPage, [['id_employee' => 70, 'firstname' => 'Synthetic', 'lastname' => 'Staff']], $baseUrl . '&support_page=2', 'synthetic');
supportAssignmentAssertSame(true, str_contains($html, 'name="id_customer_thread" value="1"'), 'The older inquiry must expose its assignment form.');
supportAssignmentAssertSame(true, str_contains($html, 'support_page=2&amp;id_customer_thread=1'), 'History navigation must preserve page two.');
supportAssignmentAssertSame(true, str_contains($html, 'action="/admin/index.php?controller=AdminKuraneaSupportAssignments&amp;token=synthetic&amp;support_page=2"'), 'Assignment POST must retain the current page.');
$_GET = [];

foreach ([SupportAssignmentSchema::currentTableSql('ps_'), SupportAssignmentSchema::historyTableSql('ps_')] as $sql) {
    supportAssignmentAssertSame(true, str_contains($sql, 'CREATE TABLE IF NOT EXISTS `ps_'), 'Upgrade schema should be additive and prefix-safe.');
}
supportAssignmentAssertThrows(static fn () => SupportAssignmentSchema::currentTableSql('x`; DROP TABLE ps_customer'), 'An unsafe table prefix must be rejected.');

require_once __DIR__ . '/support_status_rendering.php';

echo "PASS: shop-scoped support assignment, reassignment, idempotence, invalid targets, rollback, paginated older-inquiry access, and additive schema\n";
