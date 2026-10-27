<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use DateTimeImmutable;
use DateTimeZone;
use JsonException;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;
use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Domain\ProductReviewQueueRepositoryInterface;
use RuntimeException;

/**
 * Atomic, process-locked JSON persistence for the catalog review queue.
 * The caller must supply a private writable directory; this class does not
 * choose a production path or install itself into PrestaShop.
 */
final class JsonFileProductReviewQueueRepository implements ProductReviewQueueRepositoryInterface
{
    // This JSON backend is capped; larger catalogs need a different storage backend.
    public const MAX_ENTRIES = 5000;
    public const MAX_STORAGE_BYTES = 33554432;

    public function __construct(
        private readonly string $filePath,
        private readonly int $maxEntries = self::MAX_ENTRIES,
        private readonly int $maxStorageBytes = self::MAX_STORAGE_BYTES
    ) {
        if ($maxEntries < 1 || $maxEntries > self::MAX_ENTRIES
            || $maxStorageBytes < 1 || $maxStorageBytes > self::MAX_STORAGE_BYTES) {
            throw new \InvalidArgumentException('Catalog review queue limits must be positive and cannot exceed the fixed backend caps.');
        }
        $directory = dirname($this->filePath);
        if (trim($this->filePath) === '' || !is_dir($directory) || !is_writable($directory) || is_dir($this->filePath)) {
            throw new RuntimeException('Catalog review queue directory must already exist and be writable.');
        }
        if (is_link($this->filePath) || is_link($this->lockPath())) {
            throw new RuntimeException('Catalog review queue files cannot be symbolic links.');
        }
    }

    public function enqueue(
        NormalizedProductSnapshot $snapshot,
        ?DateTimeImmutable $queuedAt = null
    ): ProductReviewQueueEntry {
        return $this->access(static function (array &$entries) use ($snapshot, $queuedAt): array {
            $key = $snapshot->deduplicationKey;
            $existing = $entries[$key] ?? null;
            if ($existing instanceof ProductReviewQueueEntry) {
                if ($snapshot->fetchedAt <= $existing->snapshot->fetchedAt) {
                    return [$existing, false];
                }
                if ($existing->snapshot->contentHash === $snapshot->contentHash) {
                    $refreshed = $existing->refreshSameContentSnapshot($snapshot);
                    $entries[$key] = $refreshed;
                    return [$refreshed, true];
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
            $entries[$key] = $entry;

            return [$entry, true];
        });
    }

    public function find(string $idempotencyKey): ?ProductReviewQueueEntry
    {
        return $this->access(static fn (array &$entries): array => [$entries[$idempotencyKey] ?? null, false]);
    }

    public function save(ProductReviewQueueEntry $entry): void
    {
        $this->access(static function (array &$entries) use ($entry): array {
            if (!isset($entries[$entry->idempotencyKey])) {
                throw new RuntimeException('Cannot update a catalog review entry that is not queued.');
            }
            $entries[$entry->idempotencyKey] = $entry;

            return [null, true];
        });
    }

    public function linkDraftIfCurrent(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        ?\Kuranea\Catalog\Domain\ProductImageRightsEvidence $imageRightsEvidence = null,
        ?\Kuranea\Catalog\Domain\ProductImportReviewEvidence $importReviewEvidence = null
    ): ?ProductReviewQueueEntry {
        return $this->access(static function (array &$entries) use (
            $idempotencyKey,
            $expectedContentHash,
            $nativeProductId,
            $imageRightsEvidence,
            $importReviewEvidence
        ): array {
            $entry = $entries[$idempotencyKey] ?? null;
            if (!$entry instanceof ProductReviewQueueEntry || $entry->snapshot->contentHash !== $expectedContentHash) {
                return [null, false];
            }
            $linked = $entry->linkDraft($nativeProductId, $imageRightsEvidence, $importReviewEvidence);
            $entries[$idempotencyKey] = $linked;
            return [$linked, $linked !== $entry];
        });
    }

    public function containsLinkedNativeProduct(int $nativeProductId): bool
    {
        if ($nativeProductId < 1) return false;
        return $this->access(static function (array &$entries) use ($nativeProductId): array {
            foreach ($entries as $entry) {
                if ($entry->nativeProductId === $nativeProductId || $entry->linkedProductId === $nativeProductId) {
                    return [true, false];
                }
            }
            return [false, false];
        });
    }

    public function approveIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        string $approvedBy,
        DateTimeImmutable $approvedAt,
        ?\Kuranea\Catalog\Domain\ProductImageRightsEvidence $imageRightsEvidence = null,
        ?\Kuranea\Catalog\Domain\ProductImportReviewEvidence $importReviewEvidence = null
    ): ?ProductReviewQueueEntry {
        return $this->access(static function (array &$entries) use (
            $idempotencyKey,
            $expectedContentHash,
            $nativeProductId,
            $approvedBy,
            $approvedAt,
            $imageRightsEvidence,
            $importReviewEvidence
        ): array {
            $entry = $entries[$idempotencyKey] ?? null;
            if (!$entry instanceof ProductReviewQueueEntry || $entry->snapshot->contentHash !== $expectedContentHash) {
                return [null, false];
            }
            if ($entry->status === ProductReviewQueueEntry::STATUS_APPROVED) {
                return [$entry->nativeProductId === $nativeProductId ? $entry : null, false];
            }
            if ($entry->status !== ProductReviewQueueEntry::STATUS_PENDING) {
                return [null, false];
            }

            $approved = $entry->approve($nativeProductId, $approvedBy, $approvedAt, $imageRightsEvidence, $importReviewEvidence);
            $entries[$idempotencyKey] = $approved;

            return [$approved, true];
        });
    }

    public function rejectIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        string $rejectedBy,
        DateTimeImmutable $rejectedAt,
        string $rejectionReason
    ): ?ProductReviewQueueEntry {
        return $this->access(static function (array &$entries) use (
            $idempotencyKey,
            $expectedContentHash,
            $rejectedBy,
            $rejectedAt,
            $rejectionReason
        ): array {
            $entry = $entries[$idempotencyKey] ?? null;
            if (!$entry instanceof ProductReviewQueueEntry
                || $entry->snapshot->contentHash !== $expectedContentHash
                || $entry->status !== ProductReviewQueueEntry::STATUS_PENDING) {
                return [null, false];
            }

            $rejected = $entry->reject($rejectedBy, $rejectedAt, $rejectionReason);
            $entries[$idempotencyKey] = $rejected;

            return [$rejected, true];
        });
    }

    /** @return list<ProductReviewQueueEntry> */
    public function pending(int $limit = 50, int $offset = 0): array
    {
        if ($limit < 1 || $limit > 1000 || $offset < 0) {
            throw new \InvalidArgumentException('Catalog review page is outside the supported range.');
        }

        return $this->access(static function (array &$entries) use ($limit, $offset): array {
            $pending = array_values(array_filter(
                $entries,
                static fn (ProductReviewQueueEntry $entry): bool => $entry->status === ProductReviewQueueEntry::STATUS_PENDING
            ));

            return [array_slice($pending, $offset, $limit), false];
        });
    }

    public function countPending(): int
    {
        return $this->access(static function (array &$entries): array {
            $count = count(array_filter(
                $entries,
                static fn (ProductReviewQueueEntry $entry): bool => $entry->status === ProductReviewQueueEntry::STATUS_PENDING
            ));

            return [$count, false];
        });
    }

    /** @return list<ProductReviewQueueEntry> */
    public function recentReviewed(int $limit = 20): array
    {
        if ($limit < 1 || $limit > ProductReviewQueueRepositoryInterface::MAX_RECENT_LIMIT) {
            throw new \InvalidArgumentException('Recent catalog review limit is outside the supported range.');
        }

        return $this->access(static function (array &$entries) use ($limit): array {
            $reviewed = array_values(array_filter(
                $entries,
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
                    throw new RuntimeException('A terminal catalog review decision is missing its timestamp.');
                }
                $decisionOrder = $rightAt <=> $leftAt;

                return $decisionOrder !== 0 ? $decisionOrder : strcmp($left->idempotencyKey, $right->idempotencyKey);
            });

            return [array_slice($reviewed, 0, $limit), false];
        });
    }

    /**
     * @template TResult
     * @param callable(array<string, ProductReviewQueueEntry>&):array{0:TResult,1:bool} $operation
     * @return TResult
     */
    private function access(callable $operation): mixed
    {
        $lockPath = $this->lockPath();
        if (is_link($lockPath)) {
            throw new RuntimeException('Catalog review queue lock cannot be a symbolic link.');
        }
        $lock = fopen($lockPath, 'c+b');
        if ($lock === false) {
            throw new RuntimeException('Could not open the catalog review queue lock file.');
        }

        try {
            if (!flock($lock, LOCK_EX)) {
                throw new RuntimeException('Could not acquire the catalog review queue lock.');
            }

            $entries = $this->readEntries();
            [$result, $changed] = $operation($entries);
            if ($changed) {
                $this->writeEntries($entries);
            }

            return $result;
        } finally {
            flock($lock, LOCK_UN);
            fclose($lock);
        }
    }

    /** @return array<string, ProductReviewQueueEntry> */
    private function readEntries(): array
    {
        if (!file_exists($this->filePath)) {
            return [];
        }
        if (is_link($this->filePath)) {
            throw new RuntimeException('Catalog review queue file cannot be a symbolic link.');
        }

        clearstatcache(true, $this->filePath);
        $size = filesize($this->filePath);
        if ($size === false || $size > $this->maxStorageBytes) {
            throw new RuntimeException('Catalog review queue exceeds its fixed file-size limit; refusing to overwrite it.');
        }
        // Bound the read as well as the stat check if an external writer changes the file.
        $contents = file_get_contents($this->filePath, false, null, 0, $this->maxStorageBytes + 1);
        if ($contents === false || strlen($contents) > $this->maxStorageBytes) {
            throw new RuntimeException('Could not read the catalog review queue file.');
        }

        try {
            $document = json_decode($contents, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new RuntimeException('Catalog review queue JSON is corrupt; refusing to overwrite it.', 0, $exception);
        }
        if (!is_array($document) || ($document['schemaVersion'] ?? null) !== 1 || !is_array($document['entries'] ?? null)) {
            throw new RuntimeException('Catalog review queue schema is unsupported; refusing to overwrite it.');
        }
        if (count($document['entries']) > $this->maxEntries) {
            throw new RuntimeException('Catalog review queue exceeds its fixed entry limit; refusing to overwrite it.');
        }

        $entries = [];
        foreach ($document['entries'] as $key => $serializedEntry) {
            if (!is_string($key) || !is_array($serializedEntry)) {
                throw new RuntimeException('Catalog review queue contains an invalid entry; refusing to overwrite it.');
            }
            try {
                $entry = ProductReviewQueueEntry::fromArray($serializedEntry);
            } catch (\Throwable $exception) {
                throw new RuntimeException('Catalog review queue entry is corrupt; refusing to overwrite it.', 0, $exception);
            }
            if ($entry->idempotencyKey !== $key) {
                throw new RuntimeException('Catalog review queue entry identity does not match its key.');
            }
            $entries[$key] = $entry;
        }

        return $entries;
    }

    /** @param array<string, ProductReviewQueueEntry> $entries */
    private function writeEntries(array $entries): void
    {
        if (count($entries) > $this->maxEntries) {
            throw new RuntimeException('Catalog review queue would exceed its fixed entry limit.');
        }
        $serializedEntries = [];
        foreach ($entries as $key => $entry) {
            $serializedEntries[$key] = $entry->toArray();
        }
        try {
            $contents = json_encode([
                'schemaVersion' => 1,
                'entries' => (object) $serializedEntries,
            ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new RuntimeException('Could not encode the catalog review queue.', 0, $exception);
        }
        if (strlen($contents) > $this->maxStorageBytes) {
            throw new RuntimeException('Catalog review queue would exceed its fixed file-size limit.');
        }

        $temporaryPath = tempnam(dirname($this->filePath), '.kuranea-catalog-queue-');
        if ($temporaryPath === false) {
            throw new RuntimeException('Could not create a temporary catalog review queue file.');
        }
        try {
            $written = file_put_contents($temporaryPath, $contents, LOCK_EX);
            if ($written !== strlen($contents)) {
                throw new RuntimeException('Could not write the complete catalog review queue file.');
            }
            if (!rename($temporaryPath, $this->filePath)) {
                throw new RuntimeException('Could not atomically replace the catalog review queue file.');
            }
            $temporaryPath = '';
        } finally {
            if ($temporaryPath !== '' && file_exists($temporaryPath)) {
                unlink($temporaryPath);
            }
        }
    }

    private function lockPath(): string
    {
        return $this->filePath . '.lock';
    }
}
