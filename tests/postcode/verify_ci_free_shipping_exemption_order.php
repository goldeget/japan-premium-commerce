<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$orderId = (int) getenv('KURANEA_CI_ORDER_ID');
$productId = (int) getenv('KURANEA_CI_PRODUCT_ID');
$carrierId = (int) getenv('KURANEA_CI_CARRIER_ID');
$expectedTaxRulesGroupId = (int) getenv('KURANEA_CI_TAX_RULES_GROUP_ID');
$browserOrderPath = trim((string) getenv('KURANEA_CI_BROWSER_ORDER_PATH'));
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== 'kuranea-ci-' . $runId . '-' . $runAttempt
    || $orderId < 1 || $productId < 1 || $carrierId < 1 || $expectedTaxRulesGroupId < 1
    || $browserOrderPath !== '/tmp/ci-shipping-free-exemption-order.json') {
    fwrite(STDERR, "BLOCKED: exemption order verification requires its matching isolated GitHub Actions checkout.\n");
    exit(77);
}

$stage = 'browser exemption checkout artifact';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf(
        'KURANEA_EXEMPTION_ORDER_STAGE=%s; exception=%s; message=%s',
        $stage,
        get_class($exception),
        substr($message, 0, 1000)
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA exemption order::' . $annotation . PHP_EOL);
    }
    exit(1);
});

if (!is_file($browserOrderPath)) {
    throw new RuntimeException('The Chromium explicit exemption order artifact is missing.');
}
$browserOrder = json_decode((string) file_get_contents($browserOrderPath), true, 32, JSON_THROW_ON_ERROR);
if (!is_array($browserOrder)
    || (int) ($browserOrder['order_id'] ?? 0) !== $orderId
    || (int) ($browserOrder['product_id'] ?? 0) !== $productId
    || (int) ($browserOrder['carrier_id'] ?? 0) !== $carrierId
    || (int) ($browserOrder['quantity'] ?? 0) !== 1
    || (int) ($browserOrder['product_tax_rule_group_id'] ?? 0) !== $expectedTaxRulesGroupId
    || ($browserOrder['tax_status'] ?? null) !== 'explicit_exemption_test'
    || !is_array($browserOrder['browser_totals'] ?? null)) {
    throw new RuntimeException('The browser artifact does not match the run-scoped explicit exemption order fixture.');
}
$taxFixtureScope = (string) ($browserOrder['tax_fixture_scope'] ?? '');
if (!str_contains($taxFixtureScope, 'CI-only explicit zero-rate exemption test fixture')
    || !str_contains($taxFixtureScope, 'not a legal tax rate or tax determination')) {
    throw new RuntimeException('The explicit 0% browser artifact must carry its CI-only/not-legal disclaimer.');
}
$browserTotals = $browserOrder['browser_totals'];
$expectedBrowserTotals = [
    'products_tax_incl' => 1000,
    'products_tax_excl' => 1000,
    'shipping_tax_incl' => 0,
    'shipping_tax_excl' => 0,
    'discounts_tax_incl' => 0,
    'discounts_tax_excl' => 0,
    'tax' => 0,
    'total_tax_incl' => 1000,
    'total_tax_excl' => 1000,
    'tax_display_mode' => 'explicit_zero_rate_rule',
];
foreach ($expectedBrowserTotals as $key => $expected) {
    if (($browserTotals[$key] ?? null) !== $expected) {
        throw new RuntimeException(sprintf('Browser exemption total %s differs from the explicit fixture value.', $key));
    }
}
if ((int) ($browserOrder['displayed_unit_price'] ?? 0) !== 1000
    || (int) ($browserOrder['order_history_total'] ?? -1) !== 1000) {
    throw new RuntimeException('The product page and saved customer order history must each show the ¥1,000 fixture total.');
}
$confirmationTotals = $browserOrder['order_confirmation_totals'] ?? null;
if (!is_array($confirmationTotals)) {
    throw new RuntimeException('The order confirmation totals are missing from the browser artifact.');
}
foreach ([
    'products_tax_incl' => 1000,
    'shipping_tax_incl' => 0,
    'tax' => 0,
    'total_tax_incl' => 1000,
    'total_tax_excl' => 1000,
    'tax_display_mode' => 'explicit_zero_rate_rule',
] as $key => $expected) {
    if (($confirmationTotals[$key] ?? null) !== $expected) {
        throw new RuntimeException(sprintf('Order confirmation %s differs from the explicit zero-rate fixture.', $key));
    }
}

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php')) {
    throw new RuntimeException('The installed PrestaShop configuration is missing.');
}
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
require_once $shopRoot . '/config/config.inc.php';
$dbServer = defined('_DB_SERVER_') ? (string) _DB_SERVER_ : '';
$dbNameMatches = defined('_DB_NAME_') && (string) _DB_NAME_ === 'prestashop';
if (!in_array($dbServer, ['mariadb', 'mariadb:3306'], true)
    || getenv('DB_SERVER') !== 'mariadb'
    || getenv('DB_PORT') !== '3306'
    || !$dbNameMatches
    || (string) Db::getInstance()->getValue('SELECT DATABASE()') !== (string) _DB_NAME_) {
    throw new RuntimeException('The exemption verifier is not connected to the isolated MariaDB shop database.');
}
$japanCountryId = (int) Country::getByIso('JP');
$stage = 'native unpaid order';
$order = new Order($orderId);
if (!Validate::isLoadedObject($order)) {
    throw new RuntimeException('Chromium did not create the reported explicit exemption order.');
}
$customer = new Customer((int) $order->id_customer);
$email = strtolower((string) ($browserOrder['email'] ?? ''));
$emailRunId = substr($runId, -20);
$emailRunAttempt = substr($runAttempt, -4);
$emailLabel = 'shipping-free-explicit-exemption';
$safeEmailLabel = preg_replace('/[^a-z0-9]+/', '-', strtolower($emailLabel)) ?: 'checkout';
$emailPrefix = sprintf('qa-ordenowa-checkout-%s-%s-', $emailRunId, $emailRunAttempt);
$emailLocalPart = $emailPrefix . $safeEmailLabel;
if (strlen($emailLocalPart) > 64) {
    $emailHash = substr(hash('sha256', $emailLabel), 0, 8);
    $labelBudget = 64 - strlen($emailPrefix) - strlen($emailHash) - 1;
    if ($labelBudget < 1) {
        throw new RuntimeException('Run-scoped email metadata leaves no room for the exemption account label.');
    }
    $safeEmailLabel = rtrim(substr($safeEmailLabel, 0, $labelBudget), '-');
    if ($safeEmailLabel === '') {
        $safeEmailLabel = 'x';
    }
    $emailLocalPart = $emailPrefix . $safeEmailLabel . '-' . $emailHash;
}
$expectedEmail = strtolower($emailLocalPart . '@example.invalid');
$state = new OrderState((int) $order->current_state, (int) $order->id_lang);
$currency = new Currency((int) $order->id_currency);
if (!Validate::isLoadedObject($customer)
    || $email !== $expectedEmail
    || strlen((string) strstr($email, '@', true)) > 64
    || strtolower((string) $customer->email) !== $email
    || (bool) $customer->is_guest
    || (string) $order->module !== 'ps_checkpayment'
    || !Validate::isLoadedObject($state)
    || (bool) $state->paid
    || (float) $order->total_paid_real !== 0.0
    || !Validate::isLoadedObject($currency)
    || (string) $currency->iso_code !== 'JPY') {
    throw new RuntimeException('The exemption order must remain an unpaid JPY offline order for its run-scoped registered customer.');
}

$stage = 'explicit group and Japan rule';
$groupId = (int) Db::getInstance()->getValue(
    'SELECT `id_tax_rules_group` FROM `' . _DB_PREFIX_ . 'product_shop`'
    . ' WHERE `id_product` = ' . (int) $productId . ' AND `id_shop` = ' . (int) $order->id_shop
);
$groupName = '[CI ONLY] explicit exemption test ' . $runId . '-' . $runAttempt;
$taxGroup = new TaxRulesGroup($expectedTaxRulesGroupId);
$ruleRows = Db::getInstance()->executeS(
    'SELECT tr.`id_tax_rules_group`, tr.`id_country`, tr.`id_state`, tr.`zipcode_from`, tr.`zipcode_to`,'
    . ' t.`id_tax`, t.`rate`, t.`active`'
    . ' FROM `' . _DB_PREFIX_ . 'tax_rule` tr'
    . ' INNER JOIN `' . _DB_PREFIX_ . 'tax` t ON t.`id_tax` = tr.`id_tax`'
    . ' WHERE tr.`id_tax_rules_group` = ' . (int) $expectedTaxRulesGroupId
);
$associationCount = (int) Db::getInstance()->getValue(
    'SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'tax_rules_group_shop`'
    . ' WHERE `id_tax_rules_group` = ' . (int) $expectedTaxRulesGroupId
    . ' AND `id_shop` = ' . (int) $order->id_shop
);
if ($groupId < 1
    || $groupId !== $expectedTaxRulesGroupId
    || !Validate::isLoadedObject($taxGroup)
    || !(bool) $taxGroup->active
    || (int) $taxGroup->deleted !== 0
    || (string) $taxGroup->name !== $groupName
    || !is_array($ruleRows)
    || count($ruleRows) !== 1
    || (int) $ruleRows[0]['id_tax_rules_group'] !== $expectedTaxRulesGroupId
    || (int) $ruleRows[0]['id_country'] !== $japanCountryId
    || (int) $ruleRows[0]['id_state'] !== 0
    || (string) $ruleRows[0]['zipcode_from'] !== '0'
    || (string) $ruleRows[0]['zipcode_to'] !== '0'
    || abs((float) $ruleRows[0]['rate']) > 0.000001
    || (int) $ruleRows[0]['active'] !== 1
    || $associationCount !== 1) {
    throw new RuntimeException('The product must retain the run-scoped explicit Japan 0% group with exactly one active matching rule.');
}
$product = new Product($productId, false, null, (int) $order->id_shop);
if (!Validate::isLoadedObject($product)
    || (int) $product->id_tax_rules_group !== $expectedTaxRulesGroupId
    || abs((float) $product->price - 1000.0) > 0.000001) {
    throw new RuntimeException('The saved native product did not retain the explicit group and ¥1,000 net price.');
}

$stage = 'free Japan carrier and zero shipping';
$carrier = new Carrier($carrierId);
$japan = $japanCountryId > 0 ? new Country($japanCountryId) : false;
$zoneId = $japan instanceof Country ? (int) $japan->id_zone : 0;
$carrierZoneRows = Db::getInstance()->executeS(
    'SELECT `id_zone` FROM `' . _DB_PREFIX_ . 'carrier_zone`'
    . ' WHERE `id_carrier` = ' . (int) $carrierId . ' ORDER BY `id_zone`'
);
$zoneCountryRows = Db::getInstance()->executeS(
    'SELECT `iso_code` FROM `' . _DB_PREFIX_ . 'country` WHERE `id_zone` = ' . (int) $zoneId . ' ORDER BY `iso_code`'
);
$orderCarrierRows = Db::getInstance()->executeS(
    'SELECT `id_carrier`, `shipping_cost_tax_excl`, `shipping_cost_tax_incl`'
    . ' FROM `' . _DB_PREFIX_ . 'order_carrier` WHERE `id_order` = ' . (int) $orderId
);
$carrierZoneIds = array_values(array_map(static fn (array $row): int => (int) $row['id_zone'], is_array($carrierZoneRows) ? $carrierZoneRows : []));
$zoneCountryCodes = array_values(array_map(static fn (array $row): string => (string) $row['iso_code'], is_array($zoneCountryRows) ? $zoneCountryRows : []));
if (!Validate::isLoadedObject($carrier)
    || !(bool) $carrier->active
    || !(bool) $carrier->is_free
    || (int) $order->id_carrier !== $carrierId
    || $zoneId < 1
    || $carrierZoneIds !== [$zoneId]
    || $zoneCountryCodes !== ['JP']
    || !is_array($orderCarrierRows)
    || count($orderCarrierRows) !== 1
    || (int) $orderCarrierRows[0]['id_carrier'] !== $carrierId
    || (float) $orderCarrierRows[0]['shipping_cost_tax_excl'] !== 0.0
    || (float) $orderCarrierRows[0]['shipping_cost_tax_incl'] !== 0.0
    || (float) $order->total_shipping_tax_excl !== 0.0
    || (float) $order->total_shipping_tax_incl !== 0.0) {
    throw new RuntimeException('The saved explicit exemption order did not use the free Japan carrier at ¥0 shipping.');
}

$stage = 'saved order product, totals, and zero-rate representation';
$detailRows = Db::getInstance()->executeS(
    'SELECT `id_order_detail`, `id_tax_rules_group`, `product_id`, `product_quantity`,'
    . ' `unit_price_tax_excl`, `unit_price_tax_incl`, `total_price_tax_excl`, `total_price_tax_incl`'
    . ' FROM `' . _DB_PREFIX_ . 'order_detail` WHERE `id_order` = ' . (int) $orderId
);
if (!is_array($detailRows)
    || count($detailRows) !== 1
    || (int) $detailRows[0]['product_id'] !== $productId
    || (int) $detailRows[0]['product_quantity'] !== 1
    || (int) $detailRows[0]['id_tax_rules_group'] !== $expectedTaxRulesGroupId) {
    throw new RuntimeException('The saved order detail lost its exact explicit exemption product/group identity.');
}
$detail = $detailRows[0];
foreach ([
    'unit TTC' => [(float) $detail['unit_price_tax_incl'], 1000.0],
    'unit HT' => [(float) $detail['unit_price_tax_excl'], 1000.0],
    'subtotal TTC' => [(float) $detail['total_price_tax_incl'], 1000.0],
    'subtotal HT' => [(float) $detail['total_price_tax_excl'], 1000.0],
    'products TTC' => [(float) $order->total_products_wt, 1000.0],
    'products HT' => [(float) $order->total_products, 1000.0],
    'discount TTC' => [(float) $order->total_discounts_tax_incl, 0.0],
    'discount HT' => [(float) $order->total_discounts_tax_excl, 0.0],
    'total TTC' => [(float) $order->total_paid_tax_incl, 1000.0],
    'total HT' => [(float) $order->total_paid_tax_excl, 1000.0],
    'wrapping TTC' => [(float) $order->total_wrapping_tax_incl, 0.0],
    'wrapping HT' => [(float) $order->total_wrapping_tax_excl, 0.0],
] as $label => [$actual, $expected]) {
    if (abs($actual - $expected) > 0.000001) {
        throw new RuntimeException(sprintf('Saved exemption %s differs from expected %.4f.', $label, $expected));
    }
}
$nativeTaxTotal = (float) $order->total_paid_tax_incl - (float) $order->total_paid_tax_excl;
if (abs($nativeTaxTotal) > 0.000001) {
    throw new RuntimeException('The explicit 0% configured order produced positive native tax.');
}
$detailTaxRows = Db::getInstance()->executeS(
    'SELECT odt.`id_tax`, odt.`unit_amount`, odt.`total_amount`, t.`rate`, t.`active`,'
    . ' EXISTS(SELECT 1 FROM `' . _DB_PREFIX_ . 'tax_rule` tr'
    . ' WHERE tr.`id_tax` = odt.`id_tax` AND tr.`id_tax_rules_group` = ' . (int) $expectedTaxRulesGroupId
    . ' AND tr.`id_country` = ' . (int) $japanCountryId . ') AS `belongs_to_saved_group`'
    . ' FROM `' . _DB_PREFIX_ . 'order_detail_tax` odt'
    . ' LEFT JOIN `' . _DB_PREFIX_ . 'tax` t ON t.`id_tax` = odt.`id_tax`'
    . ' WHERE odt.`id_order_detail` = ' . (int) $detail['id_order_detail'] . ' ORDER BY odt.`id_tax`'
);
if (!is_array($detailTaxRows) || count($detailTaxRows) > 1) {
    throw new RuntimeException('The explicit zero-rate order has unexpected or duplicate persisted tax rows.');
}
if ($detailTaxRows !== []) {
    $row = $detailTaxRows[0];
    if ((int) $row['id_tax'] !== (int) $ruleRows[0]['id_tax']
        || (int) $row['belongs_to_saved_group'] !== 1
        || (int) $row['active'] !== 1
        || abs((float) $row['rate']) > 0.000001
        || abs((float) $row['unit_amount']) > 0.000001
        || abs((float) $row['total_amount']) > 0.000001) {
        throw new RuntimeException('The persisted exemption order-detail tax representation is not the exact configured zero-rate row.');
    }
}
$address = new Address((int) $order->id_address_delivery);
$states = State::getStatesByIdCountry($japanCountryId, true, 'iso_code', 'asc');
$expectedStateId = 0;
foreach (is_array($states) ? $states : [] as $stateRow) {
    if ((string) ($stateRow['iso_code'] ?? '') === 'JP-13') {
        $expectedStateId = (int) $stateRow['id_state'];
        break;
    }
}
if (!Validate::isLoadedObject($address)
    || (int) $address->id_country !== $japanCountryId
    || (int) $address->id_state !== $expectedStateId
    || $expectedStateId < 1
    || (string) $address->postcode !== '100-0004'
    || (string) $address->city !== '千代田区'
    || !str_contains((string) $address->address1, '大手町')) {
    throw new RuntimeException('The explicit exemption order did not retain the supported Tokyo delivery address.');
}

$verified = [
    'order_id' => (int) $order->id,
    'reference' => (string) $order->reference,
    'product_id' => $productId,
    'product_tax_rules_group_id' => $groupId,
    'tax_status' => 'explicit_exemption_test',
    'tax_rate_percent' => 0.0,
    'tax_fixture_scope' => $taxFixtureScope,
    'saved_order_detail_tax_group_id' => (int) $detail['id_tax_rules_group'],
    'resolved_rule' => $ruleRows[0],
    'saved_order_detail_taxes' => $detailTaxRows,
    'zero_rate_row_representation' => $detailTaxRows === [] ? 'no row; explicit group resolved 0%' : 'one matching row with rate and amount 0',
    'product_unit_tax_excl' => (float) $detail['unit_price_tax_excl'],
    'product_unit_tax_incl' => (float) $detail['unit_price_tax_incl'],
    'total_products_tax_excl' => (float) $order->total_products,
    'total_products_tax_incl' => (float) $order->total_products_wt,
    'total_shipping_tax_excl' => (float) $order->total_shipping_tax_excl,
    'total_shipping_tax_incl' => (float) $order->total_shipping_tax_incl,
    'total_paid_tax_excl' => (float) $order->total_paid_tax_excl,
    'total_paid_tax_incl' => (float) $order->total_paid_tax_incl,
    'native_tax_total' => $nativeTaxTotal,
    'payment_module' => (string) $order->module,
    'payment_amount_recorded' => (float) $order->total_paid_real,
    'postcode' => (string) $address->postcode,
    'state_iso_code' => 'JP-13',
    'browser_checkout' => $browserTotals,
    'browser_order_confirmation' => $confirmationTotals,
    'customer_order_history_total' => (int) $browserOrder['order_history_total'],
    'carrier_shipping_tax_excl' => (float) $orderCarrierRows[0]['shipping_cost_tax_excl'],
    'carrier_shipping_tax_incl' => (float) $orderCarrierRows[0]['shipping_cost_tax_incl'],
    'platform_fee' => 0,
];
echo json_encode($verified, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDERR, sprintf(
    "PASS: CI-only explicit zero-rate group %d, product/order %d/%d, ¥1,000 TTC=HT, and ¥0 Japan shipping reconciled without classifying an unassigned rule as exempt.\n",
    $expectedTaxRulesGroupId,
    $productId,
    $orderId
));
