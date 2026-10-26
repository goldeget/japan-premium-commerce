<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$orderId = (int) getenv('KURANEA_CI_ORDER_ID');
$productId = (int) getenv('KURANEA_CI_PRODUCT_ID');
$carrierId = (int) getenv('KURANEA_CI_CARRIER_ID');
$expectedTaxRulesGroupId = (int) getenv('KURANEA_CI_TAX_RULES_GROUP_ID');
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;
$browserOrderPath = trim((string) getenv('KURANEA_CI_BROWSER_ORDER_PATH'));

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== $expectedProjectName
    || $orderId < 1
    || $productId < 1
    || $carrierId < 1
    || $expectedTaxRulesGroupId < 1
    || $browserOrderPath !== '/tmp/ci-shipping-free-order.json'
) {
    fwrite(STDERR, "BLOCKED: shipping order verification requires its matching isolated GitHub Actions checkout.\n");
    exit(77);
}

$stage = 'browser checkout artifact';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf(
        'KURANEA_SHIPPING_ORDER_STAGE=%s; exception=%s; message=%s',
        $stage,
        get_class($exception),
        substr($message, 0, 1000)
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA free shipping order::' . $annotation . PHP_EOL);
    }
    exit(1);
});

if (!is_file($browserOrderPath)) {
    throw new RuntimeException('The Chromium free-shipping order artifact is missing.');
}
$browserOrder = json_decode(
    (string) file_get_contents($browserOrderPath),
    true,
    32,
    JSON_THROW_ON_ERROR
);
if (!is_array($browserOrder)
    || (int) ($browserOrder['order_id'] ?? 0) !== $orderId
    || (int) ($browserOrder['product_id'] ?? 0) !== $productId
    || (int) ($browserOrder['carrier_id'] ?? 0) !== $carrierId
    || !in_array((int) ($browserOrder['quantity'] ?? 0), [1, 2], true)
    || !is_array($browserOrder['browser_totals'] ?? null)
) {
    throw new RuntimeException('The Chromium artifact does not identify the expected free-carrier order and quantity.');
}
$browserTotals = $browserOrder['browser_totals'];

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php')) {
    throw new RuntimeException('The installed PrestaShop configuration is missing.');
}
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
require_once $shopRoot . '/config/config.inc.php';

$stage = 'native order and customer lookup';
$order = new Order($orderId);
if (!Validate::isLoadedObject($order)) {
    throw new RuntimeException('Chromium did not create the reported native order.');
}
$customer = new Customer((int) $order->id_customer);
$expectedEmailPrefix = sprintf('qa-ordenowa-checkout-%s-%s-shipping-free', $runId, $runAttempt);
$expectedEmail = strtolower((string) ($browserOrder['email'] ?? ''));
if (!Validate::isLoadedObject($customer)
    || !str_starts_with($expectedEmail, $expectedEmailPrefix)
    || !str_ends_with($expectedEmail, '@example.invalid')
    || strtolower((string) $customer->email) !== strtolower($expectedEmail)
    || (bool) $customer->is_guest
) {
    throw new RuntimeException('The free-shipping order is not linked to its run-scoped registered customer.');
}

$stage = 'unpaid JPY order';
$state = new OrderState((int) $order->current_state, (int) $order->id_lang);
$currency = new Currency((int) $order->id_currency);
if ((string) $order->module !== 'ps_checkpayment'
    || !Validate::isLoadedObject($state)
    || (bool) $state->paid
    || (float) $order->total_paid_real !== 0.0
    || !Validate::isLoadedObject($currency)
    || (string) $currency->iso_code !== 'JPY'
) {
    throw new RuntimeException('The free-shipping order must remain an unpaid JPY ps_checkpayment order.');
}

$stage = 'free carrier persistence';
$carrier = new Carrier($carrierId);
$japanCountryId = (int) Country::getByIso('JP');
$japan = $japanCountryId > 0 ? new Country($japanCountryId) : false;
$zoneId = $japan instanceof Country ? (int) $japan->id_zone : 0;
$zoneLink = Db::getInstance()->getValue(
    'SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'carrier_zone`'
    . ' WHERE `id_carrier` = ' . (int) $carrierId
    . ' AND `id_zone` = ' . (int) $zoneId
);
$carrierZoneRows = Db::getInstance()->executeS(
    'SELECT `id_zone` FROM `' . _DB_PREFIX_ . 'carrier_zone`'
    . ' WHERE `id_carrier` = ' . (int) $carrierId
    . ' ORDER BY `id_zone`'
);
$zoneCountryRows = Db::getInstance()->executeS(
    'SELECT `iso_code` FROM `' . _DB_PREFIX_ . 'country`'
    . ' WHERE `id_zone` = ' . (int) $zoneId
    . ' ORDER BY `iso_code`'
);
$carrierZoneIds = array_values(array_map(
    static fn (array $row): int => (int) $row['id_zone'],
    is_array($carrierZoneRows) ? $carrierZoneRows : []
));
$zoneCountryCodes = array_values(array_map(
    static fn (array $row): string => (string) $row['iso_code'],
    is_array($zoneCountryRows) ? $zoneCountryRows : []
));
$carrierOrderRows = Db::getInstance()->executeS(
    'SELECT `id_carrier`, `shipping_cost_tax_excl`, `shipping_cost_tax_incl`'
    . ' FROM `' . _DB_PREFIX_ . 'order_carrier`'
    . ' WHERE `id_order` = ' . (int) $orderId
);
if (!Validate::isLoadedObject($carrier)
    || !(bool) $carrier->active
    || !(bool) $carrier->is_free
    || (int) $carrier->id !== (int) $order->id_carrier
    || (string) $carrier->name !== (string) $browserOrder['carrier_name']
    || $zoneId < 1
    || (int) $zoneLink !== 1
    || $carrierZoneIds !== [$zoneId]
    || $zoneCountryCodes !== ['JP']
    || !is_array($carrierOrderRows)
    || count($carrierOrderRows) !== 1
    || (int) $carrierOrderRows[0]['id_carrier'] !== $carrierId
) {
    throw new RuntimeException('The native order did not persist the active free carrier serving Japan.');
}
$browserCarrierTaxGroupId = $browserOrder['carrier_tax_rule_group_id'] ?? null;
$persistedCarrierTaxGroupId = (int) $carrier->getIdTaxRulesGroup();
if ($browserCarrierTaxGroupId !== null
    && (int) $browserCarrierTaxGroupId !== $persistedCarrierTaxGroupId
) {
    throw new RuntimeException(sprintf(
        'AdminCarriers tax-rule group %s differs from the persisted carrier tax-rule group %d.',
        var_export($browserCarrierTaxGroupId, true),
        $persistedCarrierTaxGroupId
    ));
}

$stage = 'zero carrier shipping and handling';
$carrierShippingTaxExcl = (float) $carrierOrderRows[0]['shipping_cost_tax_excl'];
$carrierShippingTaxIncl = (float) $carrierOrderRows[0]['shipping_cost_tax_incl'];
if ($carrierShippingTaxExcl !== 0.0
    || $carrierShippingTaxIncl !== 0.0
    || (float) $order->total_shipping_tax_excl !== 0.0
    || (float) $order->total_shipping_tax_incl !== 0.0
) {
    throw new RuntimeException('The free carrier added a nonzero amount to the order shipping total.');
}

$stage = 'product quantity and explicit tax fixture';
$orderDetails = Db::getInstance()->executeS(
    'SELECT `id_order_detail`, `id_tax_rules_group`, `product_id`, `product_quantity`, `unit_price_tax_excl`, `unit_price_tax_incl`, `total_price_tax_excl`, `total_price_tax_incl`'
    . ' FROM `' . _DB_PREFIX_ . 'order_detail`'
    . ' WHERE `id_order` = ' . (int) $orderId
);
$productTaxGroupId = (int) Db::getInstance()->getValue(
    'SELECT ps.`id_tax_rules_group` FROM `' . _DB_PREFIX_ . 'product_shop` ps'
    . ' WHERE ps.`id_product` = ' . (int) $productId
    . ' AND ps.`id_shop` = ' . (int) $order->id_shop
);
$expectedQuantity = (int) $browserOrder['quantity'];
$browserProductTaxGroupId = (int) ($browserOrder['product_tax_rule_group_id'] ?? -1);
$scenario = (string) ($browserOrder['viewport'] ?? '');
$scenarioExpectations = [
    'shipping-free' => [
        'quantity' => 2,
        'coupon_applied' => true,
        'products_tax_incl' => 2200.0,
        'products_tax_excl' => 2000.0,
        'discounts_tax_incl' => 1100.0,
        'discounts_tax_excl' => 1000.0,
        'total_tax_incl' => 1100.0,
        'total_tax_excl' => 1000.0,
        'tax' => 100.0,
    ],
    'shipping-free-mobile' => [
        'quantity' => 1,
        'coupon_applied' => false,
        'products_tax_incl' => 1100.0,
        'products_tax_excl' => 1000.0,
        'discounts_tax_incl' => 0.0,
        'discounts_tax_excl' => 0.0,
        'total_tax_incl' => 1100.0,
        'total_tax_excl' => 1000.0,
        'tax' => 100.0,
    ],
    'shipping-free-taxable' => [
        'quantity' => 1,
        'coupon_applied' => true,
        'products_tax_incl' => 1100.0,
        'products_tax_excl' => 1000.0,
        'discounts_tax_incl' => 550.0,
        'discounts_tax_excl' => 500.0,
        'total_tax_incl' => 550.0,
        'total_tax_excl' => 500.0,
        'tax' => 50.0,
    ],
];
$scenarioExpected = $scenarioExpectations[$scenario] ?? null;
if (!is_array($orderDetails)
    || count($orderDetails) !== 1
    || (int) $orderDetails[0]['product_id'] !== $productId
    || (int) $orderDetails[0]['product_quantity'] !== $expectedQuantity
    || !is_array($scenarioExpected)
    || $expectedQuantity !== $scenarioExpected['quantity']
    || $productTaxGroupId < 1
    || $productTaxGroupId !== $browserProductTaxGroupId
    || $productTaxGroupId !== $expectedTaxRulesGroupId
    || (int) $orderDetails[0]['id_tax_rules_group'] !== $browserProductTaxGroupId
) {
    throw new RuntimeException('The native order scenario, quantity, or run-scoped synthetic tax group differs from the browser fixture.');
}
$expectedTaxGroupName = '[CI ONLY] synthetic product tax ' . $runId . '-' . $runAttempt;
$expectedTaxGroup = new TaxRulesGroup($expectedTaxRulesGroupId);
$expectedTaxRules = Db::getInstance()->executeS(
    'SELECT t.`rate`, t.`active`, tr.`id_country`, tr.`id_state`'
    . ' FROM `' . _DB_PREFIX_ . 'tax_rule` tr'
    . ' INNER JOIN `' . _DB_PREFIX_ . 'tax` t ON t.`id_tax` = tr.`id_tax`'
    . ' WHERE tr.`id_tax_rules_group` = ' . (int) $expectedTaxRulesGroupId
);
if (!Validate::isLoadedObject($expectedTaxGroup)
    || !(bool) $expectedTaxGroup->active
    || (int) $expectedTaxGroup->deleted !== 0
    || (string) $expectedTaxGroup->name !== $expectedTaxGroupName
    || !is_array($expectedTaxRules)
    || count($expectedTaxRules) !== 1
    || abs((float) ($expectedTaxRules[0]['rate'] ?? 0) - 10.0) > 0.0001
    || (int) ($expectedTaxRules[0]['active'] ?? 0) !== 1
    || (int) ($expectedTaxRules[0]['id_country'] ?? 0) !== (int) Country::getByIso('JP')
    || (int) ($expectedTaxRules[0]['id_state'] ?? -1) !== 0
) {
    throw new RuntimeException('The shipping-order scenarios must use the run-scoped synthetic Japan 10% test group; not a legal rate.');
}
$detailProductsTaxExcl = (float) $orderDetails[0]['total_price_tax_excl'];
$detailProductsTaxIncl = (float) $orderDetails[0]['total_price_tax_incl'];
$detailUnitTaxExcl = (float) $orderDetails[0]['unit_price_tax_excl'];
$detailUnitTaxIncl = (float) $orderDetails[0]['unit_price_tax_incl'];
if (abs($detailProductsTaxExcl - (float) $order->total_products) > 0.0001
    || abs($detailProductsTaxIncl - (float) $order->total_products_wt) > 0.0001
) {
    throw new RuntimeException('Native order product and tax-exclusive/inclusive totals do not reconcile.');
}
foreach ([
    'native unit price tax-exclusive' => [$detailUnitTaxExcl, 1000.0],
    'native unit price tax-inclusive' => [$detailUnitTaxIncl, 1100.0],
    'native product subtotal tax-exclusive' => [$detailProductsTaxExcl, $scenarioExpected['products_tax_excl']],
    'native product subtotal tax-inclusive' => [$detailProductsTaxIncl, $scenarioExpected['products_tax_incl']],
] as $checkName => [$actual, $expected]) {
    if (abs($actual - $expected) > 0.0001) {
        throw new RuntimeException(sprintf('%s mismatch: native %.4f vs %.4f.', $checkName, $actual, $expected));
    }
}

$stage = 'browser, history, native total and platform fee reconciliation';
$discountsTaxExcl = (float) $order->total_discounts_tax_excl;
$discountsTaxIncl = (float) $order->total_discounts_tax_incl;
$wrappingTaxExcl = (float) $order->total_wrapping_tax_excl;
$wrappingTaxIncl = (float) $order->total_wrapping_tax_incl;
$nativeTotalTaxExcl = $detailProductsTaxExcl - $discountsTaxExcl + $wrappingTaxExcl;
$nativeTotalTaxIncl = $detailProductsTaxIncl - $discountsTaxIncl + $wrappingTaxIncl;
$browserProductsTaxExcl = (float) ($browserTotals['products_tax_excl'] ?? -1);
$browserProductsTaxIncl = (float) ($browserTotals['products_tax_incl'] ?? -1);
$browserShippingTaxExcl = (float) ($browserTotals['shipping_tax_excl'] ?? -1);
$browserShippingTaxIncl = (float) ($browserTotals['shipping_tax_incl'] ?? -1);
$browserDiscountTaxExcl = (float) ($browserTotals['discounts_tax_excl'] ?? 0);
$browserDiscountTaxIncl = (float) ($browserTotals['discounts_tax_incl'] ?? 0);
$browserTotalTaxExcl = (float) ($browserTotals['total_tax_excl'] ?? -1);
$browserTotalTaxIncl = (float) ($browserTotals['total_tax_incl'] ?? -1);
$nativeTaxes = (float) $order->total_paid_tax_incl - (float) $order->total_paid_tax_excl;
$browserTaxDisplayMode = (string) ($browserTotals['tax_display_mode'] ?? 'detailed_breakdown');
$browserHasInclusiveTotalOnly = $browserTaxDisplayMode === 'inclusive_total_only';
if ($browserHasInclusiveTotalOnly
    && ($productTaxGroupId < 1
        || !array_key_exists('tax', $browserTotals)
        || $browserTotals['tax'] !== null
        || ($browserTotals['tax_breakdown_displayed'] ?? true) !== false
        || $nativeTaxes <= 0.0)
) {
    throw new RuntimeException('An inclusive-only browser total must leave tax unknown and reconcile to a positive native saved tax.');
}
$taxDisplayMode = (string) ($browserTotals['tax_display_mode'] ?? '');
if (!$browserHasInclusiveTotalOnly) {
    $browserTax = $browserTotals['tax'] ?? null;
    $taxDisplayMode = (string) ($browserTotals['tax_display_mode'] ?? '');
    $taxBreakdownDisplayed = $browserTotals['tax_breakdown_displayed'] ?? null;
    $hasDetailedTaxRow = $taxDisplayMode === 'detailed_breakdown'
        && $taxBreakdownDisplayed === true;
    $hasLabeledGrossNetTotals = $taxDisplayMode === 'tax_inclusive_and_exclusive_totals'
        && $taxBreakdownDisplayed === false;
    if (!is_numeric($browserTax)
        || (float) $browserTax <= 0.0
        || (!$hasDetailedTaxRow && !$hasLabeledGrossNetTotals)
    ) {
        throw new RuntimeException('A synthetic taxable browser amount must preserve positive tax and its displayed-total evidence.');
    }
}

$stage = 'saved native order detail tax rows';
$savedDetailTaxGroupId = (int) $orderDetails[0]['id_tax_rules_group'];
$storedTaxRows = Db::getInstance()->executeS(
    'SELECT odt.`id_tax`, odt.`unit_amount`, odt.`total_amount`, t.`rate`,'
    . ' EXISTS(SELECT 1 FROM `' . _DB_PREFIX_ . 'tax_rule` tr'
    . ' WHERE tr.`id_tax` = odt.`id_tax` AND tr.`id_tax_rules_group` = ' . $savedDetailTaxGroupId
    . ' AND tr.`id_country` = ' . (int) $japanCountryId . ') AS `belongs_to_saved_group`'
    . ' FROM `' . _DB_PREFIX_ . 'order_detail_tax` odt'
    . ' LEFT JOIN `' . _DB_PREFIX_ . 'tax` t ON t.`id_tax` = odt.`id_tax`'
    . ' WHERE odt.`id_order_detail` = ' . (int) $orderDetails[0]['id_order_detail']
    . ' ORDER BY odt.`id_tax`'
);
if (!is_array($storedTaxRows)) {
    throw new RuntimeException('Could not read the persisted native order detail tax rows.');
}
$savedTaxInterpretation = 'CI-only synthetic 10% calculation fixture; not a legal tax rate or determination';
if ($savedDetailTaxGroupId !== $expectedTaxRulesGroupId) {
    throw new RuntimeException('The saved order detail did not retain the run-scoped synthetic tax group.');
}
$coupon = is_array($browserOrder['coupon'] ?? null) ? $browserOrder['coupon'] : [];
$expectedCouponCode = 'ORDENOWACI' . $runId . $runAttempt;
if ($scenarioExpected['coupon_applied']) {
    if (($coupon['applied'] ?? false) !== true
        || (string) ($coupon['code'] ?? '') !== $expectedCouponCode
        || $discountsTaxExcl <= 0
        || $discountsTaxIncl <= 0
    ) {
        throw new RuntimeException('The Tokyo and synthetic-tax coupon scenarios must use their run-scoped 50% tax-inclusive coupon.');
    }
} elseif (($coupon['applied'] ?? true) !== false
    || ($coupon['code'] ?? null) !== null
    || abs($discountsTaxExcl) > 0.0001
    || abs($discountsTaxIncl) > 0.0001
) {
    throw new RuntimeException('The Osaka quantity-one control scenario must remain coupon-free with zero discount.');
}
if (count($storedTaxRows) !== 1) {
    throw new RuntimeException('Each synthetic taxable shipping scenario must retain its single native tax row.');
}

$preCouponBrowserTotals = null;
if ($scenario === 'shipping-free-taxable') {
    if (count($storedTaxRows) !== 1) {
        throw new RuntimeException('The separate synthetic taxable coupon scenario must retain its single native tax row.');
    }
    $preCouponBrowserTotals = is_array($browserOrder['pre_coupon_browser_totals'] ?? null)
        ? $browserOrder['pre_coupon_browser_totals']
        : [];
    foreach ([
        'pre-coupon product total' => [
            (float) ($preCouponBrowserTotals['products_tax_incl'] ?? -1),
            1100.0,
        ],
        'pre-coupon shipping total' => [
            (float) ($preCouponBrowserTotals['shipping_tax_incl'] ?? -1),
            0.0,
        ],
        'pre-coupon discount total' => [
            (float) ($preCouponBrowserTotals['discounts_tax_incl'] ?? -1),
            0.0,
        ],
        'pre-coupon final total' => [
            (float) ($preCouponBrowserTotals['total_tax_incl'] ?? -1),
            1100.0,
        ],
    ] as $checkName => [$actual, $expected]) {
        if (abs($actual - $expected) > 0.0001) {
            throw new RuntimeException(sprintf('%s mismatch: browser %.4f vs %.4f.', $checkName, $actual, $expected));
        }
    }
    $preCouponBrowserTax = $preCouponBrowserTotals['tax'] ?? null;
    if ($preCouponBrowserTax === null) {
        if (($preCouponBrowserTotals['tax_display_mode'] ?? null) !== 'inclusive_total_only'
            || ($preCouponBrowserTotals['tax_breakdown_displayed'] ?? true) !== false
            || ($preCouponBrowserTotals['products_tax_excl'] ?? null) !== null
            || ($preCouponBrowserTotals['discounts_tax_excl'] ?? null) !== null
            || ($preCouponBrowserTotals['total_tax_excl'] ?? null) !== null
        ) {
            throw new RuntimeException('The pre-coupon browser tax must be explicitly unknown when no tax row is rendered.');
        }
    } elseif (abs((float) $preCouponBrowserTax - 100.0) > 0.0001
        || abs((float) ($preCouponBrowserTotals['products_tax_excl'] ?? -1) - 1000.0) > 0.0001
        || abs((float) ($preCouponBrowserTotals['total_tax_excl'] ?? -1) - 1000.0) > 0.0001
        || !(
            (($preCouponBrowserTotals['tax_display_mode'] ?? null) === 'detailed_breakdown'
                && ($preCouponBrowserTotals['tax_breakdown_displayed'] ?? null) === true)
            || (($preCouponBrowserTotals['tax_display_mode'] ?? null) === 'tax_inclusive_and_exclusive_totals'
                && ($preCouponBrowserTotals['tax_breakdown_displayed'] ?? null) === false)
        )
    ) {
        throw new RuntimeException('The visible pre-coupon synthetic tax evidence does not match ¥1,100 TTC / ¥1,000 HT.');
    }
}

$storedTaxRow = $storedTaxRows[0];
$storedTaxRate = (float) $storedTaxRow['rate'];
$storedTaxUnit = (float) $storedTaxRow['unit_amount'];
$storedTaxTotal = (float) $storedTaxRow['total_amount'];
$discountedProductTaxBase = $detailProductsTaxExcl - $discountsTaxExcl;
foreach ([
    'native product unit tax-exclusive price' => [$detailUnitTaxExcl, 1000.0],
    'native product unit tax-inclusive price' => [$detailUnitTaxIncl, 1100.0],
    'native product tax-exclusive subtotal' => [$detailProductsTaxExcl, $scenarioExpected['products_tax_excl']],
    'native product tax-inclusive subtotal' => [$detailProductsTaxIncl, $scenarioExpected['products_tax_incl']],
    'native discount tax-exclusive amount' => [$discountsTaxExcl, $scenarioExpected['discounts_tax_excl']],
    'native discount tax-inclusive amount' => [$discountsTaxIncl, $scenarioExpected['discounts_tax_incl']],
    'native final tax-exclusive amount' => [(float) $order->total_paid_tax_excl, $scenarioExpected['total_tax_excl']],
    'native final tax-inclusive amount' => [(float) $order->total_paid_tax_incl, $scenarioExpected['total_tax_incl']],
    'native saved synthetic tax' => [$nativeTaxes, $scenarioExpected['tax']],
    'saved synthetic order-detail tax' => [$storedTaxTotal, $scenarioExpected['tax']],
] as $checkName => [$actual, $expected]) {
    if (abs($actual - $expected) > 0.0001) {
        throw new RuntimeException(sprintf('%s mismatch for %s: native %.4f vs %.4f.', $checkName, $scenario, $actual, $expected));
    }
}
if ((int) $storedTaxRow['id_tax'] < 1
    || (int) $storedTaxRow['belongs_to_saved_group'] !== 1
    || abs($storedTaxRate - 10.0) > 0.0001
    || $storedTaxUnit <= 0
    || $discountedProductTaxBase <= 0
    || abs($storedTaxUnit * $expectedQuantity - $storedTaxTotal) > 0.0001
    || abs($storedTaxTotal - $nativeTaxes) > 0.0001
    || abs($storedTaxTotal - $discountedProductTaxBase * $storedTaxRate / 100) > 0.0001) {
    throw new RuntimeException('The persisted synthetic tax identity, rate, or discounted amount does not reconcile to the saved order.');
}

foreach ([
    'browser product gross subtotal' => [$browserProductsTaxIncl, $scenarioExpected['products_tax_incl']],
    'browser shipping gross total' => [$browserShippingTaxIncl, 0.0],
    'browser coupon gross amount' => [$browserDiscountTaxIncl, $scenarioExpected['discounts_tax_incl']],
    'browser final gross total' => [$browserTotalTaxIncl, $scenarioExpected['total_tax_incl']],
    'native tax-exclusive total formula' => [$nativeTotalTaxExcl, $scenarioExpected['total_tax_excl']],
    'native tax-inclusive total formula' => [$nativeTotalTaxIncl, $scenarioExpected['total_tax_incl']],
] as $checkName => [$actual, $expected]) {
    if (abs($actual - $expected) > 0.0001) {
        throw new RuntimeException(sprintf('%s mismatch for %s: %.4f vs %.4f.', $checkName, $scenario, $actual, $expected));
    }
}
if (str_contains((string) ($browserOrder['tax_fixture_scope'] ?? ''), 'synthetic 10%') === false
    || str_contains((string) ($browserOrder['tax_fixture_scope'] ?? ''), 'not a legal tax rate or tax determination') === false
) {
    throw new RuntimeException('The browser artifact must label its 10% amount as a synthetic CI test, not a legal tax determination.');
}

$browserComparisons = [
    'browser product tax incl' => [$browserProductsTaxIncl, (float) $order->total_products_wt],
    'browser shipping tax incl' => [$browserShippingTaxIncl, (float) $order->total_shipping_tax_incl],
    'browser discount tax incl' => [$browserDiscountTaxIncl, $discountsTaxIncl],
    'browser total tax incl' => [$browserTotalTaxIncl, (float) $order->total_paid_tax_incl],
    'native tax-exclusive formula' => [$nativeTotalTaxExcl, (float) $order->total_paid_tax_excl],
    'native tax-inclusive formula' => [$nativeTotalTaxIncl, (float) $order->total_paid_tax_incl],
    'customer order history total' => [
        (float) ($browserOrder['order_history_total'] ?? -1),
        (float) $order->total_paid_tax_incl,
    ],
];
foreach ([
    'browser product tax excl' => ['products_tax_excl', (float) $order->total_products],
    'browser shipping tax excl' => ['shipping_tax_excl', (float) $order->total_shipping_tax_excl],
    'browser discount tax excl' => ['discounts_tax_excl', $discountsTaxExcl],
    'browser total tax excl' => ['total_tax_excl', (float) $order->total_paid_tax_excl],
] as $checkName => [$browserKey, $nativeAmount]) {
    if (is_numeric($browserTotals[$browserKey] ?? null)) {
        $browserComparisons[$checkName] = [(float) $browserTotals[$browserKey], $nativeAmount];
    }
}
if (array_key_exists('tax', $browserTotals) && $browserTotals['tax'] !== null) {
    $browserComparisons['browser tax amount'] = [(float) $browserTotals['tax'], $nativeTaxes];
} elseif ($productTaxGroupId > 0 && !$browserHasInclusiveTotalOnly) {
    throw new RuntimeException('A taxable browser total must either expose its tax amount or mark it unknown.');
}
$confirmationTotals = is_array($browserOrder['order_confirmation_totals'] ?? null)
    ? $browserOrder['order_confirmation_totals']
    : [];
$browserComparisons += [
    'order confirmation products tax incl' => [
        (float) ($confirmationTotals['products_tax_incl'] ?? -1),
        (float) $order->total_products_wt,
    ],
    'order confirmation shipping tax incl' => [
        (float) ($confirmationTotals['shipping_tax_incl'] ?? -1),
        (float) $order->total_shipping_tax_incl,
    ],
    'order confirmation total tax incl' => [
        (float) ($confirmationTotals['total_tax_incl'] ?? -1),
        (float) $order->total_paid_tax_incl,
    ],
];
if (is_numeric($confirmationTotals['total_tax_excl'] ?? null)) {
    $browserComparisons['order confirmation total tax excl'] = [
        (float) $confirmationTotals['total_tax_excl'],
        (float) $order->total_paid_tax_excl,
    ];
}
if (array_key_exists('tax', $confirmationTotals) && $confirmationTotals['tax'] !== null) {
    $browserComparisons['order confirmation tax amount'] = [(float) $confirmationTotals['tax'], $nativeTaxes];
}
foreach ($browserComparisons as $checkName => [$actual, $expected]) {
    if (abs($actual - $expected) > 0.0001) {
        throw new RuntimeException(sprintf(
            '%s mismatch: browser/native %.4f vs %.4f; an unaccounted platform fee is not allowed.',
            $checkName,
            $actual,
            $expected
        ));
    }
}
if ((float) $order->total_shipping_tax_excl !== 0.0
    || (float) $order->total_shipping_tax_incl !== 0.0
    || abs($wrappingTaxExcl) > 0.0001
    || abs($wrappingTaxIncl) > 0.0001
    || abs((float) $order->total_paid_real) > 0.0001
    || (int) ($browserTotals['quantity'] ?? 0) !== $expectedQuantity
) {
    throw new RuntimeException('The free-shipping order contains shipping, wrapping, or payment amounts outside its synthetic taxable product fixture.');
}

$stage = 'Japan destination persistence';
$address = new Address((int) $order->id_address_delivery);
$states = State::getStatesByIdCountry($japanCountryId, true, 'iso_code', 'asc');
$destination = is_array($browserOrder['destination'] ?? null) ? $browserOrder['destination'] : [];
$expectedPostcode = (string) ($destination['postcode'] ?? '');
$expectedCity = (string) ($destination['city'] ?? '');
$expectedStateIso = (string) ($destination['state_iso_code'] ?? '');
$expectedAddressFragment = (string) ($destination['address1_fragment'] ?? '');
$expectedStateId = 0;
foreach (is_array($states) ? $states : [] as $stateRow) {
    if ((string) ($stateRow['iso_code'] ?? '') === $expectedStateIso) {
        $expectedStateId = (int) $stateRow['id_state'];
        break;
    }
}
if (!Validate::isLoadedObject($address)
    || $japanCountryId < 1
    || (int) $address->id_country !== $japanCountryId
    || (int) $address->id_state !== $expectedStateId
    || $expectedStateId < 1
    || (string) $address->postcode !== $expectedPostcode
    || (string) $address->city !== $expectedCity
    || $expectedAddressFragment === ''
    || !str_contains((string) $address->address1, $expectedAddressFragment)
) {
    throw new RuntimeException('The free-shipping order did not retain its supported Japanese prefecture/address fixture.');
}

echo json_encode([
    'order_id' => (int) $order->id,
    'reference' => (string) $order->reference,
    'email' => (string) $customer->email,
    'product_id' => $productId,
    'product_quantity' => (int) $orderDetails[0]['product_quantity'],
    'product_tax_rule_group_id' => $productTaxGroupId,
    'unit_price_tax_excl' => $detailUnitTaxExcl,
    'unit_price_tax_incl' => $detailUnitTaxIncl,
    'saved_order_detail_tax_group_id' => $savedDetailTaxGroupId,
    'saved_order_detail_taxes' => $storedTaxRows,
    'saved_tax_interpretation' => $savedTaxInterpretation,
    'tax_fixture_scope' => (string) $browserOrder['tax_fixture_scope'],
    'carrier_id' => (int) $carrier->id,
    'carrier_tax_rule_group_id' => $persistedCarrierTaxGroupId,
    'carrier_is_free' => (bool) $carrier->is_free,
    'carrier_zone_id' => $zoneId,
    'carrier_zone_country_codes' => $zoneCountryCodes,
    'carrier_shipping_tax_excl' => $carrierShippingTaxExcl,
    'carrier_shipping_tax_incl' => $carrierShippingTaxIncl,
    'total_products_tax_excl' => (float) $order->total_products,
    'total_products_tax_incl' => (float) $order->total_products_wt,
    'total_shipping_tax_excl' => (float) $order->total_shipping_tax_excl,
    'total_shipping_tax_incl' => (float) $order->total_shipping_tax_incl,
    'total_wrapping_tax_excl' => $wrappingTaxExcl,
    'total_wrapping_tax_incl' => $wrappingTaxIncl,
    'total_discounts_tax_excl' => $discountsTaxExcl,
    'total_discounts_tax_incl' => $discountsTaxIncl,
    'total_paid_tax_excl' => (float) $order->total_paid_tax_excl,
    'total_paid_tax_incl' => (float) $order->total_paid_tax_incl,
    'total_paid_real' => (float) $order->total_paid_real,
    'currency' => (string) $currency->iso_code,
    'payment_module' => (string) $order->module,
    'order_state_id' => (int) $order->current_state,
    'order_state_paid' => (bool) $state->paid,
    'carrier_url_configured' => !empty($carrier->url),
    'postcode' => (string) $address->postcode,
    'state_iso_code' => $expectedStateIso,
    'browser_checkout' => $browserTotals,
    'browser_pre_coupon_checkout' => $preCouponBrowserTotals ?? null,
    'browser_order_confirmation' => $confirmationTotals,
    'platform_fee' => 0,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDERR, sprintf(
    "PASS: native order #%d/%s stores a free Japan carrier, quantity %d, ¥0 shipping, reconciled JPY tax/order totals, and no platform fee.\n",
    (int) $order->id,
    (string) $order->reference,
    $expectedQuantity
));
