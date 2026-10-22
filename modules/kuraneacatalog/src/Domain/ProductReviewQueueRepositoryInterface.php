<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;

interface ProductReviewQueueRepositoryInterface
{
    public function enqueue(
        NormalizedProductSnapshot $snapshot,
        ?DateTimeImmutable $queuedAt = null
    ): ProductReviewQueueEntry;

    public function find(string $idempotencyKey): ?ProductReviewQueueEntry;

    public function save(ProductReviewQueueEntry $entry): void;

    /**
     * Approve only the exact pending snapshot that was reviewed. Returns null
     * when a newer snapshot or a conflicting approval is already stored.
     */
    public function approveIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        string $approvedBy,
        DateTimeImmutable $approvedAt
    ): ?ProductReviewQueueEntry;

    /** @return list<ProductReviewQueueEntry> */
    public function pending(): array;
}
