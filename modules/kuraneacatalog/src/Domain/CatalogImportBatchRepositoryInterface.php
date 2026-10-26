<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;

interface CatalogImportBatchRepositoryInterface
{
    public const MAX_RECENT_LIMIT = 50;

    /** @param list<string> $urls */
    public function create(array $urls, ?DateTimeImmutable $createdAt = null): CatalogImportBatch;

    public function find(string $batchId): ?CatalogImportBatch;

    /** @return list<CatalogImportBatch> */
    public function recent(int $limit = 20): array;

    /** Advance exactly one queued entry to processing and issue its attempt generation. */
    public function markProcessing(
        string $batchId,
        string $itemId,
        ?DateTimeImmutable $startedAt = null
    ): CatalogImportBatch;

    /** Requeue expired leases and close attempts that have exhausted the retry limit. */
    public function recoverStaleProcessing(
        string $batchId,
        ?DateTimeImmutable $now = null
    ): CatalogImportBatch;

    /** Store a query-free snapshot only for the currently claimed attempt generation. */
    public function markSucceeded(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        NormalizedProductSnapshot $snapshot
    ): CatalogImportBatch;

    /** Verify the active attempt under the batch lock, commit its review snapshot, then mark it succeeded. */
    public function completeWithReviewSnapshot(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        NormalizedProductSnapshot $snapshot,
        callable $commitReviewSnapshot
    ): CatalogImportBatch;

    /** Store one fixed failure category only for the current attempt, never a raw exception or error string. */
    public function markFailed(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        string $failureCategory
    ): CatalogImportBatch;

    /** Requeue failed entries only, preserving all other entry states. */
    public function retryFailedItems(string $batchId): CatalogImportBatch;
}
