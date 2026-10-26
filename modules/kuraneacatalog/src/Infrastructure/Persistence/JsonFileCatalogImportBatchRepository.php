<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use DateTimeImmutable;
use JsonException;
use Kuranea\Catalog\Domain\CatalogImportBatch;
use Kuranea\Catalog\Domain\CatalogImportBatchRepositoryInterface;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;
use RuntimeException;

/** Atomic, process-locked persistence for bounded catalog import batches. */
final class JsonFileCatalogImportBatchRepository implements CatalogImportBatchRepositoryInterface
{
    private const SCHEMA_VERSION = 1;
    private const FILE_NAME = 'catalog-import-batches.json';
    public const MAX_BATCHES = 1000;
    public const MAX_STORAGE_BYTES = 33554432;

    private readonly string $directory;
    private readonly string $filePath;
    private readonly int $maxStorageBytes;

    public function __construct(
        string $privateDirectory,
        string $shopRoot,
        int $maxStorageBytes = self::MAX_STORAGE_BYTES
    ) {
        if ($maxStorageBytes < 1 || $maxStorageBytes > self::MAX_STORAGE_BYTES) {
            throw new \InvalidArgumentException('Catalog import storage limit must be positive and cannot exceed the fixed backend cap.');
        }
        $realDirectory = $privateDirectory === '' || is_link($privateDirectory) ? false : realpath($privateDirectory);
        $realShopRoot = $shopRoot === '' ? false : realpath($shopRoot);
        if ($realDirectory === false || !is_dir($realDirectory) || !is_writable($realDirectory)
            || $realShopRoot === false || !is_dir($realShopRoot)) {
            throw new RuntimeException('Catalog import storage must be an existing writable private directory.');
        }

        $shopRootPrefix = rtrim($realShopRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
        if ($realDirectory === $realShopRoot || str_starts_with($realDirectory, $shopRootPrefix)) {
            throw new RuntimeException('Catalog import storage must be outside the public PrestaShop webroot.');
        }

        $this->directory = $realDirectory;
        $this->filePath = $realDirectory . DIRECTORY_SEPARATOR . self::FILE_NAME;
        $this->maxStorageBytes = $maxStorageBytes;
        if (is_dir($this->filePath) || is_link($this->filePath) || is_link($this->lockPath())) {
            throw new RuntimeException('Catalog import storage files cannot be directories or symbolic links.');
        }
    }

    /** @param list<string> $urls */
    public function create(array $urls, ?DateTimeImmutable $createdAt = null): CatalogImportBatch
    {
        return $this->access(static function (array &$batches) use ($urls, $createdAt): array {
            if (count($batches) >= self::MAX_BATCHES) {
                throw new RuntimeException('Catalog import batch storage has reached its fixed batch limit.');
            }
            $batch = CatalogImportBatch::fromUrls($urls, $createdAt);
            if (isset($batches[$batch->id])) {
                throw new RuntimeException('Could not allocate a unique catalog import batch identity.');
            }
            $batches[$batch->id] = $batch;

            return [$batch, true];
        });
    }

    public function find(string $batchId): ?CatalogImportBatch
    {
        return $this->access(static fn (array &$batches): array => [$batches[$batchId] ?? null, false]);
    }

    /** @return list<CatalogImportBatch> */
    public function recent(int $limit = 20): array
    {
        if ($limit < 1 || $limit > CatalogImportBatchRepositoryInterface::MAX_RECENT_LIMIT) {
            throw new \InvalidArgumentException('Recent catalog batch limit is outside the supported range.');
        }

        return $this->access(static function (array &$batches) use ($limit): array {
            $recent = array_values($batches);
            usort($recent, static function (CatalogImportBatch $left, CatalogImportBatch $right): int {
                $createdOrder = $right->createdAt <=> $left->createdAt;

                return $createdOrder !== 0 ? $createdOrder : strcmp($left->id, $right->id);
            });

            return [array_slice($recent, 0, $limit), false];
        });
    }

    public function markProcessing(
        string $batchId,
        string $itemId,
        ?DateTimeImmutable $startedAt = null
    ): CatalogImportBatch
    {
        return $this->update(
            $batchId,
            static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->markProcessing($itemId, $startedAt)
        );
    }

    public function recoverStaleProcessing(
        string $batchId,
        ?DateTimeImmutable $now = null
    ): CatalogImportBatch {
        $now ??= new DateTimeImmutable('now', new \DateTimeZone('UTC'));

        return $this->update(
            $batchId,
            static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->recoverStaleProcessing($now)
        );
    }

    public function markSucceeded(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        NormalizedProductSnapshot $snapshot
    ): CatalogImportBatch {
        return $this->update(
            $batchId,
            static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->markSucceeded($itemId, $expectedAttempt, $snapshot)
        );
    }

    public function completeWithReviewSnapshot(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        NormalizedProductSnapshot $snapshot,
        callable $commitReviewSnapshot
    ): CatalogImportBatch {
        return $this->access(function (array &$batches) use (
            $batchId,
            $itemId,
            $expectedAttempt,
            $snapshot,
            $commitReviewSnapshot
        ): array {
            $batch = $batches[$batchId] ?? null;
            if (!$batch instanceof CatalogImportBatch) {
                throw new RuntimeException('Catalog import batch was not found.');
            }

            // The domain compare-and-swap happens before the cross-repository
            // side effect. Holding this lock prevents a stale worker from
            // replacing a newer review snapshot after lease recovery.
            $completed = $batch->markSucceeded($itemId, $expectedAttempt, $snapshot);
            $candidateBatches = $batches;
            $candidateBatches[$batchId] = $completed;
            // Reject deterministic storage-cap failures before the separate
            // review queue is mutated. writeBatches() repeats this check.
            $this->serializeBatches($candidateBatches);
            $commitReviewSnapshot();
            $batches = $candidateBatches;

            return [$completed, true];
        });
    }

    public function markFailed(
        string $batchId,
        string $itemId,
        int $expectedAttempt,
        string $failureCategory
    ): CatalogImportBatch
    {
        return $this->update(
            $batchId,
            static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->markFailed($itemId, $expectedAttempt, $failureCategory)
        );
    }

    public function retryFailedItems(string $batchId): CatalogImportBatch
    {
        return $this->update(
            $batchId,
            static fn (CatalogImportBatch $batch): CatalogImportBatch => $batch->retryFailedItems()
        );
    }

    /** @param callable(CatalogImportBatch):CatalogImportBatch $operation */
    private function update(string $batchId, callable $operation): CatalogImportBatch
    {
        return $this->access(static function (array &$batches) use ($batchId, $operation): array {
            $batch = $batches[$batchId] ?? null;
            if (!$batch instanceof CatalogImportBatch) {
                throw new RuntimeException('Catalog import batch was not found.');
            }

            $updated = $operation($batch);
            if (!$updated instanceof CatalogImportBatch || $updated->id !== $batchId) {
                throw new RuntimeException('Catalog import update returned an invalid batch.');
            }
            $changed = $updated !== $batch;
            if ($changed) {
                $batches[$batchId] = $updated;
            }

            return [$updated, $changed];
        });
    }

    /**
     * @template TResult
     * @param callable(array<string, CatalogImportBatch>&):array{0:TResult,1:bool} $operation
     * @return TResult
     */
    private function access(callable $operation): mixed
    {
        $lockPath = $this->lockPath();
        if (is_link($lockPath) || is_link($this->filePath)) {
            throw new RuntimeException('Catalog import storage files cannot be symbolic links.');
        }
        $lock = fopen($lockPath, 'c+b');
        if ($lock === false) {
            throw new RuntimeException('Could not open the catalog import storage lock.');
        }
        chmod($lockPath, 0600);

        try {
            if (!flock($lock, LOCK_EX)) {
                throw new RuntimeException('Could not acquire the catalog import storage lock.');
            }

            $batches = $this->readBatches();
            [$result, $changed] = $operation($batches);
            if ($changed) {
                $this->writeBatches($batches);
            }

            return $result;
        } finally {
            flock($lock, LOCK_UN);
            fclose($lock);
        }
    }

    /** @return array<string, CatalogImportBatch> */
    private function readBatches(): array
    {
        if (!file_exists($this->filePath)) {
            return [];
        }
        if (is_link($this->filePath) || !is_file($this->filePath)) {
            throw new RuntimeException('Catalog import storage file is not a regular file.');
        }
        clearstatcache(true, $this->filePath);
        $size = filesize($this->filePath);
        if ($size === false || $size > $this->maxStorageBytes) {
            throw new RuntimeException('Catalog import storage exceeds its fixed file-size limit.');
        }

        $contents = file_get_contents($this->filePath);
        if ($contents === false || strlen($contents) > $this->maxStorageBytes) {
            throw new RuntimeException('Could not read the catalog import storage file.');
        }

        try {
            $document = json_decode($contents, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new RuntimeException('Catalog import JSON is corrupt; refusing to overwrite it.', 0, $exception);
        }
        if (!is_array($document)
            || array_diff(array_keys($document), ['schemaVersion', 'batches']) !== []
            || array_diff(['schemaVersion', 'batches'], array_keys($document)) !== []
            || ($document['schemaVersion'] ?? null) !== self::SCHEMA_VERSION
            || !is_array($document['batches'] ?? null)
            || ($document['batches'] !== [] && array_is_list($document['batches']))) {
            throw new RuntimeException('Catalog import schema is unsupported or invalid; refusing to overwrite it.');
        }

        $batches = [];
        foreach ($document['batches'] as $key => $batchData) {
            if (!is_string($key) || !is_array($batchData)) {
                throw new RuntimeException('Catalog import storage contains an invalid batch; refusing to overwrite it.');
            }
            try {
                $batch = CatalogImportBatch::fromArray($batchData);
            } catch (\Throwable $exception) {
                throw new RuntimeException('Catalog import batch is corrupt; refusing to overwrite it.', 0, $exception);
            }
            if ($batch->id !== $key) {
                throw new RuntimeException('Catalog import batch identity does not match its storage key.');
            }
            $batches[$key] = $batch;
        }

        return $batches;
    }

    /** @param array<string, CatalogImportBatch> $batches */
    private function writeBatches(array $batches): void
    {
        $contents = $this->serializeBatches($batches);

        $temporaryPath = tempnam($this->directory, '.kuranea-catalog-import-');
        if ($temporaryPath === false) {
            throw new RuntimeException('Could not create a temporary catalog import storage file.');
        }
        try {
            chmod($temporaryPath, 0600);
            $written = file_put_contents($temporaryPath, $contents, LOCK_EX);
            if ($written !== strlen($contents)) {
                throw new RuntimeException('Could not write the complete catalog import storage file.');
            }
            if (!rename($temporaryPath, $this->filePath)) {
                throw new RuntimeException('Could not atomically replace the catalog import storage file.');
            }
            $temporaryPath = '';
        } finally {
            if ($temporaryPath !== '' && file_exists($temporaryPath)) {
                unlink($temporaryPath);
            }
        }
    }

    /** @param array<string, CatalogImportBatch> $batches */
    private function serializeBatches(array $batches): string
    {
        $serializedBatches = [];
        foreach ($batches as $id => $batch) {
            if (!$batch instanceof CatalogImportBatch || $batch->id !== $id) {
                throw new RuntimeException('Catalog import batch identity is invalid; refusing to write storage.');
            }
            $serializedBatches[$id] = $batch->toArray();
        }

        try {
            $contents = json_encode([
                'schemaVersion' => self::SCHEMA_VERSION,
                'batches' => (object) $serializedBatches,
            ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new RuntimeException('Could not encode catalog import batches.', 0, $exception);
        }
        if (strlen($contents) > $this->maxStorageBytes) {
            throw new RuntimeException('Catalog import storage would exceed its fixed file-size limit.');
        }

        return $contents;
    }

    private function lockPath(): string
    {
        return $this->filePath . '.lock';
    }
}
