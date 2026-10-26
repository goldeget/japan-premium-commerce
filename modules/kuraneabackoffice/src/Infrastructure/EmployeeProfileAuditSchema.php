<?php

declare(strict_types=1);

namespace Kuranea\Backoffice\Infrastructure;

use InvalidArgumentException;

final class EmployeeProfileAuditSchema
{
    public static function tableSql(string $prefix): string
    {
        if (preg_match('/\A[A-Za-z0-9_]*\z/D', $prefix) !== 1) {
            throw new InvalidArgumentException('Invalid PrestaShop table prefix.');
        }

        $table = '`' . $prefix . 'kuraneabackoffice_employee_profile_audit`';

        return "CREATE TABLE IF NOT EXISTS {$table} (
            `id_event` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            `id_shop` INT UNSIGNED NOT NULL,
            `actor_employee_id` INT UNSIGNED DEFAULT NULL,
            `target_employee_id` INT UNSIGNED NOT NULL,
            `old_profile_id` INT UNSIGNED NOT NULL,
            `new_profile_id` INT UNSIGNED NOT NULL,
            `changed_at_utc` DATETIME NOT NULL,
            PRIMARY KEY (`id_event`),
            KEY `shop_event` (`id_shop`, `id_event`),
            KEY `shop_target_event` (`id_shop`, `target_employee_id`, `id_event`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    }
}
