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
        if ($existing !== null) {
            if ($snapshot->fetchedAt <= $existing->snapshot->fetchedAt) {
                return $existing;
            }
            if ($existing->snapshot->contentHash === $snapshot->contentHash) {
                return $this->entries[$key] = $existing->refreshSameContentSnapshot($snapshot);
            }
        }

        $entry = new ProductReviewQueueEntry(
            $key,
            ProductReviewQueueEntry::STATUS_PENDING,
            $snapshot->withApprovalStatus('pending'),
            $existing?->queuedAt ?? $queuedAt ?? new DateTimeImmutable('now', new DateTimeZone('UTC')),
            previousSnapshot: $existing?->snapshot,
            linkedProductId: $existing?->nativeProductId ?? $existing?->linkedProductId,
            imageRightsEvidence: $existing?->imageRightsEvidence,
            importReviewEvidence: null
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

    public function linkDraftIfCurrent(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        ?ProductImageRightsEvidence $imageRightsEvidence = null,
        ?ProductImportReviewEvidence $importReviewEvidence = null
    ): ?ProductReviewQueueEntry {
        $entry = $this->entries[$idempotencyKey] ?? null;
        if ($entry === null || $entry->snapshot->contentHash !== $expectedContentHash) {
            return null;
        }
        $linked = $entry->linkDraft($nativeProductId, $imageRightsEvidence, $importReviewEvidence);
        return $this->entries[$idempotencyKey] = $linked;
    }

    public function containsLinkedNativeProduct(int $nativeProductId): bool
    {
        if ($nativeProductId < 1) return false;
        foreach ($this->entries as $entry) {
            if ($entry->nativeProductId === $nativeProductId || $entry->linkedProductId === $nativeProductId) {
                return true;
            }
        }
        return false;
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

        return $this->entries[$idempotencyKey] = $entry->approve(
            $nativeProductId,
            $approvedBy,
            $approvedAt,
            $imageRightsEvidence,
            $importReviewEvidence
        );
    }

    public function rejectIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        string $rejectedBy,
        DateTimeImmutable $rejectedAt,
        string $rejectionReason
    ): ?ProductReviewQueueEntry {
        $entry = $this->entries[$idempotencyKey] ?? null;
        if ($entry === null
            || $entry->snapshot->contentHash !== $expectedContentHash
            || $entry->status !== ProductReviewQueueEntry::STATUS_PENDING) {
            return null;
        }

        return $this->entries[$idempotencyKey] = $entry->reject($rejectedBy, $rejectedAt, $rejectionReason);
    }

    /** @return list<ProductReviewQueueEntry> */
    public function pending(): array
    {
        return array_values(array_filter(
            $this->entries,
            static fn (ProductReviewQueueEntry $entry): bool => $entry->status === ProductReviewQueueEntry::STATUS_PENDING
        ));
    }

    /** @return list<ProductReviewQueueEntry> */
    public function recentReviewed(int $limit = 20): array
    {
        if ($limit < 1 || $limit > ProductReviewQueueRepositoryInterface::MAX_RECENT_LIMIT) {
            throw new \InvalidArgumentException('Recent catalog review limit is outside the supported range.');
        }

        $reviewed = array_values(array_filter(
            $this->entries,
            static fn (ProductReviewQueueEntry $entry): bool => in_array(
                $entry->status,
                [ProductReviewQueueEntry::STATUS_APPROVED, ProductReviewQueueEntry::STATUS_REJECTED],
                true
            )
        ));
        usort($reviewed, static function (ProductReviewQueueEntry $left, ProductReviewQueueEntry $right): int {
            $leftAt = $left->status === ProductReviewQueueEntry::STATUS_APPROVED ? $left->approvedAt : $left->rejectedAt;
            $rightAt = $right->status === ProductReviewQueueEntry::STATUS_APPROVED ? $right->approvedAt : $right->rejectedAt;
            if ($leftAt === null || $rightAt === null) {
                throw new \LogicException('A terminal catalog review decision is missing its timestamp.');
            }
            $decisionOrder = $rightAt <=> $leftAt;

            return $decisionOrder !== 0 ? $decisionOrder : strcmp($left->idempotencyKey, $right->idempotencyKey);
        });

        return array_slice($reviewed, 0, $limit);
    }
}
