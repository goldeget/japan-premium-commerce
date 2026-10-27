<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$label = trim((string) getenv('KURANEA_CI_VIEWPORT'));
$orderId = (int) getenv('KURANEA_CI_ORDER_ID');
$productId = (int) getenv('KURANEA_CI_PRODUCT_ID');
$expectedIso = trim((string) getenv('KURANEA_CI_EXPECTED_LANG_ISO'));
$expectedReference = trim((string) getenv('KURANEA_CI_EXPECTED_ORDER_REFERENCE'));
$localeByLabel = ['mail-ja' => 'ja', 'mail-en' => 'en', 'mail-ko' => 'ko'];

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== 'kuranea-ci-' . $runId . '-' . $runAttempt
    || !isset($localeByLabel[$label])
    || $localeByLabel[$label] !== $expectedIso
    || preg_match('/\A[A-Z0-9]{8,16}\z/D', $expectedReference) !== 1
    || $orderId < 1
    || $productId < 1
) {
    fwrite(STDERR, "BLOCKED: customer email order readback requires its matching isolated GitHub Actions checkout.\n");
    exit(77);
}

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php')) {
    throw new RuntimeException('The installed PrestaShop configuration is missing.');
}
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once $shopRoot . '/config/config.inc.php';

$expectedShopId = (int) Configuration::get('PS_SHOP_DEFAULT');
$order = new Order($orderId);
if (!Validate::isLoadedObject($order)
    || (string) $order->reference !== $expectedReference
    || $expectedShopId < 1
    || (int) $order->id_shop !== $expectedShopId
) {
    throw new RuntimeException('The browser order reference did not read back from the native order.');
}
$customer = new Customer((int) $order->id_customer);
$safeRunId = substr($runId, -20);
$safeAttempt = substr($runAttempt, -4);
$expectedEmail = sprintf('qa-ordenowa-checkout-%s-%s-%s@example.invalid', $safeRunId, $safeAttempt, $label);
if (!Validate::isLoadedObject($customer)
    || strtolower((string) $customer->email) !== strtolower($expectedEmail)
    || (bool) $customer->is_guest
    || (int) $customer->id_shop !== $expectedShopId
) {
    throw new RuntimeException('The order did not read back to its run-scoped registered customer.');
}

$orderLanguage = new Language((int) $order->id_lang);
$customerLanguage = new Language((int) $customer->id_lang);
if (!Validate::isLoadedObject($orderLanguage)
    || !Validate::isLoadedObject($customerLanguage)
    || (string) $orderLanguage->iso_code !== $expectedIso
    || (string) $customerLanguage->iso_code !== $expectedIso
) {
    throw new RuntimeException('The persisted customer and order language did not match the selected locale.');
}

$state = new OrderState((int) $order->current_state, (int) $order->id_lang);
$currency = new Currency((int) $order->id_currency);
if ((string) $order->module !== 'ps_checkpayment'
    || !Validate::isLoadedObject($state)
    || (bool) $state->paid
    || (float) $order->total_paid_real !== 0.0
    || (float) $order->total_paid_tax_incl <= 0.0
    || !Validate::isLoadedObject($currency)
    || (string) $currency->iso_code !== 'JPY'
) {
    throw new RuntimeException('The native mail acceptance order must remain an unpaid positive JPY ps_checkpayment order.');
}

$orderDetails = Db::getInstance()->executeS(
    'SELECT `product_id`, `product_quantity` FROM `' . _DB_PREFIX_ . 'order_detail`'
    . ' WHERE `id_order` = ' . (int) $order->id
);
if (!is_array($orderDetails)
    || count($orderDetails) !== 1
    || (int) $orderDetails[0]['product_id'] !== $productId
    || (int) $orderDetails[0]['product_quantity'] !== 1
) {
    throw new RuntimeException('The persisted mail acceptance order must contain its exact CI product once.');
}

$address = new Address((int) $order->id_address_delivery);
$japanCountryId = (int) Country::getByIso('JP');
$expectedBuilding = 'ORDENOWA CI ' . strtoupper($label) . ' TEST BUILDING 101';
if (!Validate::isLoadedObject($address)
    || (int) $address->id_customer !== (int) $customer->id
    || $japanCountryId < 1
    || (int) $address->id_country !== $japanCountryId
    || (string) $address->postcode !== '100-0004'
    || (string) $address->city !== '千代田区'
    || !str_contains((string) $address->address1, '大手町1-2-3')
    || (string) $address->address2 !== $expectedBuilding
) {
    throw new RuntimeException('The persisted mail acceptance order lost its synthetic Japan delivery address.');
}

echo json_encode([
    'language_iso' => $expectedIso,
    'customer_persisted' => true,
    'order_persisted' => true,
    'unpaid' => true,
    'payment_module' => (string) $order->module,
    'product_quantity' => (int) $orderDetails[0]['product_quantity'],
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
