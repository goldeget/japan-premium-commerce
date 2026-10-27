<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use DateTimeImmutable;
use Kuranea\Catalog\Domain\CatalogImportBatch;
use Kuranea\Catalog\Domain\CatalogImportBatchRepositoryInterface;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;
use RuntimeException;
use Throwable;

/** Per-batch indexed SQL storage; each state transition locks only its bounded batch row. */
final class DatabaseCatalogImportBatchRepository implements CatalogImportBatchRepositoryInterface
{
    public function __construct(
        private readonly object $database,
        private readonly string $table,
        private readonly int $shopId
    ) {
        if ($shopId < 1 || preg_match('/\A`?[A-Za-z0-9_]+`?\z/D', $table) !== 1) {
            throw new RuntimeException('Catalog batch storage is unavailable.');
        }
    }

    public function create(array $urls, ?DateTimeImmutable $createdAt = null): CatalogImportBatch
    {
        $batch = CatalogImportBatch::fromUrls($urls, $createdAt);
        $payload = CatalogDatabaseSql::encode($batch->toArray());
        $sql = 'INSERT INTO ' . $this->table
            . ' (id_shop, id_batch, created_at, payload_sha256, payload) VALUES ('
            . $this->shopId . ', ' . CatalogDatabaseSql::quote($batch->id) . ', '
            . CatalogDatabaseSql::quote(CatalogDatabaseSql::timestamp($batch->createdAt)) . ', '
            . CatalogDatabaseSql::quote(hash('sha256', $payload)) . ', '
            . CatalogDatabaseSql::quote($payload) . ')';
        if (!$this->database->execute($sql)) {
            throw new RuntimeException('Catalog import batch could not be stored.');
        }

        return $batch;
    }

    public function find(string $batchId): ?CatalogImportBatch
    {
        if (preg_match('/\A[a-f0-9]{32}\z/D', $batchId) !== 1) {
            return null;
        }
        $row = $this->database->getRow(
            'SELECT payload, payload_sha256 FROM ' . $this->table . ' WHERE id_shop = ' . $this->shopId
            . ' AND id_batch = ' . CatalogDatabaseSql::quote($batchId)
        );

        return is_array($row) && is_string($row['payload'] ?? null) && is_string($row['payload_sha256'] ?? null)
            ? $this->decodeBatch($row['payload'], $batchId, $row['payload_sha256'])
            : null;
    }

    public function recent(int $limit = 20): array
    {
        if ($limit < 1 || $limit > CatalogImportBatchRepositoryInterface::MAX_RECENT_LIMIT) {
            throw new \InvalidArgumentException('Recent catalog batch limit is outside the supported range.');
        }
        $rows = $this->database->executeS(
            'SELECT id_batch, payload, payload_sha256 FROM ' . $this->table
            . ' WHERE id_shop = ' . $this->shopId
            . ' ORDER BY created_at DESC, id_batch DESC LIMIT ' . (int) $limit
        );
        if (!is_array($rows)) {
            throw new RuntimeException('Recent catalog batches could not be read.');
        }
        $batches = [];
        foreach ($rows as $row) {
            if (!is_array($row) || !is_string($row['payload'] ?? null) || !is_string($row['id_batch'] ?? null)
                || !is_string($row['payload_sha256'] ?? null)) {
                throw new RuntimeException('Stored catalog batch is invalid.');
            }
            $batches[] = $this->decodeBatch($row['payload'], $row['id_batch'], $row['payload_sha256']);
        }

        return $batches;
    }

    public function markProcessing(string $batchId, string $itemId, ?DateTimeImmutable $startedAt = null): CatalogImportBatch
    {
        return $this->mutate($batchId, static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->markProcessing($itemId, $startedAt));
    }

    public function recoverStaleProcessing(string $batchId, ?DateTimeImmutable $now = null): CatalogImportBatch
    {
        $now ??= new DateTimeImmutable('now', new \DateTimeZone('UTC'));

        return $this->mutate($batchId, static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->recoverStaleProcessing($now));
    }

    public function markSucceeded(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        NormalizedProductSnapshot $snapshot
    ): CatalogImportBatch {
        return $this->mutate($batchId, static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->markSucceeded($itemId, $expectedAttempt, $snapshot));
    }

    public function completeWithReviewSnapshot(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        NormalizedProductSnapshot $snapshot,
        callable $commitReviewSnapshot
    ): CatalogImportBatch {
        return $this->mutate(
            $batchId,
            static function (CatalogImportBatch $batch) use (
                $itemId,
                $expectedAttempt,
                $snapshot,
                $commitReviewSnapshot
            ): CatalogImportBatch {
                $completed = $batch->markSucceeded($itemId, $expectedAttempt, $snapshot);
                $commitReviewSnapshot();

                return $completed;
            }
        );
    }

    public function markFailed(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        string $failureCategory
    ): CatalogImportBatch {
        return $this->mutate($batchId, static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->markFailed($itemId, $expectedAttempt, $failureCategory));
    }

    public function retryFailedItems(string $batchId): CatalogImportBatch
    {
        return $this->mutate($batchId, static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->retryFailedItems());
    }

    private function mutate(string $batchId, callable $change): CatalogImportBatch
    {
        if (preg_match('/\A[a-f0-9]{32}\z/D', $batchId) !== 1) {
            throw new RuntimeException('Catalog import batch was not found.');
        }

        return CatalogDatabaseTransaction::run($this->database, function () use ($batchId, $change): CatalogImportBatch {
            $row = $this->database->getRow(
                'SELECT payload, payload_sha256 FROM ' . $this->table . ' WHERE id_shop = ' . $this->shopId
                . ' AND id_batch = ' . CatalogDatabaseSql::quote($batchId) . ' FOR UPDATE'
            );
            if (!is_array($row) || !is_string($row['payload'] ?? null) || !is_string($row['payload_sha256'] ?? null)) {
                throw new RuntimeException('Catalog import batch was not found.');
            }
            $batch = $this->decodeBatch($row['payload'], $batchId, $row['payload_sha256']);
            $updated = $change($batch);
            $payload = CatalogDatabaseSql::encode($updated->toArray());
            $sql = 'UPDATE ' . $this->table . ' SET created_at = '
                . CatalogDatabaseSql::quote(CatalogDatabaseSql::timestamp($updated->createdAt))
                . ', payload_sha256 = ' . CatalogDatabaseSql::quote(hash('sha256', $payload))
                . ', payload = ' . CatalogDatabaseSql::quote($payload)
                . ' WHERE id_shop = ' . $this->shopId . ' AND id_batch = ' . CatalogDatabaseSql::quote($batchId);
            if (!$this->database->execute($sql)) {
                throw new RuntimeException('Catalog import batch update failed.');
            }

            return $updated;
        });
    }

    private function decodeBatch(string $payload, string $expectedId, string $expectedHash): CatalogImportBatch
    {
        if (preg_match('/\A[a-f0-9]{64}\z/D', $expectedHash) !== 1
            || !hash_equals($expectedHash, hash('sha256', $payload))) {
            throw new RuntimeException('Stored catalog batch checksum is invalid.');
        }
        try {
            $batch = CatalogImportBatch::fromArray(CatalogDatabaseSql::decode($payload));
        } catch (Throwable $exception) {
            throw new RuntimeException('Stored catalog batch is invalid.', 0, $exception);
        }
        if (!hash_equals($expectedId, $batch->id)) {
            throw new RuntimeException('Stored catalog batch identity is invalid.');
        }

        return $batch;
    }
}
