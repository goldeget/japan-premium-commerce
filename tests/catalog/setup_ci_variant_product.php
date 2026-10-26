<?php

declare(strict_types=1);

// Creates one searchable option product only inside the matching disposable CI shop.
$runId = trim((string) getenv('KURANEA_CI_RUN_ID'));
$attempt = trim((string) getenv('KURANEA_CI_RUN_ATTEMPT'));
$project = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$taxRulesGroupId = trim((string) getenv('CI_TEST_TAX_RULES_GROUP_ID'));
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $attempt) !== 1
    || preg_match('/\A[1-9][0-9]{0,8}\z/D', $taxRulesGroupId) !== 1
    || $project !== 'kuranea-ci-' . $runId . '-' . $attempt) {
    fwrite(STDERR, "BLOCKED: the CI-only variant product requires the matching isolated GitHub Actions database.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf(
        'ORDENOWA_CI_VARIANT_PRODUCT_STAGE=%s; exception=%s; message=%s',
        $stage,
        get_class($exception),
        substr($message, 0, 1000)
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA CI variant product::' . $annotation . PHP_EOL);
    }
    exit(1);
});

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php') || !is_file($shopRoot . '/app/AdminKernel.php')) {
    throw new RuntimeException('The disposable PrestaShop installation or Back Office kernel is missing.');
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
$languageId = (int) Language::getIdByIso('ja', true);
$currencyId = (int) Currency::getIdByIsoCode('JPY', $shopId);
if ($languageId < 1 || $currencyId < 1) {
    throw new RuntimeException('The isolated shop is missing Japanese or JPY.');
}
$context = Context::getContext();
$context->shop = new Shop($shopId);
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
$taxRulesGroupId = (int) $taxRulesGroupId;

$reference = 'OWA-CI-VARIANT-' . $runId . '-' . $attempt;
$existingId = (int) Db::getInstance()->getValue(
    "SELECT `id_product` FROM `" . _DB_PREFIX_ . "product` WHERE `reference` = '" . pSQL($reference) . "' LIMIT 1"
);
$manager = new PrestaShopNativeProductManager();
$availableTaxGroupIds = array_map(
    static fn (array $row): int => (int) $row['id_tax_rules_group'],
    $manager->taxRulesGroups()
);
if (!in_array($taxRulesGroupId, $availableTaxGroupIds, true)) {
    throw new RuntimeException('The seeded synthetic CI tax rules group is not available to this shop.');
}
$defaultCountryId = (int) Configuration::get('PS_COUNTRY_DEFAULT');
$taxAddress = new Address();
$taxAddress->id_country = $defaultCountryId;
$taxAddress->id_state = 0;
$taxAddress->postcode = '0';
$taxCalculator = TaxManagerFactory::getManager($taxAddress, $taxRulesGroupId)->getTaxCalculator();
if (round((float) $taxCalculator->getTotalRate(), 6) !== 10.0) {
    throw new RuntimeException('The cart fixture requires the CI synthetic group to resolve to the 10% test rate.');
}
if ($existingId > 0) {
    $stage = 'existing run-scoped fixture validation';
    $product = new Product($existingId, false, $languageId, $shopId);
    $groups = $manager->optionGroups($existingId, $languageId, $shopId);
    $combinationRows = Db::getInstance()->executeS(
        'SELECT pa.`id_product_attribute`, pac.`id_attribute`, a.`id_attribute_group`, al.`name` AS `value_name`, agl.`name` AS `group_name`, pa.`default_on`
        FROM `' . _DB_PREFIX_ . 'product_attribute` pa
        INNER JOIN `' . _DB_PREFIX_ . 'product_attribute_combination` pac
            ON pac.`id_product_attribute` = pa.`id_product_attribute`
        INNER JOIN `' . _DB_PREFIX_ . 'attribute` a ON a.`id_attribute` = pac.`id_attribute`
        INNER JOIN `' . _DB_PREFIX_ . 'attribute_lang` al
            ON al.`id_attribute` = a.`id_attribute` AND al.`id_lang` = ' . (int) $languageId . '
        INNER JOIN `' . _DB_PREFIX_ . 'attribute_group_lang` agl
            ON agl.`id_attribute_group` = a.`id_attribute_group` AND agl.`id_lang` = ' . (int) $languageId . '
        WHERE pa.`id_product` = ' . (int) $existingId . '
        ORDER BY pa.`id_product_attribute` ASC'
    );
    $defaultRows = is_array($combinationRows)
        ? array_values(array_filter($combinationRows, static fn (array $row): bool => (int) $row['default_on'] === 1))
        : [];
    $koreanLanguageId = (int) Language::getIdByIso('ko', true);
    $koreanName = $koreanLanguageId > 0
        ? (string) Db::getInstance()->getValue(
            'SELECT `name` FROM `' . _DB_PREFIX_ . 'product_lang`
            WHERE `id_product` = ' . (int) $existingId . ' AND `id_shop` = ' . (int) $shopId . ' AND `id_lang` = ' . (int) $koreanLanguageId
        )
        : '';
    if (!Validate::isLoadedObject($product)
        || (string) $product->reference !== $reference
        || (string) $product->name !== '[CI ONLY] ORDENOWA カートオプション ' . $runId . '-' . $attempt
        || $koreanName !== '[CI ONLY] ORDENOWA 장바구니 옵션 ' . $runId . '-' . $attempt
        || (int) $product->id_tax_rules_group !== $taxRulesGroupId
        || abs((int) Tools::ps_round($taxCalculator->addTaxes((float) $product->price), 0) - 550) > 0
        || !(bool) $product->active
        || (string) $product->visibility !== 'both'
        || !(bool) $product->available_for_order
        || !(bool) $product->show_price
        || count($groups) !== 1
        || ($groups[0] ?? []) !== ['name' => 'Color', 'values' => ['Blue', 'Red']]
        || !is_array($combinationRows)
        || count($combinationRows) !== 2
        || array_column($combinationRows, 'value_name') !== ['Blue', 'Red']
        || array_column($combinationRows, 'group_name') !== ['Color', 'Color']
        || count($defaultRows) !== 1
        || (string) ($defaultRows[0]['value_name'] ?? '') !== 'Blue'
        || (int) StockAvailable::getQuantityAvailableByProduct($existingId, 0, $shopId) !== 0) {
        throw new RuntimeException('A partial or invalid run-scoped variant fixture already exists; refusing to create a duplicate.');
    }
    foreach ($combinationRows as $row) {
        $quantity = (int) StockAvailable::getQuantityAvailableByProduct(
            $existingId,
            (int) $row['id_product_attribute'],
            $shopId
        );
        if ($quantity !== 8) {
            throw new RuntimeException('An existing variant fixture combination does not have the expected quantity of eight.');
        }
    }
    $productId = $existingId;
} else {
    $stage = 'native variant fixture draft';
    $categories = $manager->categories();
    $categoryId = (int) ($categories[0]['id_category'] ?? 0);
    if ($categoryId < 1) {
        throw new RuntimeException('The isolated shop has no active product category for the variant fixture.');
    }
    $taxGroupIsAvailable = in_array(
        $taxRulesGroupId,
        array_map(static fn (array $row): int => (int) $row['id_tax_rules_group'], $manager->taxRulesGroups()),
        true
    );
    if (!$taxGroupIsAvailable) {
        throw new RuntimeException('The seeded synthetic CI tax rules group is not available to this shop.');
    }
    $draft = ProductAdminDraft::fromArray([
        'name_ja' => '[CI ONLY] ORDENOWA カートオプション ' . $runId . '-' . $attempt,
        'name_ko' => '[CI ONLY] ORDENOWA 장바구니 옵션 ' . $runId . '-' . $attempt,
        // Synthetic 10% test group: JPY 550 customer price stores as JPY 500 before tax.
        'price_jpy' => '550',
        'tax_rules_group_id' => (string) $taxRulesGroupId,
        'quantity' => '8',
        'category_ids' => [(string) $categoryId],
        'description_ja' => '[CI ONLY] カート操作テスト用の合成商品です。販売用商品ではありません。',
        'description_ko' => '[CI ONLY] 장바구니 옵션 선택 검증용 합성 상품입니다. 판매용 상품이 아닙니다.',
        'options' => 'Color:Blue|Red',
        'combination_quantities' => [],
    ]);
    $productId = $manager->save(null, $draft);
    $storedDraft = new Product($productId, false, $languageId, $shopId);
    $editorDraft = $manager->editorData($productId);
    if (!Validate::isLoadedObject($storedDraft)
        || (int) $storedDraft->id_tax_rules_group !== $taxRulesGroupId
        || abs((float) $storedDraft->price - 500.0) > 0.00001
        || (int) ($editorDraft['price_jpy'] ?? 0) !== 550
        || (int) ($editorDraft['tax_rules_group_id'] ?? -1) !== $taxRulesGroupId) {
        throw new RuntimeException('The taxable option fixture must store JPY 550 inclusive as JPY 500 before tax under its explicit synthetic group.');
    }

    $stage = 'activate disposable searchable fixture';
    $product = new Product($productId, false, null, $shopId);
    if (!Validate::isLoadedObject($product)) {
        throw new RuntimeException('Could not reload the native product fixture.');
    }
    $product->reference = $reference;
    $product->active = 1;
    $product->visibility = 'both';
    $product->available_for_order = 1;
    $product->show_price = 1;
    if (!$product->update()) {
        throw new RuntimeException('Could not publish the searchable fixture inside the disposable CI shop.');
    }
}

$stage = 'index active Japanese option fixture in native storefront search';
Search::indexation(false, $productId);

$stage = 'native option and stock verification';
$product = new Product($productId, false, $languageId, $shopId);
$groups = $manager->optionGroups($productId, $languageId, $shopId);
$combinationRows = Db::getInstance()->executeS(
    'SELECT pa.`id_product_attribute`, pac.`id_attribute`, a.`id_attribute_group`, al.`name` AS `value_name`, agl.`name` AS `group_name`, pa.`default_on`
    FROM `' . _DB_PREFIX_ . 'product_attribute` pa
    INNER JOIN `' . _DB_PREFIX_ . 'product_attribute_combination` pac
        ON pac.`id_product_attribute` = pa.`id_product_attribute`
    INNER JOIN `' . _DB_PREFIX_ . 'attribute` a ON a.`id_attribute` = pac.`id_attribute`
    INNER JOIN `' . _DB_PREFIX_ . 'attribute_lang` al
        ON al.`id_attribute` = a.`id_attribute` AND al.`id_lang` = ' . (int) $languageId . '
    INNER JOIN `' . _DB_PREFIX_ . 'attribute_group_lang` agl
        ON agl.`id_attribute_group` = a.`id_attribute_group` AND agl.`id_lang` = ' . (int) $languageId . '
    WHERE pa.`id_product` = ' . (int) $productId . '
    ORDER BY pa.`id_product_attribute` ASC'
);
$attributeIds = [];
$groupIds = [];
$defaultRows = [];
if (is_array($combinationRows)) {
    foreach ($combinationRows as $row) {
        $attributeIds[] = (int) $row['id_attribute'];
        $groupIds[] = (int) $row['id_attribute_group'];
        if ((int) $row['default_on'] === 1) {
            $defaultRows[] = $row;
        }
        $quantity = (int) StockAvailable::getQuantityAvailableByProduct(
            $productId,
            (int) $row['id_product_attribute'],
            $shopId
        );
        if ($quantity !== 8) {
            throw new RuntimeException('A native option combination does not have the exact expected stock of eight units.');
        }
    }
}
$koreanLanguageId = (int) Language::getIdByIso('ko', true);
$koreanName = $koreanLanguageId > 0
    ? (string) Db::getInstance()->getValue(
        'SELECT `name` FROM `' . _DB_PREFIX_ . 'product_lang`
        WHERE `id_product` = ' . (int) $productId . ' AND `id_shop` = ' . (int) $shopId . ' AND `id_lang` = ' . (int) $koreanLanguageId
    )
    : '';
if (!Validate::isLoadedObject($product)
    || (string) $product->reference !== $reference
    || (string) $product->name !== '[CI ONLY] ORDENOWA カートオプション ' . $runId . '-' . $attempt
    || $koreanName !== '[CI ONLY] ORDENOWA 장바구니 옵션 ' . $runId . '-' . $attempt
    || (int) $product->id_tax_rules_group !== $taxRulesGroupId
    || abs((float) $product->price - 500.0) > 0.00001
    || abs((int) Tools::ps_round($taxCalculator->addTaxes((float) $product->price), 0) - 550) > 0
    || !(bool) $product->active
    || (string) $product->visibility !== 'both'
    || !(bool) $product->available_for_order
    || !(bool) $product->show_price
    || count($groups) !== 1
    || ($groups[0] ?? []) !== ['name' => 'Color', 'values' => ['Blue', 'Red']]
    || !is_array($combinationRows)
    || count($combinationRows) !== 2
    || array_column($combinationRows, 'value_name') !== ['Blue', 'Red']
    || array_column($combinationRows, 'group_name') !== ['Color', 'Color']
    || count($defaultRows) !== 1
    || (string) ($defaultRows[0]['value_name'] ?? '') !== 'Blue'
    || count(array_unique($attributeIds)) !== 2
    || count(array_unique($groupIds)) !== 1
    || (int) StockAvailable::getQuantityAvailableByProduct($productId, 0, $shopId) !== 0) {
    throw new RuntimeException('The active CI fixture must expose two named native values, one Blue default, exact stock, and a zero root stock row.');
}

printf("PASS: [CI ONLY] native option product is searchable, active, and stocked.\n");
printf("CI_TEST_VARIANT_PRODUCT_ID=%d\n", $productId);
