<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Integration;

use DateTimeImmutable;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;

/** Safe, inactive registration draft derived from an explicitly approved snapshot. */
final class NativeProductRegistration
{
    public function __construct(
        public readonly string $reference,
        public readonly string $name,
        public readonly string $provenance,
        public readonly int $priceJpy,
        public readonly string $approvedBy,
        public readonly DateTimeImmutable $approvedAt,
        public readonly string $currency = 'JPY',
        public readonly bool $active = false,
        public readonly string $visibility = 'none',
        public readonly bool $availableForOrder = false
    ) {
    }

    public static function fromSnapshot(
        NormalizedProductSnapshot $snapshot,
        string $approvedBy,
        DateTimeImmutable $approvedAt
    ): self
    {
        if ($snapshot->currency !== 'JPY' || trim($approvedBy) === '') {
            throw new \InvalidArgumentException('Only reviewed JPY snapshots with a named approver can become native product drafts.');
        }

        $identity = strtoupper(substr(hash('sha256', $snapshot->deduplicationKey), 0, 12));
        $version = strtoupper(substr($snapshot->contentHash, 0, 12));
        $reference = 'TEST-' . $identity . '-' . $version;
        $provenance = implode("\n", [
            'KURANEA TEST/DEMO catalog import; not for sale.',
            'Provider: ' . $snapshot->source,
            'Source product ID: ' . $snapshot->sourceProductId,
            'Source URL: ' . $snapshot->sourceUrl,
            'Snapshot SHA-256: ' . $snapshot->contentHash,
            'Snapshot fetched at: ' . $snapshot->fetchedAt->format(DATE_ATOM),
            'Approved by: ' . trim($approvedBy),
            'Approved at: ' . $approvedAt->format(DATE_ATOM),
        ]);

        return new self(
            $reference,
            '[TEST/DEMO] ' . $snapshot->name,
            $provenance,
            $snapshot->priceJpy,
            trim($approvedBy),
            $approvedAt
        );
    }
}
