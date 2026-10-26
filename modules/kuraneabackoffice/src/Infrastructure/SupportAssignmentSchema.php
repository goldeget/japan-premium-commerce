<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Infrastructure;

use InvalidArgumentException;

final class SupportAssignmentSchema
{
    public static function currentTableSql(string $prefix): string
    {
        self::assertPrefix($prefix);
        $table = '`' . $prefix . 'kuraneabackoffice_support_assignment`';

        return "CREATE TABLE IF NOT EXISTS {$table} (
            `id_shop` INT UNSIGNED NOT NULL,
            `id_customer_thread` INT UNSIGNED NOT NULL,
            `id_employee` INT UNSIGNED NOT NULL,
            `assigned_by_employee_id` INT UNSIGNED NOT NULL,
            `assigned_at_utc` DATETIME NOT NULL,
            `updated_by_employee_id` INT UNSIGNED NOT NULL,
            `updated_at_utc` DATETIME NOT NULL,
            PRIMARY KEY (`id_shop`, `id_customer_thread`),
            KEY `shop_employee` (`id_shop`, `id_employee`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    }

    public static function historyTableSql(string $prefix): string
    {
        self::assertPrefix($prefix);
        $table = '`' . $prefix . 'kuraneabackoffice_support_assignment_history`';

        return "CREATE TABLE IF NOT EXISTS {$table} (
            `id_event` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `id_shop` INT UNSIGNED NOT NULL,
            `id_customer_thread` INT UNSIGNED NOT NULL,
            `from_employee_id` INT UNSIGNED DEFAULT NULL,
            `to_employee_id` INT UNSIGNED NOT NULL,
            `actor_employee_id` INT UNSIGNED NOT NULL,
            `changed_at_utc` DATETIME NOT NULL,
            PRIMARY KEY (`id_event`),
            KEY `shop_thread_history` (`id_shop`, `id_customer_thread`, `id_event`),
            KEY `shop_actor_time` (`id_shop`, `actor_employee_id`, `changed_at_utc`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    }

    private static function assertPrefix(string $prefix): void
    {
        if (preg_match('/\A[A-Za-z0-9_]*\z/D', $prefix) !== 1) {
            throw new InvalidArgumentException('Invalid PrestaShop table prefix.');
        }
    }
}
