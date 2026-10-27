<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use RuntimeException;

/** Schema for indexed, transactional catalog queue storage. Uninstall intentionally retains these tables. */
final class CatalogDatabaseTables
{
    private readonly string $prefix;

    public function __construct(private readonly object $database, ?string $prefix = null)
    {
        $prefix ??= defined('_DB_PREFIX_') ? (string) constant('_DB_PREFIX_') : '';
        if (preg_match('/\A[A-Za-z0-9_]*\z/D', $prefix) !== 1) {
            throw new RuntimeException('Catalog database storage is unavailable.');
        }
        $this->prefix = $prefix;
    }

    public function batches(): string
    {
        return '`' . $this->prefix . 'kuraneacatalog_batch`';
    }

    public function reviews(): string
    {
        return '`' . $this->prefix . 'kuraneacatalog_review`';
    }

    public function migrations(): string
    {
        return '`' . $this->prefix . 'kuraneacatalog_migration`';
    }

    public function install(): void
    {
        $tail = ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci';
        $statements = [
            'CREATE TABLE IF NOT EXISTS ' . $this->batches() . ' (
                id_shop INT UNSIGNED NOT NULL,
                id_batch CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                created_at DATETIME NOT NULL,
                payload_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                payload LONGTEXT NOT NULL,
                PRIMARY KEY (id_shop, id_batch),
                KEY idx_catalog_batch_recent (id_shop, created_at, id_batch)
            )' . $tail,
            'CREATE TABLE IF NOT EXISTS ' . $this->reviews() . ' (
                id_shop INT UNSIGNED NOT NULL,
                idempotency_key VARCHAR(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
                source_identity_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                provider VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                status VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                content_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                queued_at DATETIME NOT NULL,
                decision_at DATETIME NULL,
                native_product_id INT UNSIGNED NULL,
                linked_product_id INT UNSIGNED NULL,
                payload_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                payload LONGTEXT NOT NULL,
                PRIMARY KEY (id_shop, idempotency_key),
                UNIQUE KEY uq_catalog_source (id_shop, source_identity_hash),
                KEY idx_catalog_review_pending (id_shop, status, queued_at, idempotency_key),
                KEY idx_catalog_review_recent (id_shop, status, decision_at, idempotency_key),
                KEY idx_catalog_review_product (id_shop, native_product_id),
                KEY idx_catalog_review_linked_product (id_shop, linked_product_id)
            )' . $tail,
            'CREATE TABLE IF NOT EXISTS ' . $this->migrations() . ' (
                id_shop INT UNSIGNED NOT NULL,
                store_name VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
                imported_rows INT UNSIGNED NOT NULL,
                state VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
                verified_at DATETIME NULL,
                PRIMARY KEY (id_shop, store_name)
            )' . $tail,
        ];

        foreach ($statements as $sql) {
            if (!$this->database->execute($sql)) {
                throw new RuntimeException('Catalog database schema could not be installed.');
            }
        }
    }

    public function isInstalled(): bool
    {
        $rows = $this->database->executeS('SHOW TABLES');
        if (!is_array($rows)) {
            return false;
        }
        $present = [];
        foreach ($rows as $row) {
            if (is_array($row)) {
                foreach ($row as $name) {
                    if (is_string($name)) {
                        $present[$name] = true;
                    }
                }
            }
        }

        foreach ([$this->batches(), $this->reviews(), $this->migrations()] as $table) {
            if (!isset($present[trim($table, '`')])) {
                return false;
            }
        }

        return true;
    }
}
