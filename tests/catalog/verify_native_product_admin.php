<?php

declare(strict_types=1);

// This integration test writes only to the disposable shop created by this CI run.
$runId = trim((string) getenv('KURANEA_CI_RUN_ID'));
$attempt = trim((string) getenv('KURANEA_CI_RUN_ATTEMPT'));
$project = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $attempt) !== 1
    || $project !== 'kuranea-ci-' . $runId . '-' . $attempt) {
    fwrite(STDERR, "BLOCKED: native product administration tests require the matching isolated GitHub Actions database.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf('KURANEA_NATIVE_PRODUCT_ADMIN_STAGE=%s; exception=%s; message=%s', $stage, get_class($exception), substr($message, 0, 1000));
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA native product admin::' . $annotation . PHP_EOL);
    }
    exit(1);
});

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php') || !is_file($shopRoot . '/app/AdminKernel.php')) {
    throw new RuntimeException('The isolated PrestaShop installation or Back Office kernel is missing.');
}
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
require_once $shopRoot . '/config/config.inc.php';
require_once $shopRoot . '/app/AdminKernel.php';
require_once $shopRoot . '/modules/kuraneacatalog/autoload.php';

use Kuranea\Catalog\Domain\ProductAdminDraft;
use Kuranea\Catalog\Integration\PrestaShopNativeProductManager;
use PrestaShop\PrestaShop\Adapter\SymfonyContainer;
use PrestaShop\PrestaShop\Core\Security\Permission;

global $kernel;
$stage = 'Back Office kernel boot';
$kernel = new AdminKernel(_PS_ENV_, _PS_MODE_DEV_);
$kernel->boot();

$shopId = 1;
$shop = new Shop($shopId);
$languageId = (int) Language::getIdByIso('ja', true);
$englishLanguageId = (int) Language::getIdByIso('en', true);
$currencyId = (int) Currency::getIdByIsoCode('JPY', $shopId);
$categoryId = (int) Configuration::get('PS_HOME_CATEGORY');
if (!Validate::isLoadedObject($shop) || $languageId < 1 || $englishLanguageId < 1 || $currencyId < 1 || $categoryId < 1) {
    throw new RuntimeException('The isolated shop is missing Japanese, English, JPY, or its home category.');
}
$context = Context::getContext();
$context->shop = $shop;
Shop::setContext(Shop::CONTEXT_SHOP, $shopId);
$context->language = new Language($languageId);
$context->currency = new Currency($currencyId, null, $shopId);
$context->employee = new Employee(1);
$kernel->getContainer()
    ->get(PrestaShop\PrestaShop\Core\Context\ContextBuilderPreparer::class)
    ->prepareFromLegacyContext($context);
if (SymfonyContainer::getInstance() === null) {
    throw new RuntimeException('The PrestaShop command bus container is unavailable.');
}
$managerTabId = (int) Tab::getIdFromClassName('AdminOrdenowaProductManager');
$shopParametersTabId = (int) Tab::getIdFromClassName('ShopParameters');
$managerTab = $managerTabId > 0 ? new Tab($managerTabId) : null;
if (!$managerTab instanceof Tab
    || $shopParametersTabId < 1
    || (int) $managerTab->id_parent !== $shopParametersTabId) {
    throw new RuntimeException('The Korean product manager tab is not registered under the visible ShopParameters menu.');
}
$stage = 'product manager read permission';
$readPermission = Permission::PREFIX_TAB . 'ADMINORDENOWAPRODUCTMANAGER_READ';
if (!Access::isGranted($readPermission, 1)) {
    throw new RuntimeException('The isolated shop administrator profile cannot read the Korean product manager tab.');
}

$stage = 'synthetic product edit category';
$editCategoryName = 'ORDENOWA CI EDIT CATEGORY ' . $runId . '-' . $attempt;
$categoryNames = [];
foreach (Language::getLanguages(false) as $language) {
    $idLanguage = (int) ($language['id_lang'] ?? 0);
    if ($idLanguage > 0) {
        $categoryNames[$idLanguage] = $editCategoryName;
    }
}
if ($categoryNames === []) {
    throw new RuntimeException('The isolated shop has no active language for its product edit category fixture.');
}
$editCategory = new Category();
$editCategory->id_parent = $categoryId;
$editCategory->id_shop_default = $shopId;
$editCategory->is_root_category = false;
$editCategory->active = 1;
$editCategory->name = $categoryNames;
$editCategory->link_rewrite = array_fill_keys(
    array_keys($categoryNames),
    'ordenowa-ci-edit-category-' . $runId . '-' . $attempt
);
if (!$editCategory->add()) {
    throw new RuntimeException('Could not create the isolated native product edit category.');
}
$editCategoryId = (int) $editCategory->id;
$visibleEditCategory = array_filter(
    (new PrestaShopNativeProductManager())->categories(),
    static fn (array $row): bool => (int) $row['id_category'] === $editCategoryId
);
if ($editCategoryId < 1 || $editCategoryId === $categoryId || count($visibleEditCategory) !== 1) {
    throw new RuntimeException('The isolated native product edit category is not available in the shop.');
}

$stage = 'synthetic product draft and image upload';
$png = base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGNU8qplYGBgYmBgYGBgAAAKuwDtbIwH5AAAAABJRU5ErkJggg==', true);
if (!is_string($png)) {
    throw new RuntimeException('Could not decode the synthetic image fixture.');
}
$imagePath = tempnam(sys_get_temp_dir(), 'ordenowa-product-admin-');
if ($imagePath === false || file_put_contents($imagePath, $png) === false) {
    throw new RuntimeException('Could not create the temporary synthetic product image.');
}
$imageUpload = ['name' => 'synthetic-product.png', 'tmp_name' => $imagePath, 'size' => strlen($png), 'error' => UPLOAD_ERR_OK];
$manager = new PrestaShopNativeProductManager();
$draft = ProductAdminDraft::fromArray([
    'name_ja' => 'ORDENOWA CI 合成商品',
    'name_en' => 'ORDENOWA CI Synthetic Product',
    'name_ko' => 'ORDENOWA CI 합성 상품',
    'price_jpy' => '1280',
    'tax_rules_group_id' => '0',
    'quantity' => '3',
    'category_ids' => [(string) $categoryId],
    'description_ja' => 'CI用の商品説明',
    'description_en' => 'Synthetic English product description',
    'description_ko' => 'CI용 상세 설명',
    'options' => "色:青|赤\nサイズ:S|M",
]);

$stage = 'native product create';
$productId = $manager->save(null, $draft, [$imageUpload]);
$product = new Product($productId, false, $languageId, $shopId);
$englishProduct = new Product($productId, false, $englishLanguageId, $shopId);
$combinationRows = Db::getInstance()->executeS(
    'SELECT `id_product_attribute` FROM `' . _DB_PREFIX_ . 'product_attribute` WHERE `id_product` = ' . (int) $productId . ' ORDER BY `id_product_attribute` ASC'
);
$createdCombinationIds = array_map(static fn (array $row): int => (int) $row['id_product_attribute'], is_array($combinationRows) ? $combinationRows : []);
$imageIds = $manager->imageIds($productId);
$englishSlug = (string) Db::getInstance()->getValue(
    'SELECT `link_rewrite` FROM `' . _DB_PREFIX_ . 'product_lang`'
    . ' WHERE `id_product` = ' . (int) $productId . ' AND `id_lang` = ' . (int) $englishLanguageId
    . ' AND `id_shop` = ' . (int) $shopId . ' LIMIT 1'
);
$englishImageLegend = (string) Db::getInstance()->getValue(
    'SELECT `legend` FROM `' . _DB_PREFIX_ . 'image_lang`'
    . ' WHERE `id_image` = ' . (int) ($imageIds[0] ?? 0) . ' AND `id_lang` = ' . (int) $englishLanguageId . ' LIMIT 1'
);
$categories = array_map('intval', Product::getProductCategories($productId));
$createdEditor = $manager->editorData($productId);
$createdManagedProducts = array_values(array_filter(
    $manager->managedProducts(),
    static fn (array $row): bool => (int) $row['id_product'] === $productId
));
$createdManagedProduct = $createdManagedProducts[0] ?? [];
$createChecks = [
    'loaded product' => Validate::isLoadedObject($product),
    'managed product reference' => str_starts_with((string) $product->reference, 'OWA-ADMIN-'),
    'inactive sale gate' => !(bool) $product->active
        && (string) $product->visibility === 'none'
        && !(bool) $product->available_for_order,
    'hidden price' => !(bool) $product->show_price,
    'JPY price' => (int) round((float) $product->price) === 1280,
    'Japanese name' => (string) $product->name === 'ORDENOWA CI 合成商品',
    'default category' => (int) $product->id_category_default === $categoryId,
    'category association' => in_array($categoryId, $categories, true),
    'editor Japanese name' => ($createdEditor['name_ja'] ?? '') === 'ORDENOWA CI 合成商品',
    'English name' => ($createdEditor['name_en'] ?? '') === 'ORDENOWA CI Synthetic Product',
    'editor Korean name' => ($createdEditor['name_ko'] ?? '') === 'ORDENOWA CI 합성 상품',
    'Japanese description' => ($createdEditor['description_ja'] ?? '') === 'CI用の商品説明',
    'English description' => ($createdEditor['description_en'] ?? '') === 'Synthetic English product description',
    'Korean description' => ($createdEditor['description_ko'] ?? '') === 'CI용 상세 설명',
    'native English product name' => (string) $englishProduct->name === 'ORDENOWA CI Synthetic Product',
    'native English product description' => strip_tags((string) $englishProduct->description) === 'Synthetic English product description',
    'English product slug' => $englishSlug === (string) Tools::str2url('ORDENOWA CI Synthetic Product'),
    'English image legend' => $englishImageLegend === 'ORDENOWA CI Synthetic Product',
    'editor category association' => in_array($categoryId, $createdEditor['category_ids'] ?? [], true),
    'managed product filter' => count($createdManagedProducts) === 1,
    'managed product Japanese name' => ($createdManagedProduct['name'] ?? '') === 'ORDENOWA CI 合成商品',
    'native option combinations' => is_array($combinationRows) && count($combinationRows) === 4,
    'product image count' => count($imageIds) === 1,
];
$createFailures = array_keys(array_filter($createChecks, static fn (bool $passed): bool => !$passed));
if ($createFailures !== []) {
    $englishFieldReadback = json_encode([
        'english_language_id' => $englishLanguageId,
        'expected_slug' => (string) Tools::str2url('ORDENOWA CI Synthetic Product'),
        'saved_slug' => substr($englishSlug, 0, 128),
        'expected_image_legend' => 'ORDENOWA CI Synthetic Product',
        'saved_image_legend' => substr($englishImageLegend, 0, 128),
    ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    if (!is_string($englishFieldReadback)) {
        $englishFieldReadback = '{}';
    }
    throw new RuntimeException(
        'Native product create failed checks: ' . implode(', ', $createFailures)
        . '; english-field readback=' . substr($englishFieldReadback, 0, 800) . '.'
    );
}

$createdEditorCombinationIds = array_map('intval', array_keys($createdEditor['combination_quantities'] ?? []));
sort($createdCombinationIds, SORT_NUMERIC);
sort($createdEditorCombinationIds, SORT_NUMERIC);
if ($createdEditorCombinationIds !== $createdCombinationIds
    || array_values($createdEditor['combination_quantities'] ?? []) !== [3, 3, 3, 3]
    || (int) ($createdEditor['quantity'] ?? -1) !== 0) {
    throw new RuntimeException('The product editor did not load stock for each native combination.');
}

foreach ($combinationRows as $row) {
    if ((int) StockAvailable::getQuantityAvailableByProduct($productId, (int) $row['id_product_attribute'], $shopId) !== 3) {
        throw new RuntimeException('The native stock rows do not contain the submitted per-combination quantity.');
    }
}
$storedGroups = $manager->optionGroups($productId, $languageId, $shopId);
if ($storedGroups !== [
    ['name' => '色', 'values' => ['青', '赤']],
    ['name' => 'サイズ', 'values' => ['S', 'M']],
]) {
    throw new RuntimeException('The native combinations do not preserve the submitted option groups.');
}
$firstImage = new Image($imageIds[0], null, $shopId);
$oldImagePath = (string) $firstImage->getPathForCreation() . '.jpg';
if (!is_file($oldImagePath) || getimagesize($oldImagePath) === false) {
    throw new RuntimeException('The product image was not converted to a readable PrestaShop image.');
}

$stage = 'image count validation before product mutation';
$tooManyImagesRejected = false;
try {
    $manager->save($productId, ProductAdminDraft::fromArray([
        'name_ja' => 'ORDENOWA CI validation should not save',
        'name_ko' => '저장되면 안 되는 이미지 제한 테스트',
        'price_jpy' => '1280',
        'tax_rules_group_id' => '0',
        'quantity' => '3',
        'category_ids' => [(string) $categoryId],
        'description_ja' => 'Unchanged if validation runs before mutation.',
        'description_ko' => '검증 실패 시 변경되지 않아야 합니다.',
        'options' => "色:青|赤\nサイズ:S|M",
    ]), array_fill(0, 5, $imageUpload));
} catch (InvalidArgumentException) {
    $tooManyImagesRejected = true;
}
$unchangedProduct = new Product($productId, false, $languageId, $shopId);
if (!$tooManyImagesRejected
    || (string) $unchangedProduct->name !== 'ORDENOWA CI 合成商品'
    || count($manager->imageIds($productId)) !== 1) {
    throw new RuntimeException('Adding a sixth image was not rejected before product or image mutation.');
}

$stage = 'native product edit';
$editedDraft = ProductAdminDraft::fromArray([
    'name_ja' => 'ORDENOWA CI 合成商品 수정',
    'name_en' => 'ORDENOWA CI Synthetic Product edited',
    'name_ko' => 'ORDENOWA CI 합성 상품 수정',
    'price_jpy' => '1490',
    'tax_rules_group_id' => '0',
    'quantity' => '5',
    'category_ids' => [(string) $editCategoryId],
    'description_ja' => '更新した説明',
    'description_en' => 'Updated English product description',
    'description_ko' => '수정한 상세 설명',
    'options' => "色:青|緑\nサイズ:S|M",
]);
$savedProductId = $manager->save($productId, $editedDraft, [$imageUpload], [$imageIds[0]]);
$editedProduct = new Product($savedProductId, false, $languageId, $shopId);
$editedEnglishProduct = new Product($savedProductId, false, $englishLanguageId, $shopId);
$editedCombinationRows = Db::getInstance()->executeS(
    'SELECT `id_product_attribute` FROM `' . _DB_PREFIX_ . 'product_attribute` WHERE `id_product` = ' . (int) $savedProductId . ' ORDER BY `id_product_attribute` ASC'
);
$editedCombinationIds = array_map(static fn (array $row): int => (int) $row['id_product_attribute'], is_array($editedCombinationRows) ? $editedCombinationRows : []);
$nativeCombinationValueRows = Db::getInstance()->executeS('
    SELECT pa.`id_product_attribute`, agl.`name` AS `group_name`, al.`name` AS `attribute_name`
    FROM `' . _DB_PREFIX_ . 'product_attribute` pa
    INNER JOIN `' . _DB_PREFIX_ . 'product_attribute_combination` pac
        ON pac.`id_product_attribute` = pa.`id_product_attribute`
    INNER JOIN `' . _DB_PREFIX_ . 'attribute` a ON a.`id_attribute` = pac.`id_attribute`
    INNER JOIN `' . _DB_PREFIX_ . 'attribute_group` ag ON ag.`id_attribute_group` = a.`id_attribute_group`
    INNER JOIN `' . _DB_PREFIX_ . 'attribute_group_lang` agl
        ON agl.`id_attribute_group` = ag.`id_attribute_group` AND agl.`id_lang` = ' . (int) $languageId . '
    INNER JOIN `' . _DB_PREFIX_ . 'attribute_lang` al
        ON al.`id_attribute` = a.`id_attribute` AND al.`id_lang` = ' . (int) $languageId . '
    WHERE pa.`id_product` = ' . (int) $savedProductId . '
    ORDER BY pa.`id_product_attribute` ASC, ag.`position` ASC, a.`position` ASC
');
$nativeCombinationValuesById = [];
foreach (is_array($nativeCombinationValueRows) ? $nativeCombinationValueRows : [] as $row) {
    $nativeCombinationValuesById[(int) $row['id_product_attribute']][(string) $row['group_name']] = (string) $row['attribute_name'];
}
$editedCombinationValueSets = [];
foreach ($nativeCombinationValuesById as $valuesByGroup) {
    if (isset($valuesByGroup['色'], $valuesByGroup['サイズ'])) {
        $editedCombinationValueSets[] = $valuesByGroup['色'] . '|' . $valuesByGroup['サイズ'];
    }
}
sort($editedCombinationValueSets, SORT_STRING);
$expectedEditedCombinationValueSets = ['青|S', '青|M', '緑|S', '緑|M'];
sort($expectedEditedCombinationValueSets, SORT_STRING);
$editedCategoryIds = array_map('intval', Product::getProductCategories($savedProductId));
$newImageIds = $manager->imageIds($savedProductId);
$editedEnglishSlug = (string) Db::getInstance()->getValue(
    'SELECT `link_rewrite` FROM `' . _DB_PREFIX_ . 'product_lang`'
    . ' WHERE `id_product` = ' . (int) $savedProductId . ' AND `id_lang` = ' . (int) $englishLanguageId
    . ' AND `id_shop` = ' . (int) $shopId . ' LIMIT 1'
);
$editedEnglishImageLegend = (string) Db::getInstance()->getValue(
    'SELECT `legend` FROM `' . _DB_PREFIX_ . 'image_lang`'
    . ' WHERE `id_image` = ' . (int) ($newImageIds[0] ?? 0) . ' AND `id_lang` = ' . (int) $englishLanguageId . ' LIMIT 1'
);
$editedEditor = $manager->editorData($savedProductId);
$editedOptionGroups = $manager->optionGroups($savedProductId, $languageId, $shopId);
$editedManagedProducts = array_values(array_filter(
    $manager->managedProducts(),
    static fn (array $row): bool => (int) $row['id_product'] === $savedProductId
));
// Report each persistence signal separately so CI annotations point to the data
// that failed instead of hiding it behind one aggregate assertion.
$editChecks = [
    'saved product ID' => $savedProductId === $productId,
    'Japanese name' => (string) $editedProduct->name === 'ORDENOWA CI 合成商品 수정',
    'price' => (int) round((float) $editedProduct->price) === 1490,
    'sale gate' => !(bool) $editedProduct->active
        && (string) $editedProduct->visibility === 'none'
        && !(bool) $editedProduct->available_for_order,
    'editor Japanese name' => ($editedEditor['name_ja'] ?? '') === 'ORDENOWA CI 合成商品 수정',
    'editor English name' => ($editedEditor['name_en'] ?? '') === 'ORDENOWA CI Synthetic Product edited',
    'editor Korean name' => ($editedEditor['name_ko'] ?? '') === 'ORDENOWA CI 합성 상품 수정',
    'Japanese description' => ($editedEditor['description_ja'] ?? '') === '更新した説明',
    'English description' => ($editedEditor['description_en'] ?? '') === 'Updated English product description',
    'Korean description' => ($editedEditor['description_ko'] ?? '') === '수정한 상세 설명',
    'native English product name' => (string) $editedEnglishProduct->name === 'ORDENOWA CI Synthetic Product edited',
    'native English product description' => strip_tags((string) $editedEnglishProduct->description) === 'Updated English product description',
    'English product slug' => $editedEnglishSlug === (string) Tools::str2url('ORDENOWA CI Synthetic Product edited'),
    'English image legend' => $editedEnglishImageLegend === 'ORDENOWA CI Synthetic Product edited',
    'category default' => (int) $editedProduct->id_category_default === $editCategoryId,
    'categories' => ($editedEditor['category_ids'] ?? []) === [$editCategoryId],
    'category association changed' => !in_array($editCategoryId, $createdEditor['category_ids'] ?? [], true),
    'new category association' => in_array($editCategoryId, $editedCategoryIds, true),
    'old category association removed' => !in_array($categoryId, $editedCategoryIds, true),
    'options' => ($editedEditor['options'] ?? '') === "色:青|緑\nサイズ:S|M",
    'managed product row count' => count($editedManagedProducts) === 1,
    'managed product name' => ($editedManagedProducts[0]['name'] ?? '') === 'ORDENOWA CI 合成商品 수정',
    'combination count' => count($editedCombinationRows) === 4,
    'combination IDs replaced' => count($editedCombinationIds) === 4
        && array_intersect($editedCombinationIds, $createdCombinationIds) === [],
    'option groups' => $editedOptionGroups === [
        ['name' => '色', 'values' => ['青', '緑']],
        ['name' => 'サイズ', 'values' => ['S', 'M']],
    ],
    'native option combinations' => $editedCombinationValueSets === $expectedEditedCombinationValueSets,
    'image count' => count($newImageIds) === 1,
    'image replacement' => count($newImageIds) === 1 && $newImageIds[0] !== $imageIds[0],
    'old image removal' => !file_exists($oldImagePath),
];
$editFailures = array_keys(array_filter($editChecks, static fn (bool $passed): bool => !$passed));
if ($editFailures !== []) {
    $englishEditFieldReadback = json_encode([
        'english_language_id' => $englishLanguageId,
        'expected_slug' => (string) Tools::str2url('ORDENOWA CI Synthetic Product edited'),
        'saved_slug' => substr($editedEnglishSlug, 0, 128),
        'expected_image_legend' => 'ORDENOWA CI Synthetic Product edited',
        'saved_image_legend' => substr($editedEnglishImageLegend, 0, 128),
    ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    if (!is_string($englishEditFieldReadback)) {
        $englishEditFieldReadback = '{}';
    }
    throw new RuntimeException(
        'Native product edit failed checks: ' . implode(', ', $editFailures)
        . '; english-field readback=' . substr($englishEditFieldReadback, 0, 800) . '.'
    );
}
foreach ($editedCombinationRows as $row) {
    if ((int) StockAvailable::getQuantityAvailableByProduct($savedProductId, (int) $row['id_product_attribute'], $shopId) !== 5) {
        throw new RuntimeException('Editing the product did not update every combination stock row.');
    }
}

$distinctCombinationQuantities = array_combine($editedCombinationIds, [0, 2, 4, 6]);
if (!is_array($distinctCombinationQuantities)) {
    throw new RuntimeException('Could not prepare distinct option stock values for the native combinations.');
}
$distinctStockDraft = ProductAdminDraft::fromArray([
    'name_ja' => 'ORDENOWA CI 合成商品 수정',
    'name_ko' => 'ORDENOWA CI 합성 상품 수정',
    'price_jpy' => '1490',
    'tax_rules_group_id' => '0',
    'quantity' => '5',
    'category_ids' => [(string) $editCategoryId],
    'description_ja' => '更新した説明',
    'description_ko' => '수정한 상세 설명',
    'options' => "色:青|緑\nサイズ:S|M",
    'combination_quantities' => $distinctCombinationQuantities,
]);
$manager->save($savedProductId, $distinctStockDraft);
$distinctStockEditor = $manager->editorData($savedProductId);
$actualDistinctCombinationQuantities = [];
foreach ($editedCombinationRows as $row) {
    $combinationId = (int) $row['id_product_attribute'];
    $actualDistinctCombinationQuantities[$combinationId] = (int) StockAvailable::getQuantityAvailableByProduct(
        $savedProductId,
        $combinationId,
        $shopId
    );
}
if ($actualDistinctCombinationQuantities !== $distinctCombinationQuantities
    || ($distinctStockEditor['combination_quantities'] ?? []) !== $distinctCombinationQuantities) {
    throw new RuntimeException('Saving unique combination quantities did not persist each native stock row.');
}

$savedProductAfterDistinctStock = new Product($savedProductId, false, $languageId, $shopId);
$quantityValidationCases = [
    'missing combination ID' => array_slice($distinctCombinationQuantities, 1, null, true),
];
$foreignCombinationId = max($editedCombinationIds) + 1;
$quantityValidationCases['foreign combination ID'] = $distinctCombinationQuantities + [$foreignCombinationId => 1];
foreach ($quantityValidationCases as $caseName => $invalidQuantityMap) {
    $quantityMapRejected = false;
    try {
        $manager->save($savedProductId, ProductAdminDraft::fromArray([
            'name_ja' => 'ORDENOWA CI INVALID STOCK MAP MUST NOT SAVE',
            'name_ko' => '저장되면 안 되는 옵션 재고 테스트',
            'price_jpy' => '1490',
            'tax_rules_group_id' => '0',
            'quantity' => '5',
            'category_ids' => [(string) $editCategoryId],
            'description_ja' => 'Invalid combination stock IDs must fail before product persistence.',
            'description_ko' => '옵션 재고 조합 검증은 상품 저장 전에 실행되어야 합니다.',
            'options' => "色:青|緑\nサイズ:S|M",
            'combination_quantities' => $invalidQuantityMap,
        ]));
    } catch (InvalidArgumentException) {
        $quantityMapRejected = true;
    }

    $productAfterInvalidQuantityMap = new Product($savedProductId, false, $languageId, $shopId);
    $stocksAfterInvalidQuantityMap = [];
    foreach ($editedCombinationRows as $row) {
        $combinationId = (int) $row['id_product_attribute'];
        $stocksAfterInvalidQuantityMap[$combinationId] = (int) StockAvailable::getQuantityAvailableByProduct(
            $savedProductId,
            $combinationId,
            $shopId
        );
    }
    if (!$quantityMapRejected
        || (string) $productAfterInvalidQuantityMap->name !== (string) $savedProductAfterDistinctStock->name
        || $stocksAfterInvalidQuantityMap !== $distinctCombinationQuantities) {
        throw new RuntimeException('Invalid ' . $caseName . ' was not rejected before product or stock persistence.');
    }
}

@unlink($imagePath);
printf("PASS: Korean admin service created and edited native inactive product ID=%d with JPY, categories, 4 variants, stock, and image replacement.\n", $productId);
