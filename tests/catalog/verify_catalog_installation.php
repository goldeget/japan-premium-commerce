<?php

declare(strict_types=1);

$shopDomain = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['HTTP_HOST'] = $shopDomain;
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $shopDomain, PHP_URL_PORT) ?: 80);

require_once '/var/www/html/config/config.inc.php';
require_once '/var/www/html/modules/kuraneacatalog/autoload.php';

$moduleName = 'kuraneacatalog';
$module = Module::getInstanceByName($moduleName);
if (!$module || !Module::isInstalled($moduleName) || !(bool) $module->active) {
    throw new RuntimeException('KURANEA catalog review module was not installed and enabled.');
}

$adminTabId = (int) Tab::getIdFromClassName('AdminKuraneaCatalogReview');
$adminTab = $adminTabId > 0 ? new Tab($adminTabId) : null;
$tabNames = is_object($adminTab) && is_array($adminTab->name) ? array_values($adminTab->name) : [];
if ($adminTabId < 1 || !(bool) ($adminTab->active ?? false)
    || !in_array('상품 검수 대기열', $tabNames, true)) {
    throw new RuntimeException('The Korean catalog review Back Office tab is unavailable.');
}

$repository = \Kuranea\Catalog\Infrastructure\Persistence\CatalogQueueRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_);
$sourceDirectory = (string) getenv('KURANEA_CATALOG_QUEUE_DIR');
$resolvedQueueDirectory = realpath($sourceDirectory);
$resolvedShopRoot = realpath(_PS_ROOT_DIR_);
if ($resolvedQueueDirectory === false || $resolvedShopRoot === false
    || $resolvedQueueDirectory === $resolvedShopRoot
    || str_starts_with($resolvedQueueDirectory, rtrim($resolvedShopRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR)) {
    throw new RuntimeException('Catalog review storage is not outside the public PrestaShop webroot.');
}

$fetchedAt = new DateTimeImmutable('2026-10-22T00:00:00+00:00');
$fixture = file_get_contents('/tmp/kuranea-catalog-fixtures/amazon-jp-product.synthetic.html');
if ($fixture === false) {
    throw new RuntimeException('The synthetic catalog fixture could not be read.');
}
$snapshot = (new \Kuranea\Catalog\Parsing\AmazonJapanHtmlParser())->parse(
    $fixture,
    'https://www.amazon.co.jp/dp/B0KURANEA1',
    $fetchedAt
);
$entry = $repository->enqueue($snapshot, $fetchedAt);
$restored = $repository->find($entry->idempotencyKey);
if ($restored === null || $restored->snapshot->contentHash !== $snapshot->contentHash
    || $restored->status !== 'pending' || $restored->snapshot->source !== 'amazon_jp') {
    throw new RuntimeException('The synthetic pending review snapshot did not persist in the private queue volume.');
}

echo "PASS: Korean catalog admin tab and persistent synthetic review queue are installed\n";
