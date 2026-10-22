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

global $kernel;
$stage = 'Back Office kernel boot';
$kernel = new AdminKernel(_PS_ENV_, _PS_MODE_DEV_);
$kernel->boot();

$shopId = 1;
$shop = new Shop($shopId);
$languageId = (int) Language::getIdByIso('ja', true);
$currencyId = (int) Currency::getIdByIsoCode('JPY', $shopId);
$categoryId = (int) Configuration::get('PS_HOME_CATEGORY');
if (!Validate::isLoadedObject($shop) || $languageId < 1 || $currencyId < 1 || $categoryId < 1) {
    throw new RuntimeException('The isolated shop is missing Japanese, JPY, or its home category.');
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

$stage = 'synthetic product draft and image upload';
$png = base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/kWQAAAAASUVORK5CYII=', true);
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
    'name_ko' => 'ORDENOWA CI 합성 상품',
    'price_jpy' => '1280',
    'quantity' => '3',
    'category_ids' => [(string) $categoryId],
    'description_ja' => 'CI用の商品説明',
    'description_ko' => 'CI용 상세 설명',
    'options' => "色:青|赤\nサイズ:S|M",
]);

$stage = 'native product create';
$productId = $manager->save(null, $draft, [$imageUpload]);
$product = new Product($productId, false, $languageId, $shopId);
$combinationRows = Db::getInstance()->executeS(
    'SELECT `id_product_attribute` FROM `' . _DB_PREFIX_ . 'product_attribute` WHERE `id_product` = ' . (int) $productId . ' ORDER BY `id_product_attribute` ASC'
);
$createdCombinationIds = array_map(static fn (array $row): int => (int) $row['id_product_attribute'], is_array($combinationRows) ? $combinationRows : []);
$imageIds = $manager->imageIds($productId);
$categories = array_map('intval', Product::getProductCategories($productId));
$createdEditor = $manager->editorData($productId);
$createdManagedProducts = array_values(array_filter(
    $manager->managedProducts(),
    static fn (array $row): bool => (int) $row['id_product'] === $productId
));
if (!Validate::isLoadedObject($product)
    || !str_starts_with((string) $product->reference, 'OWA-ADMIN-')
    || (bool) $product->active
    || (string) $product->visibility !== 'none'
    || (bool) $product->available_for_order
    || (bool) $product->show_price
    || (int) round((float) $product->price) !== 1280
    || (string) $product->name !== 'ORDENOWA CI 合成商品'
    || (int) $product->id_category_default !== $categoryId
    || !in_array($categoryId, $categories, true)
    || ($createdEditor['name_ja'] ?? '') !== 'ORDENOWA CI 合成商品'
    || ($createdEditor['name_ko'] ?? '') !== 'ORDENOWA CI 합성 상품'
    || ($createdEditor['description_ja'] ?? '') !== 'CI用の商品説明'
    || ($createdEditor['description_ko'] ?? '') !== 'CI용 상세 설명'
    || !in_array($categoryId, $createdEditor['category_ids'] ?? [], true)
    || count($createdManagedProducts) !== 1
    || $createdManagedProducts[0]['name'] !== 'ORDENOWA CI 合成商品'
    || !is_array($combinationRows)
    || count($combinationRows) !== 4
    || count($imageIds) !== 1) {
    throw new RuntimeException('The created native product is missing fields or violated its inactive sale gate.');
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
    'name_ko' => 'ORDENOWA CI 합성 상품 수정',
    'price_jpy' => '1490',
    'quantity' => '5',
    'category_ids' => [(string) $categoryId],
    'description_ja' => '更新した説明',
    'description_ko' => '수정한 상세 설명',
    'options' => "色:青|赤\nサイズ:S|M",
]);
$savedProductId = $manager->save($productId, $editedDraft, [$imageUpload], [$imageIds[0]]);
$editedProduct = new Product($savedProductId, false, $languageId, $shopId);
$editedCombinationRows = Db::getInstance()->executeS(
    'SELECT `id_product_attribute` FROM `' . _DB_PREFIX_ . 'product_attribute` WHERE `id_product` = ' . (int) $savedProductId . ' ORDER BY `id_product_attribute` ASC'
);
$editedCombinationIds = array_map(static fn (array $row): int => (int) $row['id_product_attribute'], is_array($editedCombinationRows) ? $editedCombinationRows : []);
$newImageIds = $manager->imageIds($savedProductId);
$editedEditor = $manager->editorData($savedProductId);
$editedManagedProducts = array_values(array_filter(
    $manager->managedProducts(),
    static fn (array $row): bool => (int) $row['id_product'] === $savedProductId
));
if ($savedProductId !== $productId
    || (string) $editedProduct->name !== 'ORDENOWA CI 合成商品 수정'
    || (int) round((float) $editedProduct->price) !== 1490
    || (bool) $editedProduct->active
    || (string) $editedProduct->visibility !== 'none'
    || (bool) $editedProduct->available_for_order
    || ($editedEditor['name_ja'] ?? '') !== 'ORDENOWA CI 合成商品 수정'
    || ($editedEditor['name_ko'] ?? '') !== 'ORDENOWA CI 합성 상품 수정'
    || ($editedEditor['description_ja'] ?? '') !== '更新した説明'
    || ($editedEditor['description_ko'] ?? '') !== '수정한 상세 설명'
    || !in_array($categoryId, $editedEditor['category_ids'] ?? [], true)
    || ($editedEditor['options'] ?? '') !== "色:青|赤\nサイズ:S|M"
    || count($editedManagedProducts) !== 1
    || $editedManagedProducts[0]['name'] !== 'ORDENOWA CI 合成商品 수정'
    || count($editedCombinationRows) !== 4
    || $editedCombinationIds !== $createdCombinationIds
    || $manager->optionGroups($savedProductId, $languageId, $shopId) !== $storedGroups
    || count($newImageIds) !== 1
    || $newImageIds[0] === $imageIds[0]
    || file_exists($oldImagePath)) {
    throw new RuntimeException('The native product edit did not update fields, replace its image, or preserve the sale gate.');
}
foreach ($editedCombinationRows as $row) {
    if ((int) StockAvailable::getQuantityAvailableByProduct($savedProductId, (int) $row['id_product_attribute'], $shopId) !== 5) {
        throw new RuntimeException('Editing the product did not update every combination stock row.');
    }
}

@unlink($imagePath);
printf("PASS: Korean admin service created and edited native inactive product ID=%d with JPY, categories, 4 variants, stock, and image replacement.\n", $productId);
