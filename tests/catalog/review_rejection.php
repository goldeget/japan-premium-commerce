<?php

declare(strict_types=1);

use Kuranea\Catalog\Domain\ProductReviewQueue;
use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Infrastructure\Persistence\JsonFileProductReviewQueueRepository;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

function assertCatalogRejectionSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertCatalogRejectionTrue(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

function assertCatalogRejectionThrows(string $class, callable $callback, string $message): Throwable
{
    try {
        $callback();
    } catch (Throwable $exception) {
        if ($exception instanceof $class) {
            return $exception;
        }
        throw new RuntimeException($message . '; got ' . $exception::class, 0, $exception);
    }

    throw new RuntimeException($message . '; no exception was thrown');
}

$fixturePath = __DIR__ . '/fixtures/amazon-jp-product.synthetic.html';
$fixtureHtml = file_get_contents($fixturePath);
if ($fixtureHtml === false) {
    throw new RuntimeException('Could not read the synthetic catalog fixture for rejection tests.');
}
$fetchedAt = new DateTimeImmutable('2026-10-25T12:00:00+00:00');
$snapshot = (new AmazonJapanHtmlParser())->parse(
    $fixtureHtml,
    'https://www.amazon.co.jp/dp/B0KURANEA1',
    $fetchedAt
);
$changedSnapshot = (new AmazonJapanHtmlParser())->parse(
    str_replace('"price": "5980"', '"price": "5990"', $fixtureHtml),
    'https://www.amazon.co.jp/dp/B0KURANEA1',
    $fetchedAt->modify('+1 day')
);
$reviewedAt = new DateTimeImmutable('2026-10-25T13:30:00+00:00');
$reason = '商品名と掲載内容が一致しません。';

$queue = new ProductReviewQueue();
$pending = $queue->enqueue($snapshot, $fetchedAt);
$rejected = $queue->rejectIfPending(
    $snapshot->deduplicationKey,
    $snapshot->contentHash,
    ' employee:42 ',
    $reviewedAt,
    ' ' . $reason . ' '
);
assertCatalogRejectionTrue($rejected !== null, 'A named reviewer should be able to reject the exact pending snapshot.');
assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_REJECTED, $rejected->status, 'A valid review decision should persist the rejected state.');
assertCatalogRejectionSame('rejected', $rejected->snapshot->approvalStatus, 'The normalized snapshot should record the rejected state.');
assertCatalogRejectionSame('employee:42', $rejected->rejectedBy, 'The rejection should retain the trimmed reviewer identity.');
assertCatalogRejectionSame($reason, $rejected->rejectionReason, 'The rejection should retain the trimmed reason.');
assertCatalogRejectionSame('UTC', $rejected->rejectedAt?->getTimezone()->getName(), 'The rejection timestamp should be stored in UTC.');
assertCatalogRejectionSame($snapshot->contentHash, $rejected->snapshot->contentHash, 'Rejection should preserve the snapshot content hash.');
$recentMemoryDecisions = $queue->recentReviewed();
assertCatalogRejectionSame([$snapshot->deduplicationKey], array_map(
    static fn (ProductReviewQueueEntry $entry): string => $entry->idempotencyKey,
    $recentMemoryDecisions
), 'The in-memory review queue should expose terminal decisions through the same bounded history API.');
$expectedSnapshot = $pending->snapshot->toArray();
$expectedSnapshot['approvalStatus'] = 'rejected';
assertCatalogRejectionSame($expectedSnapshot, $rejected->snapshot->toArray(), 'Rejection should preserve every source snapshot field.');
assertCatalogRejectionSame(0, count($queue->pending()), 'Rejected entries must leave the pending review list.');
assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_REJECTED, $queue->enqueue($snapshot, $fetchedAt)->status, 'Re-importing identical rejected content must not reopen the decision.');
assertCatalogRejectionSame(null, $queue->rejectIfPending(
    $snapshot->deduplicationKey,
    $snapshot->contentHash,
    'employee:43',
    $reviewedAt->modify('+1 minute'),
    'A second decision must not replace the rejection.'
), 'A rejected item must not accept a second rejection.');
assertCatalogRejectionSame(null, $queue->approveIfPending(
    $snapshot->deduplicationKey,
    $snapshot->contentHash,
    7001,
    'employee:43',
    $reviewedAt
), 'A rejected item must not be approved.');
assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_REJECTED, $queue->find($snapshot->deduplicationKey)?->status, 'Blocked replay attempts must leave the rejection unchanged.');

$staleQueue = new ProductReviewQueue();
$staleQueue->enqueue($snapshot, $fetchedAt);
$latestPending = $staleQueue->enqueue($changedSnapshot, $fetchedAt->modify('+1 day'));
assertCatalogRejectionSame(null, $staleQueue->rejectIfPending(
    $snapshot->deduplicationKey,
    $snapshot->contentHash,
    'employee:42',
    $reviewedAt,
    $reason
), 'A stale content hash must not reject a newer queued snapshot.');
assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_PENDING, $staleQueue->find($snapshot->deduplicationKey)?->status, 'Stale rejection must leave the newer version pending.');
assertCatalogRejectionSame($latestPending->snapshot->contentHash, $staleQueue->find($snapshot->deduplicationKey)?->snapshot->contentHash, 'Stale rejection must preserve the newer content hash.');

$approvedQueue = new ProductReviewQueue();
$approvedQueue->enqueue($snapshot, $fetchedAt);
$approved = $approvedQueue->approveIfPending(
    $snapshot->deduplicationKey,
    $snapshot->contentHash,
    7002,
    'employee:42',
    $reviewedAt
);
assertCatalogRejectionTrue($approved !== null, 'The approval boundary fixture should reach approved state.');
assertCatalogRejectionSame([$snapshot->deduplicationKey], array_map(
    static fn (ProductReviewQueueEntry $entry): string => $entry->idempotencyKey,
    $approvedQueue->recentReviewed()
), 'The in-memory review queue history should include a persisted approval.');
assertCatalogRejectionSame(null, $approvedQueue->rejectIfPending(
    $snapshot->deduplicationKey,
    $snapshot->contentHash,
    'employee:43',
    $reviewedAt,
    $reason
), 'An approved item must not be rejected.');
assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_APPROVED, $approvedQueue->find($snapshot->deduplicationKey)?->status, 'A rejected transition must not replace an approval.');

foreach ([
    'empty reviewer' => static fn (ProductReviewQueue $target) => $target->rejectIfPending($snapshot->deduplicationKey, $snapshot->contentHash, '  ', $reviewedAt, $reason),
    'empty reason' => static fn (ProductReviewQueue $target) => $target->rejectIfPending($snapshot->deduplicationKey, $snapshot->contentHash, 'employee:42', $reviewedAt, " \t "),
    'oversized reason' => static fn (ProductReviewQueue $target) => $target->rejectIfPending($snapshot->deduplicationKey, $snapshot->contentHash, 'employee:42', $reviewedAt, str_repeat('界', 2001)),
    'non-UTC timestamp' => static fn (ProductReviewQueue $target) => $target->rejectIfPending($snapshot->deduplicationKey, $snapshot->contentHash, 'employee:42', new DateTimeImmutable('2026-10-25T22:30:00+09:00'), $reason),
] as $case => $reject) {
    $validationQueue = new ProductReviewQueue();
    $validationQueue->enqueue($snapshot, $fetchedAt);
    assertCatalogRejectionThrows(InvalidArgumentException::class, static fn () => $reject($validationQueue), 'Rejection must reject ' . $case . '.');
    assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_PENDING, $validationQueue->find($snapshot->deduplicationKey)?->status, 'Invalid rejection metadata must leave the entry pending.');
}

$queueDirectory = sys_get_temp_dir() . '/kuranea-catalog-rejection-' . bin2hex(random_bytes(8));
if (!mkdir($queueDirectory, 0700) && !is_dir($queueDirectory)) {
    throw new RuntimeException('Could not create an isolated catalog rejection directory.');
}

try {
    $queuePath = $queueDirectory . '/review-queue.json';
    $persistentQueue = new JsonFileProductReviewQueueRepository($queuePath);
    $persistentQueue->enqueue($snapshot, $fetchedAt);
    assertCatalogRejectionSame(null, $persistentQueue->rejectIfPending(
        $snapshot->deduplicationKey,
        'stale-content-hash',
        'employee:42',
        $reviewedAt,
        $reason
    ), 'The JSON repository must reject a stale content hash without changing the queue.');
    $persistedRejection = $persistentQueue->rejectIfPending(
        $snapshot->deduplicationKey,
        $snapshot->contentHash,
        'employee:42',
        $reviewedAt,
        $reason
    );
    assertCatalogRejectionTrue($persistedRejection !== null, 'The JSON repository should reject an exact pending snapshot.');
    $reopenedQueue = new JsonFileProductReviewQueueRepository($queuePath);
    $restoredRejection = $reopenedQueue->find($snapshot->deduplicationKey);
    assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_REJECTED, $restoredRejection?->status, 'Rejected state should survive a JSON repository reload.');
    assertCatalogRejectionSame('employee:42', $restoredRejection?->rejectedBy, 'Reviewer identity should survive a JSON repository reload.');
    assertCatalogRejectionSame($reason, $restoredRejection?->rejectionReason, 'Rejection reason should survive a JSON repository reload.');
    assertCatalogRejectionSame($reviewedAt->format('Y-m-d\TH:i:sP'), $restoredRejection?->rejectedAt?->format('Y-m-d\TH:i:sP'), 'UTC rejection time should survive a JSON repository reload.');
    assertCatalogRejectionSame($snapshot->contentHash, $restoredRejection?->snapshot->contentHash, 'The source content hash should survive a JSON repository reload.');

    $approvedHistorySnapshot = (new AmazonJapanHtmlParser())->parse(
        $fixtureHtml,
        'https://www.amazon.co.jp/dp/B0KURANEA2',
        $fetchedAt->modify('+1 minute')
    );
    $pendingHistorySnapshot = (new AmazonJapanHtmlParser())->parse(
        $fixtureHtml,
        'https://www.amazon.co.jp/dp/B0KURANEA3',
        $fetchedAt->modify('+2 minutes')
    );
    $historyApprovalTime = $reviewedAt->modify('+1 hour');
    $historyPending = $persistentQueue->enqueue($approvedHistorySnapshot, $fetchedAt->modify('+1 minute'));
    $historyApproval = $persistentQueue->approveIfPending(
        $historyPending->idempotencyKey,
        $historyPending->snapshot->contentHash,
        8202,
        'employee:43',
        $historyApprovalTime
    );
    assertCatalogRejectionTrue($historyApproval !== null, 'History fixture approval should persist before a fresh repository read.');
    $persistentQueue->enqueue($pendingHistorySnapshot, $fetchedAt->modify('+2 minutes'));

    $historyBeforeRead = file_get_contents($queuePath);
    $reviewHistory = (new JsonFileProductReviewQueueRepository($queuePath))->recentReviewed(2);
    assertCatalogRejectionSame(
        [$historyPending->idempotencyKey, $snapshot->deduplicationKey],
        array_map(static fn (ProductReviewQueueEntry $entry): string => $entry->idempotencyKey, $reviewHistory),
        'Fresh review history should return approved and rejected decisions newest-first, excluding pending entries.'
    );
    assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_APPROVED, $reviewHistory[0]->status, 'Review history should retain the approved state.');
    assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_REJECTED, $reviewHistory[1]->status, 'Review history should retain the rejected state.');
    assertCatalogRejectionSame([$historyPending->idempotencyKey], array_map(
        static fn (ProductReviewQueueEntry $entry): string => $entry->idempotencyKey,
        $reopenedQueue->recentReviewed(1)
    ), 'The history limit should be enforced after reopening the repository.');
    assertCatalogRejectionSame($historyBeforeRead, file_get_contents($queuePath), 'Reading review history must not mutate persisted decisions.');
    assertCatalogRejectionThrows(InvalidArgumentException::class, static fn () => $persistentQueue->recentReviewed(0), 'Review history must reject a zero limit.');
    assertCatalogRejectionThrows(InvalidArgumentException::class, static fn () => $persistentQueue->recentReviewed(51), 'Review history must reject a limit above the hard cap.');

    $legacyQueuePath = $queueDirectory . '/legacy-queue.json';
    $legacyEntry = $pending->toArray();
    unset($legacyEntry['rejectedBy'], $legacyEntry['rejectedAt'], $legacyEntry['rejectionReason']);
    $approvedLegacySnapshot = (new AmazonJapanHtmlParser())->parse(
        file_get_contents(__DIR__ . '/fixtures/amazon-jp-og-fallback.synthetic.html') ?: '',
        'https://www.amazon.co.jp/dp/B0KURANEA2',
        $fetchedAt
    );
    $approvedLegacy = (new ProductReviewQueue())->enqueue($approvedLegacySnapshot, $fetchedAt)
        ->approve(8100, 'legacy-reviewer', $reviewedAt)
        ->toArray();
    unset($approvedLegacy['rejectedBy'], $approvedLegacy['rejectedAt'], $approvedLegacy['rejectionReason']);
    $legacyDocument = json_encode([
        'schemaVersion' => 1,
        'entries' => [
            $pending->idempotencyKey => $legacyEntry,
            $approvedLegacy['idempotencyKey'] => $approvedLegacy,
        ],
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
    file_put_contents($legacyQueuePath, $legacyDocument);
    $legacyQueue = new JsonFileProductReviewQueueRepository($legacyQueuePath);
    $legacyEntryRestored = $legacyQueue->find($pending->idempotencyKey);
    assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_PENDING, $legacyEntryRestored?->status, 'An old schema-version-one pending entry should remain readable.');
    assertCatalogRejectionSame(null, $legacyEntryRestored?->rejectedBy, 'Old queue entries should default to no rejection reviewer.');
    assertCatalogRejectionSame(null, $legacyEntryRestored?->rejectedAt, 'Old queue entries should default to no rejection timestamp.');
    assertCatalogRejectionSame(null, $legacyEntryRestored?->rejectionReason, 'Old queue entries should default to no rejection reason.');
    $legacyApprovedRestored = $legacyQueue->find($approvedLegacy['idempotencyKey']);
    assertCatalogRejectionSame(ProductReviewQueueEntry::STATUS_APPROVED, $legacyApprovedRestored?->status, 'An old schema-version-one approved entry should remain readable.');
    assertCatalogRejectionSame('legacy-reviewer', $legacyApprovedRestored?->approvedBy, 'Legacy approval metadata should remain readable with absent rejection fields.');

    $corruptQueuePath = $queueDirectory . '/corrupt-rejection-queue.json';
    $corruptEntry = $persistedRejection->toArray();
    $corruptEntry['rejectionReason'] = '   ';
    $corruptDocument = json_encode([
        'schemaVersion' => 1,
        'entries' => [$persistedRejection->idempotencyKey => $corruptEntry],
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
    file_put_contents($corruptQueuePath, $corruptDocument);
    $corruptQueue = new JsonFileProductReviewQueueRepository($corruptQueuePath);
    assertCatalogRejectionThrows(RuntimeException::class, static fn () => $corruptQueue->find($snapshot->deduplicationKey), 'Corrupt rejection metadata should fail closed.');
    assertCatalogRejectionSame($corruptDocument, file_get_contents($corruptQueuePath), 'Corrupt rejection data must not be overwritten after a read error.');
} finally {
    foreach (glob($queueDirectory . '/*') ?: [] as $queueFile) {
        unlink($queueFile);
    }
    rmdir($queueDirectory);
}

echo "PASS: one-way catalog review rejection, persistence, and legacy JSON compatibility checks\n";
