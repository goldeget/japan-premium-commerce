<?php

declare(strict_types=1);

/** Called only after the disposable procurement CI shop has been bootstrapped. */
function prepareCiProcurementProduct(): array
{
    $runId = trim((string) getenv('GITHUB_RUN_ID'));
    $attempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
    if (getenv('CI') !== 'true' || getenv('GITHUB_ACTIONS') !== 'true' || getenv('KURANEA_ISOLATED_CI') !== '1'
        || getenv('ORDENOWA_APP_MODE') !== 'procurement' || getenv('DB_SERVER') !== 'mariadb'
        || preg_match('/\A[0-9]+\z/D', $runId) !== 1 || preg_match('/\A[0-9]+\z/D', $attempt) !== 1
        || getenv('KURANEA_CI_PROJECT_NAME') !== 'ordenowa-procurement-ci-' . $runId . '-' . $attempt
        || !defined('_DB_SERVER_') || !in_array((string) _DB_SERVER_, ['mariadb', 'mariadb:3306'], true)
        || !defined('_DB_NAME_') || _DB_NAME_ !== 'prestashop'
        || !class_exists('Db') || (string) Db::getInstance()->getValue('SELECT DATABASE()', false) !== 'prestashop') {
        throw new RuntimeException('Procurement product preparation requires the matching disposable CI database.');
    }
    $shopRoot = defined('_PS_ROOT_DIR_') ? (string) _PS_ROOT_DIR_ : '/var/www/html';
    require_once $shopRoot . '/modules/kuraneacatalog/autoload.php';
    $context = Context::getContext();
    $shopId = (int) ($context->shop->id ?? 0);
    $employeeId = (int) ($context->employee->id ?? 0);
    if ($shopId < 1 || $employeeId < 1) throw new RuntimeException('Fixture requires trusted shop and employee context.');
    global $kernel;
    if (!is_object($kernel)) {
        require_once $shopRoot . '/app/AdminKernel.php';
        $kernel = new AdminKernel(_PS_ENV_, _PS_MODE_DEV_);
        $kernel->boot();
    }
    $fixturePath = __DIR__ . '/fixtures/amazon-jp-review-single-option.synthetic.html';
    $html = is_file($fixturePath) ? file_get_contents($fixturePath) : false;
    if (!is_string($html) || $html === '') throw new RuntimeException('Offline catalog fixture is missing.');
    // This is a synthetic identity, never fetched from Amazon and never represented as a real listing.
    $asin = strtoupper(substr(hash('sha256', 'ordenowa-procurement-' . $runId . '-' . $attempt), 0, 10));
    $snapshot = (new \Kuranea\Catalog\Parsing\AmazonJapanHtmlParser())->parse(
        $html, 'https://www.amazon.co.jp/dp/' . $asin
    );
    $tables = new \Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseTables(Db::getInstance(), _DB_PREFIX_);
    $tables->install();
    $queue = new \Kuranea\Catalog\Infrastructure\Persistence\DatabaseProductReviewQueueRepository(Db::getInstance(), $tables->reviews(), $shopId);
    $entry = $queue->enqueue($snapshot, new DateTimeImmutable('now', new DateTimeZone('UTC')));
    $categoryId = (int) Configuration::get('PS_HOME_CATEGORY');
    $draft = \Kuranea\Catalog\Domain\ProductAdminDraft::fromArray([
        'name_ja' => '[CI ONLY] 合成発注商品 ' . $runId . '-' . $attempt,
        'name_en' => '[CI ONLY] Synthetic procurement product ' . $runId . '-' . $attempt,
        'name_ko' => '[CI ONLY] 합성 발주 상품 ' . $runId . '-' . $attempt,
        'description_ja' => '隔離 CI の合成商品。実在商品または販売価格の証拠ではありません。',
        'description_en' => 'Synthetic isolated CI product; no real listing or sale price claim.',
        'description_ko' => '격리 CI 합성 상품. 실제 원본 또는 판매가격의 근거가 아닙니다.',
        'price_jpy' => $snapshot->priceJpy + 17, 'tax_rules_group_id' => 0, 'quantity' => 0,
        'category_ids' => [$categoryId], 'options' => "サイズ:M|L",
    ]);
    $result = (new \Kuranea\Catalog\Integration\PrestaShopNativeProductManager())->saveImportedDraftWithResult($snapshot->deduplicationKey, $draft);
    if ($entry->status !== \Kuranea\Catalog\Domain\ProductReviewQueueEntry::STATUS_APPROVED) {
        $evidence = new \Kuranea\Catalog\Domain\ProductImportReviewEvidence(
            $draft->priceJpy, 0, 'explicitly_exempt', 'isolated synthetic CI only ' . $runId . '-' . $attempt,
            0, [$categoryId], true, ['en', 'ko'], $snapshot->contentHash
        );
        $linked = $queue->linkDraftIfCurrent($snapshot->deduplicationKey, $snapshot->contentHash, $result->productId, null, $evidence);
        if ($linked === null || $queue->approveIfPending($snapshot->deduplicationKey, $snapshot->contentHash, $result->productId,
            'employee:' . $employeeId, new DateTimeImmutable('now', new DateTimeZone('UTC')), null, $evidence) === null) {
            throw new RuntimeException('Offline source revision could not be approved.');
        }
    }
    $product = new Product($result->productId, false, null, $shopId);
    if ((int) $product->id !== $result->productId || $product->active || $product->available_for_order
        || $product->visibility !== 'none' || $product->show_price) throw new RuntimeException('Fixture product became retail-visible.');
    $attributeId = (int) Db::getInstance()->getValue('SELECT pa.id_product_attribute FROM `' . _DB_PREFIX_ . 'product_attribute` pa'
        . ' INNER JOIN `' . _DB_PREFIX_ . 'product_attribute_shop` pas ON pas.id_product_attribute = pa.id_product_attribute AND pas.id_shop = ' . $shopId
        . ' WHERE pa.id_product = ' . $result->productId . ' ORDER BY pa.id_product_attribute ASC', false);
    if ($attributeId < 1) throw new RuntimeException('Fixture single-option combinations were not persisted.');
    return ['product_id' => $result->productId, 'product_attribute_id' => $attributeId,
        'synthetic_source' => true, 'reviewed_source' => true, 'inactive_nonorderable' => true, 'images_not_used' => true];
}
