<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use Kuranea\Catalog\Domain\CatalogImportBatch;
use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use RuntimeException;
use Throwable;

/** Idempotently imports v1 JSON stores while retaining the source files for rollback and comparison. */
final class CatalogDatabaseLegacyImporter
{
    private const MAX_LEGACY_BYTES = 33554432;
    private const VERIFY_CHUNK = 100;

    public function __construct(private readonly CatalogDatabaseContext $context)
    {
    }

    public function import(): void
    {
        $batchDocument = $this->readDocument('catalog-import-batches.json', 'batches');
        $reviewDocument = $this->readDocument('review-queue.json', 'entries');
        $hasRows = $batchDocument['rows'] !== [] || $reviewDocument['rows'] !== [];
        $shopIds = $this->shopIds();
        if ($hasRows && count($shopIds) !== 1) {
            throw new RuntimeException('Legacy catalog data has no shop identity and cannot be migrated into a multishop database.');
        }

        foreach ($shopIds as $shopId) {
            $target = $shopId === $this->context->shopId
                ? $this
                : new self(new CatalogDatabaseContext(
                    $this->context->database,
                    $this->context->tables,
                    $this->context->privateDirectory,
                    $this->context->shopRoot,
                    $shopId
                ));
            $target->importStore('batches', $batchDocument, function (array $row) use ($target): void {
                $target->insertBatch($row);
            });
            $target->importStore('reviews', $reviewDocument, function (array $row) use ($target): void {
                $target->insertReview($row);
            });
        }
    }

    /** @return list<int> */
    private function shopIds(): array
    {
        if (!class_exists('Shop') || !method_exists('Shop', 'getShops')) {
            return [$this->context->shopId];
        }
        $shops = \Shop::getShops(false);
        if (!is_array($shops) || $shops === []) {
            throw new RuntimeException('Catalog shop list could not be read for migration.');
        }
        $ids = [];
        foreach ($shops as $shop) {
            $id = is_array($shop) ? (int) ($shop['id_shop'] ?? 0) : 0;
            if ($id > 0) {
                $ids[$id] = $id;
            }
        }
        if (!isset($ids[$this->context->shopId])) {
            throw new RuntimeException('Current catalog shop is not present in the migration shop list.');
        }

        sort($ids, SORT_NUMERIC);

        return array_values($ids);
    }

    /** @return array{path: string, hash: ?string, rows: list<array<string, mixed>>} */
    private function readDocument(string $fileName, string $key): array
    {
        $path = $this->context->privateDirectory . DIRECTORY_SEPARATOR . $fileName;
        if (!file_exists($path)) {
            return ['path' => $path, 'hash' => null, 'rows' => []];
        }
        if (is_link($path) || !is_file($path)) {
            throw new RuntimeException('Legacy catalog data is not a regular file; migration stopped without changing it.');
        }

        clearstatcache(true, $path);
        $size = filesize($path);
        if (!is_int($size) || $size > self::MAX_LEGACY_BYTES) {
            throw new RuntimeException('Legacy catalog data exceeds the fixed import boundary.');
        }
        $contents = file_get_contents($path, false, null, 0, self::MAX_LEGACY_BYTES + 1);
        if (!is_string($contents) || strlen($contents) > self::MAX_LEGACY_BYTES) {
            throw new RuntimeException('Legacy catalog data could not be read safely.');
        }

        try {
            $document = json_decode($contents, true, 512, JSON_THROW_ON_ERROR);
        } catch (\Throwable $exception) {
            throw new RuntimeException('Legacy catalog data is invalid; source files were retained.', 0, $exception);
        }
        if (!is_array($document) || array_diff(array_keys($document), ['schemaVersion', $key]) !== []
            || array_diff(['schemaVersion', $key], array_keys($document)) !== []
            || ($document['schemaVersion'] ?? null) !== 1 || !is_array($document[$key] ?? null)
            || ($document[$key] !== [] && array_is_list($document[$key]))) {
            throw new RuntimeException('Legacy catalog schema is unsupported; source files were retained.');
        }

        $rows = [];
        foreach ($document[$key] as $identity => $data) {
            if (!is_string($identity) || !is_array($data)) {
                throw new RuntimeException('Legacy catalog entry is invalid; source files were retained.');
            }
            try {
                if ($key === 'batches') {
                    $model = CatalogImportBatch::fromArray($data);
                    if (!hash_equals($model->id, $identity)) {
                        throw new RuntimeException('Legacy batch identity does not match its stored key.');
                    }
                    $payload = CatalogDatabaseSql::encode($model->toArray());
                    $rows[] = [
                        'key' => $model->id,
                        'created_at' => CatalogDatabaseSql::timestamp($model->createdAt),
                        'hash' => hash('sha256', $payload),
                        'payload' => $payload,
                    ];
                } else {
                    $model = ProductReviewQueueEntry::fromArray($data);
                    if (!hash_equals($model->idempotencyKey, $identity)) {
                        throw new RuntimeException('Legacy review identity does not match its stored key.');
                    }
                    $rows[] = CatalogDatabaseRowMapper::review($model);
                }
            } catch (Throwable $exception) {
                throw new RuntimeException('Legacy catalog entry failed validation; source files were retained.', 0, $exception);
            }
        }

        return ['path' => $path, 'hash' => hash('sha256', $contents), 'rows' => $rows];
    }

    /** @param array{path: string, hash: ?string, rows: list<array<string, mixed>>} $source */
    private function importStore(string $storeName, array $source, callable $insert): void
    {
        $existing = $this->context->database->getRow(
            'SELECT source_sha256, state FROM ' . $this->context->tables->migrations()
            . ' WHERE id_shop = ' . $this->context->shopId
            . ' AND store_name = ' . CatalogDatabaseSql::quote($storeName)
        );
        if (is_array($existing) && ($existing['state'] ?? '') === 'verified'
            && ($existing['source_sha256'] ?? null) === $source['hash']) {
            return;
        }

        $this->setState($storeName, $source['hash'], count($source['rows']), 'importing', null);
        foreach (array_chunk($source['rows'], self::VERIFY_CHUNK) as $chunk) {
            CatalogDatabaseTransaction::run($this->context->database, static function () use ($chunk, $insert): void {
                foreach ($chunk as $row) {
                    $insert($row);
                }
            });
        }

        foreach (array_chunk($source['rows'], self::VERIFY_CHUNK) as $chunk) {
            $keys = array_map(static fn (array $row): string => CatalogDatabaseSql::quote((string) $row['key']), $chunk);
            if ($keys === []) {
                continue;
            }
            $column = $storeName === 'batches' ? 'id_batch' : 'idempotency_key';
            $table = $storeName === 'batches' ? $this->context->tables->batches() : $this->context->tables->reviews();
            $rows = $this->context->database->executeS(
                'SELECT ' . $column . ' AS record_key, payload_sha256 FROM ' . $table
                . ' WHERE id_shop = ' . $this->context->shopId
                . ' AND ' . $column . ' IN (' . implode(',', $keys) . ')'
            );
            if (!is_array($rows)) {
                throw new RuntimeException('Legacy catalog verification query failed; source files were retained.');
            }
            $actual = [];
            foreach ($rows as $row) {
                if (isset($row['record_key'], $row['payload_sha256'])) {
                    $actual[(string) $row['record_key']] = (string) $row['payload_sha256'];
                }
            }
            foreach ($chunk as $sourceRow) {
                if (!hash_equals((string) $sourceRow['hash'], $actual[(string) $sourceRow['key']] ?? '')) {
                    throw new RuntimeException('Legacy catalog migration could not verify every imported row; source files were retained.');
                }
            }
        }

        $this->setState($storeName, $source['hash'], count($source['rows']), 'verified', gmdate('Y-m-d H:i:s'));
    }

    /** @param array<string, mixed> $row */
    private function insertBatch(array $row): void
    {
        $sql = 'INSERT IGNORE INTO ' . $this->context->tables->batches()
            . ' (id_shop, id_batch, created_at, payload_sha256, payload) VALUES ('
            . $this->context->shopId . ', '
            . CatalogDatabaseSql::quote((string) $row['key']) . ', '
            . CatalogDatabaseSql::quote((string) $row['created_at']) . ', '
            . CatalogDatabaseSql::quote((string) $row['hash']) . ', '
            . CatalogDatabaseSql::quote((string) $row['payload']) . ')';
        if (!$this->context->database->execute($sql)) {
            throw new RuntimeException('Legacy catalog batch import failed; source files were retained.');
        }
    }

    /** @param array<string, mixed> $row */
    private function insertReview(array $row): void
    {
        $sql = 'INSERT IGNORE INTO ' . $this->context->tables->reviews()
            . ' (id_shop, idempotency_key, source_identity_hash, provider, status, content_hash, queued_at, decision_at, native_product_id, linked_product_id, payload_sha256, payload) VALUES ('
            . $this->context->shopId . ', '
            . CatalogDatabaseSql::quote((string) $row['key']) . ', '
            . CatalogDatabaseSql::quote((string) $row['source_identity_hash']) . ', '
            . CatalogDatabaseSql::quote((string) $row['provider']) . ', '
            . CatalogDatabaseSql::quote((string) $row['status']) . ', '
            . CatalogDatabaseSql::quote((string) $row['content_hash']) . ', '
            . CatalogDatabaseSql::quote((string) $row['queued_at']) . ', '
            . ($row['decision_at'] === null ? 'NULL' : CatalogDatabaseSql::quote((string) $row['decision_at'])) . ', '
            . ($row['native_product_id'] === null ? 'NULL' : (int) $row['native_product_id']) . ', '
            . ($row['linked_product_id'] === null ? 'NULL' : (int) $row['linked_product_id']) . ', '
            . CatalogDatabaseSql::quote((string) $row['hash']) . ', '
            . CatalogDatabaseSql::quote((string) $row['payload']) . ')';
        if (!$this->context->database->execute($sql)) {
            throw new RuntimeException('Legacy catalog review import failed; source files were retained.');
        }
    }

    private function setState(string $store, ?string $hash, int $count, string $state, ?string $verifiedAt): void
    {
        $sql = 'INSERT INTO ' . $this->context->tables->migrations()
            . ' (id_shop, store_name, source_sha256, imported_rows, state, verified_at) VALUES ('
            . $this->context->shopId . ', '
            . CatalogDatabaseSql::quote($store) . ', '
            . ($hash === null ? 'NULL' : CatalogDatabaseSql::quote($hash)) . ', '
            . max(0, $count) . ', ' . CatalogDatabaseSql::quote($state) . ', '
            . ($verifiedAt === null ? 'NULL' : CatalogDatabaseSql::quote($verifiedAt))
            . ') ON DUPLICATE KEY UPDATE source_sha256 = VALUES(source_sha256), imported_rows = VALUES(imported_rows), state = VALUES(state), verified_at = VALUES(verified_at)';
        if (!$this->context->database->execute($sql)) {
            throw new RuntimeException('Catalog migration status could not be stored.');
        }
    }

}
