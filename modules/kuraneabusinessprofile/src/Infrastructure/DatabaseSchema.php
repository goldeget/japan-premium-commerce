<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Infrastructure;

use InvalidArgumentException;

final class DatabaseSchema
{
    public static function createVersionTableSql(string $prefix): string
    {
        self::assertPrefix($prefix);
        $table = '`' . $prefix . 'kuraneabusinessprofile_version`';

        return "CREATE TABLE IF NOT EXISTS {$table} (
            `id_version` INT UNSIGNED NOT NULL AUTO_INCREMENT,
            `id_shop` INT UNSIGNED NOT NULL,
            `parent_version_id` INT UNSIGNED DEFAULT NULL,
            `profile_json` LONGTEXT NOT NULL,
            `id_employee` INT UNSIGNED NOT NULL,
            `created_at` DATETIME NOT NULL,
            PRIMARY KEY (`id_version`),
            KEY `shop_created` (`id_shop`, `created_at`),
            KEY `parent_version` (`parent_version_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    }

    public static function createStateTableSql(string $prefix): string
    {
        self::assertPrefix($prefix);
        $table = '`' . $prefix . 'kuraneabusinessprofile_state`';

        return "CREATE TABLE IF NOT EXISTS {$table} (
            `id_shop` INT UNSIGNED NOT NULL,
            `draft_version_id` INT UNSIGNED DEFAULT NULL,
            `published_version_id` INT UNSIGNED DEFAULT NULL,
            `published_by` INT UNSIGNED DEFAULT NULL,
            `published_at` DATETIME DEFAULT NULL,
            `updated_at` DATETIME NOT NULL,
            PRIMARY KEY (`id_shop`),
            KEY `draft_version` (`draft_version_id`),
            KEY `published_version` (`published_version_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    }

    private static function assertPrefix(string $prefix): void
    {
        if (preg_match('/\A[A-Za-z0-9_]*\z/D', $prefix) !== 1) {
            throw new InvalidArgumentException('Invalid PrestaShop table prefix.');
        }
    }
}
