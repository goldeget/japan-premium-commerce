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
    public function __construct(private readonly string $filePath)
    {
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
            if ($existing instanceof ProductReviewQueueEntry && $existing->snapshot->contentHash === $snapshot->contentHash) {
                return [$existing, false];
            }

            $entry = new ProductReviewQueueEntry(
                $key,
                ProductReviewQueueEntry::STATUS_PENDING,
                $snapshot->withApprovalStatus('pending'),
                $existing?->queuedAt ?? $queuedAt ?? new DateTimeImmutable('now', new DateTimeZone('UTC'))
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

    public function approveIfPending(
        string $idempotencyKey,
        string $expectedContentHash,
        int $nativeProductId,
        string $approvedBy,
        DateTimeImmutable $approvedAt
    ): ?ProductReviewQueueEntry {
        return $this->access(static function (array &$entries) use (
            $idempotencyKey,
            $expectedContentHash,
            $nativeProductId,
            $approvedBy,
            $approvedAt
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

            $approved = $entry->approve($nativeProductId, $approvedBy, $approvedAt);
            $entries[$idempotencyKey] = $approved;

            return [$approved, true];
        });
    }

    /** @return list<ProductReviewQueueEntry> */
    public function pending(): array
    {
        return $this->access(static function (array &$entries): array {
            $pending = array_values(array_filter(
                $entries,
                static fn (ProductReviewQueueEntry $entry): bool => $entry->status === ProductReviewQueueEntry::STATUS_PENDING
            ));

            return [$pending, false];
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

        $contents = file_get_contents($this->filePath);
        if ($contents === false) {
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
