<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Service;

use DateTimeImmutable;
use DateTimeZone;
use InvalidArgumentException;
use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Domain\ProductReviewQueueRepositoryInterface;
use Kuranea\Catalog\Integration\NativeProductRegistration;
use Kuranea\Catalog\Integration\NativeProductRegistrarInterface;
use RuntimeException;

/** Explicit staff-only boundary between parsed snapshots and native products. */
final class ProductApprovalService
{
    public function __construct(
        private readonly ProductReviewQueueRepositoryInterface $queue,
        private readonly NativeProductRegistrarInterface $registrar
    ) {
    }

    public function approve(
        string $idempotencyKey,
        string $approvedBy,
        ?DateTimeImmutable $approvedAt = null,
        bool $confirmed = false
    ): ProductReviewQueueEntry {
        $approvedBy = trim($approvedBy);
        if ($approvedBy === '') {
            throw new InvalidArgumentException('A staff identity is required for catalog approval.');
        }

        $entry = $this->queue->find($idempotencyKey);
        if ($entry === null) {
            throw new RuntimeException('Catalog review item was not found.');
        }
        if ($entry->status === ProductReviewQueueEntry::STATUS_APPROVED) {
            return $entry;
        }
        if ($entry->status !== ProductReviewQueueEntry::STATUS_PENDING) {
            throw new RuntimeException('Catalog review item cannot be approved from its current status.');
        }
        if (!$confirmed) {
            throw new InvalidArgumentException('Explicit confirmation is required before creating a native product.');
        }
        if ($entry->snapshot->currency !== 'JPY') {
            throw new RuntimeException('Only JPY catalog snapshots can be registered to the Japanese shop.');
        }

        $approvalTimestamp = $approvedAt ?? new DateTimeImmutable('now', new DateTimeZone('UTC'));
        $registration = NativeProductRegistration::fromSnapshot($entry->snapshot, $approvedBy, $approvalTimestamp);
        $nativeProductId = $this->registrar->register($registration);
        if ($nativeProductId < 1) {
            throw new RuntimeException('Native product registrar returned an invalid product identity.');
        }

        $approved = $this->queue->approveIfPending(
            $entry->idempotencyKey,
            $entry->snapshot->contentHash,
            $nativeProductId,
            $approvedBy,
            $approvalTimestamp
        );
        if ($approved === null) {
            throw new RuntimeException('Catalog review item changed while registration was in progress; the latest snapshot remains pending review.');
        }

        return $approved;
    }
}
