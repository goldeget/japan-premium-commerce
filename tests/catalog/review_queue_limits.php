<?php

declare(strict_types=1);

use Kuranea\Catalog\Infrastructure\Persistence\JsonFileProductReviewQueueRepository;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

$assertQueueLimit = static function (bool $condition, string $message): void {
    if (!$condition) {
        throw new RuntimeException($message);
    }
};
$rejectQueueLimit = static function (callable $operation) use ($assertQueueLimit): void {
    try {
        $operation();
    } catch (RuntimeException $exception) {
        $assertQueueLimit(str_contains($exception->getMessage(), 'limit'), 'Overflow must fail with a fixed limit error.');
        return;
    }
    throw new RuntimeException('An overflowing review queue operation must be rejected.');
};

$queueLimitHtml = file_get_contents(__DIR__ . '/fixtures/amazon-jp-product.synthetic.html');
if ($queueLimitHtml === false) {
    throw new RuntimeException('Could not read the synthetic fixture for queue limit checks.');
}
$queueLimitTime = new DateTimeImmutable('2026-10-25T12:00:00+00:00');
$queueLimitParser = new AmazonJapanHtmlParser();
$queueLimitFirst = $queueLimitParser->parse($queueLimitHtml, 'https://www.amazon.co.jp/dp/B0KURANEA1', $queueLimitTime);
$queueLimitSecond = $queueLimitParser->parse($queueLimitHtml, 'https://www.amazon.co.jp/dp/B0KURANEA2', $queueLimitTime);
$queueLimitChanged = $queueLimitParser->parse(
    str_replace('"price": "5980"', '"price": "5990"', $queueLimitHtml),
    'https://www.amazon.co.jp/dp/B0KURANEA1',
    $queueLimitTime->modify('+1 second')
);
$queueLimitDirectory = sys_get_temp_dir() . '/ordenowa-queue-limits-' . bin2hex(random_bytes(8));
$assertQueueLimit(mkdir($queueLimitDirectory, 0700), 'Could not create private queue limit fixtures.');

try {
    $assertQueueLimit(JsonFileProductReviewQueueRepository::MAX_ENTRIES === 5000, 'JSON review storage must declare its 5,000-entry cap.');
    $assertQueueLimit(JsonFileProductReviewQueueRepository::MAX_STORAGE_BYTES === 33554432, 'JSON review storage must declare its 32MiB cap.');

    $queueLimitCountPath = $queueLimitDirectory . '/count.json';
    $queueLimitCountRepository = new JsonFileProductReviewQueueRepository($queueLimitCountPath, maxEntries: 1);
    $queueLimitEntry = $queueLimitCountRepository->enqueue($queueLimitFirst, $queueLimitTime);
    $queueLimitOriginalBytes = file_get_contents($queueLimitCountPath);
    $assertQueueLimit(is_string($queueLimitOriginalBytes), 'The initial queue entry must be persisted.');
    $queueLimitCountRepository->enqueue($queueLimitFirst, $queueLimitTime);
    $assertQueueLimit(file_get_contents($queueLimitCountPath) === $queueLimitOriginalBytes, 'An identical import at capacity must preserve original bytes.');
    $rejectQueueLimit(static fn () => $queueLimitCountRepository->enqueue($queueLimitSecond, $queueLimitTime));
    $assertQueueLimit(file_get_contents($queueLimitCountPath) === $queueLimitOriginalBytes, 'Entry overflow must preserve original bytes.');
    $assertQueueLimit($queueLimitCountRepository->find($queueLimitSecond->deduplicationKey) === null, 'Rejected entries must not be persisted.');
    $queueLimitCountRepository->enqueue($queueLimitChanged, $queueLimitTime);
    $assertQueueLimit($queueLimitCountRepository->find($queueLimitFirst->deduplicationKey)?->snapshot->contentHash === $queueLimitChanged->contentHash,
        'Updating an existing identity at the entry cap must remain possible.');

    // The fixture is only a few KiB; inject its exact size instead of allocating 32MiB.
    $queueLimitBytePath = $queueLimitDirectory . '/bytes.json';
    $queueLimitExactBytes = strlen($queueLimitOriginalBytes);
    $queueLimitByteRepository = new JsonFileProductReviewQueueRepository($queueLimitBytePath, maxStorageBytes: $queueLimitExactBytes);
    $queueLimitByteRepository->enqueue($queueLimitFirst, $queueLimitTime);
    $assertQueueLimit(file_get_contents($queueLimitBytePath) === $queueLimitOriginalBytes, 'A write at the exact byte cap must succeed.');
    $queueLimitByteRepository->save($queueLimitEntry);
    $assertQueueLimit(file_get_contents($queueLimitBytePath) === $queueLimitOriginalBytes, 'A read and update at the exact byte cap must succeed.');
    $rejectQueueLimit(static fn () => $queueLimitByteRepository->enqueue($queueLimitSecond, $queueLimitTime));
    $rejectQueueLimit(static fn () => $queueLimitByteRepository->enqueue($queueLimitChanged, $queueLimitTime));
    $rejectQueueLimit(static fn () => $queueLimitByteRepository->save($queueLimitEntry->approve(21, 'employee:1', $queueLimitTime)));
    $assertQueueLimit(file_get_contents($queueLimitBytePath) === $queueLimitOriginalBytes, 'Oversized insert, source refresh, and approval updates must preserve original bytes.');
    $assertQueueLimit($queueLimitByteRepository->find($queueLimitFirst->deduplicationKey)?->status === 'pending', 'A rejected update must preserve the pending entry.');

    $queueLimitEmptyPath = $queueLimitDirectory . '/too-small.json';
    $queueLimitEmptyRepository = new JsonFileProductReviewQueueRepository($queueLimitEmptyPath, maxStorageBytes: 1);
    $rejectQueueLimit(static fn () => $queueLimitEmptyRepository->enqueue($queueLimitFirst, $queueLimitTime));
    $assertQueueLimit(!file_exists($queueLimitEmptyPath), 'A rejected first write must not create a queue file.');

    $queueLimitOversizedBytes = $queueLimitOriginalBytes . "\n";
    file_put_contents($queueLimitBytePath, $queueLimitOversizedBytes);
    $rejectQueueLimit(static fn () => $queueLimitByteRepository->find($queueLimitFirst->deduplicationKey));
    $assertQueueLimit(file_get_contents($queueLimitBytePath) === $queueLimitOversizedBytes, 'An existing oversized file must fail closed without changing its bytes.');

    $queueLimitLoadedPath = $queueLimitDirectory . '/loaded-count.json';
    $queueLimitLoadedRepository = new JsonFileProductReviewQueueRepository($queueLimitLoadedPath);
    $queueLimitLoadedRepository->enqueue($queueLimitFirst, $queueLimitTime);
    $queueLimitLoadedRepository->enqueue($queueLimitSecond, $queueLimitTime);
    $queueLimitLoadedBytes = file_get_contents($queueLimitLoadedPath);
    $queueLimitRestrictedRepository = new JsonFileProductReviewQueueRepository($queueLimitLoadedPath, maxEntries: 1);
    $rejectQueueLimit(static fn () => $queueLimitRestrictedRepository->enqueue($queueLimitChanged, $queueLimitTime));
    $assertQueueLimit(file_get_contents($queueLimitLoadedPath) === $queueLimitLoadedBytes, 'An existing excess entry count must fail closed without pruning records.');
    $assertQueueLimit(glob($queueLimitDirectory . '/.kuranea-catalog-queue-*') === [], 'Rejected writes must not leave temporary replacement files.');
} finally {
    foreach (glob($queueLimitDirectory . '/*') ?: [] as $queueLimitFile) {
        unlink($queueLimitFile);
    }
    rmdir($queueLimitDirectory);
}

echo "PASS: JSON review queue entry and byte caps preserve existing records on overflow\n";
