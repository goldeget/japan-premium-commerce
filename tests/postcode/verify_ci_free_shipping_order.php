<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$orderId = (int) getenv('KURANEA_CI_ORDER_ID');
$productId = (int) getenv('KURANEA_CI_PRODUCT_ID');
$carrierId = (int) getenv('KURANEA_CI_CARRIER_ID');
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
if ($browserCarrierTaxGroupId !== null
    && (int) $browserCarrierTaxGroupId !== (int) $carrier->id_tax_rules_group
) {
    throw new RuntimeException('The carrier tax-rule selection in AdminCarriers differs from the persisted carrier.');
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
    'SELECT `id_order_detail`, `id_tax_rules_group`, `product_id`, `product_quantity`, `total_price_tax_excl`, `total_price_tax_incl`'
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
if (!is_array($orderDetails)
    || count($orderDetails) !== 1
    || (int) $orderDetails[0]['product_id'] !== $productId
    || (int) $orderDetails[0]['product_quantity'] !== $expectedQuantity
    || $productTaxGroupId !== $browserProductTaxGroupId
    || (int) $orderDetails[0]['id_tax_rules_group'] !== $browserProductTaxGroupId
) {
    throw new RuntimeException('The native order quantity or product tax-rule group differs from the browser fixture.');
}
$detailProductsTaxExcl = (float) $orderDetails[0]['total_price_tax_excl'];
$detailProductsTaxIncl = (float) $orderDetails[0]['total_price_tax_incl'];
if (abs($detailProductsTaxExcl - (float) $order->total_products) > 0.0001
    || abs($detailProductsTaxIncl - (float) $order->total_products_wt) > 0.0001
) {
    throw new RuntimeException('Native order product and tax-exclusive/inclusive totals do not reconcile.');
}
if ($productTaxGroupId === 0 && abs($detailProductsTaxExcl - $detailProductsTaxIncl) > 0.0001) {
    throw new RuntimeException('A product with no assigned tax rule unexpectedly has a nonzero product tax.');
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
$savedTaxInterpretation = 'No assigned calculation rule; not a legal tax determination';
if ($savedDetailTaxGroupId > 0) {
    // This branch is scoped to the nationwide synthetic 10% CI fixture, not a legal rate.
    $coupon = is_array($browserOrder['coupon'] ?? null) ? $browserOrder['coupon'] : [];
    $expectedCouponCode = 'ORDENOWACI' . $runId . $runAttempt;
    if (($coupon['applied'] ?? false) !== true
        || (string) ($coupon['code'] ?? '') !== $expectedCouponCode
        || $discountsTaxExcl <= 0
        || $discountsTaxIncl <= 0
    ) {
        throw new RuntimeException('The synthetic taxable order must use its run-scoped tax-inclusive coupon.');
    }
    if (count($storedTaxRows) !== 1) {
        throw new RuntimeException('The synthetic taxable order must retain its single native tax row.');
    }
    $storedTaxRow = $storedTaxRows[0];
    $storedTaxRate = (float) $storedTaxRow['rate'];
    $storedTaxUnit = (float) $storedTaxRow['unit_amount'];
    $storedTaxTotal = (float) $storedTaxRow['total_amount'];
    $discountedProductTaxBase = $detailProductsTaxExcl - $discountsTaxExcl;
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
    $savedTaxInterpretation = 'CI-only synthetic 10% calculation fixture; not a legal tax rate or determination';
} elseif ($storedTaxRows !== []) {
    throw new RuntimeException('The fixture with no assigned calculation rule unexpectedly has persisted tax rows.');
}

foreach ([
    'browser product tax excl' => [$browserProductsTaxExcl, (float) $order->total_products],
    'browser product tax incl' => [$browserProductsTaxIncl, (float) $order->total_products_wt],
    'browser shipping tax excl' => [$browserShippingTaxExcl, (float) $order->total_shipping_tax_excl],
    'browser shipping tax incl' => [$browserShippingTaxIncl, (float) $order->total_shipping_tax_incl],
    'browser discount tax excl' => [$browserDiscountTaxExcl, $discountsTaxExcl],
    'browser discount tax incl' => [$browserDiscountTaxIncl, $discountsTaxIncl],
    'browser total tax excl' => [$browserTotalTaxExcl, (float) $order->total_paid_tax_excl],
    'browser total tax incl' => [$browserTotalTaxIncl, (float) $order->total_paid_tax_incl],
    'native tax-exclusive formula' => [$nativeTotalTaxExcl, (float) $order->total_paid_tax_excl],
    'native tax-inclusive formula' => [$nativeTotalTaxIncl, (float) $order->total_paid_tax_incl],
    'customer order history total' => [
        (float) ($browserOrder['order_history_total'] ?? -1),
        (float) $order->total_paid_tax_incl,
    ],
    'browser tax amount' => [
        (float) ($browserTotals['tax'] ?? -1),
        $nativeTaxes,
    ],
] as $checkName => [$actual, $expected]) {
    if (abs($actual - $expected) > 0.0001) {
        throw new RuntimeException(sprintf(
            '%s mismatch: browser/native %.4f vs %.4f; an unaccounted platform fee is not allowed.',
            $checkName,
            $actual,
            $expected
        ));
    }
}
if (($productTaxGroupId === 0 && abs($nativeTaxes) > 0.0001)
    || (float) $order->total_shipping_tax_excl !== 0.0
    || (float) $order->total_shipping_tax_incl !== 0.0
    || abs($wrappingTaxExcl) > 0.0001
    || abs($wrappingTaxIncl) > 0.0001
    || abs((float) $order->total_paid_real) > 0.0001
    || (int) ($browserTotals['quantity'] ?? 0) !== $expectedQuantity
) {
    throw new RuntimeException('The free-shipping order contains shipping, wrapping, tax, or payment amounts outside its configured product fixture.');
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
    'saved_order_detail_tax_group_id' => $savedDetailTaxGroupId,
    'saved_order_detail_taxes' => $storedTaxRows,
    'saved_tax_interpretation' => $savedTaxInterpretation,
    'tax_fixture_scope' => (string) $browserOrder['tax_fixture_scope'],
    'carrier_id' => (int) $carrier->id,
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
    'postcode' => (string) $address->postcode,
    'state_iso_code' => $expectedStateIso,
    'browser_checkout' => $browserTotals,
    'platform_fee' => 0,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDERR, sprintf(
    "PASS: native order #%d/%s stores a free Japan carrier, quantity %d, ¥0 shipping, reconciled JPY tax/order totals, and no platform fee.\n",
    (int) $order->id,
    (string) $order->reference,
    $expectedQuantity
));
