<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Infrastructure;

use InvalidArgumentException;
use RuntimeException;
use Throwable;

/** Shop-scoped assignment storage kept separate from PrestaShop customer messages. */
final class SupportAssignmentRepository
{
    private object $database;
    private string $prefix;

    public function __construct(?object $database = null, ?string $prefix = null)
    {
        if ($database === null) {
            if (!class_exists('Db')) {
                throw new RuntimeException('PrestaShop database service is not available.');
            }
            $database = \Db::getInstance();
        }

        $this->database = $database;
        $this->prefix = $prefix ?? (defined('_DB_PREFIX_') ? (string) _DB_PREFIX_ : '');
        SupportAssignmentSchema::currentTableSql($this->prefix);
    }

    /** Returns at most 100 threads plus one lookahead row for navigation.
     * @return list<array<string, mixed>>
     */
    public function threadsForShop(int $shopId, int $page = 1): array
    {
        self::assertPositiveId($shopId, '쇼핑몰');
        if ($page < 1 || $page > intdiv(PHP_INT_MAX, 100)) {
            throw new InvalidArgumentException('문의 목록 페이지가 올바르지 않습니다.');
        }
        $offset = ($page - 1) * 100;
        $rows = $this->rows(
            'SELECT t.`id_customer_thread`, t.`status`, t.`date_add`'
            . ', a.`id_employee`, e.`firstname` AS `assigned_firstname`, e.`lastname` AS `assigned_lastname`'
            . ' FROM `' . $this->prefix . 'customer_thread` t'
            . ' LEFT JOIN `' . $this->currentTable() . '` a'
            . ' ON a.`id_shop` = ' . $shopId . ' AND a.`id_customer_thread` = t.`id_customer_thread`'
            . ' LEFT JOIN `' . $this->prefix . 'employee` e ON e.`id_employee` = a.`id_employee`'
            . ' WHERE t.`id_shop` = ' . $shopId
            . ' ORDER BY t.`date_upd` DESC, t.`id_customer_thread` DESC LIMIT 101 OFFSET ' . $offset,
            '문의 목록을 불러오지 못했습니다.'
        );

        return $rows;
    }

    /** @return list<array{id_employee:int,firstname:string,lastname:string}> */
    public function employeesForShop(int $shopId): array
    {
        self::assertPositiveId($shopId, '쇼핑몰');
        $rows = $this->rows(
            'SELECT e.`id_employee`, e.`firstname`, e.`lastname`'
            . ' FROM `' . $this->prefix . 'employee` e'
            . ' INNER JOIN `' . $this->prefix . 'employee_shop` es'
            . ' ON es.`id_employee` = e.`id_employee` AND es.`id_shop` = ' . $shopId
            . ' WHERE e.`active` = 1 ORDER BY e.`lastname`, e.`firstname`, e.`id_employee`',
            '담당자 목록을 불러오지 못했습니다.'
        );

        return array_map(static fn (array $row): array => [
            'id_employee' => (int) $row['id_employee'],
            'firstname' => (string) $row['firstname'],
            'lastname' => (string) $row['lastname'],
        ], $rows);
    }

    /** @return array{id_customer_thread:int,status:string,date_add:string}|null */
    public function threadForShop(int $shopId, int $threadId): ?array
    {
        self::assertPositiveId($shopId, '쇼핑몰');
        self::assertPositiveId($threadId, '문의');
        $rows = $this->rows(
            'SELECT t.`id_customer_thread`, t.`status`, t.`date_add`'
            . ' FROM `' . $this->prefix . 'customer_thread` t'
            . ' WHERE t.`id_shop` = ' . $shopId
            . ' AND t.`id_customer_thread` = ' . $threadId . ' LIMIT 1',
            '문의를 확인하지 못했습니다.'
        );

        return isset($rows[0]) ? [
            'id_customer_thread' => (int) $rows[0]['id_customer_thread'],
            'status' => (string) $rows[0]['status'],
            'date_add' => (string) $rows[0]['date_add'],
        ] : null;
    }

    /** @return list<array<string, mixed>> */
    public function historyForThread(int $shopId, int $threadId): array
    {
        self::assertPositiveId($shopId, '쇼핑몰');
        self::assertPositiveId($threadId, '문의');
        return $this->rows(
            'SELECT h.`id_event`, h.`from_employee_id`, h.`to_employee_id`, h.`actor_employee_id`, h.`changed_at_utc`'
            . ', old_e.`firstname` AS `from_firstname`, old_e.`lastname` AS `from_lastname`'
            . ', new_e.`firstname` AS `to_firstname`, new_e.`lastname` AS `to_lastname`'
            . ', actor_e.`firstname` AS `actor_firstname`, actor_e.`lastname` AS `actor_lastname`'
            . ' FROM `' . $this->historyTable() . '` h'
            . ' INNER JOIN `' . $this->prefix . 'customer_thread` t'
            . ' ON t.`id_customer_thread` = h.`id_customer_thread` AND t.`id_shop` = h.`id_shop`'
            . ' LEFT JOIN `' . $this->prefix . 'employee` old_e ON old_e.`id_employee` = h.`from_employee_id`'
            . ' LEFT JOIN `' . $this->prefix . 'employee` new_e ON new_e.`id_employee` = h.`to_employee_id`'
            . ' LEFT JOIN `' . $this->prefix . 'employee` actor_e ON actor_e.`id_employee` = h.`actor_employee_id`'
            . ' WHERE h.`id_shop` = ' . $shopId . ' AND h.`id_customer_thread` = ' . $threadId
            . ' ORDER BY h.`id_event` DESC LIMIT 100',
            '담당자 변경 이력을 불러오지 못했습니다.'
        );
    }

    /**
     * Assigns or reassigns one same-shop active employee. Repeating the current
     * assignment is idempotent and does not append a duplicate history event.
     *
     * @return array{changed:bool,from_employee_id:?int,to_employee_id:int,changed_at_utc:?string}
     */
    public function assign(
        int $shopId,
        int $threadId,
        int $employeeId,
        int $actorEmployeeId,
        bool $canCreate,
        bool $canUpdate
    ): array
    {
        self::assertPositiveId($shopId, '쇼핑몰');
        self::assertPositiveId($threadId, '문의');
        self::assertPositiveId($employeeId, '담당자');
        self::assertPositiveId($actorEmployeeId, '관리자');

        if (!$this->database->execute('START TRANSACTION')) {
            throw new RuntimeException('담당자 변경을 시작하지 못했습니다.');
        }

        try {
            $threadRows = $this->rows(
                'SELECT t.`id_customer_thread` FROM `' . $this->prefix . 'customer_thread` t'
                . ' WHERE t.`id_customer_thread` = ' . $threadId . ' AND t.`id_shop` = ' . $shopId
                . ' LIMIT 1 FOR UPDATE',
                '문의를 확인하지 못했습니다.',
                false
            );
            if ($threadRows === []) {
                throw new InvalidArgumentException('선택한 쇼핑몰의 문의를 찾을 수 없습니다.');
            }

            $this->assertActiveEmployee($shopId, $employeeId);
            $this->assertActiveActor($actorEmployeeId);

            $currentRows = $this->rows(
                'SELECT `id_employee` FROM `' . $this->currentTable() . '`'
                . ' WHERE `id_shop` = ' . $shopId . ' AND `id_customer_thread` = ' . $threadId
                . ' LIMIT 1 FOR UPDATE',
                '현재 담당자를 확인하지 못했습니다.',
                false
            );
            $fromEmployeeId = isset($currentRows[0]) ? (int) $currentRows[0]['id_employee'] : null;
            if ($fromEmployeeId === null && !$canCreate) {
                throw new InvalidArgumentException('고객 문의 담당자를 지정할 권한이 없습니다.');
            }
            if ($fromEmployeeId !== null && !$canUpdate) {
                throw new InvalidArgumentException('고객 문의 담당자를 변경할 권한이 없습니다.');
            }
            if ($fromEmployeeId === $employeeId) {
                if (!$this->database->execute('COMMIT')) {
                    throw new RuntimeException('담당자 변경을 완료하지 못했습니다.');
                }
                return [
                    'changed' => false,
                    'from_employee_id' => $fromEmployeeId,
                    'to_employee_id' => $employeeId,
                    'changed_at_utc' => null,
                ];
            }

            $changedAt = gmdate('Y-m-d H:i:s');
            $changedAtSql = "'" . $changedAt . "'";
            if ($fromEmployeeId === null) {
                $sql = 'INSERT INTO `' . $this->currentTable() . '`'
                    . ' (`id_shop`, `id_customer_thread`, `id_employee`, `assigned_by_employee_id`, `assigned_at_utc`'
                    . ', `updated_by_employee_id`, `updated_at_utc`) VALUES ('
                    . $shopId . ', ' . $threadId . ', ' . $employeeId . ', ' . $actorEmployeeId . ', '
                    . $changedAtSql . ', ' . $actorEmployeeId . ', ' . $changedAtSql . ')';
            } else {
                $sql = 'UPDATE `' . $this->currentTable() . '` SET'
                    . ' `id_employee` = ' . $employeeId
                    . ', `updated_by_employee_id` = ' . $actorEmployeeId
                    . ', `updated_at_utc` = ' . $changedAtSql
                    . ' WHERE `id_shop` = ' . $shopId . ' AND `id_customer_thread` = ' . $threadId;
            }
            if (!$this->database->execute($sql)) {
                throw new RuntimeException('담당자를 저장하지 못했습니다.');
            }

            $fromValue = $fromEmployeeId === null ? 'NULL' : (string) $fromEmployeeId;
            $historySql = 'INSERT INTO `' . $this->historyTable() . '`'
                . ' (`id_shop`, `id_customer_thread`, `from_employee_id`, `to_employee_id`, `actor_employee_id`, `changed_at_utc`) VALUES ('
                . $shopId . ', ' . $threadId . ', ' . $fromValue . ', ' . $employeeId . ', ' . $actorEmployeeId
                . ', ' . $changedAtSql . ')';
            if (!$this->database->execute($historySql)) {
                throw new RuntimeException('담당자 변경 이력을 저장하지 못했습니다.');
            }

            if (!$this->database->execute('COMMIT')) {
                throw new RuntimeException('담당자 변경을 완료하지 못했습니다.');
            }

            return [
                'changed' => true,
                'from_employee_id' => $fromEmployeeId,
                'to_employee_id' => $employeeId,
                'changed_at_utc' => $changedAt,
            ];
        } catch (Throwable $exception) {
            $this->database->execute('ROLLBACK');
            throw $exception;
        }
    }

    private function assertActiveEmployee(int $shopId, int $employeeId): void
    {
        $rows = $this->rows(
            'SELECT e.`id_employee` FROM `' . $this->prefix . 'employee` e'
            . ' INNER JOIN `' . $this->prefix . 'employee_shop` es'
            . ' ON es.`id_employee` = e.`id_employee` AND es.`id_shop` = ' . $shopId
            . ' WHERE e.`id_employee` = ' . $employeeId . ' AND e.`active` = 1 LIMIT 1 FOR UPDATE',
            '담당자를 확인하지 못했습니다.',
            false
        );
        if ($rows === []) {
            throw new InvalidArgumentException('선택한 담당자가 이 쇼핑몰의 활성 관리자 계정이 아닙니다.');
        }
    }

    private function assertActiveActor(int $actorEmployeeId): void
    {
        $rows = $this->rows(
            'SELECT e.`id_employee` FROM `' . $this->prefix . 'employee` e'
            . ' WHERE e.`id_employee` = ' . $actorEmployeeId . ' AND e.`active` = 1 LIMIT 1 FOR UPDATE',
            '관리자 계정을 확인하지 못했습니다.',
            false
        );
        if ($rows === []) {
            throw new InvalidArgumentException('현재 관리자 계정을 확인할 수 없습니다.');
        }
    }

    /** @return list<array<string, mixed>> */
    private function rows(string $sql, string $failureMessage, bool $useCache = true): array
    {
        $rows = $this->database->executeS($sql, true, $useCache);
        if (!is_array($rows)) {
            throw new RuntimeException($failureMessage);
        }

        return $rows;
    }

    private function currentTable(): string
    {
        return $this->prefix . 'kuraneabackoffice_support_assignment';
    }

    private function historyTable(): string
    {
        return $this->prefix . 'kuraneabackoffice_support_assignment_history';
    }

    private static function assertPositiveId(int $id, string $label): void
    {
        if ($id < 1) {
            throw new InvalidArgumentException($label . ' ID가 올바르지 않습니다.');
        }
    }
}
