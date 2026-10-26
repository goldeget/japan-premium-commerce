<?php

declare(strict_types=1);

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

use Kuranea\Catalog\Domain\CatalogImportBatch;
use Kuranea\Catalog\Domain\CatalogImportBatchItem;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;
use Kuranea\Catalog\Domain\ProductImageSnapshot;
use Kuranea\Catalog\Domain\ProductOptionSnapshot;
use Kuranea\Catalog\Infrastructure\Persistence\JsonFileCatalogImportBatchRepository;

function catalogImportAssertSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function catalogImportAssertTrue(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

function catalogImportAssertThrows(callable $callback, string $message, string $exceptionClass = InvalidArgumentException::class): void
{
    try {
        $callback();
    } catch (Throwable $exception) {
        if ($exception instanceof $exceptionClass) {
            return;
        }
        throw new RuntimeException($message . '; wrong exception ' . get_class($exception), 0, $exception);
    }

    throw new RuntimeException($message . '; no exception was thrown');
}

function catalogImportSyntheticSnapshot(string $source, string $productId, string $url): NormalizedProductSnapshot
{
    $image = new ProductImageSnapshot(
        'https://images.example.invalid/catalog/item.jpg?signature=private-image-token#gallery',
        '합성 이미지',
        0,
        $source
    );
    $option = new ProductOptionSnapshot('색상', ['남색', '회색']);
    $reviews = [];
    $snapshotData = [
        'source' => $source,
        'sourceProductId' => $productId,
        'sourceUrl' => $url,
        'name' => '[TEST FIXTURE] 합성 상품',
        'brand' => '합성 상표',
        'description' => '실제 판매 페이지가 아닌 로컬 합성 데이터입니다.',
        'categories' => ['합성 카테고리'],
        'priceJpy' => 1200,
        'currency' => 'JPY',
        'images' => [[
            'url' => $image->url,
            'altText' => $image->altText,
            'position' => $image->position,
            'source' => $image->source,
        ]],
        'options' => [[
            'name' => $option->name,
            'values' => $option->values,
        ]],
        'reviews' => [],
        'sourceRating' => null,
        'sourceReviewCount' => null,
        'availability' => 'https://schema.org/InStock',
    ];

    return new NormalizedProductSnapshot(
        $source,
        $productId,
        $source . ':' . $productId,
        $url,
        '[TEST FIXTURE] 합성 상품',
        '합성 상표',
        '실제 판매 페이지가 아닌 로컬 합성 데이터입니다.',
        ['합성 카테고리'],
        1200,
        'JPY',
        [$image],
        [$option],
        $reviews,
        null,
        null,
        'https://schema.org/InStock',
        'pending',
        new DateTimeImmutable('2026-10-25T00:00:00+00:00'),
        hash('sha256', json_encode($snapshotData, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR))
    );
}

function catalogImportRemoveTree(string $path): void
{
    if (!is_dir($path) || is_link($path)) {
        if (file_exists($path) || is_link($path)) {
            unlink($path);
        }
        return;
    }

    foreach (scandir($path) ?: [] as $entry) {
        if ($entry === '.' || $entry === '..') {
            continue;
        }
        catalogImportRemoveTree($path . DIRECTORY_SEPARATOR . $entry);
    }
    rmdir($path);
}

$batch = CatalogImportBatch::fromUrls([
    'https://amazon.co.jp/a-title/dp/b0kuranea1?session=must-not-persist#top',
    'https://www.amazon.co.jp/dp/B0KURANEA1?tag=tracking-only',
    'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/?access_token=must-not-persist',
    'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/#details',
]);

catalogImportAssertSame(2, count($batch->items), 'Equivalent provider URLs and product IDs should create one batch item per product.');
catalogImportAssertSame('https://www.amazon.co.jp/dp/B0KURANEA1', $batch->items[0]->canonicalUrl, 'Amazon URLs should normalize to the canonical product URL.');
catalogImportAssertSame('https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/', $batch->items[1]->canonicalUrl, 'Rakuten URLs should normalize to the canonical item URL.');
catalogImportAssertSame('queued', $batch->items[0]->status, 'New batch entries should start queued.');
catalogImportAssertSame(['queued' => 2, 'processing' => 0, 'succeeded' => 0, 'failed' => 0], $batch->counts(), 'Batch counts should include every status with zero values.');
catalogImportAssertTrue(!str_contains(json_encode($batch->toArray(), JSON_THROW_ON_ERROR), 'must-not-persist'), 'URL query values and fragments must not be persisted.');

catalogImportAssertThrows(
    static fn () => CatalogImportBatch::fromUrls(array_map(
        static fn (int $index): string => 'https://www.amazon.co.jp/dp/' . sprintf('B%09d', $index),
        range(1, 11)
    )),
    'A batch must reject more than ten submitted product URLs.'
);
catalogImportAssertThrows(
    static fn () => CatalogImportBatch::fromUrls(['https://amazon.co.jp.evil.invalid/dp/B0KURANEA1']),
    'A batch must reject lookalike marketplace hostnames.'
);
catalogImportAssertThrows(
    static fn () => CatalogImportBatch::fromUrls(['https://www.rakuten.co.jp/fixture-shop/synthetic-case-b/']),
    'A batch must reject Rakuten content pages that are not canonical item host product URLs.'
);
catalogImportAssertThrows(
    static fn () => CatalogImportBatch::fromUrls(['https://item.rakuten.co.jp./fixture-shop/synthetic-case-b/']),
    'A batch must reject trailing-dot marketplace hostnames.'
);

$accessBlockedItem = CatalogImportBatchItem::fromUrl('https://www.amazon.co.jp/dp/B0KURANEA9')
    ->markProcessing()
    ->markFailed(CatalogImportBatchItem::FAILURE_ACCESS_BLOCKED, 1);
catalogImportAssertSame('access_blocked', $accessBlockedItem->failureCategory, 'Explicit access block failures should retain the fixed category code.');
catalogImportAssertSame('판매처에서 상품 정보 접근을 제한했습니다.', $accessBlockedItem->failureMessage(), 'Access block failures should use the fixed Korean-safe message.');

$temporaryRoot = sys_get_temp_dir() . '/kuranea-catalog-import-' . bin2hex(random_bytes(8));
$privateDirectory = $temporaryRoot . '/private';
$shopRoot = $temporaryRoot . '/webroot';
if (!mkdir($privateDirectory, 0700, true) || !mkdir($shopRoot, 0700, true)) {
    throw new RuntimeException('Could not create isolated local catalog import storage directories.');
}

try {
    $repository = new JsonFileCatalogImportBatchRepository($privateDirectory, $shopRoot);
    $stored = $repository->create([
        'https://www.amazon.co.jp/dp/B0KURANEA1?token=private-amazon-token',
        'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/?token=private-rakuten-token',
        'https://www.amazon.co.jp/dp/B0KURANEA2',
    ]);
    $amazonItem = $stored->items[0];
    $rakutenItem = $stored->items[1];
    $untouchedItem = $stored->items[2];

    $stored = $repository->markProcessing($stored->id, $amazonItem->id);
    catalogImportAssertSame('processing', $stored->item($amazonItem->id)->status, 'A one-item progress update should mark only its target processing.');
    catalogImportAssertSame('queued', $stored->item($rakutenItem->id)->status, 'Other entries should remain queued after a one-item progress update.');
    $stored = $repository->markSucceeded(
        $stored->id,
        $amazonItem->id,
        1,
        catalogImportSyntheticSnapshot('amazon_jp', 'B0KURANEA1', 'https://amazon.co.jp/dp/B0KURANEA1?session=private-snapshot-token')
    );
    $stored = $repository->markProcessing($stored->id, $rakutenItem->id);
    $stored = $repository->markFailed($stored->id, $rakutenItem->id, 1, CatalogImportBatchItem::FAILURE_PARSE_FAILED);
    catalogImportAssertSame('parse_failed', $stored->item($rakutenItem->id)->failureCategory, 'Failures should retain only their fixed category code.');
    catalogImportAssertTrue(preg_match('/[가-힣]/u', $stored->item($rakutenItem->id)->failureMessage()) === 1, 'Failure categories should expose a fixed Korean-safe message.');
    catalogImportAssertSame('queued', $stored->item($untouchedItem->id)->status, 'An unrelated queued item should remain queued.');
    catalogImportAssertSame(['queued' => 1, 'processing' => 0, 'succeeded' => 1, 'failed' => 1], $stored->counts(), 'Counts should reflect per-item progress.');

    $failedReopened = new JsonFileCatalogImportBatchRepository($privateDirectory, $shopRoot);
    $persistedFailure = $failedReopened->find($stored->id);
    catalogImportAssertTrue($persistedFailure instanceof CatalogImportBatch, 'Failed batches should survive repository reconstruction.');
    catalogImportAssertSame('failed', $persistedFailure->item($rakutenItem->id)->status, 'Failed status should survive persistence before retry.');
    catalogImportAssertSame('parse_failed', $persistedFailure->item($rakutenItem->id)->failureCategory, 'Fixed failure categories should survive persistence before retry.');

    catalogImportAssertThrows(
        static fn () => $repository->markFailed($stored->id, $amazonItem->id, 1, 'raw token=must-not-persist'),
        'Failure updates must reject non-enumerated categories.'
    );
    catalogImportAssertThrows(
        static fn () => $repository->markProcessing($stored->id, $amazonItem->id),
        'A succeeded item must not move back into processing.',
        LogicException::class
    );

    $retried = $repository->retryFailedItems($stored->id);
    catalogImportAssertSame('queued', $retried->item($rakutenItem->id)->status, 'Retry should queue a failed item again.');
    catalogImportAssertSame('succeeded', $retried->item($amazonItem->id)->status, 'Retry must leave succeeded entries untouched.');
    catalogImportAssertSame('queued', $retried->item($untouchedItem->id)->status, 'Retry must leave never-started entries untouched.');
    catalogImportAssertSame(1, $retried->item($rakutenItem->id)->attempts, 'Retry should preserve completed attempt count until processing starts again.');

    $reopened = new JsonFileCatalogImportBatchRepository($privateDirectory, $shopRoot);
    $persisted = $reopened->find($stored->id);
    catalogImportAssertTrue($persisted instanceof CatalogImportBatch, 'Stored batches should survive repository reconstruction.');
    catalogImportAssertSame('succeeded', $persisted->item($amazonItem->id)->status, 'Succeeded status should survive persistence.');
    catalogImportAssertSame('https://www.amazon.co.jp/dp/B0KURANEA1', $persisted->item($amazonItem->id)->snapshot->sourceUrl, 'Persisted snapshots should use the canonical source URL without its query.');
    catalogImportAssertSame('https://images.example.invalid/catalog/item.jpg', $persisted->item($amazonItem->id)->snapshot->images[0]->url, 'Image metadata queries and fragments should be removed before persistence.');
    catalogImportAssertSame('queued', $persisted->item($rakutenItem->id)->status, 'Retry status should survive persistence.');
    catalogImportAssertSame(null, $persisted->item($rakutenItem->id)->failureCategory, 'Retry should clear the failure category in persisted state.');

    $storedJson = file_get_contents($privateDirectory . '/catalog-import-batches.json');
    catalogImportAssertTrue(is_string($storedJson), 'The repository should create its JSON store in the private directory.');
    foreach (['private-amazon-token', 'private-rakuten-token', 'private-snapshot-token', 'signature=private-image-token', 'raw token=must-not-persist'] as $secret) {
        catalogImportAssertTrue(!str_contains($storedJson, $secret), 'Storage must not contain a URL query or raw error: ' . $secret);
    }

    $webrootRejected = false;
    try {
        new JsonFileCatalogImportBatchRepository($shopRoot . '/catalog-data', $shopRoot);
    } catch (RuntimeException) {
        $webrootRejected = true;
    }
    catalogImportAssertTrue($webrootRejected, 'Catalog batch storage must refuse the public shop webroot.');

    $recoveryBatch = $repository->create(['https://www.amazon.co.jp/dp/B0KURANEA4']);
    $recoveryItemId = $recoveryBatch->items[0]->id;
    $attemptStartedAt = new DateTimeImmutable('2026-10-25T10:00:00+00:00');
    $firstAttemptBatch = $repository->markProcessing($recoveryBatch->id, $recoveryItemId, $attemptStartedAt);
    $firstAttempt = $firstAttemptBatch->item($recoveryItemId)->attempts;
    catalogImportAssertSame(1, $firstAttempt, 'The first claimed attempt should have a monotonically increasing attempt number.');
    catalogImportAssertSame(
        $attemptStartedAt->format(DATE_ATOM),
        $firstAttemptBatch->item($recoveryItemId)->processingStartedAt?->format(DATE_ATOM),
        'A processing claim should persist its lease start time.'
    );

    $beforeLeaseExpiry = $repository->recoverStaleProcessing(
        $recoveryBatch->id,
        $attemptStartedAt->modify('+299 seconds')
    );
    catalogImportAssertSame('processing', $beforeLeaseExpiry->item($recoveryItemId)->status, 'An active lease must not be reclaimed before its fixed expiry.');
    $leaseExpiredAt = $attemptStartedAt->modify('+300 seconds');
    $recoveredBatch = $repository->recoverStaleProcessing($recoveryBatch->id, $leaseExpiredAt);
    catalogImportAssertSame('queued', $recoveredBatch->item($recoveryItemId)->status, 'An expired processing lease should return an item with attempts remaining to the queue.');
    catalogImportAssertSame(1, $recoveredBatch->item($recoveryItemId)->attempts, 'Recovering a crashed attempt must retain its attempt count.');
    catalogImportAssertSame(null, $recoveredBatch->item($recoveryItemId)->processingStartedAt, 'A recovered queued item must not retain an active lease.');

    $secondAttemptBatch = $repository->markProcessing($recoveryBatch->id, $recoveryItemId, $leaseExpiredAt);
    $secondAttempt = $secondAttemptBatch->item($recoveryItemId)->attempts;
    catalogImportAssertSame(2, $secondAttempt, 'Reclaiming a crashed item should create a new attempt generation.');
    catalogImportAssertThrows(
        static fn () => $repository->markSucceeded(
            $recoveryBatch->id,
            $recoveryItemId,
            $firstAttempt,
            catalogImportSyntheticSnapshot('amazon_jp', 'B0KURANEA4', 'https://www.amazon.co.jp/dp/B0KURANEA4')
        ),
        'An old worker must not complete a newer processing attempt.',
        LogicException::class
    );
    catalogImportAssertThrows(
        static fn () => $repository->markFailed(
            $recoveryBatch->id,
            $recoveryItemId,
            $firstAttempt,
            CatalogImportBatchItem::FAILURE_FETCH_FAILED
        ),
        'An old worker must not fail a newer processing attempt.',
        LogicException::class
    );
    $completedSecondAttempt = $repository->markSucceeded(
        $recoveryBatch->id,
        $recoveryItemId,
        $secondAttempt,
        catalogImportSyntheticSnapshot('amazon_jp', 'B0KURANEA4', 'https://www.amazon.co.jp/dp/B0KURANEA4')
    );
    catalogImportAssertSame('succeeded', $completedSecondAttempt->item($recoveryItemId)->status, 'The current worker should still be able to complete its own attempt.');

    $retryLimitBatch = $repository->create(['https://www.amazon.co.jp/dp/B0KURANEA5']);
    $retryLimitItemId = $retryLimitBatch->items[0]->id;
    for ($attemptNumber = 1; $attemptNumber <= 3; ++$attemptNumber) {
        $startedAt = (new DateTimeImmutable('2026-10-25T11:00:00+00:00'))->modify('+' . (($attemptNumber - 1) * 600) . ' seconds');
        $retryLimitBatch = $repository->markProcessing($retryLimitBatch->id, $retryLimitItemId, $startedAt);
        catalogImportAssertSame($attemptNumber, $retryLimitBatch->item($retryLimitItemId)->attempts, 'Every processing start should count toward the fixed total attempt limit.');
        if ($attemptNumber === 3) {
            $retryLimitBatch = $repository->recoverStaleProcessing($retryLimitBatch->id, $startedAt->modify('+300 seconds'));
            catalogImportAssertSame('failed', $retryLimitBatch->item($retryLimitItemId)->status, 'A crashed final attempt should become a terminal failure.');
            catalogImportAssertSame(CatalogImportBatchItem::FAILURE_PROCESSING_FAILED, $retryLimitBatch->item($retryLimitItemId)->failureCategory, 'A crashed final attempt should use a fixed safe failure category.');
            break;
        }
        $retryLimitBatch = $repository->markFailed($retryLimitBatch->id, $retryLimitItemId, $attemptNumber, CatalogImportBatchItem::FAILURE_FETCH_FAILED);
        $retryLimitBatch = $repository->retryFailedItems($retryLimitBatch->id);
        catalogImportAssertSame('queued', $retryLimitBatch->item($retryLimitItemId)->status, 'Failed items below the attempt limit should remain retryable.');
    }
    $exhaustedRetryBatch = $repository->retryFailedItems($retryLimitBatch->id);
    catalogImportAssertSame('failed', $exhaustedRetryBatch->item($retryLimitItemId)->status, 'The retry operation must leave an exhausted item failed.');
    catalogImportAssertSame(3, $exhaustedRetryBatch->item($retryLimitItemId)->attempts, 'Exhausting retries must never increase the attempt count.');

    $legacyRecoveryDirectory = $temporaryRoot . '/legacy-processing-private';
    mkdir($legacyRecoveryDirectory, 0700, true);
    $legacyProcessingBatch = CatalogImportBatch::fromUrls(
        ['https://www.amazon.co.jp/dp/B0KURANEA6'],
        new DateTimeImmutable('2026-10-25T09:00:00+00:00')
    );
    $legacyProcessingBatch = $legacyProcessingBatch->markProcessing(
        $legacyProcessingBatch->items[0]->id,
        new DateTimeImmutable('2026-10-25T09:01:00+00:00')
    );
    $legacyProcessingData = $legacyProcessingBatch->toArray();
    unset($legacyProcessingData['items'][0]['processingStartedAt']);
    $legacyBatchPath = $legacyRecoveryDirectory . '/catalog-import-batches.json';
    file_put_contents($legacyBatchPath, json_encode([
        'schemaVersion' => 1,
        'batches' => [$legacyProcessingBatch->id => $legacyProcessingData],
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));
    $legacyRecoveryRepository = new JsonFileCatalogImportBatchRepository($legacyRecoveryDirectory, $shopRoot);
    $legacyRecoveredBatch = $legacyRecoveryRepository->recoverStaleProcessing(
        $legacyProcessingBatch->id,
        new DateTimeImmutable('2026-10-25T09:02:00+00:00')
    );
    catalogImportAssertSame('queued', $legacyRecoveredBatch->items[0]->status, 'A legacy processing item without lease metadata should be safely treated as stale.');

    $countLimitDirectory = $temporaryRoot . '/batch-count-limit-private';
    mkdir($countLimitDirectory, 0700, true);
    $fullBatchMap = [];
    for ($index = 0; $index < JsonFileCatalogImportBatchRepository::MAX_BATCHES; ++$index) {
        $productId = 'B' . str_pad((string) $index, 9, '0', STR_PAD_LEFT);
        $seedBatch = CatalogImportBatch::fromUrls(['https://www.amazon.co.jp/dp/' . $productId]);
        $fullBatchMap[$seedBatch->id] = $seedBatch->toArray();
    }
    $countLimitPath = $countLimitDirectory . '/catalog-import-batches.json';
    file_put_contents($countLimitPath, json_encode([
        'schemaVersion' => 1,
        'batches' => (object) $fullBatchMap,
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));
    $countLimitBefore = file_get_contents($countLimitPath);
    $countLimitRepository = new JsonFileCatalogImportBatchRepository($countLimitDirectory, $shopRoot);
    catalogImportAssertThrows(
        static fn () => $countLimitRepository->create(['https://www.amazon.co.jp/dp/B999999999']),
        'Creating a batch at the fixed batch-count limit must fail without pruning stored batches.',
        RuntimeException::class
    );
    catalogImportAssertSame($countLimitBefore, file_get_contents($countLimitPath), 'A rejected batch-count overflow must leave every existing record byte-for-byte unchanged.');

    $sizeLimitDirectory = $temporaryRoot . '/batch-size-limit-private';
    mkdir($sizeLimitDirectory, 0700, true);
    $sizeLimitPath = $sizeLimitDirectory . '/catalog-import-batches.json';
    $sizeLimitHandle = fopen($sizeLimitPath, 'wb');
    if ($sizeLimitHandle === false) {
        throw new RuntimeException('Could not create the oversized catalog batch fixture.');
    }
    $sizeLimitWritten = fwrite($sizeLimitHandle, '{"schemaVersion":1,"batches":{}}');
    $sizeLimitTruncated = ftruncate($sizeLimitHandle, JsonFileCatalogImportBatchRepository::MAX_STORAGE_BYTES + 1);
    fclose($sizeLimitHandle);
    if ($sizeLimitWritten === false || !$sizeLimitTruncated) {
        throw new RuntimeException('Could not create the oversized catalog batch fixture.');
    }
    $oversizedFileHash = hash_file('sha256', $sizeLimitPath);
    $sizeLimitRepository = new JsonFileCatalogImportBatchRepository($sizeLimitDirectory, $shopRoot);
    catalogImportAssertThrows(
        static fn () => $sizeLimitRepository->create(['https://www.amazon.co.jp/dp/B999999998']),
        'Reading a catalog batch file above the fixed storage limit must fail closed before accepting new work.',
        RuntimeException::class
    );
    catalogImportAssertSame(JsonFileCatalogImportBatchRepository::MAX_STORAGE_BYTES + 1, filesize($sizeLimitPath), 'A rejected storage-size overflow must preserve the original file size.');
    catalogImportAssertSame($oversizedFileHash, hash_file('sha256', $sizeLimitPath), 'A rejected storage-size overflow must leave the existing file unchanged.');

    $legacyDirectory = $temporaryRoot . '/legacy-private';
    mkdir($legacyDirectory, 0700, true);
    $legacyPath = $legacyDirectory . '/catalog-import-batches.json';
    $legacyContent = '{"schemaVersion":0,"batches":{"obsolete":{"raw":"do-not-overwrite"}}}';
    file_put_contents($legacyPath, $legacyContent);
    $legacyRepository = new JsonFileCatalogImportBatchRepository($legacyDirectory, $shopRoot);
    catalogImportAssertThrows(
        static fn () => $legacyRepository->create(['https://www.amazon.co.jp/dp/B0KURANEA3']),
        'Unsupported older schemas must fail closed rather than overwrite stored batches.',
        RuntimeException::class
    );
    catalogImportAssertSame($legacyContent, file_get_contents($legacyPath), 'Unsupported schema contents must remain byte-for-byte unchanged.');

    // Capacity failures must be rejected before the review queue side effect.
    $capacityDirectory = $temporaryRoot . '/completion-capacity-private';
    mkdir($capacityDirectory, 0700, true);
    $capacityRepository = new JsonFileCatalogImportBatchRepository($capacityDirectory, $shopRoot, 4096);
    $capacityBatch = $capacityRepository->create(['https://www.amazon.co.jp/dp/B0KURANEA8']);
    $capacityItem = $capacityBatch->items[0];
    $capacityRepository->markProcessing(
        $capacityBatch->id,
        $capacityItem->id,
        new DateTimeImmutable('2026-10-25T12:00:00.100000+00:00')
    );
    $oversizedData = catalogImportSyntheticSnapshot(
        'amazon_jp',
        'B0KURANEA8',
        'https://www.amazon.co.jp/dp/B0KURANEA8'
    )->toArray();
    $oversizedData['description'] = str_repeat('x', 8192);
    $oversizedData['contentHash'] = hash('sha256', $oversizedData['description']);
    $oversizedSnapshot = NormalizedProductSnapshot::fromArray($oversizedData);
    $capacityPath = $capacityDirectory . '/catalog-import-batches.json';
    $beforeCapacityCompletion = file_get_contents($capacityPath);
    $reviewCommitCalls = 0;
    catalogImportAssertThrows(static function () use (
        $capacityRepository,
        $capacityBatch,
        $capacityItem,
        $oversizedSnapshot,
        &$reviewCommitCalls
    ): void {
        $capacityRepository->completeWithReviewSnapshot(
            $capacityBatch->id,
            $capacityItem->id,
            1,
            $oversizedSnapshot,
            static function () use (&$reviewCommitCalls): void { ++$reviewCommitCalls; }
        );
    }, 'Oversized success state must be rejected before queue mutation.', RuntimeException::class);
    catalogImportAssertSame(0, $reviewCommitCalls, 'A rejected oversized batch must not commit the review snapshot.');
    catalogImportAssertSame($beforeCapacityCompletion, file_get_contents($capacityPath),
        'A rejected completion must preserve batch storage bytes and processing state.');
    $capacityReload = (new JsonFileCatalogImportBatchRepository($capacityDirectory, $shopRoot, 4096))
        ->find($capacityBatch->id);
    catalogImportAssertSame(CatalogImportBatchItem::STATUS_PROCESSING, $capacityReload?->item($capacityItem->id)->status,
        'The same processing attempt should remain available for a safe retry.');

    // The exact size boundary must succeed. A callback failure must leave the
    // processing batch byte-for-byte unchanged so the same attempt can retry.
    $completionUrl = 'https://www.amazon.co.jp/dp/B0KURANEA9';
    $completionSnapshot = catalogImportSyntheticSnapshot('amazon_jp', 'B0KURANEA9', $completionUrl);
    $createdAt = new DateTimeImmutable('2026-10-25T12:00:00+00:00');
    $processingAt = new DateTimeImmutable('2026-10-25T12:01:00.123456+00:00');

    $sizingDirectory = $temporaryRoot . '/completion-sizing-private';
    mkdir($sizingDirectory, 0700, true);
    $sizingRepository = new JsonFileCatalogImportBatchRepository($sizingDirectory, $shopRoot, 65536);
    $sizingBatch = $sizingRepository->create([$completionUrl], $createdAt);
    $sizingItemId = $sizingBatch->items[0]->id;
    $sizingRepository->markProcessing($sizingBatch->id, $sizingItemId, $processingAt);
    $beforeCallbackFailure = file_get_contents($sizingDirectory . '/catalog-import-batches.json');
    catalogImportAssertThrows(static function () use (
        $sizingRepository,
        $sizingBatch,
        $sizingItemId,
        $completionSnapshot
    ): void {
        $sizingRepository->completeWithReviewSnapshot(
            $sizingBatch->id,
            $sizingItemId,
            1,
            $completionSnapshot,
            static function (): void { throw new RuntimeException('synthetic queue callback failure'); }
        );
    }, 'A review-queue callback failure must be propagated before the batch is completed.', RuntimeException::class);
    $afterCallbackFailure = file_get_contents($sizingDirectory . '/catalog-import-batches.json');
    catalogImportAssertSame($beforeCallbackFailure, $afterCallbackFailure,
        'A failed queue callback must leave the batch processing state byte-for-byte unchanged.');

    $sizingCallbackCalls = 0;
    $sizingRepository->completeWithReviewSnapshot(
        $sizingBatch->id,
        $sizingItemId,
        1,
        $completionSnapshot,
        static function () use (&$sizingCallbackCalls): void { ++$sizingCallbackCalls; }
    );
    $exactStorageLimit = filesize($sizingDirectory . '/catalog-import-batches.json');
    catalogImportAssertTrue(is_int($exactStorageLimit) && $exactStorageLimit > 0,
        'The sizing completion must produce a readable serialized byte length.');
    catalogImportAssertSame(1, $sizingCallbackCalls, 'A successful queue callback should run exactly once.');

    $exactDirectory = $temporaryRoot . '/completion-exact-limit-private';
    mkdir($exactDirectory, 0700, true);
    $exactRepository = new JsonFileCatalogImportBatchRepository($exactDirectory, $shopRoot, $exactStorageLimit);
    $exactBatch = $exactRepository->create([$completionUrl], $createdAt);
    $exactItemId = $exactBatch->items[0]->id;
    $exactRepository->markProcessing($exactBatch->id, $exactItemId, $processingAt);
    $exactCallbackCalls = 0;
    $exactCompleted = $exactRepository->completeWithReviewSnapshot(
        $exactBatch->id,
        $exactItemId,
        1,
        $completionSnapshot,
        static function () use (&$exactCallbackCalls): void { ++$exactCallbackCalls; }
    );
    catalogImportAssertSame($exactStorageLimit, filesize($exactDirectory . '/catalog-import-batches.json'),
        'A completion whose serialized state exactly meets the fixed byte cap must be committed.');
    catalogImportAssertSame(1, $exactCallbackCalls, 'The exact-cap queue callback should run exactly once.');
    catalogImportAssertSame(CatalogImportBatchItem::STATUS_SUCCEEDED,
        $exactCompleted->item($exactItemId)->status, 'The exact-cap batch should persist success.');
} finally {
    catalogImportRemoveTree($temporaryRoot);
}

echo "PASS: bounded catalog import batch repository\n";
