<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Infrastructure;

use InvalidArgumentException;
use RuntimeException;

/** Append-only employee profile transitions, visible to their shop and to every shop when global. */
final class EmployeeProfileAuditRepository
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
        EmployeeProfileAuditSchema::tableSql($this->prefix);
    }

    public function profileIdForEmployee(int $employeeId): ?int
    {
        self::assertPositiveId($employeeId, '관리자');
        $rows = $this->rows(
            'SELECT `id_profile` FROM `' . $this->prefix . 'employee`'
            . ' WHERE `id_employee` = ' . $employeeId . ' LIMIT 1',
            '관리자 프로필을 확인하지 못했습니다.'
        );
        if (!isset($rows[0]['id_profile']) || (int) $rows[0]['id_profile'] < 1) {
            return null;
        }

        return (int) $rows[0]['id_profile'];
    }

    /** Insert only a changed profile transition; actor null means no authenticated employee context. */
    public function appendProfileChange(
        int $shopId,
        ?int $actorEmployeeId,
        int $targetEmployeeId,
        int $oldProfileId,
        int $newProfileId
    ): bool {
        if ($shopId < 0) {
            throw new InvalidArgumentException('쇼핑몰 ID가 올바르지 않습니다.');
        }
        if ($actorEmployeeId !== null) {
            self::assertPositiveId($actorEmployeeId, '처리 관리자');
        }
        self::assertPositiveId($targetEmployeeId, '대상 관리자');
        self::assertPositiveId($oldProfileId, '이전 프로필');
        self::assertPositiveId($newProfileId, '새 프로필');
        if ($oldProfileId === $newProfileId) {
            return false;
        }

        $actorValue = $actorEmployeeId === null ? 'NULL' : (string) $actorEmployeeId;
        $changedAt = gmdate('Y-m-d H:i:s');
        $inserted = $this->database->execute(
            'INSERT INTO `' . $this->auditTable() . '`'
            . ' (`id_shop`, `actor_employee_id`, `target_employee_id`, `old_profile_id`, `new_profile_id`, `changed_at_utc`) VALUES ('
            . $shopId . ', ' . $actorValue . ', ' . $targetEmployeeId . ', ' . $oldProfileId . ', ' . $newProfileId
            . ", '" . $changedAt . "')"
        );
        if (!$inserted) {
            throw new RuntimeException('관리자 프로필 변경 이력을 저장하지 못했습니다.');
        }

        return true;
    }

    /** @return array{rows:list<array{id_event:int,actor_employee_id:?int,target_employee_id:int,old_profile_id:int,new_profile_id:int,changed_at_utc:string}>,has_next:bool} */
    public function pageForShop(int $shopId, int $page): array
    {
        self::assertPositiveId($shopId, '쇼핑몰');
        if ($page < 1 || $page > intdiv(PHP_INT_MAX, 50)) {
            throw new InvalidArgumentException('이력 페이지가 올바르지 않습니다.');
        }
        $offset = ($page - 1) * 50;
        $rows = $this->rows(
            'SELECT `id_event`, `actor_employee_id`, `target_employee_id`, `old_profile_id`, `new_profile_id`, `changed_at_utc`'
            . ' FROM `' . $this->auditTable() . '` WHERE (`id_shop` = ' . $shopId . ' OR `id_shop` = 0)'
            . ' ORDER BY `id_event` DESC LIMIT 51 OFFSET ' . $offset,
            '관리자 프로필 변경 이력을 불러오지 못했습니다.'
        );
        $hasNext = count($rows) > 50;
        if ($hasNext) {
            array_pop($rows);
        }

        return [
            'rows' => array_map(static fn (array $row): array => [
                'id_event' => (int) ($row['id_event'] ?? 0),
                'actor_employee_id' => isset($row['actor_employee_id']) ? (int) $row['actor_employee_id'] : null,
                'target_employee_id' => (int) ($row['target_employee_id'] ?? 0),
                'old_profile_id' => (int) ($row['old_profile_id'] ?? 0),
                'new_profile_id' => (int) ($row['new_profile_id'] ?? 0),
                'changed_at_utc' => (string) ($row['changed_at_utc'] ?? ''),
            ], $rows),
            'has_next' => $hasNext,
        ];
    }

    /** @return list<array<string, mixed>> */
    private function rows(string $sql, string $failureMessage): array
    {
        $rows = $this->database->executeS($sql, true, false);
        if (!is_array($rows)) {
            throw new RuntimeException($failureMessage);
        }

        return $rows;
    }

    private function auditTable(): string
    {
        return $this->prefix . 'kuraneabackoffice_employee_profile_audit';
    }

    private static function assertPositiveId(int $id, string $label): void
    {
        if ($id < 1) {
            throw new InvalidArgumentException($label . ' ID가 올바르지 않습니다.');
        }
    }
}
