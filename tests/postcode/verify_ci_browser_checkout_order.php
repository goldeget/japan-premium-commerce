<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$viewport = trim((string) getenv('KURANEA_CI_VIEWPORT'));
$orderId = (int) getenv('KURANEA_CI_ORDER_ID');
$productId = (int) getenv('KURANEA_CI_PRODUCT_ID');
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== $expectedProjectName
    || !in_array($viewport, ['desktop', 'mobile'], true)
    || $orderId < 1
    || $productId < 1
) {
    fwrite(STDERR, "BLOCKED: browser order verification requires its matching isolated GitHub Actions checkout.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf(
        'KURANEA_BROWSER_ORDER_STAGE=%s; exception=%s; message=%s',
        $stage,
        get_class($exception),
        substr($message, 0, 1000)
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA browser order::' . $annotation . PHP_EOL);
    }
    exit(1);
});

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php')) {
    throw new RuntimeException('The installed PrestaShop configuration is missing.');
}
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
require_once $shopRoot . '/config/config.inc.php';

$stage = 'browser customer order lookup';
$order = new Order($orderId);
if (!Validate::isLoadedObject($order)) {
    throw new RuntimeException('The browser checkout did not create the reported native order.');
}
$customer = new Customer((int) $order->id_customer);
$expectedEmail = sprintf('qa-ordenowa-checkout-%s-%s-%s@example.invalid', $runId, $runAttempt, $viewport);
if (!Validate::isLoadedObject($customer)
    || strtolower((string) $customer->email) !== strtolower($expectedEmail)
    || (bool) $customer->is_guest
) {
    throw new RuntimeException('The browser order must be linked to its run-scoped registered customer.');
}

$stage = 'unpaid ps_checkpayment order';
$state = new OrderState((int) $order->current_state, (int) $order->id_lang);
$cancelledStateId = (int) Configuration::get('PS_OS_CANCELED');
$cancelledState = $cancelledStateId > 0
    ? new OrderState($cancelledStateId, (int) $order->id_lang)
    : false;
$currency = new Currency((int) $order->id_currency);
if ((string) $order->module !== 'ps_checkpayment'
    || !Validate::isLoadedObject($state)
    || (bool) $state->paid
    || (float) $order->total_paid_real !== 0.0
    || (float) $order->total_paid_tax_incl <= 0.0
    || !($cancelledState instanceof OrderState)
    || !Validate::isLoadedObject($cancelledState)
    || (bool) $cancelledState->paid
    || (bool) $cancelledState->logable
    || !Validate::isLoadedObject($currency)
    || (string) $currency->iso_code !== 'JPY'
) {
    throw new RuntimeException('The browser order must be a positive JPY ps_checkpayment order whose state is still unpaid.');
}

$stage = 'searched product persistence';
$orderDetails = Db::getInstance()->executeS(
    'SELECT `product_id`, `product_quantity` FROM `' . _DB_PREFIX_ . 'order_detail`'
    . ' WHERE `id_order` = ' . (int) $order->id
);
if (!is_array($orderDetails)
    || count($orderDetails) !== 1
    || (int) $orderDetails[0]['product_id'] !== $productId
    || (int) $orderDetails[0]['product_quantity'] !== 1
) {
    throw new RuntimeException('The browser order must contain exactly one unit of the searched CI-only product.');
}

$stage = 'Japanese delivery-address persistence';
$address = new Address((int) $order->id_address_delivery);
$japanCountryId = (int) Country::getByIso('JP');
$tokyoStateId = 0;
$states = State::getStatesByIdCountry($japanCountryId, true, 'iso_code', 'asc');
foreach (is_array($states) ? $states : [] as $stateRow) {
    if ((string) ($stateRow['iso_code'] ?? '') === 'JP-13') {
        $tokyoStateId = (int) $stateRow['id_state'];
        break;
    }
}
$expectedBuilding = 'ORDENOWA CI ' . strtoupper($viewport) . ' TEST BUILDING 101';
if (!Validate::isLoadedObject($address)
    || (int) $address->id_customer !== (int) $customer->id
    || $japanCountryId < 1
    || $tokyoStateId < 1
    || (int) $address->id_country !== $japanCountryId
    || (int) $address->id_state !== $tokyoStateId
    || (string) $address->postcode !== '100-0004'
    || (string) $address->city !== '千代田区'
    || !str_contains((string) $address->address1, '大手町')
    || !str_contains((string) $address->address1, '1-2-3')
    || (string) $address->address2 !== $expectedBuilding
) {
    throw new RuntimeException('The browser order must retain its selected Tokyo postcode and manually entered building address.');
}

echo json_encode([
    'order_id' => (int) $order->id,
    'reference' => (string) $order->reference,
    'email' => (string) $customer->email,
    'product_id' => $productId,
    'product_quantity' => (int) $orderDetails[0]['product_quantity'],
    'payment_module' => (string) $order->module,
    'cancelled_state_id' => $cancelledStateId,
    'state' => (string) $state->name,
    'total_paid_real' => (float) $order->total_paid_real,
    'currency' => (string) $currency->iso_code,
    'postcode' => (string) $address->postcode,
    'city' => (string) $address->city,
    'state_iso_code' => 'JP-13',
    'address1' => (string) $address->address1,
    'address2' => (string) $address->address2,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDOUT, sprintf(
    'PASS: browser %s order #%d/%s contains one searched product and is unpaid JPY ps_checkpayment with Tokyo address 100-0004.\n',
    $viewport,
    (int) $order->id,
    (string) $order->reference
));
