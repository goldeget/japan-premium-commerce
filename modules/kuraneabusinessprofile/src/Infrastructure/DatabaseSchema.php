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

    public static function createBankTransferInstructionTableSql(string $prefix): string
    {
        self::assertPrefix($prefix);
        $table = '`' . $prefix . 'kuraneabusinessprofile_bank_transfer_instruction`';

        return "CREATE TABLE IF NOT EXISTS {$table} (
            `id_order` INT UNSIGNED NOT NULL,
            `id_shop` INT UNSIGNED NOT NULL,
            `order_reference` VARCHAR(64) NOT NULL,
            `total_paid` DECIMAL(20,6) NOT NULL,
            `currency_iso` CHAR(3) NOT NULL,
            `profile_version_id` INT UNSIGNED NOT NULL,
            `bank_account_id` CHAR(32) NOT NULL,
            `issued_by_employee_id` INT UNSIGNED NOT NULL,
            `issued_at_utc` DATETIME NOT NULL,
            PRIMARY KEY (`id_order`),
            UNIQUE KEY `order_shop` (`id_order`, `id_shop`),
            KEY `shop_issued` (`id_shop`, `issued_at_utc`),
            KEY `profile_version` (`profile_version_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    }

    /** Dedicated immutable success ledger for the separate receipt-confirmation flow. */
    public static function createBankTransferReceiptLedgerTableSql(string $prefix): string
    {
        self::assertPrefix($prefix);
        $table = '`' . $prefix . 'kuraneabusinessprofile_bank_transfer_receipt`';

        return "CREATE TABLE IF NOT EXISTS {$table} (
            `id_receipt` INT UNSIGNED NOT NULL AUTO_INCREMENT,
            `id_order` INT UNSIGNED NOT NULL,
            `id_shop` INT UNSIGNED NOT NULL,
            `order_reference` VARCHAR(64) NOT NULL,
            `bank_account_id` CHAR(32) NOT NULL,
            `received_amount` DECIMAL(20,6) NOT NULL,
            `currency_iso` CHAR(3) NOT NULL,
            `receipt_reference_sha256` CHAR(64) NOT NULL,
            `confirmed_by_employee_id` INT UNSIGNED NOT NULL,
            `confirmed_at_utc` DATETIME NOT NULL,
            `id_order_payment` INT UNSIGNED NOT NULL,
            `id_order_history` INT UNSIGNED NOT NULL,
            `is_synthetic` TINYINT(1) UNSIGNED NOT NULL DEFAULT 0,
            PRIMARY KEY (`id_receipt`),
            UNIQUE KEY `one_confirmation_per_order` (`id_order`),
            UNIQUE KEY `one_use_per_bank_reference` (`id_shop`, `bank_account_id`, `receipt_reference_sha256`),
            KEY `shop_confirmed` (`id_shop`, `confirmed_at_utc`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";
    }

    private static function assertPrefix(string $prefix): void
    {
        if (preg_match('/\A[A-Za-z0-9_]*\z/D', $prefix) !== 1) {
            throw new InvalidArgumentException('Invalid PrestaShop table prefix.');
        }
    }
}
