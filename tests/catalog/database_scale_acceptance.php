<?php

declare(strict_types=1);

use Kuranea\Catalog\Domain\CatalogImportBatch;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;
use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseBootstrap;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseContext;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseRowMapper;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseSql;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseTransaction;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseLegacyImporter;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogImportBatchRepositoryFactory;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogQueueRepositoryFactory;
use Kuranea\Catalog\Fetching\FetchException;
use Kuranea\Catalog\Fetching\ProductPageFetcherInterface;
use Kuranea\Catalog\Service\CatalogImportService;

require_once '/var/www/html/modules/kuraneacatalog/autoload.php';

final class CatalogScaleRollbackSignal extends RuntimeException
{
}

final class CatalogScaleUnavailableFetcher implements ProductPageFetcherInterface
{
    public function fetch(string $url): \Kuranea\Catalog\Fetching\FetchedProduct
    {
        throw new FetchException('Synthetic source unavailable.', FetchException::FAILURE_SOURCE_UNAVAILABLE);
    }
}

function assertCatalogScale(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

function catalogScaleP95(array $samples): float
{
    sort($samples, SORT_NUMERIC);
    $index = max(0, (int) ceil(count($samples) * 0.95) - 1);

    return round((float) ($samples[$index] ?? 0.0), 3);
}

function insertCatalogScaleChunk(object $database, string $table, array $values, bool $batchRows): void
{
    $columns = $batchRows
        ? '(id_shop, id_batch, created_at, payload_sha256, payload)'
        : '(id_shop, idempotency_key, source_identity_hash, provider, status, content_hash, queued_at, decision_at, native_product_id, linked_product_id, payload_sha256, payload)';
    if (!$database->execute('INSERT INTO ' . $table . ' ' . $columns . ' VALUES ' . implode(',', $values))) {
        throw new RuntimeException('Synthetic catalog scale chunk could not be stored.');
    }
}

function verifyLegacyImport(CatalogDatabaseContext $context, string $nonce): void
{
    $private = sys_get_temp_dir() . '/ordenowa-catalog-migration-' . $nonce;
    if (!mkdir($private, 0700)) {
        throw new RuntimeException('Synthetic migration directory could not be created.');
    }
    $at = new DateTimeImmutable('2026-10-27T00:00:00+00:00');
    $key = 'migration-' . $nonce;
    $snapshot = new NormalizedProductSnapshot(
        'synthetic_ci', $key, $key, 'https://example.invalid/' . $key,
        '[TEST/DEMO] Migration fixture', null, 'Synthetic CI only.', [], 1000, 'JPY',
        [], [], [], null, null, 'in_stock', 'pending', $at, hash('sha256', $key)
    );
    $entry = new ProductReviewQueueEntry($key, 'pending', $snapshot, $at);
    $batch = CatalogImportBatch::fromUrls(['https://www.amazon.co.jp/dp/B0KURANEA1'], $at);
    $reviewContent = json_encode(['schemaVersion' => 1, 'entries' => (object) [$key => $entry->toArray()]], JSON_THROW_ON_ERROR);
    $batchContent = json_encode(['schemaVersion' => 1, 'batches' => (object) [$batch->id => $batch->toArray()]], JSON_THROW_ON_ERROR);
    $reviewPath = $private . DIRECTORY_SEPARATOR . 'review-queue.json';
    $batchPath = $private . DIRECTORY_SEPARATOR . 'catalog-import-batches.json';
    file_put_contents($reviewPath, $reviewContent, LOCK_EX);
    file_put_contents($batchPath, $batchContent, LOCK_EX);
    $reviewHash = hash_file('sha256', $reviewPath);
    $batchHash = hash_file('sha256', $batchPath);
    $migrationContext = new CatalogDatabaseContext($context->database, $context->tables, $private, $context->shopRoot, $context->shopId);
    $importer = new CatalogDatabaseLegacyImporter($migrationContext);
    $importer->import();
    $importer->import();

    $review = $context->database->getRow(
        'SELECT payload_sha256 FROM ' . $context->tables->reviews()
        . ' WHERE id_shop = ' . $context->shopId . ' AND idempotency_key = ' . CatalogDatabaseSql::quote($key)
    );
    $storedBatch = $context->database->getRow(
        'SELECT payload_sha256 FROM ' . $context->tables->batches()
        . ' WHERE id_shop = ' . $context->shopId . ' AND id_batch = ' . CatalogDatabaseSql::quote($batch->id)
    );
    assertCatalogScale(is_array($review) && hash_equals(hash('sha256', json_encode($entry->toArray(), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR)), (string) ($review['payload_sha256'] ?? '')), 'Legacy review payload did not verify.');
    assertCatalogScale(is_array($storedBatch) && hash_equals(hash('sha256', json_encode($batch->toArray(), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR)), (string) ($storedBatch['payload_sha256'] ?? '')), 'Legacy batch payload did not verify.');
    assertCatalogScale(is_file($reviewPath) && hash_equals((string) $reviewHash, (string) hash_file('sha256', $reviewPath)), 'Legacy review JSON was not retained intact.');
    assertCatalogScale(is_file($batchPath) && hash_equals((string) $batchHash, (string) hash_file('sha256', $batchPath)), 'Legacy batch JSON was not retained intact.');
    $reviewDuplicates = (int) $context->database->getValue(
        'SELECT COUNT(*) FROM ' . $context->tables->reviews()
        . ' WHERE id_shop = ' . $context->shopId . ' AND idempotency_key = ' . CatalogDatabaseSql::quote($key)
    );
    assertCatalogScale($reviewDuplicates === 1, 'Idempotent review import created a duplicate row.');
    $batchDuplicates = (int) $context->database->getValue(
        'SELECT COUNT(*) FROM ' . $context->tables->batches()
        . ' WHERE id_shop = ' . $context->shopId . ' AND id_batch = ' . CatalogDatabaseSql::quote($batch->id)
    );
    assertCatalogScale($batchDuplicates === 1, 'Idempotent batch import created a duplicate row.');
}

if (getenv('CI') !== 'true' || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1' || !class_exists('Db') || !class_exists('Shop')) {
    throw new RuntimeException('Catalog scale acceptance is restricted to the isolated Actions database.');
}
$runId = getenv('GITHUB_RUN_ID');
$runAttempt = getenv('GITHUB_RUN_ATTEMPT');
$expectedProject = is_string($runId) && is_string($runAttempt)
    && preg_match('/\A[0-9]+\z/D', $runId) === 1
    && preg_match('/\A[0-9]+\z/D', $runAttempt) === 1
    ? 'kuranea-ci-' . $runId . '-' . $runAttempt
    : '';
if ($expectedProject === '' || getenv('KURANEA_CI_PROJECT_NAME') !== $expectedProject
    || getenv('KURANEA_CATALOG_IMPORT_FIXTURE_MODE') !== '1'
    || getenv('KURANEA_CATALOG_QUEUE_DIR') !== '/var/lib/kuranea/catalog-import-qa') {
    throw new RuntimeException('Catalog scale acceptance did not resolve the run-scoped disposable catalog fixture.');
}
if (strtolower((string) Db::getInstance()->getValue('SELECT DATABASE()')) !== 'prestashop'
    || (int) Shop::getTotalShops(false) !== 1) {
    throw new RuntimeException('Catalog scale acceptance did not resolve the disposable single-shop PrestaShop database.');
}

$context = CatalogDatabaseContext::fromPrestaShop(_PS_ROOT_DIR_);
CatalogDatabaseBootstrap::assertReady($context);
$database = $context->database;
$tables = $context->tables;
$queue = CatalogQueueRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_);
$batches = CatalogImportBatchRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_);
$shopId = $context->shopId;
$nonce = bin2hex(random_bytes(6));
$runKey = 'scale-' . $nonce;
$metrics = [];

try {
    CatalogDatabaseTransaction::run($database, function () use (
        $context, $database, $tables, $queue, $batches, $shopId, $nonce, $runKey,
        &$metrics
    ): void {
        verifyLegacyImport($context, $nonce);
        $sourceRowsBefore = (int) $database->getValue('SELECT COUNT(*) FROM ' . $tables->reviews() . ' WHERE id_shop = ' . $shopId);
        $batchRowsBefore = (int) $database->getValue('SELECT COUNT(*) FROM ' . $tables->batches() . ' WHERE id_shop = ' . $shopId);
        $pendingBefore = $queue->countPending();

        $preservationRow = $database->getRow(
            'SELECT idempotency_key, COALESCE(native_product_id, linked_product_id) AS product_id'
            . ' FROM ' . $tables->reviews() . ' WHERE id_shop = ' . $shopId
            . ' AND COALESCE(native_product_id, linked_product_id) IS NOT NULL'
            . ' ORDER BY queued_at DESC LIMIT 1'
        );
        assertCatalogScale(is_array($preservationRow) && is_string($preservationRow['idempotency_key'] ?? null)
            && (int) ($preservationRow['product_id'] ?? 0) > 0, 'Catalog browser fixture has no linked synthetic draft.');
        $existingEntry = $queue->find((string) $preservationRow['idempotency_key']);
        $productId = (int) $preservationRow['product_id'];
        assertCatalogScale($existingEntry !== null, 'Linked synthetic review entry could not be read.');
        $langId = (int) Language::getIdByIso('ja', true);
        $product = new Product($productId, false, $langId, $shopId);
        assertCatalogScale(Validate::isLoadedObject($product) && str_starts_with((string) $product->reference, 'OWA-IMPORT-'), 'Linked item is not a synthetic imported draft.');
        $editedName = '[TEST/DEMO] Human edit preservation scale fixture';
        $editSql = 'UPDATE ' . _DB_PREFIX_ . 'product_lang SET name = '
            . CatalogDatabaseSql::quote($editedName) . ' WHERE id_product = ' . $productId
            . ' AND id_shop = ' . $shopId . ' AND id_lang = ' . $langId;
        assertCatalogScale((bool) $database->execute($editSql), 'Could not edit the synthetic native product.');
        $editReadback = $database->getRow(
            'SELECT p.reference, ps.price, ps.active, ps.visibility, ps.available_for_order, pl.name'
            . ' FROM ' . _DB_PREFIX_ . 'product p'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'product_shop ps ON ps.id_product = p.id_product AND ps.id_shop = ' . $shopId
            . ' INNER JOIN ' . _DB_PREFIX_ . 'product_lang pl ON pl.id_product = p.id_product AND pl.id_shop = ' . $shopId . ' AND pl.id_lang = ' . $langId
            . ' WHERE p.id_product = ' . $productId . ' LIMIT 1'
        );
        assertCatalogScale(is_array($editReadback) && ($editReadback['name'] ?? '') === $editedName, 'Manual product edit did not persist.');

        $failureBatch = $batches->create([$existingEntry->snapshot->sourceUrl]);
        $failedBatch = (new CatalogImportService($batches, $queue, new CatalogScaleUnavailableFetcher()))
            ->processNext($failureBatch->id);
        $failedItem = $failedBatch->items[0] ?? null;
        assertCatalogScale($failedItem !== null && $failedItem->status === 'failed'
            && $failedItem->failureCategory === 'source_unavailable', 'Synthetic failed source refresh did not record its fixed outcome.');
        $afterFailure = $database->getRow(
            'SELECT p.reference, ps.price, ps.active, ps.visibility, ps.available_for_order, pl.name'
            . ' FROM ' . _DB_PREFIX_ . 'product p'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'product_shop ps ON ps.id_product = p.id_product AND ps.id_shop = ' . $shopId
            . ' INNER JOIN ' . _DB_PREFIX_ . 'product_lang pl ON pl.id_product = p.id_product AND pl.id_shop = ' . $shopId . ' AND pl.id_lang = ' . $langId
            . ' WHERE p.id_product = ' . $productId . ' LIMIT 1'
        );
        assertCatalogScale($afterFailure === $editReadback, 'Failed source refresh changed the manually edited native product.');

        $newer = $existingEntry->snapshot->withFetchedAt($existingEntry->snapshot->fetchedAt->modify('+1 day'));
        $refreshed = $queue->enqueue($newer, $newer->fetchedAt);
        assertCatalogScale(($refreshed->nativeProductId ?? $refreshed->linkedProductId) === $productId, 'Source refresh lost the same native product ID.');
        $afterRefresh = $database->getRow(
            'SELECT p.reference, ps.price, ps.active, ps.visibility, ps.available_for_order, pl.name'
            . ' FROM ' . _DB_PREFIX_ . 'product p'
            . ' INNER JOIN ' . _DB_PREFIX_ . 'product_shop ps ON ps.id_product = p.id_product AND ps.id_shop = ' . $shopId
            . ' INNER JOIN ' . _DB_PREFIX_ . 'product_lang pl ON pl.id_product = p.id_product AND pl.id_shop = ' . $shopId . ' AND pl.id_lang = ' . $langId
            . ' WHERE p.id_product = ' . $productId . ' LIMIT 1'
        );
        assertCatalogScale($afterRefresh === $editReadback, 'Source refresh changed a manually edited native product value.');

        $lastQueueKey = '';
        $lastBatchId = '';
        $priorLevel = 0;
        foreach ([1000, 10000, 100000] as $level) {
            $queueValues = [];
            for ($index = $priorLevel; $index < $level; $index++) {
                $key = $runKey . '-' . str_pad((string) $index, 6, '0', STR_PAD_LEFT);
                $at = new DateTimeImmutable('2100-01-01T00:00:00+00:00');
                $snapshot = new NormalizedProductSnapshot(
                    'synthetic_ci', $key, $key, 'https://example.invalid/catalog/' . $key,
                    '[TEST/DEMO] Synthetic catalog scale fixture', null, 'Synthetic CI only.', [],
                    1000, 'JPY', [], [], [], null, null, 'in_stock', 'pending', $at, hash('sha256', $key)
                );
                $entry = new ProductReviewQueueEntry($key, 'pending', $snapshot, $at);
                $row = CatalogDatabaseRowMapper::review($entry);
                $queueValues[] = '(' . $shopId . ', '
                    . CatalogDatabaseSql::quote((string) $row['key']) . ', '
                    . CatalogDatabaseSql::quote((string) $row['source_identity_hash']) . ', '
                    . CatalogDatabaseSql::quote((string) $row['provider']) . ', '
                    . CatalogDatabaseSql::quote((string) $row['status']) . ', '
                    . CatalogDatabaseSql::quote((string) $row['content_hash']) . ', '
                    . CatalogDatabaseSql::quote((string) $row['queued_at']) . ', NULL, NULL, NULL, '
                    . CatalogDatabaseSql::quote((string) $row['hash']) . ', '
                    . CatalogDatabaseSql::quote((string) $row['payload']) . ')';
                $lastQueueKey = $key;
                if (count($queueValues) === 500) {
                    insertCatalogScaleChunk($database, $tables->reviews(), $queueValues, false);
                    $queueValues = [];
                }
            }
            if ($queueValues !== []) {
                insertCatalogScaleChunk($database, $tables->reviews(), $queueValues, false);
            }

            $batchValues = [];
            $batchCount = (int) (($level - $priorLevel) / CatalogImportBatch::MAX_ITEMS);
            for ($batchIndex = 0; $batchIndex < $batchCount; $batchIndex++) {
                $urls = [];
                for ($item = 0; $item < CatalogImportBatch::MAX_ITEMS; $item++) {
                    $id = str_pad((string) (($priorLevel + $batchIndex * CatalogImportBatch::MAX_ITEMS + $item) % 100000), 9, '0', STR_PAD_LEFT);
                    $urls[] = 'https://www.amazon.co.jp/dp/B' . $id;
                }
                $batch = CatalogImportBatch::fromUrls($urls, new DateTimeImmutable('2100-01-01T00:00:00+00:00'));
                $payload = CatalogDatabaseSql::encode($batch->toArray());
                $batchValues[] = '(' . $shopId . ', ' . CatalogDatabaseSql::quote($batch->id) . ', '
                    . CatalogDatabaseSql::quote(CatalogDatabaseSql::timestamp($batch->createdAt)) . ', '
                    . CatalogDatabaseSql::quote(hash('sha256', $payload)) . ', '
                    . CatalogDatabaseSql::quote($payload) . ')';
                $lastBatchId = $batch->id;
                if (count($batchValues) === 100) {
                    insertCatalogScaleChunk($database, $tables->batches(), $batchValues, true);
                    $batchValues = [];
                }
            }
            if ($batchValues !== []) {
                insertCatalogScaleChunk($database, $tables->batches(), $batchValues, true);
            }

            $expectedPending = $pendingBefore + $level;
            $storedReviewRows = (int) $database->getValue(
                'SELECT COUNT(*) FROM ' . $tables->reviews() . ' WHERE id_shop = ' . $shopId
            );
            $storedBatchRows = (int) $database->getValue(
                'SELECT COUNT(*) FROM ' . $tables->batches() . ' WHERE id_shop = ' . $shopId
            );
            assertCatalogScale($storedReviewRows === $sourceRowsBefore + $level, 'Catalog review capacity did not reach the fixture level.');
            assertCatalogScale($storedBatchRows === $batchRowsBefore + 1 + (int) ($level / CatalogImportBatch::MAX_ITEMS), 'Catalog batch capacity did not reach the fixture level.');
            assertCatalogScale($queue->countPending() === $expectedPending, 'Pending catalog capacity did not match the fixture level.');
            $pageOffset = $pendingBefore + $level - 50;
            $lookupSamples = [];
            $pageSamples = [];
            $countSamples = [];
            for ($sample = 0; $sample < 25; $sample++) {
                $started = hrtime(true);
                $found = $queue->find($lastQueueKey);
                $lookupSamples[] = (hrtime(true) - $started) / 1_000_000;
                assertCatalogScale($found !== null && $found->idempotencyKey === $lastQueueKey, 'Indexed catalog source lookup failed.');
                $started = hrtime(true);
                $page = $queue->pending(50, max(0, $pageOffset));
                $pageSamples[] = (hrtime(true) - $started) / 1_000_000;
                assertCatalogScale(count($page) === 50, 'Bounded catalog review page did not return 50 entries.');
                $started = hrtime(true);
                $count = $queue->countPending();
                $countSamples[] = (hrtime(true) - $started) / 1_000_000;
                assertCatalogScale($count === $expectedPending, 'Pending catalog count changed unexpectedly.');
            }
            $batchLookupSamples = [];
            $batchRecentSamples = [];
            for ($sample = 0; $sample < 25; $sample++) {
                $batchStarted = hrtime(true);
                $batchFound = $batches->find($lastBatchId);
                $batchLookupSamples[] = (hrtime(true) - $batchStarted) / 1_000_000;
                assertCatalogScale($batchFound !== null && $batchFound->id === $lastBatchId, 'Indexed catalog batch lookup failed.');
                $batchStarted = hrtime(true);
                $recent = $batches->recent(50);
                $batchRecentSamples[] = (hrtime(true) - $batchStarted) / 1_000_000;
                assertCatalogScale(count($recent) === 50, 'Bounded catalog batch history did not return 50 records.');
            }

            $metrics[(string) $level] = [
                'sku_capacity' => $level,
                'batch_count' => $batchRowsBefore + (int) ($level / CatalogImportBatch::MAX_ITEMS),
                'lookup_p95_ms' => catalogScaleP95($lookupSamples),
                'review_page_50_p95_ms' => catalogScaleP95($pageSamples),
                'pending_count_p95_ms' => catalogScaleP95($countSamples),
                'batch_lookup_p95_ms' => catalogScaleP95($batchLookupSamples),
                'batch_recent_50_p95_ms' => catalogScaleP95($batchRecentSamples),
            ];
            assertCatalogScale($metrics[(string) $level]['lookup_p95_ms'] <= 250, 'Indexed catalog lookup exceeded 250ms.');
            assertCatalogScale($metrics[(string) $level]['review_page_50_p95_ms'] <= 1000, 'Catalog review page exceeded 1s.');
            assertCatalogScale($metrics[(string) $level]['pending_count_p95_ms'] <= 1000, 'Catalog pending count exceeded 1s.');
            assertCatalogScale($metrics[(string) $level]['batch_lookup_p95_ms'] <= 250, 'Indexed catalog batch lookup exceeded 250ms.');
            assertCatalogScale($metrics[(string) $level]['batch_recent_50_p95_ms'] <= 1000, 'Catalog batch history page exceeded 1s.');
            $priorLevel = $level;
        }

        assertCatalogScale($lastQueueKey !== '' && $queue->find($lastQueueKey) !== null, 'Synthetic scale rows were not persisted.');
        assertCatalogScale($lastBatchId !== '' && $batches->find($lastBatchId) !== null, 'Synthetic batch scale rows were not persisted.');
        throw new CatalogScaleRollbackSignal('Rollback disposable catalog scale fixture.');
    });
} catch (CatalogScaleRollbackSignal) {
    // The InnoDB transaction rolls back every synthetic queue row, batch row, and test edit.
}

echo 'CATALOG_DATABASE_SCALE_METRICS=' . json_encode($metrics, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
echo 'PASS: indexed catalog storage, idempotent legacy import, 1k/10k/100k capacity, latency and edit preservation' . PHP_EOL;
