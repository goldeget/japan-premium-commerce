<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;
use DateTimeZone;

/** Review status and staff decision trail for a normalized source snapshot. */
final class ProductReviewQueueEntry
{
    public const STATUS_PENDING = 'pending';
    public const STATUS_APPROVED = 'approved';
    public const STATUS_REJECTED = 'rejected';
    public const MAX_REJECTION_REASON_LENGTH = 2000;

    public function __construct(
        public readonly string $idempotencyKey,
        public readonly string $status,
        public readonly NormalizedProductSnapshot $snapshot,
        public readonly DateTimeImmutable $queuedAt,
        public readonly ?string $approvedBy = null,
        public readonly ?DateTimeImmutable $approvedAt = null,
        public readonly ?int $nativeProductId = null,
        public readonly ?string $rejectedBy = null,
        public readonly ?DateTimeImmutable $rejectedAt = null,
        public readonly ?string $rejectionReason = null,
        public readonly ?NormalizedProductSnapshot $previousSnapshot = null,
        public readonly ?int $linkedProductId = null,
        public readonly ?ProductImageRightsEvidence $imageRightsEvidence = null,
        public readonly ?ProductImportReviewEvidence $importReviewEvidence = null
    ) {
        if ($idempotencyKey === '' || $idempotencyKey !== $snapshot->deduplicationKey) {
            throw new \InvalidArgumentException('Queue entry identity must match its normalized snapshot.');
        }
        if (!in_array($status, [self::STATUS_PENDING, self::STATUS_APPROVED, self::STATUS_REJECTED], true)) {
            throw new \InvalidArgumentException('Unsupported product review queue status.');
        }
        if ($snapshot->approvalStatus !== $status) {
            throw new \InvalidArgumentException('Queue status must match its normalized snapshot approval state.');
        }
        if ($linkedProductId !== null && $linkedProductId < 1) {
            throw new \InvalidArgumentException('A linked inactive product identity must be positive.');
        }
        if ($importReviewEvidence?->sourceContentHash !== null
            && !hash_equals($snapshot->contentHash, $importReviewEvidence->sourceContentHash)) {
            throw new \InvalidArgumentException('Commercial import review evidence must match the exact source revision.');
        }
        if ($previousSnapshot !== null
            && ($previousSnapshot->deduplicationKey !== $idempotencyKey
                || $previousSnapshot->contentHash === $snapshot->contentHash)) {
            throw new \InvalidArgumentException('A source-change comparison must refer to a different revision of the same product.');
        }
        if ($status === self::STATUS_APPROVED && $linkedProductId !== null) {
            throw new \InvalidArgumentException('Approved queue entries use nativeProductId as their current product link.');
        }
        if ($status === self::STATUS_APPROVED
            && (trim((string) $approvedBy) === '' || $approvedAt === null || $nativeProductId === null || $nativeProductId < 1)) {
            throw new \InvalidArgumentException('Approved queue entries require reviewer, timestamp, and native product identity.');
        }
        if ($status === self::STATUS_APPROVED
            && ($rejectedBy !== null || $rejectedAt !== null || $rejectionReason !== null)) {
            throw new \InvalidArgumentException('Approved queue entries cannot contain rejection metadata.');
        }
        if ($status === self::STATUS_PENDING
            && ($approvedBy !== null || $approvedAt !== null || $nativeProductId !== null
                || $rejectedBy !== null || $rejectedAt !== null || $rejectionReason !== null)) {
            throw new \InvalidArgumentException('Pending queue entries cannot contain review metadata.');
        }
        if ($status === self::STATUS_REJECTED) {
            if ($approvedBy !== null || $approvedAt !== null || $nativeProductId !== null) {
                throw new \InvalidArgumentException('Rejected queue entries cannot contain approval metadata.');
            }
            if (trim((string) $rejectedBy) === '' || $rejectedAt === null || $rejectionReason === null) {
                throw new \InvalidArgumentException('Rejected queue entries require reviewer, UTC timestamp, and reason.');
            }
            self::validateRejectionReason($rejectionReason);
            if ($rejectedAt->getOffset() !== 0) {
                throw new \InvalidArgumentException('Rejected queue timestamps must use UTC.');
            }
        }
    }

    public function approve(
        int $nativeProductId,
        string $approvedBy,
        DateTimeImmutable $approvedAt,
        ?ProductImageRightsEvidence $imageRightsEvidence = null,
        ?ProductImportReviewEvidence $importReviewEvidence = null
    ): self
    {
        if ($this->status !== self::STATUS_PENDING) {
            throw new \LogicException('Only pending catalog entries can transition to approved.');
        }
        if ($nativeProductId < 1 || trim($approvedBy) === ''
            || ($this->linkedProductId !== null && $this->linkedProductId !== $nativeProductId)) {
            throw new \InvalidArgumentException('Product approval metadata is incomplete.');
        }

        return new self(
            $this->idempotencyKey,
            self::STATUS_APPROVED,
            $this->snapshot->withApprovalStatus('approved'),
            $this->queuedAt,
            trim($approvedBy),
            $approvedAt,
            $nativeProductId,
            previousSnapshot: $this->previousSnapshot,
            imageRightsEvidence: $imageRightsEvidence ?? $this->imageRightsEvidence,
            importReviewEvidence: $importReviewEvidence ?? $this->importReviewEvidence
        );
    }

    public function linkDraft(
        int $nativeProductId,
        ?ProductImageRightsEvidence $imageRightsEvidence = null,
        ?ProductImportReviewEvidence $importReviewEvidence = null
    ): self {
        if ($nativeProductId < 1) {
            throw new \InvalidArgumentException('A linked native draft identity must be positive.');
        }
        if ($this->status === self::STATUS_APPROVED) {
            if ($this->nativeProductId !== $nativeProductId) {
                throw new \LogicException('An approved catalog entry cannot be linked to another native product.');
            }
            return $this;
        }

        if (!in_array($this->status, [self::STATUS_PENDING, self::STATUS_REJECTED], true)
            || ($this->linkedProductId !== null && $this->linkedProductId !== $nativeProductId)) {
            throw new \LogicException('Only the same inactive draft can be linked to a current review entry.');
        }

        return new self(
            $this->idempotencyKey,
            $this->status,
            $this->snapshot,
            $this->queuedAt,
            $this->approvedBy,
            $this->approvedAt,
            $this->nativeProductId,
            $this->rejectedBy,
            $this->rejectedAt,
            $this->rejectionReason,
            $this->previousSnapshot,
            $nativeProductId,
            $imageRightsEvidence ?? $this->imageRightsEvidence,
            $importReviewEvidence ?? $this->importReviewEvidence
        );
    }

    public function reject(
        string $rejectedBy,
        DateTimeImmutable $rejectedAt,
        string $rejectionReason
    ): self {
        if ($this->status !== self::STATUS_PENDING) {
            throw new \LogicException('Only pending catalog entries can transition to rejected.');
        }

        $rejectedBy = trim($rejectedBy);
        $rejectionReason = trim($rejectionReason);
        if ($rejectedBy === '') {
            throw new \InvalidArgumentException('Catalog rejection requires a named reviewer.');
        }
        self::validateRejectionReason($rejectionReason);
        if ($rejectedAt->getOffset() !== 0) {
            throw new \InvalidArgumentException('Catalog rejection timestamps must use UTC.');
        }

        return new self(
            $this->idempotencyKey,
            self::STATUS_REJECTED,
            $this->snapshot->withApprovalStatus(self::STATUS_REJECTED),
            $this->queuedAt,
            rejectedBy: $rejectedBy,
            rejectedAt: $rejectedAt->setTimezone(new DateTimeZone('UTC')),
            rejectionReason: $rejectionReason,
            previousSnapshot: $this->previousSnapshot,
            linkedProductId: $this->linkedProductId,
            imageRightsEvidence: $this->imageRightsEvidence,
            importReviewEvidence: $this->importReviewEvidence
        );
    }

    public function refreshSameContentSnapshot(NormalizedProductSnapshot $snapshot): self
    {
        if ($snapshot->deduplicationKey !== $this->idempotencyKey
            || $snapshot->contentHash !== $this->snapshot->contentHash
            || $snapshot->fetchedAt <= $this->snapshot->fetchedAt) {
            throw new \LogicException('Only a newer observation of the same source content can refresh a review entry.');
        }

        return new self(
            $this->idempotencyKey,
            $this->status,
            $snapshot->withApprovalStatus($this->status),
            $this->queuedAt,
            $this->approvedBy,
            $this->approvedAt,
            $this->nativeProductId,
            $this->rejectedBy,
            $this->rejectedAt,
            $this->rejectionReason,
            $this->previousSnapshot,
            $this->linkedProductId,
            $this->imageRightsEvidence,
            $this->importReviewEvidence
        );
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'idempotencyKey' => $this->idempotencyKey,
            'status' => $this->status,
            'snapshot' => $this->snapshot->toArray(),
            'queuedAt' => $this->queuedAt->format(DATE_ATOM),
            'approvedBy' => $this->approvedBy,
            'approvedAt' => $this->approvedAt?->format(DATE_ATOM),
            'nativeProductId' => $this->nativeProductId,
            'rejectedBy' => $this->rejectedBy,
            'rejectedAt' => $this->rejectedAt?->format(DATE_ATOM),
            'rejectionReason' => $this->rejectionReason,
            'previousSnapshot' => $this->previousSnapshot?->toArray(),
            'linkedProductId' => $this->linkedProductId,
            'imageRightsEvidence' => $this->imageRightsEvidence?->toArray(),
            'importReviewEvidence' => $this->importReviewEvidence?->toArray(),
        ];
    }

    /** @param array<string, mixed> $data */
    public static function fromArray(array $data): self
    {
        $idempotencyKey = $data['idempotencyKey'] ?? null;
        $status = $data['status'] ?? null;
        $snapshotData = $data['snapshot'] ?? null;
        $queuedAt = $data['queuedAt'] ?? null;
        $approvedBy = $data['approvedBy'] ?? null;
        $approvedAt = $data['approvedAt'] ?? null;
        $nativeProductId = $data['nativeProductId'] ?? null;
        $rejectedBy = $data['rejectedBy'] ?? null;
        $rejectedAt = $data['rejectedAt'] ?? null;
        $rejectionReason = $data['rejectionReason'] ?? null;
        $previousSnapshotData = $data['previousSnapshot'] ?? null;
        $linkedProductId = $data['linkedProductId'] ?? null;
        $imageRightsEvidenceData = $data['imageRightsEvidence'] ?? null;
        $importReviewEvidenceData = $data['importReviewEvidence'] ?? null;
        if (!is_string($idempotencyKey) || !is_string($status) || !is_array($snapshotData) || !is_string($queuedAt)
            || ($approvedBy !== null && !is_string($approvedBy))
            || ($approvedAt !== null && !is_string($approvedAt))
            || ($nativeProductId !== null && !is_int($nativeProductId))
            || ($rejectedBy !== null && !is_string($rejectedBy))
            || ($rejectedAt !== null && !is_string($rejectedAt))
            || ($rejectionReason !== null && !is_string($rejectionReason))
            || ($previousSnapshotData !== null && !is_array($previousSnapshotData))
            || ($linkedProductId !== null && !is_int($linkedProductId))
            || ($imageRightsEvidenceData !== null && !is_array($imageRightsEvidenceData))
            || ($importReviewEvidenceData !== null && !is_array($importReviewEvidenceData))) {
            throw new \UnexpectedValueException('Persisted product review queue entry is invalid.');
        }

        try {
            $queuedDate = new DateTimeImmutable($queuedAt);
            $approvedDate = $approvedAt === null ? null : new DateTimeImmutable($approvedAt);
            $rejectedDate = $rejectedAt === null ? null : new DateTimeImmutable($rejectedAt);
            $previousSnapshot = $previousSnapshotData === null
                ? null
                : NormalizedProductSnapshot::fromArray($previousSnapshotData);
            $imageRightsEvidence = $imageRightsEvidenceData === null
                ? null
                : ProductImageRightsEvidence::fromArray($imageRightsEvidenceData);
            $importReviewEvidence = $importReviewEvidenceData === null
                ? null
                : ProductImportReviewEvidence::fromArray($importReviewEvidenceData);
        } catch (\Throwable $exception) {
            throw new \UnexpectedValueException('Persisted product review timestamp is invalid.', 0, $exception);
        }

        return new self(
            $idempotencyKey,
            $status,
            NormalizedProductSnapshot::fromArray($snapshotData),
            $queuedDate,
            $approvedBy,
            $approvedDate,
            $nativeProductId,
            $rejectedBy,
            $rejectedDate,
            $rejectionReason,
            $previousSnapshot,
            $linkedProductId,
            $imageRightsEvidence,
            $importReviewEvidence
        );
    }

    private static function validateRejectionReason(string $reason): void
    {
        if ($reason === '' || $reason !== trim($reason)) {
            throw new \InvalidArgumentException('Catalog rejection requires a non-empty normalized reason.');
        }

        $length = preg_match_all('/./us', $reason);
        if ($length === false || $length > self::MAX_REJECTION_REASON_LENGTH) {
            throw new \InvalidArgumentException('Catalog rejection reason is invalid or exceeds the maximum length.');
        }
    }
}
