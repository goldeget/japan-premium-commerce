<?php

declare(strict_types=1);

use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Infrastructure\Persistence\JsonFileProductReviewQueueRepository;
use Kuranea\Catalog\Integration\NativeProductRegistrarInterface;
use Kuranea\Catalog\Integration\NativeProductRegistration;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;
use Kuranea\Catalog\Service\ProductApprovalService;

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

function assertCatalogWorkflowSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertCatalogWorkflowTrue(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

function assertCatalogWorkflowThrows(string $class, callable $callback, string $message): Throwable
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

final class CatalogTestNativeProductRegistrar implements NativeProductRegistrarInterface
{
    /** @var list<NativeProductRegistration> */
    public array $registrations = [];

    public function register(NativeProductRegistration $registration): int
    {
        $this->registrations[] = $registration;
        return 7000 + count($this->registrations);
    }
}

final class CatalogTestFailingNativeProductRegistrar implements NativeProductRegistrarInterface
{
    public function register(NativeProductRegistration $registration): int
    {
        throw new RuntimeException('synthetic registrar failure');
    }
}

final class CatalogTestInterleavingNativeProductRegistrar implements NativeProductRegistrarInterface
{
    public function __construct(private readonly \Closure $duringRegistration, private readonly int $nativeProductId = 7999)
    {
    }

    public function register(NativeProductRegistration $registration): int
    {
        ($this->duringRegistration)();

        return $this->nativeProductId;
    }
}

$catalogFixturePath = __DIR__ . '/fixtures/amazon-jp-product.synthetic.html';
$catalogFixtureHtml = file_get_contents($catalogFixturePath);
if ($catalogFixtureHtml === false) {
    throw new RuntimeException('Could not read synthetic catalog fixture for persistence tests.');
}
$catalogFetchedAt = new DateTimeImmutable('2026-10-22T12:30:00+00:00');
$catalogSnapshot = (new AmazonJapanHtmlParser())->parse(
    $catalogFixtureHtml,
    'https://www.amazon.co.jp/dp/B0KURANEA1',
    $catalogFetchedAt
);
$catalogQueueDir = sys_get_temp_dir() . '/kuranea-catalog-review-' . bin2hex(random_bytes(8));
if (!mkdir($catalogQueueDir, 0700) && !is_dir($catalogQueueDir)) {
    throw new RuntimeException('Could not create isolated temporary catalog queue directory.');
}
$catalogQueuePath = $catalogQueueDir . '/review-queue.json';

try {
    $queue = new JsonFileProductReviewQueueRepository($catalogQueuePath);
    $queued = $queue->enqueue($catalogSnapshot, $catalogFetchedAt);
    assertCatalogWorkflowSame(ProductReviewQueueEntry::STATUS_PENDING, $queued->status, 'Parsed snapshots must be persisted as pending review.');
    assertCatalogWorkflowSame(1, count($queue->pending()), 'The persistent queue should expose a new pending snapshot.');

    $reopenedQueue = new JsonFileProductReviewQueueRepository($catalogQueuePath);
    $reloaded = $reopenedQueue->find($catalogSnapshot->deduplicationKey);
    assertCatalogWorkflowTrue($reloaded !== null, 'A new repository instance should reload the persisted item.');
    assertCatalogWorkflowSame($catalogSnapshot->contentHash, $reloaded->snapshot->contentHash, 'Persistence should retain the snapshot content fingerprint.');
    assertCatalogWorkflowSame($catalogSnapshot->images[0]->altText, $reloaded->snapshot->images[0]->altText, 'Persistence should retain image metadata.');
    assertCatalogWorkflowSame($catalogSnapshot->reviews[0]->origin, $reloaded->snapshot->reviews[0]->origin, 'Persistence should retain source review provenance.');
    assertCatalogWorkflowSame($catalogFetchedAt->format(DateTimeInterface::ATOM), $reloaded->queuedAt->format(DateTimeInterface::ATOM), 'Persistence should retain the original queue timestamp.');

    $reimported = $reopenedQueue->enqueue($catalogSnapshot, $catalogFetchedAt->modify('+1 hour'));
    assertCatalogWorkflowSame($reloaded->queuedAt->format(DATE_ATOM), $reimported->queuedAt->format(DATE_ATOM), 'Reimporting unchanged source data should preserve its first queue timestamp.');
    assertCatalogWorkflowSame(1, count($reopenedQueue->pending()), 'Reimporting the same item must not duplicate the persistent queue entry.');

    $registrar = new CatalogTestNativeProductRegistrar();
    $approvalService = new ProductApprovalService($reopenedQueue, $registrar);
    assertCatalogWorkflowThrows(
        InvalidArgumentException::class,
        static fn () => $approvalService->approve($catalogSnapshot->deduplicationKey, '   ', $catalogFetchedAt),
        'Approval requires a named reviewer.'
    );
    assertCatalogWorkflowThrows(
        InvalidArgumentException::class,
        static fn () => $approvalService->approve($catalogSnapshot->deduplicationKey, 'catalog-operator', $catalogFetchedAt, false),
        'Product registration requires an explicit confirmation signal.'
    );
    assertCatalogWorkflowSame(0, count($registrar->registrations), 'Invalid approval requests must never call the native product registrar.');

    $approved = $approvalService->approve($catalogSnapshot->deduplicationKey, 'catalog-operator', $catalogFetchedAt, true);
    assertCatalogWorkflowSame(ProductReviewQueueEntry::STATUS_APPROVED, $approved->status, 'Explicit approval should transition the persistent queue entry.');
    assertCatalogWorkflowSame('approved', $approved->snapshot->approvalStatus, 'The stored snapshot should record approved status.');
    assertCatalogWorkflowSame(7001, $approved->nativeProductId, 'The native product identity should be retained for audit and retry.');
    assertCatalogWorkflowSame('catalog-operator', $approved->approvedBy, 'The approving staff identity should be retained.');
    assertCatalogWorkflowSame(1, count($registrar->registrations), 'A confirmed approval should register exactly one native product.');

    $registration = $registrar->registrations[0];
    assertCatalogWorkflowTrue(str_starts_with($registration->name, '[TEST/DEMO] '), 'The native product name should be clearly labeled TEST/DEMO.');
    assertCatalogWorkflowTrue(str_starts_with($registration->reference, 'TEST-'), 'The native product reference should be clearly labeled TEST.');
    assertCatalogWorkflowSame(false, $registration->active, 'Generated catalog products must remain inactive by default.');
    assertCatalogWorkflowSame('none', $registration->visibility, 'Generated catalog products must not be visible in the storefront.');
    assertCatalogWorkflowTrue(str_contains($registration->provenance, $catalogSnapshot->sourceUrl), 'The native product should retain its source URL provenance.');
    assertCatalogWorkflowTrue(str_contains($registration->provenance, $catalogSnapshot->contentHash), 'The native product should retain its source snapshot fingerprint.');
    assertCatalogWorkflowTrue(str_contains($registration->provenance, 'Approved by: catalog-operator'), 'The native product should retain its staff approval provenance.');
    assertCatalogWorkflowSame(5980, $registration->priceJpy, 'The native product registration draft should retain its JPY price.');

    $reopenedAfterApproval = new JsonFileProductReviewQueueRepository($catalogQueuePath);
    $approvedAfterReload = $reopenedAfterApproval->find($catalogSnapshot->deduplicationKey);
    assertCatalogWorkflowSame(ProductReviewQueueEntry::STATUS_APPROVED, $approvedAfterReload?->status, 'Approval state should survive repository reload.');
    assertCatalogWorkflowSame(7001, $approvedAfterReload?->nativeProductId, 'Native product ID should survive repository reload.');
    assertCatalogWorkflowSame('catalog-operator', $approvedAfterReload?->approvedBy, 'Approving staff identity should survive repository reload.');
    assertCatalogWorkflowSame($catalogFetchedAt->format(DATE_ATOM), $approvedAfterReload?->approvedAt?->format(DATE_ATOM), 'Approval timestamp should survive repository reload.');
    $approvalServiceAfterReload = new ProductApprovalService($reopenedAfterApproval, $registrar);
    assertCatalogWorkflowSame(7001, $approvalServiceAfterReload->approve($catalogSnapshot->deduplicationKey, 'catalog-operator', $catalogFetchedAt)->nativeProductId, 'Repeated approval should return the already registered native product.');
    assertCatalogWorkflowSame(1, count($registrar->registrations), 'Repeated approval must not create a duplicate native product.');

    $changedSnapshot = (new AmazonJapanHtmlParser())->parse(
        str_replace('"price": "5980"', '"price": "5990"', $catalogFixtureHtml),
        'https://www.amazon.co.jp/dp/B0KURANEA1',
        $catalogFetchedAt->modify('+1 day')
    );
    $changedEntry = $reopenedAfterApproval->enqueue($changedSnapshot, $catalogFetchedAt->modify('+1 day'));
    assertCatalogWorkflowSame(ProductReviewQueueEntry::STATUS_PENDING, $changedEntry->status, 'Changed source content must return to manual review after an earlier approval.');
    assertCatalogWorkflowSame(null, $changedEntry->nativeProductId, 'Changed content must not reuse the previous native product identity.');
    assertCatalogWorkflowSame(7001, $changedEntry->linkedProductId, 'Changed content must retain a link to the existing native draft.');
    assertCatalogWorkflowSame($catalogSnapshot->contentHash, $changedEntry->previousSnapshot?->contentHash, 'Changed content should retain the previous snapshot for comparison.');
    $approvedChange = $approvalServiceAfterReload->approve($changedSnapshot->deduplicationKey, 'catalog-operator', $catalogFetchedAt->modify('+1 day'), true);
    assertCatalogWorkflowSame(7001, $approvedChange->nativeProductId, 'A changed source revision should stay linked to the existing native draft.');
    assertCatalogWorkflowSame(1, count($registrar->registrations), 'Reapproval of changed source content must not register a duplicate native product.');

    $concurrentQueue = new JsonFileProductReviewQueueRepository($catalogQueueDir . '/concurrent-queue.json');
    $concurrentQueue->enqueue($catalogSnapshot, $catalogFetchedAt);
    $interleavingRegistrar = new CatalogTestInterleavingNativeProductRegistrar(
        static fn () => $concurrentQueue->enqueue($changedSnapshot, $catalogFetchedAt->modify('+1 day'))
    );
    $concurrentApprovalService = new ProductApprovalService($concurrentQueue, $interleavingRegistrar);
    assertCatalogWorkflowThrows(
        RuntimeException::class,
        static fn () => $concurrentApprovalService->approve($catalogSnapshot->deduplicationKey, 'catalog-operator', $catalogFetchedAt, true),
        'Approval must reject a snapshot that changed while native registration was in progress.'
    );
    $latestConcurrentEntry = $concurrentQueue->find($catalogSnapshot->deduplicationKey);
    assertCatalogWorkflowSame(ProductReviewQueueEntry::STATUS_PENDING, $latestConcurrentEntry?->status, 'A concurrent source update must remain pending after the older snapshot registration completes.');
    assertCatalogWorkflowSame($changedSnapshot->contentHash, $latestConcurrentEntry?->snapshot->contentHash, 'Approval must not overwrite a newer queued snapshot.');

    $failingQueue = new JsonFileProductReviewQueueRepository($catalogQueueDir . '/failure-queue.json');
    $failingQueue->enqueue($catalogSnapshot, $catalogFetchedAt);
    $failingService = new ProductApprovalService($failingQueue, new CatalogTestFailingNativeProductRegistrar());
    assertCatalogWorkflowThrows(
        RuntimeException::class,
        static fn () => $failingService->approve($catalogSnapshot->deduplicationKey, 'catalog-operator', $catalogFetchedAt, true),
        'Native product registration failures should be surfaced.'
    );
    assertCatalogWorkflowSame(ProductReviewQueueEntry::STATUS_PENDING, $failingQueue->find($catalogSnapshot->deduplicationKey)?->status, 'A failed registration must leave the review item pending.');

    $corruptQueuePath = $catalogQueueDir . '/corrupt-queue.json';
    file_put_contents($corruptQueuePath, '{corrupt');
    $corruptQueue = new JsonFileProductReviewQueueRepository($corruptQueuePath);
    assertCatalogWorkflowThrows(
        RuntimeException::class,
        static fn () => $corruptQueue->find($catalogSnapshot->deduplicationKey),
        'Corrupt persisted queue data should fail closed.'
    );
    assertCatalogWorkflowSame('{corrupt', file_get_contents($corruptQueuePath), 'Corrupt queue data must not be overwritten after a read error.');
} finally {
    foreach (glob($catalogQueueDir . '/*') ?: [] as $catalogQueueFile) {
        unlink($catalogQueueFile);
    }
    rmdir($catalogQueueDir);
}

echo "PASS: persistent review queue and explicitly approved TEST/DEMO product registration checks\n";
