<?php

declare(strict_types=1);

// This integration test only runs in a unique, disposable GitHub Actions shop.
// It approves one synthetic catalog snapshot; the actual native Product must
// remain inactive, invisible and non-orderable. No external product is fetched.
$runId = trim((string) getenv('KURANEA_CI_RUN_ID'));
$attempt = trim((string) getenv('KURANEA_CI_RUN_ATTEMPT'));
$project = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $attempt) !== 1
    || $project !== 'kuranea-ci-' . $runId . '-' . $attempt) {
    fwrite(STDERR, "BLOCKED: this native product test requires its own isolated GitHub Actions CI database.\n");
    exit(77);
}

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';
require_once '/var/www/html/modules/kuraneacatalog/autoload.php';

use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogQueueRepositoryFactory;
use Kuranea\Catalog\Integration\NativeProductRegistration;
use Kuranea\Catalog\Integration\PrestaShopNativeProductRegistrar;
use Kuranea\Catalog\Service\ProductApprovalService;

$shop = new Shop(1);
$langId = (int) Language::getIdByIso('ja', true);
if (!Validate::isLoadedObject($shop) || $langId < 1) {
    throw new RuntimeException('The isolated PrestaShop shop or Japanese locale is missing.');
}
$context = Context::getContext();
$context->shop = $shop;
$context->language = new Language($langId);
$context->currency = new Currency((int) Configuration::get('PS_CURRENCY_DEFAULT'));

$fixture = file_get_contents('/tmp/kuranea-catalog-fixtures/amazon-jp-product.synthetic.html');
if (!is_string($fixture) || $fixture === '') {
    throw new RuntimeException('The offline synthetic product fixture is missing.');
}
$fetchedAt = new DateTimeImmutable('2026-10-22T00:00:00+00:00');
$snapshot = (new AmazonJapanHtmlParser())->parse(
    $fixture,
    'https://www.amazon.co.jp/dp/B0KURANEA1',
    $fetchedAt
);
$queue = CatalogQueueRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_);
$entry = $queue->enqueue($snapshot, $fetchedAt);
$approver = 'CI-only-catalog-reviewer';
$approvedAt = new DateTimeImmutable('2026-10-22T12:30:00+00:00');
$expected = NativeProductRegistration::fromSnapshot($snapshot, $approver, $approvedAt);
$service = new ProductApprovalService($queue, new PrestaShopNativeProductRegistrar());
$approved = $service->approve($entry->idempotencyKey, $approver, $approvedAt, true);
$secondApproval = $service->approve($entry->idempotencyKey, $approver, $approvedAt, true);
$productId = (int) $approved->nativeProductId;
$product = new Product($productId, false, $langId, (int) $shop->id);

if ($productId < 1
    || (int) $secondApproval->nativeProductId !== $productId
    || !Validate::isLoadedObject($product)
    || (string) $product->reference !== $expected->reference
    || !str_starts_with((string) $product->name, '[TEST/DEMO] ')
    || (bool) $product->active
    || (string) $product->visibility !== 'none'
    || (bool) $product->available_for_order
    || (int) Product::getIdByReference($expected->reference) !== $productId) {
    throw new RuntimeException('Synthetic review approval did not produce one safe, inactive native Product.');
}
$matching = (int) Db::getInstance()->getValue(
    "SELECT COUNT(*) FROM " . _DB_PREFIX_ . "product WHERE reference = '" . pSQL($expected->reference) . "'"
);
if ($matching !== 1) {
    throw new RuntimeException('Synthetic catalog approval created duplicate native Product references.');
}
printf("PASS: reviewed synthetic product registered as one inactive, hidden, non-orderable PrestaShop Product ID=%d.\n", $productId);
