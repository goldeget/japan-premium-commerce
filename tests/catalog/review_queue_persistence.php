<?php

declare(strict_types=1);

use Kuranea\Catalog\Domain\ProductImageRightsEvidence;
use Kuranea\Catalog\Domain\ProductImportReviewEvidence;
use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Infrastructure\Persistence\JsonFileProductReviewQueueRepository;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

$assertQueuePersistence = static function (bool $condition, string $message): void {
    if (!$condition) {
        throw new RuntimeException($message);
    }
};

$fixturePath = __DIR__ . '/fixtures/amazon-jp-product.synthetic.html';
$fixtureHtml = file_get_contents($fixturePath);
if ($fixtureHtml === false) {
    throw new RuntimeException('Could not read the synthetic catalog fixture for JSON persistence checks.');
}

$fetchedAt = new DateTimeImmutable('2026-10-25T02:00:00+00:00');
$reviewedAt = new DateTimeImmutable('2026-10-25T02:05:00+00:00');
$parser = new AmazonJapanHtmlParser();
$originalSnapshot = $parser->parse(
    $fixtureHtml,
    'https://www.amazon.co.jp/dp/B0KURANEA1',
    $fetchedAt
);
$changedSnapshot = $parser->parse(
    str_replace('"price": "5980"', '"price": "5990"', $fixtureHtml),
    'https://www.amazon.co.jp/dp/B0KURANEA1',
    $fetchedAt->modify('+1 day')
);

$queueDirectory = sys_get_temp_dir() . '/ordenowa-queue-persistence-' . bin2hex(random_bytes(8));
if (!mkdir($queueDirectory, 0700) && !is_dir($queueDirectory)) {
    throw new RuntimeException('Could not create a private temporary queue directory for JSON persistence checks.');
}
$queuePath = $queueDirectory . '/review-queue.json';

try {
    $queue = new JsonFileProductReviewQueueRepository($queuePath);
    $queued = $queue->enqueue($originalSnapshot, $fetchedAt);
    $imageEvidence = ProductImageRightsEvidence::record(
        'licensed',
        'CI synthetic license evidence',
        'employee:1',
        $reviewedAt,
        [51, 52]
    );
    $importEvidence = new ProductImportReviewEvidence(
        1560,
        4,
        'taxable',
        'CI synthetic tax review',
        2,
        [7, 8],
        true,
        ['en', 'ko'],
        $originalSnapshot->contentHash
    );
    $approved = $queue->approveIfPending(
        $queued->idempotencyKey,
        $originalSnapshot->contentHash,
        7301,
        'employee:1',
        $reviewedAt,
        $imageEvidence,
        $importEvidence
    );
    $assertQueuePersistence($approved !== null && $approved->status === ProductReviewQueueEntry::STATUS_APPROVED,
        'The exact pending catalog snapshot should transition to approved for persistence setup.');
    $assertQueuePersistence($queue->containsLinkedNativeProduct(7301),
        'Queue lookup should retain imported product origin after an approval.');

    $changed = $queue->enqueue($changedSnapshot, $fetchedAt->modify('+1 day'));
    $assertQueuePersistence($changed->status === ProductReviewQueueEntry::STATUS_PENDING,
        'Changed source content should return to pending review.');
    $assertQueuePersistence($changed->linkedProductId === 7301,
        'Changed content should remain linked to its existing native draft.');
    $assertQueuePersistence($changed->previousSnapshot?->contentHash === $originalSnapshot->contentHash,
        'Changed content should retain its previous snapshot for comparison.');
    $assertQueuePersistence($changed->importReviewEvidence === null,
        'Commercial review evidence from an older source revision must not be attached to the changed snapshot.');

    $reloaded = (new JsonFileProductReviewQueueRepository($queuePath))->find($changed->idempotencyKey);
    $assertQueuePersistence($reloaded !== null, 'A new JSON repository instance should reload the changed queue entry.');
    $assertQueuePersistence($reloaded->status === ProductReviewQueueEntry::STATUS_PENDING,
        'The changed pending status should survive a JSON repository reload.');
    $assertQueuePersistence($reloaded->snapshot->contentHash === $changedSnapshot->contentHash,
        'The current source revision should survive a JSON repository reload.');
    $assertQueuePersistence($reloaded->previousSnapshot?->contentHash === $originalSnapshot->contentHash,
        'The previous source revision should survive a JSON repository reload.');
    $assertQueuePersistence($reloaded->linkedProductId === 7301,
        'The existing native draft link should survive a JSON repository reload.');
    $assertQueuePersistence($reloaded->imageRightsEvidence?->toArray() === $imageEvidence->toArray(),
        'Image rights evidence should survive a JSON repository reload.');
    $assertQueuePersistence($reloaded->importReviewEvidence === null,
        'Changed source content must remain without commercial review evidence for the new revision.');

    $recoverSnapshot = (new AmazonJapanHtmlParser())->parse(
        $fixtureHtml,
        'https://www.amazon.co.jp/dp/B0KURANEA2',
        $fetchedAt->modify('+2 days')
    );
    $recoverImportEvidence = new ProductImportReviewEvidence(
        1560,
        4,
        'taxable',
        'CI synthetic tax review',
        2,
        [7, 8],
        true,
        ['en', 'ko'],
        $recoverSnapshot->contentHash
    );
    $recoverablePending = $queue->enqueue($recoverSnapshot);
    $linkedBeforeApproval = $queue->linkDraftIfCurrent(
        $recoverablePending->idempotencyKey,
        $recoverablePending->snapshot->contentHash,
        7303,
        $imageEvidence,
        $recoverImportEvidence
    );
    $assertQueuePersistence($linkedBeforeApproval?->linkedProductId === 7303
        && $linkedBeforeApproval->imageRightsEvidence?->toArray() === $imageEvidence->toArray(),
        'Draft identity and persisted image review evidence should be recorded before approval.');
    $reopenedBeforeApproval = (new JsonFileProductReviewQueueRepository($queuePath))->find($recoverablePending->idempotencyKey);
    $assertQueuePersistence($reopenedBeforeApproval?->linkedProductId === 7303
        && $reopenedBeforeApproval->importReviewEvidence?->toArray() === $recoverImportEvidence->toArray(),
        'A native draft link should remain recoverable after a repository reload before approval.');
    $approvedAfterRecovery = (new JsonFileProductReviewQueueRepository($queuePath))->approveIfPending(
        $recoverablePending->idempotencyKey,
        $recoverablePending->snapshot->contentHash,
        7303,
        'employee:1',
        $reviewedAt
    );
    $assertQueuePersistence($approvedAfterRecovery?->nativeProductId === 7303
        && $approvedAfterRecovery->imageRightsEvidence?->toArray() === $imageEvidence->toArray(),
        'A later request should safely complete approval from the persisted draft link and image evidence.');
    $assertQueuePersistence($queue->containsLinkedNativeProduct(7303),
        'Stable imported origin lookup should include linked and approved drafts.');

    $orderingQueuePath = $queueDirectory . '/ordering-queue.json';
    $orderingQueue = new JsonFileProductReviewQueueRepository($orderingQueuePath);
    $observedAt1 = new DateTimeImmutable('2026-10-25T12:00:00.100000+00:00');
    $observedAt2 = new DateTimeImmutable('2026-10-25T12:00:00.200000+00:00');
    $observedAt3 = new DateTimeImmutable('2026-10-25T12:00:00.300000+00:00');
    $observedAt4 = new DateTimeImmutable('2026-10-25T12:00:00.400000+00:00');
    $orderedOriginal = $originalSnapshot->withFetchedAt($observedAt1);
    $orderingPending = $orderingQueue->enqueue($orderedOriginal);
    $orderingApproved = $orderingQueue->approveIfPending(
        $orderingPending->idempotencyKey,
        $orderedOriginal->contentHash,
        7302,
        'employee:1',
        $reviewedAt,
        $imageEvidence,
        $importEvidence
    );
    $assertQueuePersistence($orderingApproved !== null, 'The source-order fixture should begin from an approved snapshot.');
    $sameContentLater = $orderingQueue->enqueue($orderedOriginal->withFetchedAt($observedAt3));
    $assertQueuePersistence($sameContentLater->status === ProductReviewQueueEntry::STATUS_APPROVED
        && $sameContentLater->nativeProductId === 7302,
        'A newer observation with identical content must preserve the existing review decision and product link.');
    $orderedReload = (new JsonFileProductReviewQueueRepository($orderingQueuePath))->find($orderingPending->idempotencyKey);
    $assertQueuePersistence($orderedReload?->snapshot->fetchedAt == $observedAt3,
        'The subsecond source observation watermark must survive JSON reload.');
    $staleChanged = $changedSnapshot->withFetchedAt($observedAt2);
    $afterStaleChange = (new JsonFileProductReviewQueueRepository($orderingQueuePath))->enqueue($staleChanged);
    $assertQueuePersistence($afterStaleChange->status === ProductReviewQueueEntry::STATUS_APPROVED
        && $afterStaleChange->snapshot->contentHash === $orderedOriginal->contentHash,
        'An older different source snapshot must not replace a newer accepted observation.');
    $newerChanged = $changedSnapshot->withFetchedAt($observedAt4);
    $acceptedChange = (new JsonFileProductReviewQueueRepository($orderingQueuePath))->enqueue($newerChanged);
    $assertQueuePersistence($acceptedChange->status === ProductReviewQueueEntry::STATUS_PENDING
        && $acceptedChange->previousSnapshot?->fetchedAt == $observedAt3
        && $acceptedChange->linkedProductId === 7302
        && $acceptedChange->importReviewEvidence === null,
        'A newer source change should reopen review, preserve its draft link, and clear revision-specific commercial evidence.');
} finally {
    foreach (glob($queueDirectory . '/*') ?: [] as $queueFile) {
        unlink($queueFile);
    }
    rmdir($queueDirectory);
}

echo "PASS: changed-source queue links and staff review evidence survive JSON persistence\n";
