<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== 'kuranea-ci-' . $runId . '-' . $runAttempt) {
    fwrite(STDERR, "BLOCKED: explicit exemption fixtures require their matching isolated GitHub Actions database.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf(
        'ORDENOWA_CI_EXEMPTION_PRODUCT_STAGE=%s; exception=%s; message=%s',
        $stage,
        get_class($exception),
        substr($message, 0, 800)
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA explicit exemption fixture::' . $annotation . PHP_EOL);
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
$dbNameMatches = defined('_DB_NAME_') && (string) _DB_NAME_ === 'prestashop';
$activeDatabaseMatches = $dbNameMatches
    && (string) Db::getInstance()->getValue('SELECT DATABASE()') === (string) _DB_NAME_;
if (!in_array($dbServer, ['mariadb', 'mariadb:3306'], true)
    || getenv('DB_SERVER') !== 'mariadb'
    || getenv('DB_PORT') !== '3306'
    || !$activeDatabaseMatches) {
    throw new RuntimeException('The explicit exemption fixture is not connected to its isolated MariaDB database.');
}

use Kuranea\Catalog\Domain\ProductAdminDraft;
use Kuranea\Catalog\Integration\PrestaShopNativeProductManager;

global $kernel;
$stage = 'isolated Back Office kernel boot';
$kernel = new AdminKernel(_PS_ENV_, _PS_MODE_DEV_);
$kernel->boot();
$shopId = 1;
$languageId = (int) Language::getIdByIso('ja', true);
$currencyId = (int) Currency::getIdByIsoCode('JPY', $shopId);
$homeCategoryId = (int) Configuration::get('PS_HOME_CATEGORY');
$japanCountryId = (int) Country::getByIso('JP');
if ($languageId < 1 || $currencyId < 1 || $homeCategoryId < 1 || $japanCountryId < 1) {
    throw new RuntimeException('The isolated shop is missing Japanese, JPY, home category, or Japan country data.');
}
$context = Context::getContext();
$context->shop = new Shop($shopId);
$context->language = new Language($languageId, null, $shopId);
$context->currency = new Currency($currencyId, null, $shopId);
Shop::setContext(Shop::CONTEXT_SHOP, $shopId);

$stage = 'create explicit CI-only zero-rate rules group';
$taxGroup = new TaxRulesGroup();
$taxGroup->name = '[CI ONLY] explicit exemption test ' . $runId . '-' . $runAttempt;
$taxGroup->active = 1;
$taxGroup->deleted = 0;
if (!$taxGroup->add()) {
    throw new RuntimeException('Could not create the CI-only explicit exemption tax rules group.');
}
$taxGroupId = (int) $taxGroup->id;
if ($taxGroupId < 1 || (method_exists($taxGroup, 'associateTo') && !$taxGroup->associateTo([$shopId]))) {
    throw new RuntimeException('Could not associate the explicit exemption tax group with the isolated shop.');
}

$languageIds = array_values(array_filter(array_map(
    static fn (array $language): int => (int) ($language['id_lang'] ?? 0),
    Language::getLanguages(false)
), static fn (int $id): bool => $id > 0));
$tax = new Tax();
$tax->rate = 0.0;
$tax->active = 1;
$tax->deleted = 0;
$taxName = '[CI ONLY] explicit 0% QA';
if (strlen($taxName) > 32) {
    throw new RuntimeException('The CI-only tax label exceeds PrestaShop\'s native 32-character limit.');
}
$tax->name = array_fill_keys($languageIds, $taxName);
if (!$tax->add()) {
    throw new RuntimeException('Could not create the CI-only explicit zero tax rate.');
}
$taxId = (int) $tax->id;
$taxRule = new TaxRule();
$taxRule->id_tax_rules_group = $taxGroupId;
$taxRule->id_country = $japanCountryId;
$taxRule->id_state = 0;
$taxRule->zipcode_from = '0';
$taxRule->zipcode_to = '0';
$taxRule->id_tax = $taxId;
$taxRule->behavior = 0;
$taxRule->description = '[CI ONLY] explicit zero-rate exemption QA; not a legal tax determination';
if (!$taxRule->add()) {
    throw new RuntimeException('Could not add the explicit CI-only Japan zero-rate tax rule.');
}

$ruleRows = Db::getInstance()->executeS(
    'SELECT tr.`id_tax_rules_group`, tr.`id_country`, tr.`id_state`, tr.`zipcode_from`, tr.`zipcode_to`,'
    . ' t.`id_tax`, t.`rate`, t.`active`'
    . ' FROM `' . _DB_PREFIX_ . 'tax_rule` tr'
    . ' INNER JOIN `' . _DB_PREFIX_ . 'tax` t ON t.`id_tax` = tr.`id_tax`'
    . ' WHERE tr.`id_tax_rules_group` = ' . (int) $taxGroupId
);
$shopAssociationCount = (int) Db::getInstance()->getValue(
    'SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'tax_rules_group_shop`'
    . ' WHERE `id_tax_rules_group` = ' . (int) $taxGroupId . ' AND `id_shop` = ' . (int) $shopId
);
if (!(bool) $taxGroup->active
    || (int) $taxGroup->deleted !== 0
    || (string) $taxGroup->name !== '[CI ONLY] explicit exemption test ' . $runId . '-' . $runAttempt
    || !is_array($ruleRows)
    || count($ruleRows) !== 1
    || (int) $ruleRows[0]['id_tax_rules_group'] !== $taxGroupId
    || (int) $ruleRows[0]['id_tax'] !== $taxId
    || (int) $ruleRows[0]['id_country'] !== $japanCountryId
    || (int) $ruleRows[0]['id_state'] !== 0
    || (string) $ruleRows[0]['zipcode_from'] !== '0'
    || (string) $ruleRows[0]['zipcode_to'] !== '0'
    || abs((float) $ruleRows[0]['rate']) > 0.000001
    || (int) $ruleRows[0]['active'] !== 1
    || $shopAssociationCount !== 1) {
    throw new RuntimeException('The exemption test group must have exactly one active Japan-wide 0% rule and shop association.');
}
$japanAddress = new Address();
$japanAddress->id_country = $japanCountryId;
$japanAddress->id_state = 0;
$japanAddress->postcode = '100-0004';
$taxCalculator = TaxManagerFactory::getManager($japanAddress, $taxGroupId)->getTaxCalculator();
if (abs((float) $taxCalculator->getTotalRate()) > 0.000001
    || abs((float) Tools::ps_round($taxCalculator->addTaxes(1000.0), 0) - 1000.0) > 0.000001) {
    throw new RuntimeException('PrestaShop did not resolve the explicit zero-rate rule for the Tokyo test address.');
}

$stage = 'create explicit CI-only exemption product';
$manager = new PrestaShopNativeProductManager();
$categories = $manager->categories();
$categoryIds = array_map(static fn (array $row): int => (int) $row['id_category'], $categories);
if (!in_array($homeCategoryId, $categoryIds, true)) {
    throw new RuntimeException('The home category is unavailable to the Korean product manager in the isolated shop.');
}
$draft = ProductAdminDraft::fromArray([
    'name_ja' => '[CI ONLY] ORDENOWA explicit exemption test ' . $runId . '-' . $runAttempt,
    'name_ko' => '[CI ONLY] ORDENOWA 명시 면세 QA 상품 ' . $runId . '-' . $runAttempt,
    'price_jpy' => '1000',
    'tax_rules_group_id' => (string) $taxGroupId,
    'quantity' => '5',
    'category_ids' => [(string) $homeCategoryId],
    'description_ja' => '[CI ONLY] Explicit zero-rate test fixture for exemption-path QA; not a legal tax determination.',
    'description_ko' => '[CI ONLY] 명시적 0% 세금 그룹 테스트 상품이며 실제 세무 판정이나 법정 세율이 아닙니다.',
    'options' => '',
]);
$productId = $manager->save(null, $draft);
$product = new Product($productId, false, $languageId, $shopId);
$editor = $manager->editorData($productId);
if (!Validate::isLoadedObject($product)
    || (int) $product->id_tax_rules_group !== $taxGroupId
    || abs((float) $product->price - 1000.0) > 0.000001
    || (int) ($editor['price_jpy'] ?? 0) !== 1000
    || (int) ($editor['tax_rules_group_id'] ?? -1) !== $taxGroupId) {
    throw new RuntimeException('The native product manager did not preserve the ¥1,000 price and explicit positive exemption group ID.');
}
$product->reference = 'ORDENOWA-CI-EXEMPT-' . $runId . '-' . $runAttempt;
$product->active = 1;
$product->visibility = 'both';
$product->available_for_order = 1;
$product->show_price = 1;
if (!$product->update()) {
    throw new RuntimeException('Could not activate the exemption test product in the disposable CI shop.');
}
Search::indexation(false, (int) $product->id);
$product = new Product($productId, false, $languageId, $shopId);
$stockQuantity = (int) StockAvailable::getQuantityAvailableByProduct($productId, 0, $shopId);
if (!Validate::isLoadedObject($product)
    || (int) $product->id_tax_rules_group !== $taxGroupId
    || !(bool) $product->active
    || !(bool) $product->available_for_order
    || !(bool) $product->show_price
    || abs((float) $product->price - 1000.0) > 0.000001
    || $stockQuantity < 1) {
    throw new RuntimeException('The exemption test product failed its active, price, tax-group, or stock readback.');
}

$taxFixtureScope = 'CI-only explicit zero-rate exemption test fixture; not a legal tax rate or tax determination';
echo json_encode([
    'product_id' => $productId,
    'reference' => (string) $product->reference,
    'price_jpy' => 1000,
    'price_tax_excl_jpy' => (float) $product->price,
    'quantity' => $stockQuantity,
    'tax_status' => 'explicit_exemption_test',
    'tax_rules_group_id' => $taxGroupId,
    'tax_rate_percent' => 0.0,
    'tax_fixture_scope' => $taxFixtureScope,
    'fixture_scope' => 'run-scoped isolated GitHub Actions disposable checkout database',
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDERR, sprintf(
    "PASS: [CI ONLY] explicit zero-rate Japan test group %d is attached to product %d; no seller tax status was inferred.\n",
    $taxGroupId,
    $productId
));
