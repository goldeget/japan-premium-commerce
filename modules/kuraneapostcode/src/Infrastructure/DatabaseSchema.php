<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Infrastructure;

use InvalidArgumentException;

final class DatabaseSchema
{
    public static function createAddressTableSql(string $prefix): string
    {
        if (preg_match('/^[A-Za-z0-9_]*$/D', $prefix) !== 1) {
            throw new InvalidArgumentException('Invalid PrestaShop table prefix.');
        }

        $table = '`' . $prefix . 'kuraneapostcode_address`';

        return "CREATE TABLE IF NOT EXISTS {$table} (
            `candidate_id` CHAR(64) NOT NULL,
            `postcode` CHAR(8) NOT NULL,
            `jis_code` CHAR(5) NOT NULL,
            `prefecture` VARCHAR(32) NOT NULL,
            `municipality` VARCHAR(128) NOT NULL,
            `town` VARCHAR(512) NOT NULL DEFAULT '',
            PRIMARY KEY (`candidate_id`),
            KEY `postcode` (`postcode`),
            KEY `jis_code` (`jis_code`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    }

    public static function createStageTableSql(string $prefix): string
    {
        if (preg_match('/^[A-Za-z0-9_]*$/D', $prefix) !== 1) {
            throw new InvalidArgumentException('Invalid PrestaShop table prefix.');
        }

        return 'CREATE TABLE IF NOT EXISTS `' . $prefix . 'kuraneapostcode_stage` LIKE `'
            . $prefix . 'kuraneapostcode_address`';
    }
}
