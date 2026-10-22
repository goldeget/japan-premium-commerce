<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;

/** Review status, staff approval trail, and native product identity for a snapshot. */
final class ProductReviewQueueEntry
{
    public const STATUS_PENDING = 'pending';
    public const STATUS_APPROVED = 'approved';

    public function __construct(
        public readonly string $idempotencyKey,
        public readonly string $status,
        public readonly NormalizedProductSnapshot $snapshot,
        public readonly DateTimeImmutable $queuedAt,
        public readonly ?string $approvedBy = null,
        public readonly ?DateTimeImmutable $approvedAt = null,
        public readonly ?int $nativeProductId = null
    ) {
        if ($idempotencyKey === '' || $idempotencyKey !== $snapshot->deduplicationKey) {
            throw new \InvalidArgumentException('Queue entry identity must match its normalized snapshot.');
        }
        if (!in_array($status, [self::STATUS_PENDING, self::STATUS_APPROVED], true)) {
            throw new \InvalidArgumentException('Unsupported product review queue status.');
        }
        if ($snapshot->approvalStatus !== $status) {
            throw new \InvalidArgumentException('Queue status must match its normalized snapshot approval state.');
        }
        if ($status === self::STATUS_APPROVED
            && (trim((string) $approvedBy) === '' || $approvedAt === null || $nativeProductId === null || $nativeProductId < 1)) {
            throw new \InvalidArgumentException('Approved queue entries require reviewer, timestamp, and native product identity.');
        }
        if ($status === self::STATUS_PENDING && ($approvedBy !== null || $approvedAt !== null || $nativeProductId !== null)) {
            throw new \InvalidArgumentException('Pending queue entries cannot contain approval metadata.');
        }
    }

    public function approve(int $nativeProductId, string $approvedBy, DateTimeImmutable $approvedAt): self
    {
        if ($this->status !== self::STATUS_PENDING) {
            throw new \LogicException('Only pending catalog entries can transition to approved.');
        }
        if ($nativeProductId < 1 || trim($approvedBy) === '') {
            throw new \InvalidArgumentException('Product approval metadata is incomplete.');
        }

        return new self(
            $this->idempotencyKey,
            self::STATUS_APPROVED,
            $this->snapshot->withApprovalStatus('approved'),
            $this->queuedAt,
            trim($approvedBy),
            $approvedAt,
            $nativeProductId
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
        if (!is_string($idempotencyKey) || !is_string($status) || !is_array($snapshotData) || !is_string($queuedAt)
            || ($approvedBy !== null && !is_string($approvedBy))
            || ($approvedAt !== null && !is_string($approvedAt))
            || ($nativeProductId !== null && !is_int($nativeProductId))) {
            throw new \UnexpectedValueException('Persisted product review queue entry is invalid.');
        }

        try {
            $queuedDate = new DateTimeImmutable($queuedAt);
            $approvedDate = $approvedAt === null ? null : new DateTimeImmutable($approvedAt);
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
            $nativeProductId
        );
    }
}
