<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;
use DateTimeZone;

/**
 * In-memory queue behavior for offline parsing and tests. Persistent storage
 * and administrator actions are intentionally outside this parser task.
 */
final class ProductReviewQueue
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
            $snapshot,
            $existing?->queuedAt ?? $queuedAt ?? new DateTimeImmutable('now', new DateTimeZone('UTC'))
        );
        $this->entries[$key] = $entry;

        return $entry;
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
