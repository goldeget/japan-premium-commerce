<?php

declare(strict_types=1);

/** Called only after the disposable procurement CI shop has been bootstrapped. */
function prepareCiProcurementProduct(string $scenario = 'primary'): array
{
    if (!in_array($scenario, ['primary','gallery'], true)) throw new InvalidArgumentException('Unsupported isolated product scenario.');
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
    $asin = strtoupper(substr(hash('sha256', 'ordenowa-procurement-' . $runId . '-' . $attempt . ($scenario === 'primary' ? '' : '-gallery')), 0, 10));
    $snapshot = (new \Kuranea\Catalog\Parsing\AmazonJapanHtmlParser())->parse(
        $html, 'https://www.amazon.co.jp/dp/' . $asin
    );
    $tables = new \Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseTables(Db::getInstance(), _DB_PREFIX_);
    $tables->install();
    $queue = new \Kuranea\Catalog\Infrastructure\Persistence\DatabaseProductReviewQueueRepository(Db::getInstance(), $tables->reviews(), $shopId);
    $entry = $queue->enqueue($snapshot, new DateTimeImmutable('now', new DateTimeZone('UTC')));
    $categoryIds = prepareCiProcurementReviewedCategoryIds($scenario,$entry,$shopId,$runId,$attempt);
    $draft = \Kuranea\Catalog\Domain\ProductAdminDraft::fromArray([
        'name_ja' => '[CI ONLY] 合成発注商品 ' . $runId . '-' . $attempt,
        'name_en' => '[CI ONLY] Synthetic procurement product ' . $runId . '-' . $attempt,
        'name_ko' => '[CI ONLY] 합성 발주 상품 ' . $runId . '-' . $attempt,
        'description_ja' => '隔離 CI の合成商品。実在商品または販売価格の証拠ではありません。',
        'description_en' => 'Synthetic isolated CI product; no real listing or sale price claim.',
        'description_ko' => '격리 CI 합성 상품. 실제 원본 또는 판매가격의 근거가 아닙니다.',
        'price_jpy' => $snapshot->priceJpy + 17, 'tax_rules_group_id' => 0, 'quantity' => 0,
        'category_ids' => $categoryIds, 'options' => "サイズ:M|L",
    ]);
    $manager = new \Kuranea\Catalog\Integration\PrestaShopNativeProductManager();
    $result = $manager->saveImportedDraftWithResult($snapshot->deduplicationKey, $draft);
    $imageIds = $manager->imageIds($result->productId);
    $imageRights = null;
    if ($scenario === 'gallery' && $entry->status !== \Kuranea\Catalog\Domain\ProductReviewQueueEntry::STATUS_APPROVED) {
        if ($imageIds === []) {
            for ($position = 1; $position <= 2; ++$position) {
                $temporary = tempnam(sys_get_temp_dir(), 'ordenowa-original-');
                if ($temporary === false) throw new RuntimeException('Could not create isolated original image.');
                try {
                    $canvas = imagecreatetruecolor(480,480);
                    if ($canvas === false) throw new RuntimeException('Could not create isolated original image.');
                    $background = imagecolorallocate($canvas,245,245,240);
                    $foreground = imagecolorallocate($canvas,$position === 1 ? 35 : 180,95,$position === 1 ? 170 : 65);
                    imagefilledrectangle($canvas,0,0,479,479,$background);
                    imagefilledellipse($canvas,240,240,160 + $position * 40,160 + $position * 40,$foreground);
                    if (!imagejpeg($canvas,$temporary,90)) throw new RuntimeException('Could not encode isolated original image.');
                    imagedestroy($canvas);
                    $image = new Image();
                    $image->id_product = $result->productId;
                    $image->position = $position;
                    $image->cover = $position === 1;
                    $image->legend = [];
                    foreach (Language::getLanguages(false) as $language) $image->legend[(int)$language['id_lang']] = 'CI original geometry ' . $position;
                    if (!$image->add() || !$image->associateTo([$shopId],$result->productId)) throw new RuntimeException('Could not associate isolated original image.');
                    $basePath = $image->getPathForCreation();
                    if (!ImageManager::resize($temporary,$basePath . '.jpg')) throw new RuntimeException('Could not persist isolated original image.');
                    foreach (ImageType::getImagesTypes('products') as $type) {
                        if (!ImageManager::resize($temporary,$basePath . '-' . $type['name'] . '.jpg',(int)$type['width'],(int)$type['height'])) throw new RuntimeException('Could not resize isolated original image.');
                    }
                } finally {
                    if (is_file($temporary)) unlink($temporary);
                }
            }
            $imageIds = $manager->imageIds($result->productId);
        }
        if (count($imageIds) !== 2) throw new RuntimeException('Gallery scenario requires exactly two local original images.');
        $imageRights = \Kuranea\Catalog\Domain\ProductImageRightsEvidence::record('seller_owned',
            'CI-generated original geometric images; local files only; run ' . $runId . '-' . $attempt . '; scenario gallery',
            'employee:' . $employeeId,new DateTimeImmutable('now',new DateTimeZone('UTC')),$imageIds);
    }
    if ($entry->status !== \Kuranea\Catalog\Domain\ProductReviewQueueEntry::STATUS_APPROVED) {
        $evidence = new \Kuranea\Catalog\Domain\ProductImportReviewEvidence(
            $draft->priceJpy, 0, 'explicitly_exempt', 'isolated synthetic CI only ' . $runId . '-' . $attempt,
            0, $categoryIds, true, ['en', 'ko'], $snapshot->contentHash
        );
        $linked = $queue->linkDraftIfCurrent($snapshot->deduplicationKey, $snapshot->contentHash, $result->productId, $imageRights, $evidence);
        if ($linked === null || $queue->approveIfPending($snapshot->deduplicationKey, $snapshot->contentHash, $result->productId,
            'employee:' . $employeeId, new DateTimeImmutable('now', new DateTimeZone('UTC')), $imageRights, $evidence) === null) {
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
        'synthetic_source' => true, 'reviewed_source' => true, 'inactive_nonorderable' => true, 'images_not_used' => $imageIds === [], 'image_ids' => $imageIds, 'category_ids' => $categoryIds];
}


/** Fixed, explicitly reviewed synthetic source path. Approved native drafts are never reclassified. */
function prepareCiProcurementReviewedCategoryIds(string $scenario, object $entry, int $shopId, string $runId, string $attempt): array
{
    if ($entry->status === \Kuranea\Catalog\Domain\ProductReviewQueueEntry::STATUS_APPROVED) {
        $ids = array_values(array_filter(array_map('intval', Product::getProductCategories((int)$entry->nativeProductId)),static fn(int $id): bool=>$id>0));
        if ($ids === []) throw new RuntimeException('Approved native fixture category association is missing.');
        return $ids;
    }
    if ($entry->status !== \Kuranea\Catalog\Domain\ProductReviewQueueEntry::STATUS_PENDING) throw new RuntimeException('Only a pending synthetic source may receive category review.');
    $homeId = (int)Configuration::get('PS_HOME_CATEGORY');
    if ($homeId < 1) throw new RuntimeException('Native fixture home category unavailable.');
    if ($scenario !== 'gallery') return [$homeId];
    if ($entry->snapshot->categories !== ['生活用品 > キッチン用品']) throw new RuntimeException('Synthetic source category mapping was not reviewed.');
    $groups = array_values(array_filter(array_map(static fn(array $row):int=>(int)$row['id_group'],Group::getGroups((int)Context::getContext()->language->id,$shopId)),static fn(int $id):bool=>$id>0));
    if ($groups === []) throw new RuntimeException('Native category access groups unavailable.');
    $parent = $homeId;
    foreach ([['ja'=>'生活用品','en'=>'Daily necessities','ko'=>'생활용품'],['ja'=>'キッチン用品','en'=>'Kitchenware','ko'=>'주방용품']] as $level=>$names) {
        $slug = 'ordenowa-ci-source-category-' . substr(hash('sha256',$runId . '-' . $attempt . '-gallery'),0,16) . '-' . $level;
        $existing = Db::getInstance()->getValue('SELECT cl.id_category FROM `'._DB_PREFIX_.'category_lang` cl INNER JOIN `'._DB_PREFIX_.'category_shop` cs ON cs.id_category=cl.id_category AND cs.id_shop=' . $shopId
            . ' WHERE cl.id_shop=' . $shopId . " AND cl.link_rewrite='" . pSQL($slug) . "' ORDER BY cl.id_category",false);
        if ((int)$existing > 0) {
            $category = new Category((int)$existing,null,$shopId);
            if ((int)$category->id_parent !== $parent || !(bool)$category->active || (int)$category->id_shop_default !== $shopId) throw new RuntimeException('Synthetic category identity collides with unrelated data.');
        } else {
            $category = new Category();
            $category->id_parent = $parent;
            $category->id_shop_default = $shopId;
            $category->is_root_category = false;
            $category->active = 1;
            $category->groupBox = $groups;
            $category->name = $category->link_rewrite = $category->description = [];
            foreach (Language::getLanguages(false) as $language) {
                $id = (int)$language['id_lang'];
                $category->name[$id] = $names[$language['iso_code']] ?? $names['ja'];
                $category->link_rewrite[$id] = $slug;
                $category->description[$id] = 'Explicit synthetic source category review; isolated CI only.';
            }
            if (!$category->add() || !$category->associateTo([$shopId])) throw new RuntimeException('Could not create reviewed native category path.');
        }
        $parent = (int)$category->id;
        if ($parent < 1) throw new RuntimeException('Native reviewed category identity missing.');
    }
    return [$parent];
}
