<?php

declare(strict_types=1);

// Disposable CI integration: synthetic tax rules are test data, not a statement about legal tax rates.
$runId = trim((string) getenv('KURANEA_CI_RUN_ID'));
$attempt = trim((string) getenv('KURANEA_CI_RUN_ATTEMPT'));
$project = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $attempt) !== 1
    || $project !== 'kuranea-ci-' . $runId . '-' . $attempt) {
    fwrite(STDERR, "BLOCKED: the synthetic product tax test requires the matching isolated GitHub Actions database.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf(
        'ORDENOWA_CI_PRODUCT_TAX_STAGE=%s; exception=%s; message=%s',
        $stage,
        get_class($exception),
        substr($message, 0, 1000)
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA synthetic product tax::' . $annotation . PHP_EOL);
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
$languageId = (int) Language::getIdByIso('ja', true);
$currencyId = (int) Currency::getIdByIsoCode('JPY', $shopId);
$japanCountryId = (int) Country::getByIso('JP');
$homeCategoryId = (int) Configuration::get('PS_HOME_CATEGORY');
$shopGroups = Group::getGroups($languageId, $shopId);
$shopGroupPriceMethods = [];
foreach (is_array($shopGroups) ? $shopGroups : [] as $groupRow) {
    $groupId = (int) ($groupRow['id_group'] ?? 0);
    if ($groupId > 0) {
        $shopGroupPriceMethods[$groupId] = (int) ($groupRow['price_display_method'] ?? -1);
    }
}
$requiredGroupIds = array_map(
    static fn (string $configurationKey): int => (int) Configuration::get($configurationKey),
    ['PS_UNIDENTIFIED_GROUP', 'PS_GUEST_GROUP', 'PS_CUSTOMER_GROUP']
);
$groupPriceDisplayConstantsMatchPrestaShop92 = Group::PRICE_DISPLAY_METHOD_TAX_INCL === 0
    && Group::PRICE_DISPLAY_METHOD_TAX_EXCL === 1;
$allStorefrontGroupPricesIncludeTax = $shopGroupPriceMethods !== []
    && $groupPriceDisplayConstantsMatchPrestaShop92
    && array_reduce(
        $shopGroupPriceMethods,
        static fn (bool $included, int $method): bool => $included && $method === Group::PRICE_DISPLAY_METHOD_TAX_INCL,
        true
    )
    && array_reduce(
        $requiredGroupIds,
        static fn (bool $present, int $groupId): bool => $present && $groupId > 0 && array_key_exists($groupId, $shopGroupPriceMethods),
        true
    );
$shop = new Shop($shopId);
if (!Validate::isLoadedObject($shop)
    || $languageId < 1
    || $currencyId < 1
    || $japanCountryId < 1
    || $homeCategoryId < 1
    || !(bool) Configuration::get('PS_TAX')
    || !$allStorefrontGroupPricesIncludeTax) {
    throw new RuntimeException('The isolated Japanese JPY shop must have active tax calculation and tax-included display for all configured customer groups in this test.');
}
$context = Context::getContext();
$context->shop = $shop;
Shop::setContext(Shop::CONTEXT_SHOP, $shopId);
$context->language = new Language($languageId);
$context->country = new Country($japanCountryId, $languageId);
$context->currency = new Currency($currencyId, null, $shopId);
$context->employee = new Employee(1);
$context->cart = new Cart();
$kernel->getContainer()
    ->get(PrestaShop\PrestaShop\Core\Context\ContextBuilderPreparer::class)
    ->prepareFromLegacyContext($context);
if (SymfonyContainer::getInstance() === null) {
    throw new RuntimeException('The PrestaShop command bus container is unavailable.');
}

$stage = 'synthetic CI tax rule creation';
$taxGroup = new TaxRulesGroup();
$taxGroup->name = '[CI ONLY] synthetic product tax ' . $runId . '-' . $attempt;
$taxGroup->active = 1;
$taxGroup->deleted = 0;
if (!$taxGroup->add()) {
    throw new RuntimeException('Could not create the CI-only synthetic tax rules group.');
}
$taxGroupId = (int) $taxGroup->id;
if ($taxGroupId < 1 || (method_exists($taxGroup, 'associateTo') && !$taxGroup->associateTo([$shopId]))) {
    throw new RuntimeException('Could not associate the synthetic tax rules group with the isolated shop.');
}

$languageIds = array_values(array_filter(array_map(
    static fn (array $language): int => (int) ($language['id_lang'] ?? 0),
    Language::getLanguages(false)
), static fn (int $id): bool => $id > 0));
$tax = new Tax();
$tax->rate = 10.0;
$tax->active = 1;
$tax->deleted = 0;
$tax->name = array_fill_keys($languageIds, '[CI ONLY] synthetic 10%');
if (!$tax->add()) {
    throw new RuntimeException('Could not create the CI-only synthetic tax rate.');
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
$taxRule->description = '[CI ONLY] synthetic 10% conversion test; not a legal rate';
if (!$taxRule->add()) {
    throw new RuntimeException('Could not create the CI-only nationwide synthetic tax rule.');
}
$calculatorAddress = new Address();
$calculatorAddress->id_country = $japanCountryId;
$calculatorAddress->id_state = 0;
$calculatorAddress->postcode = '0';
$taxCalculator = TaxManagerFactory::getManager($calculatorAddress, $taxGroupId)->getTaxCalculator();
if (round((float) $taxCalculator->getTotalRate(), 6) !== 10.0) {
    throw new RuntimeException('PrestaShop did not resolve the synthetic tax group to its 10% CI-only test rate.');
}

$stage = 'native product price conversion';
$manager = new PrestaShopNativeProductManager();
$categories = $manager->categories();
$categoryIds = array_map(static fn (array $row): int => (int) $row['id_category'], $categories);
if (!in_array($homeCategoryId, $categoryIds, true)) {
    throw new RuntimeException('The home category is unavailable to the Korean product manager in the isolated shop.');
}
$draft = ProductAdminDraft::fromArray([
    'name_ja' => '[CI ONLY] ORDENOWA synthetic tax product ' . $runId . '-' . $attempt,
    'name_ko' => '[CI ONLY] ORDENOWA synthetic tax 합성 세금 상품 ' . $runId . '-' . $attempt,
    'price_jpy' => '1100',
    'tax_rules_group_id' => (string) $taxGroupId,
    'quantity' => '5',
    'category_ids' => [(string) $homeCategoryId],
    'description_ja' => '[CI ONLY] Synthetic test of tax-included JPY price conversion.',
    'description_ko' => '[CI ONLY] 세금 포함 JPY 가격 환산 테스트용 합성 상품입니다.',
    'options' => '',
]);
$productId = $manager->save(null, $draft);
$product = new Product($productId, false, $languageId, $shopId);
$editor = $manager->editorData($productId);
$expectedNetPrice = 1000.0;
if (!Validate::isLoadedObject($product)
    || (int) $product->id_tax_rules_group !== $taxGroupId
    || abs((float) $product->price - $expectedNetPrice) > 0.00001
    || (int) ($editor['price_jpy'] ?? 0) !== 1100
    || (int) ($editor['tax_rules_group_id'] ?? -1) !== $taxGroupId) {
    throw new RuntimeException('The Korean product manager did not store JPY 1100 tax-included as JPY 1000 tax-excluded under the selected native group.');
}

$stage = 'activate and index run-scoped CI-only taxable order fixture';
$ciProductReference = 'OWA-CI-TAX-' . $runId . '-' . $attempt;
$product = new Product($productId, false, null, $shopId);
$product->reference = $ciProductReference;
$product->active = 1;
$product->visibility = 'both';
$product->available_for_order = 1;
$product->show_price = 1;
if (!$product->update()) {
    throw new RuntimeException('Could not activate the synthetic taxable product inside the disposable CI shop.');
}
Search::indexation(false, (int) $product->id);
$product = new Product($productId, false, $languageId, $shopId);
$productQuantity = (int) StockAvailable::getQuantityAvailableByProduct($productId, 0, $shopId);
if (!Validate::isLoadedObject($product)
    || (string) $product->reference !== $ciProductReference
    || !(bool) $product->active
    || (string) $product->visibility !== 'both'
    || !(bool) $product->available_for_order
    || !(bool) $product->show_price
    || (int) $product->id_tax_rules_group !== $taxGroupId
    || abs((float) $product->price - 1000.0) > 0.00001
    || $productQuantity < 1) {
    throw new RuntimeException('The run-scoped CI-only taxable fixture failed its active, orderable, price, tax-group, or stock re-read guard.');
}

$stage = 'CI-only customer, address, and free carrier';
$customerGroupId = (int) Configuration::get('PS_CUSTOMER_GROUP');
$customer = new Customer();
$customer->firstname = 'ORDENOWA';
$customer->lastname = 'CI ONLY';
$customer->email = 'ordenowa-tax-' . $runId . '-' . $attempt . '@example.invalid';
$customer->passwd = Tools::hash(bin2hex(random_bytes(24)));
$customer->id_lang = $languageId;
$customer->id_default_group = $customerGroupId;
$customer->id_shop = $shopId;
$customer->secure_key = md5(bin2hex(random_bytes(16)));
if (!$customer->add()) {
    throw new RuntimeException('Could not create the CI-only synthetic-tax customer.');
}
$states = State::getStatesByIdCountry($japanCountryId, true, 'iso_code', 'asc');
$stateId = (int) ($states[0]['id_state'] ?? 0);
$address = new Address();
$address->id_customer = (int) $customer->id;
$address->id_country = $japanCountryId;
$address->id_state = $stateId;
$address->alias = 'CI only synthetic tax QA';
$address->firstname = (string) $customer->firstname;
$address->lastname = (string) $customer->lastname;
$address->address1 = '1-1 CI ONLY synthetic tax test';
$address->address2 = '';
$address->postcode = '100-0004';
$address->city = '千代田区';
$address->phone = '0312345678';
if (!$address->add()) {
    throw new RuntimeException('Could not create the CI-only Japanese destination address.');
}

$japan = new Country($japanCountryId, $languageId);
$carrier = new Carrier();
$carrier->name = 'ORDENOWA CI ONLY - synthetic tax test carrier';
$carrier->active = 1;
$carrier->is_free = 1;
$carrier->shipping_handling = 0;
$carrier->shipping_external = 0;
$carrier->range_behavior = 0;
$carrier->shipping_method = Carrier::SHIPPING_METHOD_FREE;
$carrier->max_weight = 100000;
$carrier->need_range = 0;
$carrier->is_module = 0;
$carrier->delay = [];
foreach (Language::getLanguages(false) as $language) {
    $carrier->delay[(int) $language['id_lang']] = 'CI only; no physical dispatch';
}
if (!$carrier->add()
    || !Validate::isLoadedObject($japan)
    || !$carrier->addZone((int) $japan->id_zone)
    || !$carrier->setGroups([$customerGroupId])) {
    throw new RuntimeException('Could not configure the free CI-only Japan delivery carrier.');
}

$paymentModuleName = 'ps_checkpayment';
$paymentModule = Module::getInstanceByName($paymentModuleName);
if (!$paymentModule) {
    throw new RuntimeException('The official offline ps_checkpayment module is not present in this PrestaShop image.');
}
if (!Module::isInstalled($paymentModuleName) && !$paymentModule->install()) {
    throw new RuntimeException('Could not install the offline payment module in the isolated CI shop.');
}
if (!(bool) $paymentModule->active && !$paymentModule->enable()) {
    throw new RuntimeException('Could not enable the offline payment module in the isolated CI shop.');
}
$paymentModule = Module::getInstanceByName($paymentModuleName);
$pendingStateId = (int) Configuration::get('PS_OS_CHEQUE');
$pendingState = $pendingStateId > 0 ? new OrderState($pendingStateId, $languageId) : false;
if (!($paymentModule instanceof PaymentModule)
    || !($pendingState instanceof OrderState)
    || !Validate::isLoadedObject($pendingState)
    || (bool) $pendingState->paid) {
    throw new RuntimeException('The offline CI payment module or unpaid order state is unavailable.');
}
if (!Country::addModuleRestrictions(
    [$shopId],
    [['id_country' => $japanCountryId]],
    [['id_module' => (int) $paymentModule->id]]
)) {
    throw new RuntimeException('Could not allow Japan for offline payment in the isolated CI shop.');
}
$paymentModuleId = (int) $paymentModule->id;
$jpyAllowed = false;
foreach (Currency::checkPaymentCurrencies($paymentModuleId, $shopId) ?: [] as $currencyRestriction) {
    if ((int) ($currencyRestriction['id_currency'] ?? 0) === $currencyId) {
        $jpyAllowed = true;
        break;
    }
}
if (!$jpyAllowed && !Db::getInstance()->execute(sprintf(
    'INSERT IGNORE INTO `%smodule_currency` (`id_module`, `id_shop`, `id_currency`) VALUES (%d, %d, %d)',
    _DB_PREFIX_, $paymentModuleId, $shopId, $currencyId
))) {
    throw new RuntimeException('Could not allow JPY for the isolated offline payment module.');
}
if (!Db::getInstance()->execute(sprintf(
    'INSERT IGNORE INTO `%smodule_group` (`id_module`, `id_shop`, `id_group`) VALUES (%d, %d, %d)',
    _DB_PREFIX_, $paymentModuleId, $shopId, $customerGroupId
))) {
    throw new RuntimeException('Could not allow the CI-only customer group for offline payment.');
}

$stage = 'unpaid CI-only order with stored tax line';
$oldMailMethod = Configuration::get('PS_MAIL_METHOD');
if (!Configuration::updateValue('PS_MAIL_METHOD', Mail::METHOD_DISABLE)) {
    throw new RuntimeException('Could not disable email delivery in the isolated CI shop.');
}
$restoreMailMethod = static function () use ($oldMailMethod): void {
    $restored = $oldMailMethod === false
        ? Configuration::deleteByName('PS_MAIL_METHOD')
        : Configuration::updateValue('PS_MAIL_METHOD', $oldMailMethod);
    if (!$restored) {
        throw new RuntimeException('Could not restore the isolated CI email delivery setting.');
    }
};
try {
    $cart = new Cart();
    $cart->id_customer = (int) $customer->id;
    $cart->id_address_delivery = (int) $address->id;
    $cart->id_address_invoice = (int) $address->id;
    $cart->id_currency = $currencyId;
    $cart->id_lang = $languageId;
    $cart->id_shop = $shopId;
    $cart->id_shop_group = (int) $shop->id_shop_group;
    $cart->id_carrier = (int) $carrier->id;
    $cart->secure_key = (string) $customer->secure_key;
    if (!$cart->add()) {
        throw new RuntimeException('Could not create the native CI-only tax test cart.');
    }
    $context->cart = $cart;
    $context->customer = $customer;
    $quantityAdded = $cart->updateQty(1, $productId, 0, false, 'up', (int) $address->id, $shop);
    if (!$quantityAdded) {
        throw new RuntimeException('Could not add the CI-only synthetic taxable product to the cart.');
    }
    $deliveryOptions = $cart->getDeliveryOptionList($japan, true);
    $addressOptions = $deliveryOptions[(int) $address->id] ?? [];
    if (!is_array($addressOptions) || $addressOptions === []) {
        throw new RuntimeException('The CI-only test cart has no delivery option for its Japanese address.');
    }
    $ciCarrierOptionKey = null;
    foreach ($addressOptions as $optionKey => $option) {
        $optionCarriers = $option['carrier_list'] ?? [];
        if (is_array($optionCarriers)
            && count($optionCarriers) === 1
            && isset($optionCarriers[(int) $carrier->id])) {
            $ciCarrierOptionKey = (string) $optionKey;
            break;
        }
    }
    if ($ciCarrierOptionKey === null) {
        throw new RuntimeException('The Japanese cart has no delivery option for its dedicated CI-only tax test carrier.');
    }
    $cart->setDeliveryOption([(int) $address->id => $ciCarrierOptionKey]);
    if (!$cart->update()
        || (float) $cart->getOrderTotal(true, Cart::ONLY_PRODUCTS) !== 1100.0
        || (float) $cart->getOrderTotal(true, Cart::ONLY_SHIPPING) !== 0.0
        || (float) $cart->getOrderTotal(true, Cart::BOTH) !== 1100.0) {
        throw new RuntimeException('PrestaShop did not calculate the tax-included JPY 1100 product price, zero shipping, and JPY 1100 final cart total.');
    }
    $orderTotal = (float) $cart->getOrderTotal(true, Cart::BOTH);
    $paymentModule->validateOrder(
        (int) $cart->id,
        $pendingStateId,
        $orderTotal,
        'ORDENOWA CI ONLY - offline check payment, no capture',
        '[CI ONLY] Synthetic 10% tax calculation test; not a legal tax rate.',
        [],
        $currencyId,
        false,
        (string) $customer->secure_key,
        $shop
    );
    $orderId = (int) $paymentModule->currentOrder;
    $order = $orderId > 0 ? new Order($orderId) : false;
    $orderDetailRows = $orderId > 0 ? Db::getInstance()->executeS(
        'SELECT `id_order_detail`, `product_id`, `product_attribute_id`, `product_quantity`, `id_tax_rules_group`, '
        . '`product_price`, `unit_price_tax_excl`, `unit_price_tax_incl`, `tax_rate`, '
        . '`total_price_tax_excl`, `total_price_tax_incl` FROM `' . _DB_PREFIX_ . 'order_detail` '
        . 'WHERE `id_order` = ' . (int) $orderId . ' ORDER BY `id_order_detail` ASC'
    ) : false;
    $orderDetailRows = is_array($orderDetailRows) ? $orderDetailRows : [];
    $matchingTaxOrderDetails = array_values(array_filter(
        $orderDetailRows,
        static fn (array $row): bool => (int) ($row['product_id'] ?? 0) === $productId
            && (int) ($row['product_attribute_id'] ?? 0) === 0
    ));
    $detailRow = count($matchingTaxOrderDetails) === 1 ? $matchingTaxOrderDetails[0] : false;
    $orderDetailObject = is_array($detailRow)
        ? new OrderDetail((int) $detailRow['id_order_detail'])
        : false;
    $orderIsLoaded = $order instanceof Order && Validate::isLoadedObject($order);
    $orderDetailIsLoaded = is_array($detailRow);
    $orderDetailObjectIsLoaded = $orderDetailObject instanceof OrderDetail
        && Validate::isLoadedObject($orderDetailObject);
    $observedTaxOrder = [
        'order_loaded' => $orderIsLoaded,
        'order_total_paid_real' => $orderIsLoaded ? (float) $order->total_paid_real : null,
        'order_total_paid_tax_excl' => $orderIsLoaded ? (float) $order->total_paid_tax_excl : null,
        'order_total_paid_tax_incl' => $orderIsLoaded ? (float) $order->total_paid_tax_incl : null,
        'order_total_shipping_tax_excl' => $orderIsLoaded ? (float) $order->total_shipping_tax_excl : null,
        'order_total_shipping_tax_incl' => $orderIsLoaded ? (float) $order->total_shipping_tax_incl : null,
        'order_total_products_tax_excl' => $orderIsLoaded ? (float) $order->total_products : null,
        'order_total_products_tax_incl' => $orderIsLoaded ? (float) $order->total_products_wt : null,
        'order_detail_row_count' => count($orderDetailRows),
        'order_detail_loaded' => $orderDetailIsLoaded,
        'order_detail_object_loaded' => $orderDetailObjectIsLoaded,
        'order_detail_quantity' => $orderDetailIsLoaded ? (int) $detailRow['product_quantity'] : null,
        'order_detail_tax_group_id' => $orderDetailIsLoaded ? (int) $detailRow['id_tax_rules_group'] : null,
        'order_detail_product_price' => $orderDetailIsLoaded ? (float) $detailRow['product_price'] : null,
        'order_detail_unit_tax_excl' => $orderDetailIsLoaded ? (float) $detailRow['unit_price_tax_excl'] : null,
        'order_detail_unit_tax_incl' => $orderDetailIsLoaded ? (float) $detailRow['unit_price_tax_incl'] : null,
        'order_detail_tax_rate' => $orderDetailIsLoaded ? (float) $detailRow['tax_rate'] : null,
        'order_detail_total_tax_excl' => $orderDetailIsLoaded ? (float) $detailRow['total_price_tax_excl'] : null,
        'order_detail_total_tax_incl' => $orderDetailIsLoaded ? (float) $detailRow['total_price_tax_incl'] : null,
    ];
    $expectedTaxOrder = [
        'order_loaded' => true,
        'order_total_paid_real' => 0.0,
        'order_total_paid_tax_excl' => 1000.0,
        'order_total_paid_tax_incl' => 1100.0,
        'order_total_shipping_tax_excl' => 0.0,
        'order_total_shipping_tax_incl' => 0.0,
        'order_total_products_tax_excl' => 1000.0,
        'order_total_products_tax_incl' => 1100.0,
        'order_detail_row_count' => 1,
        'order_detail_loaded' => true,
        'order_detail_quantity' => 1,
        'order_detail_tax_group_id' => $taxGroupId,
        'order_detail_product_price' => 1000.0,
        'order_detail_unit_tax_excl' => 1000.0,
        'order_detail_unit_tax_incl' => 1100.0,
        'order_detail_tax_rate' => 10.0,
        'order_detail_total_tax_excl' => 1000.0,
        'order_detail_total_tax_incl' => 1100.0,
    ];
    $taxOrderMismatch = [];
    foreach ($expectedTaxOrder as $field => $expected) {
        $actual = $observedTaxOrder[$field] ?? null;
        $matches = is_bool($expected)
            ? $actual === $expected
            : (is_numeric($actual) && abs((float) $actual - (float) $expected) <= 0.00001);
        if (!$matches) {
            $taxOrderMismatch[$field] = ['expected' => $expected, 'actual' => $actual];
        }
    }
    if ($taxOrderMismatch !== []) {
        $detailRowDiagnostics = array_map(
            static fn (array $row): array => [
                'id_order_detail' => (int) ($row['id_order_detail'] ?? 0),
                'product_id' => (int) ($row['product_id'] ?? 0),
                'product_attribute_id' => (int) ($row['product_attribute_id'] ?? 0),
                'product_quantity' => (int) ($row['product_quantity'] ?? 0),
                'id_tax_rules_group' => (int) ($row['id_tax_rules_group'] ?? 0),
                'unit_price_tax_excl' => (float) ($row['unit_price_tax_excl'] ?? 0),
                'unit_price_tax_incl' => (float) ($row['unit_price_tax_incl'] ?? 0),
                'tax_rate' => (float) ($row['tax_rate'] ?? 0),
                'total_price_tax_excl' => (float) ($row['total_price_tax_excl'] ?? 0),
                'total_price_tax_incl' => (float) ($row['total_price_tax_incl'] ?? 0),
            ],
            $orderDetailRows
        );
        throw new RuntimeException(
            'The unpaid CI-only order does not reconcile to the JPY 1000/1100 synthetic tax line; '
            . 'observed mismatches=' . json_encode(
                [
                    'mismatches' => $taxOrderMismatch,
                    'order_id' => $orderId,
                    'product_id' => $productId,
                    'order_detail_object_loaded' => $orderDetailObjectIsLoaded,
                    'order_detail_rows' => $detailRowDiagnostics,
                ],
                JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR
            )
        );
    }
    $deliveryAddress = new Address((int) $order->id_address_delivery);
    $orderCarrierZoneCount = (int) Db::getInstance()->getValue(
        'SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'carrier_zone`
        WHERE `id_carrier` = ' . (int) $order->id_carrier . ' AND `id_zone` = ' . (int) $japan->id_zone
    );
    if (!Validate::isLoadedObject($deliveryAddress)
        || (int) $deliveryAddress->id_country !== $japanCountryId
        || (int) $order->id_carrier !== (int) $carrier->id
        || $orderCarrierZoneCount < 1
        || !is_array($detailRow)
        || abs((float) $order->total_products_wt - (float) $detailRow['total_price_tax_incl']) > 0.00001
        || abs((float) $order->total_products - (float) $detailRow['total_price_tax_excl']) > 0.00001) {
        throw new RuntimeException('The order delivery country/carrier zone or order totals do not match the free Japan carrier and saved product line.');
    }
    $savedState = new OrderState((int) $order->current_state, $languageId);
    if (!Validate::isLoadedObject($savedState) || (bool) $savedState->paid) {
        throw new RuntimeException('The CI-only synthetic-tax order must remain unpaid.');
    }
} finally {
    $restoreMailMethod();
}

printf("PASS: [CI ONLY] synthetic 10%% test rule stored a JPY 1100 tax-included sale as JPY 1000 before tax; unpaid order %s has a JPY 100 tax line; not a legal rate.\n", (string) $order->reference);
printf("CI_TEST_TAX_RULES_GROUP_ID=%d\n", $taxGroupId);
printf("CI_TEST_TAX_PRODUCT_ID=%d\n", $productId);
