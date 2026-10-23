<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$attempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$project = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$expectedProject = 'kuranea-ci-' . $runId . '-' . $attempt;
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $attempt) !== 1
    || $project !== $expectedProject) {
    fwrite(STDERR, "BLOCKED: free-shipping product preparation requires its matching isolated GitHub Actions database.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf(
        'ORDENOWA_CI_FREE_SHIPPING_PRODUCT_STAGE=%s; exception=%s; message=%s',
        $stage,
        get_class($exception),
        substr($message, 0, 800)
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA free-shipping product fixture::' . $annotation . PHP_EOL);
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

$dbServer = defined('_DB_SERVER_') ? (string) _DB_SERVER_ : '';
$dbServerMatches = in_array($dbServer, ['mariadb', 'mariadb:3306'], true)
    && getenv('DB_SERVER') === 'mariadb'
    && getenv('DB_PORT') === '3306';
$dbNameMatches = defined('_DB_NAME_') && (string) _DB_NAME_ === 'prestashop';
$activeDatabaseMatches = $dbNameMatches
    && (string) Db::getInstance()->getValue('SELECT DATABASE()') === (string) _DB_NAME_;
if (!$dbServerMatches || !$dbNameMatches || !$activeDatabaseMatches) {
    throw new RuntimeException(sprintf(
        'The connected shop database failed its isolation guard: server_match=%s; configured_name_match=%s; active_connection_match=%s.',
        $dbServerMatches ? 'yes' : 'no',
        $dbNameMatches ? 'yes' : 'no',
        $activeDatabaseMatches ? 'yes' : 'no'
    ));
}

use Kuranea\Catalog\Domain\ProductAdminDraft;
use Kuranea\Catalog\Integration\PrestaShopNativeProductManager;

global $kernel;
$stage = 'Back Office kernel boot';
$kernel = new AdminKernel(_PS_ENV_, _PS_MODE_DEV_);
$kernel->boot();

$shopId = 1;
$languageId = (int) Language::getIdByIso('ja', true);
$currencyId = (int) Currency::getIdByIsoCode('JPY', $shopId);
$homeCategoryId = (int) Configuration::get('PS_HOME_CATEGORY');
if ($languageId < 1 || $currencyId < 1 || $homeCategoryId < 1) {
    throw new RuntimeException('The isolated shop is missing Japanese, JPY, or its home category.');
}
$context = Context::getContext();
$context->shop = new Shop($shopId);
$context->language = new Language($languageId, null, $shopId);
$context->currency = new Currency($currencyId, null, $shopId);
Shop::setContext(Shop::CONTEXT_SHOP, $shopId);

$stage = 'run-scoped no-rule product creation';
$manager = new PrestaShopNativeProductManager();
$categories = $manager->categories();
$categoryIds = array_map(static fn (array $row): int => (int) $row['id_category'], $categories);
if (!in_array($homeCategoryId, $categoryIds, true)) {
    throw new RuntimeException('The home category is unavailable to the Korean product manager in the isolated shop.');
}
$draft = ProductAdminDraft::fromArray([
    'name_ja' => '[CI ONLY] ORDENOWA free shipping product ' . $runId . '-' . $attempt,
    'name_ko' => '[CI ONLY] ORDENOWA 무료배송 검증 상품 ' . $runId . '-' . $attempt,
    'price_jpy' => '1000',
    'tax_rules_group_id' => '0',
    'quantity' => '5',
    'category_ids' => [(string) $homeCategoryId],
    'description_ja' => '[CI ONLY] Free-shipping checkout fixture with no tax rule assigned.',
    'description_ko' => '[CI ONLY] 무료배송 검증용 격리 상품입니다. 세금 규칙 미할당은 면세 판정이 아닙니다.',
    'options' => '',
]);
$productId = $manager->save(null, $draft);
$editor = $manager->editorData($productId);
if ((int) ($editor['price_jpy'] ?? 0) !== 1000 || (int) ($editor['tax_rules_group_id'] ?? -1) !== 0) {
    throw new RuntimeException('The isolated product manager did not preserve the JPY 1000 price and unassigned rule-group fixture.');
}

$stage = 'activate run-scoped customer-facing test product';
$reference = 'KURANEA-CI-' . $runId . '-' . $attempt;
$product = new Product($productId, false, null, $shopId);
$product->reference = $reference;
$product->active = 1;
$product->visibility = 'both';
$product->available_for_order = 1;
$product->show_price = 1;
if (!$product->update()) {
    throw new RuntimeException('Could not activate the run-scoped free-shipping product in the disposable CI shop.');
}

$stage = 're-read product sale fields and stock';
$product = new Product($productId, false, $languageId, $shopId);
$stockQuantity = (int) StockAvailable::getQuantityAvailableByProduct($productId, 0, $shopId);
if (!Validate::isLoadedObject($product)
    || (string) $product->reference !== $reference
    || !(bool) $product->active
    || (string) $product->visibility !== 'both'
    || !(bool) $product->available_for_order
    || !(bool) $product->show_price
    || (int) $product->id_tax_rules_group !== 0
    || abs((float) $product->price - 1000.0) > 0.00001
    || $stockQuantity < 2) {
    throw new RuntimeException('The free-shipping product failed its active, orderable, JPY price, no-rule, or stock re-read guard.');
}

echo json_encode([
    'product_id' => (int) $product->id,
    'reference' => (string) $product->reference,
    'price_jpy' => 1000,
    'quantity' => $stockQuantity,
    'tax_rules_group_id' => 0,
    'tax_scope' => 'unassigned rule group for an isolated free-shipping fixture; not a legal tax determination',
    'fixture_scope' => 'run-scoped isolated GitHub Actions disposable checkout database',
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
