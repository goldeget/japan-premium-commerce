<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;
use DateTimeZone;

/**
 * In-memory implementation retained for isolated domain tests. Production
 * persistence is provided separately by the JSON queue repository.
 */
final class ProductReviewQueue implements ProductReviewQueueRepositoryInterface
{
    /** @var array<string, ProductReviewQueueEntry> */
    private array $entries = [];

    public function enqueue(
        NormalizedProductSnapshot $snapshot,
        ?DateTimeImmutable $queuedAt = null
    ): ProductReviewQueueEntry {
        $key = $snapshot->deduplicationKey;
        $existing = $this->entries[$key] ?? null;
        if ($existing !== null && $existing->snapshot->contentHash === $snapshot->contentHash) {
            return $existing;
        }

        $entry = new ProductReviewQueueEntry(
            $key,
            ProductReviewQueueEntry::STATUS_PENDING,
            $snapshot->withApprovalStatus('pending'),
            $existing?->queuedAt ?? $queuedAt ?? new DateTimeImmutable('now', new DateTimeZone('UTC'))
        );
        $this->entries[$key] = $entry;

        return $entry;
    }

    public function find(string $idempotencyKey): ?ProductReviewQueueEntry
    {
        return $this->entries[$idempotencyKey] ?? null;
    }

    public function save(ProductReviewQueueEntry $entry): void
    {
        if ($entry->idempotencyKey === '') {
            throw new \InvalidArgumentException('Product review queue identity cannot be empty.');
        }

        $this->entries[$entry->idempotencyKey] = $entry;
    }

    public function approveIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        string $approvedBy,
        DateTimeImmutable $approvedAt
    ): ?ProductReviewQueueEntry {
        $entry = $this->entries[$idempotencyKey] ?? null;
        if ($entry === null || $entry->snapshot->contentHash !== $expectedContentHash) {
            return null;
        }
        if ($entry->status === ProductReviewQueueEntry::STATUS_APPROVED) {
            return $entry->nativeProductId === $nativeProductId ? $entry : null;
        }
        if ($entry->status !== ProductReviewQueueEntry::STATUS_PENDING) {
            return null;
        }

        return $this->entries[$idempotencyKey] = $entry->approve($nativeProductId, $approvedBy, $approvedAt);
    }

    /** @return list<ProductReviewQueueEntry> */
    public function pending(): array
    {
        return array_values(array_filter(
            $this->entries,
            static fn (ProductReviewQueueEntry $entry): bool => $entry->status === ProductReviewQueueEntry::STATUS_PENDING
        ));
    }
}
