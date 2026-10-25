<?php

declare(strict_types=1);

use Kuranea\Catalog\Domain\CatalogImportBatchItem;
use Kuranea\Catalog\Domain\ProductReviewQueue;
use Kuranea\Catalog\Fetching\FetchException;
use Kuranea\Catalog\Fetching\FetchedProduct;
use Kuranea\Catalog\Fetching\ProductPageFetcherInterface;
use Kuranea\Catalog\Infrastructure\Persistence\JsonFileCatalogImportBatchRepository;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;
use Closure;

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';
require_once __DIR__ . '/../../modules/kuraneacatalog/src/Service/CatalogImportService.php';

function assertCatalogImportSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertCatalogImportTrue(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

final class CatalogImportFixtureFetcher implements ProductPageFetcherInterface
{
    /** @var array<string, string> */
    public array $documents = [];

    /** @var array<string, list<FetchException>> */
    public array $failures = [];

    /** @var list<string> */
    public array $requests = [];

    public ?Closure $afterRead = null;

    public function fetch(string $url): FetchedProduct
    {
        $this->requests[] = $url;
        if (($this->failures[$url] ?? []) !== []) {
            throw array_shift($this->failures[$url]);
        }
        if (!isset($this->documents[$url])) {
            throw new FetchException('private synthetic transport detail');
        }

        $body = $this->documents[$url];
        $afterRead = $this->afterRead;
        $this->afterRead = null;
        if ($afterRead !== null) {
            $afterRead($url);
        }

        return new FetchedProduct($url, $body, new DateTimeImmutable('2026-10-25T12:00:00+00:00'), 0);
    }
}

$root = realpath(__DIR__ . '/../..');
if ($root === false) {
    throw new RuntimeException('Could not resolve the isolated source root for catalog import tests.');
}
$privateDirectory = sys_get_temp_dir() . '/kuranea-catalog-import-service-' . bin2hex(random_bytes(8));
if (!mkdir($privateDirectory, 0700) && !is_dir($privateDirectory)) {
    throw new RuntimeException('Could not create isolated catalog batch storage.');
}

try {
    $amazonUrl = 'https://www.amazon.co.jp/dp/B0KURANEA1';
    $rakutenUrl = 'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/';
    $amazonHtml = file_get_contents(__DIR__ . '/fixtures/amazon-jp-product.synthetic.html');
    $rakutenHtml = file_get_contents(__DIR__ . '/fixtures/rakuten-product.synthetic.html');
    if (!is_string($amazonHtml) || !is_string($rakutenHtml)) {
        throw new RuntimeException('Could not read the checked-in synthetic catalog documents.');
    }

    $fetcher = new CatalogImportFixtureFetcher();
    $fetcher->documents = [$amazonUrl => $amazonHtml, $rakutenUrl => $rakutenHtml];
    $fetcher->failures[$rakutenUrl] = [new FetchException(
        'private synthetic access detail',
        FetchException::FAILURE_ACCESS_BLOCKED
    )];
    $queue = new ProductReviewQueue();
    $batches = new JsonFileCatalogImportBatchRepository($privateDirectory, $root);
    $service = new \Kuranea\Catalog\Service\CatalogImportService($batches, $queue, $fetcher);

    $batch = $service->createBatch([
        'https://amazon.co.jp/dp/B0KURANEA1?tag=synthetic',
        $amazonUrl,
        'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/?tracking=synthetic',
    ], new DateTimeImmutable('2026-10-25T11:00:00+00:00'));
    assertCatalogImportSame(2, count($batch->items), 'A batch should deduplicate URL variants by provider product identity.');
    assertCatalogImportSame(['queued' => 2, 'processing' => 0, 'succeeded' => 0, 'failed' => 0], $batch->counts(), 'New batch progress should start queued.');

    $batch = $service->processNext($batch->id);
    assertCatalogImportSame(1, $batch->counts()['succeeded'], 'One request should process only one marketplace item.');
    assertCatalogImportSame(1, $batch->counts()['queued'], 'Unprocessed batch entries should remain queued.');
    assertCatalogImportSame(1, count($queue->pending()), 'Successful fetch and parse should add one pending review entry.');

    $batch = $service->processNext($batch->id);
    $rakutenItem = $batch->items[1];
    assertCatalogImportSame(CatalogImportBatchItem::STATUS_FAILED, $rakutenItem->status, 'A blocked fixture request should be a failed item.');
    assertCatalogImportSame(CatalogImportBatchItem::FAILURE_ACCESS_BLOCKED, $rakutenItem->failureCategory, 'Access-blocked classification should remain a fixed safe outcome.');
    assertCatalogImportTrue(!str_contains($rakutenItem->failureMessage() ?? '', 'private synthetic access detail'), 'Batch failure text must not expose raw transport details.');
    assertCatalogImportSame(1, $rakutenItem->attempts, 'The first processing attempt should be counted.');

    $batch = $service->retryFailedItems($batch->id);
    assertCatalogImportSame(1, $batch->counts()['queued'], 'Retry should requeue failed items only.');
    assertCatalogImportSame(CatalogImportBatchItem::STATUS_SUCCEEDED, $batch->items[0]->status, 'Retry must preserve an already successful item.');
    $batch = $service->processNext($batch->id);
    assertCatalogImportSame(CatalogImportBatchItem::STATUS_SUCCEEDED, $batch->items[1]->status, 'A retry with fixture content should succeed.');
    assertCatalogImportSame(2, $batch->items[1]->attempts, 'Retry should increment the item attempt count exactly once.');
    assertCatalogImportSame(2, count($queue->pending()), 'Amazon and Rakuten snapshots should be separately reviewable.');

    // A processing lease left by a stopped request must be recovered before
    // choosing work; the retried claim receives a new fenced attempt number.
    $recovery = $service->createBatch([$amazonUrl]);
    $recoveryItemId = $recovery->items[0]->id;
    $staleStart = new DateTimeImmutable('2026-10-20T00:00:00+00:00');
    $batches->markProcessing($recovery->id, $recoveryItemId, $staleStart);
    $recovered = $service->processNext($recovery->id);
    assertCatalogImportSame(CatalogImportBatchItem::STATUS_SUCCEEDED, $recovered->items[0]->status,
        'A stale processing lease should requeue and process the same source item.');
    assertCatalogImportSame(2, $recovered->items[0]->attempts,
        'Recovered stale work should advance to a second fenced attempt.');

    // Simulate a paused first request whose lease expires while a replacement
    // worker completes with newer source content. The old response must not
    // overwrite the queue after its attempt token becomes stale.
    $raceUrl = 'https://www.amazon.co.jp/dp/B0KURANEA3';
    $raceHtml = str_replace('B0KURANEA1', 'B0KURANEA3', $amazonHtml);
    $newRaceHtml = str_replace('"price": "5980"', '"price": "6070"', $raceHtml);
    $fetcher->documents[$raceUrl] = $raceHtml;
    $raceBatch = $service->createBatch([$raceUrl]);
    $raceItemId = $raceBatch->items[0]->id;
    $newRaceSnapshot = (new AmazonJapanHtmlParser())->parse(
        $newRaceHtml,
        $raceUrl,
        new DateTimeImmutable('2026-10-25T12:01:00+00:00')
    );
    $fetcher->afterRead = static function () use ($batches, $fetcher, $service, $raceBatch, $raceItemId, $raceUrl, $newRaceHtml, $newRaceSnapshot, $queue): void {
        $batches->recoverStaleProcessing(
            $raceBatch->id,
            (new DateTimeImmutable('now', new DateTimeZone('UTC')))->modify('+' . (CatalogImportBatchItem::PROCESSING_LEASE_SECONDS + 1) . ' seconds')
        );
        $fetcher->documents[$raceUrl] = $newRaceHtml;
        $service->processNext($raceBatch->id);
        $entry = $queue->find($newRaceSnapshot->deduplicationKey);
        if ($entry === null || $entry->snapshot->contentHash !== $newRaceSnapshot->contentHash) {
            throw new RuntimeException('The replacement worker did not commit the newer synthetic review snapshot.');
        }
    };
    $afterStaleWorker = $service->processNext($raceBatch->id);
    assertCatalogImportSame(CatalogImportBatchItem::STATUS_SUCCEEDED, $afterStaleWorker->items[0]->status,
        'A stale worker should leave the replacement worker state intact.');
    assertCatalogImportSame($newRaceSnapshot->contentHash, $queue->find($newRaceSnapshot->deduplicationKey)?->snapshot->contentHash,
        'A stale worker must not overwrite the newer review snapshot after lease recovery.');

    // Batches are independent, so a slower earlier request must also be
    // fenced from replacing a later fetch for the same source product.
    $crossBatchUrl = 'https://www.amazon.co.jp/dp/B0KURANEA4';
    $crossBatchOldHtml = str_replace('B0KURANEA1', 'B0KURANEA4', $amazonHtml);
    $crossBatchNewHtml = str_replace('"price": "5980"', '"price": "6120"', $crossBatchOldHtml);
    $fetcher->documents[$crossBatchUrl] = $crossBatchOldHtml;
    $oldBatch = $service->createBatch([$crossBatchUrl]);
    $newBatch = $service->createBatch([$crossBatchUrl]);
    $newCrossSnapshot = (new AmazonJapanHtmlParser())->parse(
        $crossBatchNewHtml,
        $crossBatchUrl,
        new DateTimeImmutable('2026-10-25T12:02:00+00:00')
    );
    $fetcher->afterRead = static function () use ($fetcher, $service, $newBatch, $crossBatchUrl, $crossBatchNewHtml, $newCrossSnapshot, $queue): void {
        $fetcher->documents[$crossBatchUrl] = $crossBatchNewHtml;
        $service->processNext($newBatch->id);
        $entry = $queue->find($newCrossSnapshot->deduplicationKey);
        if ($entry === null || $entry->snapshot->contentHash !== $newCrossSnapshot->contentHash) {
            throw new RuntimeException('The later independent batch did not commit its source snapshot.');
        }
    };
    $service->processNext($oldBatch->id);
    assertCatalogImportSame($newCrossSnapshot->contentHash, $queue->find($newCrossSnapshot->deduplicationKey)?->snapshot->contentHash,
        'An earlier request from another batch must not replace the later source snapshot.');

    $reimport = $service->createBatch([$amazonUrl]);
    $changedHtml = str_replace('"price": "5980"', '"price": "5990"', $amazonHtml);
    $fetcher->documents[$amazonUrl] = $changedHtml;
    $reimport = $service->processNext($reimport->id);
    assertCatalogImportSame(CatalogImportBatchItem::STATUS_SUCCEEDED, $reimport->items[0]->status, 'Changed source content should complete as an update to the same source identity.');
    assertCatalogImportSame(4, count($queue->pending()), 'Reimport should update its existing review identity while preserving the two independent race fixtures.');
    assertCatalogImportSame('amazon_jp:B0KURANEA1', $queue->pending()[0]->idempotencyKey, 'Source identity should remain stable after reimport.');
    $reimportedSnapshot = $reimport->items[0]->snapshot;
    $reimportedEntry = $reimportedSnapshot === null ? null : $queue->find($reimportedSnapshot->deduplicationKey);
    assertCatalogImportSame(5990, $reimportedSnapshot?->priceJpy, 'Reimport should retain the changed source price in the normalized result.');
    assertCatalogImportSame($reimportedSnapshot?->contentHash, $reimportedEntry?->snapshot->contentHash,
        'The review queue should contain the exact successful reimport snapshot.');
    assertCatalogImportSame(9, count($fetcher->requests), 'Each process call should fetch exactly one URL.');
} finally {
    foreach (glob($privateDirectory . '/*') ?: [] as $path) {
        if (is_file($path) || is_link($path)) {
            unlink($path);
        }
    }
    rmdir($privateDirectory);
}

echo "PASS: catalog import orchestration uses bounded one-item processing and persistent review identities\n";
