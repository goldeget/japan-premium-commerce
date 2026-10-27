<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use DateTimeImmutable;
use DateTimeZone;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;
use Kuranea\Catalog\Domain\ProductImageRightsEvidence;
use Kuranea\Catalog\Domain\ProductImportReviewEvidence;
use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Domain\ProductReviewQueueRepositoryInterface;
use RuntimeException;
use Throwable;

/** Indexed, shop-scoped review store with atomic state transitions and bounded pages. */
final class DatabaseProductReviewQueueRepository implements ProductReviewQueueRepositoryInterface
{
    public function __construct(
        private readonly object $database,
        private readonly string $table,
        private readonly int $shopId
    ) {
        if ($shopId < 1 || preg_match('/\A`?[A-Za-z0-9_]+`?\z/D', $table) !== 1) {
            throw new RuntimeException('Catalog review storage is unavailable.');
        }
    }

    public function enqueue(NormalizedProductSnapshot $snapshot, ?DateTimeImmutable $queuedAt = null): ProductReviewQueueEntry
    {
        return CatalogDatabaseTransaction::run($this->database, function () use ($snapshot, $queuedAt): ProductReviewQueueEntry {
            $existing = $this->findForUpdate($snapshot->deduplicationKey);
            $entry = $this->entryForSnapshot($snapshot, $queuedAt, $existing);
            if ($entry === null) {
                return $existing ?? throw new RuntimeException('Catalog review source identity could not be stored.');
            }

            if ($existing === null) {
                $racedEntry = $this->insertIfAbsent($entry);
                if ($racedEntry !== null) {
                    if ($snapshot->fetchedAt <= $racedEntry->snapshot->fetchedAt) {
                        return $racedEntry;
                    }
                    $entry = $this->entryForSnapshot($snapshot, $queuedAt, $racedEntry)
                        ?? $racedEntry;
                    $this->saveEntry($entry);
                }
            } else {
                $this->assertSameSource($existing, $snapshot);
                $this->saveEntry($entry);
            }

            return $entry;
        });
    }

    public function find(string $idempotencyKey): ?ProductReviewQueueEntry
    {
        if ($idempotencyKey === '' || strlen($idempotencyKey) > 512) {
            return null;
        }
        $row = $this->database->getRow(
            'SELECT payload, payload_sha256 FROM ' . $this->table
            . ' WHERE id_shop = ' . $this->shopId
            . ' AND idempotency_key = ' . CatalogDatabaseSql::quote($idempotencyKey)
        );

        return is_array($row) && is_string($row['payload'] ?? null) && is_string($row['payload_sha256'] ?? null)
            ? $this->decodeEntry($row['payload'], $idempotencyKey, $row['payload_sha256'])
            : null;
    }

    public function save(ProductReviewQueueEntry $entry): void
    {
        CatalogDatabaseTransaction::run($this->database, function () use ($entry): void {
            if ($this->findForUpdate($entry->idempotencyKey) === null) {
                throw new RuntimeException('Cannot update a catalog review entry that is not queued.');
            }
            $this->saveEntry($entry);
        });
    }

    public function linkDraftIfCurrent(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        ?ProductImageRightsEvidence $imageRightsEvidence = null,
        ?ProductImportReviewEvidence $importReviewEvidence = null
    ): ?ProductReviewQueueEntry {
        return $this->mutatePending($idempotencyKey, $expectedContentHash, static fn (ProductReviewQueueEntry $entry): ProductReviewQueueEntry => $entry->linkDraft(
            $nativeProductId,
            $imageRightsEvidence,
            $importReviewEvidence
        ));
    }

    public function containsLinkedNativeProduct(int $nativeProductId): bool
    {
        if ($nativeProductId < 1) {
            return false;
        }
        return (int) $this->database->getValue(
            'SELECT COUNT(*) FROM ' . $this->table
            . ' WHERE id_shop = ' . $this->shopId
            . ' AND (native_product_id = ' . $nativeProductId . ' OR linked_product_id = ' . $nativeProductId . ')'
        ) > 0;
    }

    public function approveIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        string $approvedBy,
        DateTimeImmutable $approvedAt,
        ?ProductImageRightsEvidence $imageRightsEvidence = null,
        ?ProductImportReviewEvidence $importReviewEvidence = null
    ): ?ProductReviewQueueEntry {
        return $this->mutatePending($idempotencyKey, $expectedContentHash, static fn (ProductReviewQueueEntry $entry): ProductReviewQueueEntry => $entry->approve(
            $nativeProductId,
            $approvedBy,
            $approvedAt,
            $imageRightsEvidence,
            $importReviewEvidence
        ));
    }

    public function rejectIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        string $rejectedBy,
        DateTimeImmutable $rejectedAt,
        string $rejectionReason
    ): ?ProductReviewQueueEntry {
        return $this->mutatePending($idempotencyKey, $expectedContentHash, static fn (ProductReviewQueueEntry $entry): ProductReviewQueueEntry => $entry->reject(
            $rejectedBy,
            $rejectedAt,
            $rejectionReason
        ));
    }

    public function pending(int $limit = 50, int $offset = 0): array
    {
        $this->assertPage($limit, $offset);
        $rows = $this->database->executeS(
            'SELECT idempotency_key, payload, payload_sha256 FROM ' . $this->table
            . ' WHERE id_shop = ' . $this->shopId
            . ' AND status = ' . CatalogDatabaseSql::quote(ProductReviewQueueEntry::STATUS_PENDING)
            . ' ORDER BY queued_at ASC, idempotency_key ASC LIMIT ' . (int) $offset . ', ' . (int) $limit
        );
        if (!is_array($rows)) {
            throw new RuntimeException('Catalog review page could not be read.');
        }
        $entries = [];
        foreach ($rows as $row) {
            if (!is_array($row) || !is_string($row['payload'] ?? null) || !is_string($row['idempotency_key'] ?? null)
                || !is_string($row['payload_sha256'] ?? null)) {
                throw new RuntimeException('Stored catalog review row is invalid.');
            }
            $entries[] = $this->decodeEntry($row['payload'], $row['idempotency_key'], $row['payload_sha256']);
        }

        return $entries;
    }

    public function countPending(): int
    {
        $count = $this->database->getValue(
            'SELECT COUNT(*) FROM ' . $this->table
            . ' WHERE id_shop = ' . $this->shopId
            . ' AND status = ' . CatalogDatabaseSql::quote(ProductReviewQueueEntry::STATUS_PENDING)
        );
        if (!is_numeric($count)) {
            throw new RuntimeException('Catalog review count could not be read.');
        }

        return (int) $count;
    }

    public function recentReviewed(int $limit = 20): array
    {
        if ($limit < 1 || $limit > ProductReviewQueueRepositoryInterface::MAX_RECENT_LIMIT) {
            throw new \InvalidArgumentException('Recent catalog review limit is outside the supported range.');
        }
        $rows = $this->database->executeS(
            'SELECT idempotency_key, payload, payload_sha256 FROM ' . $this->table
            . ' WHERE id_shop = ' . $this->shopId
            . ' AND status IN ('
            . CatalogDatabaseSql::quote(ProductReviewQueueEntry::STATUS_APPROVED) . ', '
            . CatalogDatabaseSql::quote(ProductReviewQueueEntry::STATUS_REJECTED) . ')'
            . ' ORDER BY decision_at DESC, idempotency_key DESC LIMIT ' . (int) $limit
        );
        if (!is_array($rows)) {
            throw new RuntimeException('Catalog review history could not be read.');
        }
        $entries = [];
        foreach ($rows as $row) {
            if (!is_array($row) || !is_string($row['payload'] ?? null) || !is_string($row['idempotency_key'] ?? null)
                || !is_string($row['payload_sha256'] ?? null)) {
                throw new RuntimeException('Stored catalog review row is invalid.');
            }
            $entries[] = $this->decodeEntry($row['payload'], $row['idempotency_key'], $row['payload_sha256']);
        }

        return $entries;
    }

    private function mutatePending(string $key, string $expectedHash, callable $change): ?ProductReviewQueueEntry
    {
        if ($key === '' || strlen($key) > 512 || preg_match('/\A[a-f0-9]{64}\z/D', $expectedHash) !== 1) {
            return null;
        }

        return CatalogDatabaseTransaction::run($this->database, function () use ($key, $expectedHash, $change): ?ProductReviewQueueEntry {
            $entry = $this->findForUpdate($key);
            if ($entry === null || !hash_equals($entry->snapshot->contentHash, $expectedHash)
                || $entry->status !== ProductReviewQueueEntry::STATUS_PENDING) {
                return null;
            }
            $updated = $change($entry);
            $this->saveEntry($updated);

            return $updated;
        });
    }

    private function findForUpdate(string $key): ?ProductReviewQueueEntry
    {
        if ($key === '' || strlen($key) > 512) {
            return null;
        }
        $row = $this->database->getRow(
            'SELECT payload, payload_sha256 FROM ' . $this->table
            . ' WHERE id_shop = ' . $this->shopId
            . ' AND idempotency_key = ' . CatalogDatabaseSql::quote($key) . ' FOR UPDATE'
        );

        return is_array($row) && is_string($row['payload'] ?? null) && is_string($row['payload_sha256'] ?? null)
            ? $this->decodeEntry($row['payload'], $key, $row['payload_sha256'])
            : null;
    }

    private function saveEntry(ProductReviewQueueEntry $entry): void
    {
        if ($entry->idempotencyKey === '' || strlen($entry->idempotencyKey) > 512) {
            throw new RuntimeException('Catalog review identity is invalid.');
        }
        $row = CatalogDatabaseRowMapper::review($entry);
        $existing = $this->database->getRow(
            'SELECT source_identity_hash FROM ' . $this->table
            . ' WHERE id_shop = ' . $this->shopId
            . ' AND idempotency_key = ' . CatalogDatabaseSql::quote($entry->idempotencyKey) . ' FOR UPDATE'
        );
        if (!is_array($existing)) {
            throw new RuntimeException('Cannot update a catalog review entry that is not queued.');
        }
        if (!hash_equals((string) ($existing['source_identity_hash'] ?? ''), (string) $row['source_identity_hash'])) {
            throw new RuntimeException('Catalog review identity cannot be reassigned to another source.');
        }
        $sql = 'UPDATE ' . $this->table . ' SET status = '
                . CatalogDatabaseSql::quote((string) $row['status'])
                . ', content_hash = ' . CatalogDatabaseSql::quote((string) $row['content_hash'])
                . ', queued_at = ' . CatalogDatabaseSql::quote((string) $row['queued_at'])
                . ', decision_at = ' . ($row['decision_at'] === null ? 'NULL' : CatalogDatabaseSql::quote((string) $row['decision_at']))
                . ', native_product_id = ' . ($row['native_product_id'] === null ? 'NULL' : (int) $row['native_product_id'])
                . ', linked_product_id = ' . ($row['linked_product_id'] === null ? 'NULL' : (int) $row['linked_product_id'])
                . ', payload_sha256 = ' . CatalogDatabaseSql::quote((string) $row['hash'])
                . ', payload = ' . CatalogDatabaseSql::quote((string) $row['payload'])
                . ' WHERE id_shop = ' . $this->shopId
                . ' AND idempotency_key = ' . CatalogDatabaseSql::quote($entry->idempotencyKey);
        if (!$this->database->execute($sql)) {
            throw new RuntimeException('Catalog review record could not be stored.');
        }
    }

    private function insertIfAbsent(ProductReviewQueueEntry $entry): ?ProductReviewQueueEntry
    {
        $row = CatalogDatabaseRowMapper::review($entry);
        $sql = 'INSERT IGNORE INTO ' . $this->table
            . ' (id_shop, idempotency_key, source_identity_hash, provider, status, content_hash, queued_at, decision_at, native_product_id, linked_product_id, payload_sha256, payload) VALUES ('
            . $this->shopId . ', '
            . CatalogDatabaseSql::quote((string) $row['key']) . ', '
            . CatalogDatabaseSql::quote((string) $row['source_identity_hash']) . ', '
            . CatalogDatabaseSql::quote((string) $row['provider']) . ', '
            . CatalogDatabaseSql::quote((string) $row['status']) . ', '
            . CatalogDatabaseSql::quote((string) $row['content_hash']) . ', '
            . CatalogDatabaseSql::quote((string) $row['queued_at']) . ', NULL, NULL, '
            . ($row['linked_product_id'] === null ? 'NULL' : (int) $row['linked_product_id']) . ', '
            . CatalogDatabaseSql::quote((string) $row['hash']) . ', '
            . CatalogDatabaseSql::quote((string) $row['payload']) . ')';
        if (!$this->database->execute($sql)) {
            throw new RuntimeException('Catalog review record could not be stored.');
        }

        $stored = $this->database->getRow(
            'SELECT source_identity_hash, payload_sha256, payload FROM ' . $this->table
            . ' WHERE id_shop = ' . $this->shopId
            . ' AND idempotency_key = ' . CatalogDatabaseSql::quote($entry->idempotencyKey) . ' FOR UPDATE'
        );
        if (!is_array($stored) || !is_string($stored['payload'] ?? null) || !is_string($stored['payload_sha256'] ?? null)) {
            throw new RuntimeException('Catalog review insert could not be verified.');
        }
        if (!hash_equals((string) $row['source_identity_hash'], (string) ($stored['source_identity_hash'] ?? ''))) {
            throw new RuntimeException('Catalog review identity cannot be reassigned to another source.');
        }
        $current = $this->decodeEntry($stored['payload'], $entry->idempotencyKey, $stored['payload_sha256']);

        return hash_equals((string) $row['hash'], hash('sha256', CatalogDatabaseSql::encode($current->toArray())))
            ? null
            : $current;
    }

    private function entryForSnapshot(
        NormalizedProductSnapshot $snapshot,
        ?DateTimeImmutable $queuedAt,
        ?ProductReviewQueueEntry $existing
    ): ?ProductReviewQueueEntry {
        if ($existing !== null) {
            $this->assertSameSource($existing, $snapshot);
            if ($snapshot->fetchedAt <= $existing->snapshot->fetchedAt) {
                return null;
            }
            if ($existing->snapshot->contentHash === $snapshot->contentHash) {
                return $existing->refreshSameContentSnapshot($snapshot);
            }
        }

        return new ProductReviewQueueEntry(
            $snapshot->deduplicationKey,
            ProductReviewQueueEntry::STATUS_PENDING,
            $snapshot->withApprovalStatus(ProductReviewQueueEntry::STATUS_PENDING),
            $existing?->queuedAt ?? $queuedAt ?? new DateTimeImmutable('now', new DateTimeZone('UTC')),
            previousSnapshot: $existing?->snapshot,
            linkedProductId: $existing?->nativeProductId ?? $existing?->linkedProductId,
            imageRightsEvidence: $existing?->imageRightsEvidence
        );
    }

    private function assertSameSource(ProductReviewQueueEntry $entry, NormalizedProductSnapshot $snapshot): void
    {
        if ($entry->snapshot->source !== $snapshot->source
            || $entry->snapshot->sourceProductId !== $snapshot->sourceProductId) {
            throw new RuntimeException('Catalog review identity cannot be reassigned to another source.');
        }
    }

    private function decodeEntry(string $payload, string $expectedKey, string $expectedHash): ProductReviewQueueEntry
    {
        if (preg_match('/\A[a-f0-9]{64}\z/D', $expectedHash) !== 1
            || !hash_equals($expectedHash, hash('sha256', $payload))) {
            throw new RuntimeException('Stored catalog review checksum is invalid.');
        }
        try {
            $entry = ProductReviewQueueEntry::fromArray(CatalogDatabaseSql::decode($payload));
        } catch (Throwable $exception) {
            throw new RuntimeException('Stored catalog review record is invalid.', 0, $exception);
        }
        if (!hash_equals($expectedKey, $entry->idempotencyKey)) {
            throw new RuntimeException('Stored catalog review identity is invalid.');
        }

        return $entry;
    }

    private function assertPage(int $limit, int $offset): void
    {
        if ($limit < 1 || $limit > 1000 || $offset < 0 || $offset > 100000000) {
            throw new \InvalidArgumentException('Catalog review page is outside the supported range.');
        }
    }
}
