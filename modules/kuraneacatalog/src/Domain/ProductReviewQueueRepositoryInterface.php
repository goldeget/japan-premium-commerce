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
     * Persist the deterministic native draft link and review evidence before
     * the approval transition, so a later request can recover after a failure.
     */
    public function linkDraftIfCurrent(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        ?ProductImageRightsEvidence $imageRightsEvidence = null,
        ?ProductImportReviewEvidence $importReviewEvidence = null
    ): ?ProductReviewQueueEntry;

    public function containsLinkedNativeProduct(int $nativeProductId): bool;

    /**
     * Approve only the exact pending snapshot that was reviewed. Returns null
     * when a newer snapshot or a conflicting approval is already stored.
     */
    public function approveIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        string $approvedBy,
        DateTimeImmutable $approvedAt,
        ?ProductImageRightsEvidence $imageRightsEvidence = null,
        ?ProductImportReviewEvidence $importReviewEvidence = null
    ): ?ProductReviewQueueEntry;

    /**
     * Reject only the exact pending snapshot that was reviewed. Returns null
     * when a newer snapshot or a conflicting review decision is already stored.
     */
    public function rejectIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        string $rejectedBy,
        DateTimeImmutable $rejectedAt,
        string $rejectionReason
    ): ?ProductReviewQueueEntry;

    /** @return list<ProductReviewQueueEntry> */
    public function pending(): array;
}
