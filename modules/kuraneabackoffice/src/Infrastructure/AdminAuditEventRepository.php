<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Infrastructure;

use InvalidArgumentException;
use RuntimeException;

/** Read-only, shop-scoped feed over existing administrator event stores. */
final class AdminAuditEventRepository
{
    public const PAGE_SIZE = 50;

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
        if (preg_match('/\A[A-Za-z0-9_]*\z/D', $this->prefix) !== 1) {
            throw new InvalidArgumentException('PrestaShop table prefix is invalid.');
        }
    }

    /**
     * Only sources authorized by the caller may enter the query. The controller
     * evaluates each native Back Office tab permission independently.
     *
     * @param list<string> $authorizedSources
     * @return array{rows:list<array{source:string,event_id:int,event_at:string,time_basis:string,actor_employee_id:?int,action:string,target_type:string,target_id:int}>,has_next:bool}
     */
    public function pageForShop(int $shopId, int $page, array $authorizedSources): array
    {
        self::assertPositiveId($shopId, '쇼핑몰');
        if ($page < 1 || $page > intdiv(PHP_INT_MAX, self::PAGE_SIZE)) {
            throw new InvalidArgumentException('감사 기록 페이지가 올바르지 않습니다.');
        }

        $allowed = [
            'employee_profile',
            'order_history',
            'support_assignment',
            'bank_transfer_instruction',
            'bank_transfer_receipt',
        ];
        foreach ($authorizedSources as $source) {
            if (!is_string($source) || !in_array($source, $allowed, true)) {
                throw new InvalidArgumentException('감사 기록 출처가 올바르지 않습니다.');
            }
        }
        $sources = array_values(array_unique($authorizedSources));
        if ($sources === []) {
            return ['rows' => [], 'has_next' => false];
        }

        $shop = (int) $shopId;
        $selects = [];
        foreach ($sources as $source) {
            $selects[] = $this->selectForSource($source, $shop);
        }
        $offset = ($page - 1) * self::PAGE_SIZE;
        $rows = $this->database->executeS(
            'SELECT `event_source`, `event_id`, `event_at`, `time_basis`, `actor_employee_id`, `action_key`, `target_type`, `target_id`'
            . ' FROM (' . implode(' UNION ALL ', $selects) . ') `audit_feed`'
            . ' ORDER BY `event_at` DESC, `event_source` ASC, `event_id` DESC'
            . ' LIMIT ' . (self::PAGE_SIZE + 1) . ' OFFSET ' . $offset,
            true,
            false
        );
        if (!is_array($rows)) {
            throw new RuntimeException('관리자 활동 기록을 불러오지 못했습니다.');
        }

        $hasNext = count($rows) > self::PAGE_SIZE;
        if ($hasNext) {
            array_pop($rows);
        }

        $safeRows = [];
        foreach ($rows as $row) {
            $source = (string) ($row['event_source'] ?? '');
            $action = (string) ($row['action_key'] ?? '');
            $targetType = (string) ($row['target_type'] ?? '');
            $eventId = (int) ($row['event_id'] ?? 0);
            $targetId = (int) ($row['target_id'] ?? 0);
            if (!in_array($source, $sources, true) || !self::isEventForSource($source, $action, $targetType)
                || $eventId < 1 || $targetId < 1) {
                continue;
            }
            $timeBasis = (string) ($row['time_basis'] ?? '');
            if (!in_array($timeBasis, ['UTC', 'stored'], true)) {
                continue;
            }
            $eventAt = (string) ($row['event_at'] ?? '');
            if ($eventAt === '') {
                continue;
            }
            $rawActor = $row['actor_employee_id'] ?? null;
            $actorId = $rawActor === null ? null : (int) $rawActor;
            if ($actorId !== null && $actorId < 1) {
                $actorId = null;
            }

            // Copy only allowlisted audit fields; raw table columns never reach the view.
            $safeRows[] = [
                'source' => $source,
                'event_id' => $eventId,
                'event_at' => $eventAt,
                'time_basis' => $timeBasis,
                'actor_employee_id' => $actorId,
                'action' => $action,
                'target_type' => $targetType,
                'target_id' => $targetId,
            ];
        }

        return ['rows' => $safeRows, 'has_next' => $hasNext];
    }

    private function selectForSource(string $source, int $shopId): string
    {
        $prefix = $this->prefix;
        return match ($source) {
            'employee_profile' =>
                "SELECT 'employee_profile' AS `event_source`, `id_event` AS `event_id`, `changed_at_utc` AS `event_at`, 'UTC' AS `time_basis`, `actor_employee_id`, 'employee_profile_changed' AS `action_key`, 'employee' AS `target_type`, `target_employee_id` AS `target_id`"
                . ' FROM `' . $prefix . 'kuraneabackoffice_employee_profile_audit`'
                . ' WHERE (`id_shop` = ' . $shopId . ' OR `id_shop` = 0)',
            'order_history' =>
                "SELECT 'order_history' AS `event_source`, oh.`id_order_history` AS `event_id`, oh.`date_add` AS `event_at`, 'stored' AS `time_basis`, oh.`id_employee` AS `actor_employee_id`, 'order_status_changed' AS `action_key`, 'order' AS `target_type`, oh.`id_order` AS `target_id`"
                . ' FROM `' . $prefix . 'order_history` oh'
                . ' INNER JOIN `' . $prefix . 'orders` o ON o.`id_order` = oh.`id_order`'
                . ' WHERE o.`id_shop` = ' . $shopId,
            'support_assignment' =>
                "SELECT 'support_assignment' AS `event_source`, `id_event` AS `event_id`, `changed_at_utc` AS `event_at`, 'UTC' AS `time_basis`, `actor_employee_id`, CASE WHEN `from_employee_id` IS NULL THEN 'support_assigned' ELSE 'support_reassigned' END AS `action_key`, 'support_thread' AS `target_type`, `id_customer_thread` AS `target_id`"
                . ' FROM `' . $prefix . 'kuraneabackoffice_support_assignment_history`'
                . ' WHERE `id_shop` = ' . $shopId,
            'bank_transfer_instruction' =>
                "SELECT 'bank_transfer_instruction' AS `event_source`, `id_order` AS `event_id`, `issued_at_utc` AS `event_at`, 'UTC' AS `time_basis`, `issued_by_employee_id` AS `actor_employee_id`, 'bank_transfer_instruction_issued' AS `action_key`, 'order' AS `target_type`, `id_order` AS `target_id`"
                . ' FROM `' . $prefix . 'kuraneabusinessprofile_bank_transfer_instruction`'
                . ' WHERE `id_shop` = ' . $shopId,
            'bank_transfer_receipt' =>
                "SELECT 'bank_transfer_receipt' AS `event_source`, `id_receipt` AS `event_id`, `confirmed_at_utc` AS `event_at`, 'UTC' AS `time_basis`, `confirmed_by_employee_id` AS `actor_employee_id`, 'bank_transfer_receipt_confirmed' AS `action_key`, 'order' AS `target_type`, `id_order` AS `target_id`"
                . ' FROM `' . $prefix . 'kuraneabusinessprofile_bank_transfer_receipt`'
                . ' WHERE `id_shop` = ' . $shopId,
            default => throw new InvalidArgumentException('감사 기록 출처가 올바르지 않습니다.'),
        };
    }

    private static function isEventForSource(string $source, string $action, string $targetType): bool
    {
        return match ($source) {
            'employee_profile' => $action === 'employee_profile_changed' && $targetType === 'employee',
            'order_history' => $action === 'order_status_changed' && $targetType === 'order',
            'support_assignment' => in_array($action, ['support_assigned', 'support_reassigned'], true)
                && $targetType === 'support_thread',
            'bank_transfer_instruction' => $action === 'bank_transfer_instruction_issued' && $targetType === 'order',
            'bank_transfer_receipt' => $action === 'bank_transfer_receipt_confirmed' && $targetType === 'order',
            default => false,
        };
    }

    private static function assertPositiveId(int $id, string $label): void
    {
        if ($id < 1) {
            throw new InvalidArgumentException($label . ' ID가 올바르지 않습니다.');
        }
    }
}
