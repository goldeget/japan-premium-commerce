<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;

/** A review-required snapshot entry; this value object does not persist data. */
final class ProductReviewQueueEntry
{
    public const STATUS_PENDING = 'pending';

    public function __construct(
        public readonly string $idempotencyKey,
        public readonly string $status,
        public readonly NormalizedProductSnapshot $snapshot,
        public readonly DateTimeImmutable $queuedAt
    ) {
    }
}
