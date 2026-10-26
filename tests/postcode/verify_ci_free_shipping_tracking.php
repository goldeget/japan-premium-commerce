<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;
$trackingInputPath = trim((string) getenv('KURANEA_CI_TRACKING_INPUT_PATH'));
$expectedTrackingInputPath = '/tmp/ci-shipping-free-order-tracking.json';
$stage = 'run_scope';

set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $safeStage = preg_match('/\A[a-z][a-z0-9_]*\z/D', $stage) === 1 ? $stage : 'unknown';
    $exceptionType = preg_replace('/[^A-Za-z0-9_]/', '', get_class($exception)) ?: 'Exception';
    $diagnostic = sprintf(
        'KURANEA_SHIPPING_TRACKING_PERSISTENCE_STAGE=%s; exception=%s',
        $safeStage,
        $exceptionType
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        fwrite(STDOUT, '::error title=ORDENOWA tracking persistence::' . $diagnostic . PHP_EOL);
    }
    exit(1);
});

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== $expectedProjectName
    || $trackingInputPath !== $expectedTrackingInputPath
    || !is_file($trackingInputPath)
) {
    fwrite(STDERR, "BLOCKED: tracking persistence verification requires its matching isolated GitHub Actions checkout.\n");
    exit(77);
}

$stage = 'database_scope';
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php')) {
    throw new RuntimeException('The installed PrestaShop configuration is missing.');
}
require_once $shopRoot . '/config/config.inc.php';

$dbServer = defined('_DB_SERVER_') ? (string) _DB_SERVER_ : '';
$dbName = defined('_DB_NAME_') ? (string) _DB_NAME_ : '';
$databaseScopeMatches = in_array($dbServer, ['mariadb', 'mariadb:3306'], true)
    && getenv('DB_SERVER') === 'mariadb'
    && getenv('DB_PORT') === '3306'
    && $dbName === 'prestashop'
    && (string) Db::getInstance()->getValue('SELECT DATABASE()') === $dbName;
if (!$databaseScopeMatches) {
    throw new RuntimeException('Tracking persistence verification refused a database outside the isolated CI Compose checkout.');
}

$stage = 'tracking_artifact';
$input = json_decode((string) file_get_contents($trackingInputPath), true, 32, JSON_THROW_ON_ERROR);
$safeAdminRouteClasses = ['modern_order_detail', 'legacy_order_detail'];
$safeCustomerRouteClasses = ['order_detail_controller', 'friendly_order_detail'];
$orderId = is_array($input) ? ($input['order_id'] ?? null) : null;
$carrierId = is_array($input) ? ($input['carrier_id'] ?? null) : null;
$orderCarrierId = is_array($input) ? ($input['order_carrier_id'] ?? null) : null;
$trackingNumber = is_array($input) ? ($input['tracking_number'] ?? null) : null;
$expectedOrderTotal = is_array($input) ? ($input['admin_order_total'] ?? null) : null;
$expectedStateId = is_array($input) ? ($input['admin_order_state_id_after'] ?? null) : null;
if (!is_array($input)
    || ($input['synthetic_ci_only'] ?? null) !== true
    || !is_int($orderId)
    || $orderId < 1
    || !is_int($carrierId)
    || $carrierId < 1
    || !is_int($orderCarrierId)
    || $orderCarrierId < 1
    || !is_int($expectedOrderTotal)
    || $expectedOrderTotal < 1
    || !is_int($expectedStateId)
    || $expectedStateId < 1
    || !is_string($trackingNumber)
    || preg_match('/\AORDENOWA-CI-TRACK-[0-9]{1,20}-[0-9]{1,4}\z/D', $trackingNumber) !== 1
    || !in_array($input['admin_route_class_before_update'] ?? null, $safeAdminRouteClasses, true)
    || !in_array($input['admin_route_class_after_save'] ?? null, $safeAdminRouteClasses, true)
    || !in_array($input['admin_route_class_after_fresh_get'] ?? null, $safeAdminRouteClasses, true)
    || !in_array($input['customer_detail_route_class'] ?? null, $safeCustomerRouteClasses, true)
    || ($input['admin_origin_matches'] ?? null) !== true
    || ($input['admin_folder_matches'] ?? null) !== true
    || ($input['admin_order_id_matches'] ?? null) !== true
    || ($input['admin_post_save_order_id_matches'] ?? null) !== true
    || ($input['admin_fresh_get_order_id_matches'] ?? null) !== true
    || ($input['admin_fresh_get_method_get'] ?? null) !== true
    || ($input['customer_origin_matches'] ?? null) !== true
    || ($input['customer_order_id_matches'] ?? null) !== true
    || ($input['admin_and_customer_order_ids_match'] ?? null) !== true
    || ($input['admin_and_customer_tracking_number_matches'] ?? null) !== true
    || ($input['admin_fresh_document_readback'] ?? null) !== true
    || ($input['customer_same_order_detail_readback'] ?? null) !== true
    || ($input['admin_order_state_preserved'] ?? null) !== true
    || ($input['admin_shipping_total'] ?? null) !== 0
    || ($input['admin_order_state_id_before'] ?? null) !== $expectedStateId
    || ($input['order_state_paid'] ?? null) !== false
    || ($input['total_paid_real'] ?? null) !== 0
    || ($input['shipping_total'] ?? null) !== 0
    || ($input['free_shipping_preserved'] ?? null) !== true
    || ($input['physical_dispatch_performed'] ?? null) !== false
    || ($input['carrier_scan_performed'] ?? null) !== false
) {
    throw new RuntimeException('The browser tracking artifact does not satisfy the safe same-order readback contract.');
}

$expectedReference = $input['order_reference'] ?? null;
if (!is_string($expectedReference) || preg_match('/\A[A-Z0-9]{8,16}\z/D', $expectedReference) !== 1) {
    throw new RuntimeException('The browser tracking artifact has no safe synthetic order reference.');
}

$stage = 'native_order_and_order_carrier_readback';
$order = new Order($orderId);
$orderCarrier = new OrderCarrier($orderCarrierId);
$carrier = new Carrier($carrierId);
$state = Validate::isLoadedObject($order)
    ? new OrderState((int) $order->current_state, (int) $order->id_lang)
    : false;
$currency = Validate::isLoadedObject($order)
    ? new Currency((int) $order->id_currency)
    : false;
$carrierRows = Db::getInstance()->executeS(
    'SELECT `id_order_carrier` FROM `' . _DB_PREFIX_ . 'order_carrier`'
    . ' WHERE `id_order` = ' . (int) $orderId
    . ' ORDER BY `id_order_carrier`'
);
$carrierRowMatches = is_array($carrierRows)
    && count($carrierRows) === 1
    && (int) $carrierRows[0]['id_order_carrier'] === $orderCarrierId;

if (!Validate::isLoadedObject($order)
    || !Validate::isLoadedObject($orderCarrier)
    || !Validate::isLoadedObject($carrier)
    || !Validate::isLoadedObject($state)
    || !Validate::isLoadedObject($currency)
    || !$carrierRowMatches
    || (int) $order->id !== $orderId
    || (string) $order->reference !== $expectedReference
    || (int) $order->id_carrier !== $carrierId
    || (int) $order->current_state !== $expectedStateId
    || (string) $order->module !== 'ps_checkpayment'
    || (bool) $state->paid
    || (float) $order->total_paid_real !== 0.0
    || (float) $order->total_shipping_tax_excl !== 0.0
    || (float) $order->total_shipping_tax_incl !== 0.0
    || abs((float) $order->total_paid_tax_incl - (float) $expectedOrderTotal) > 0.0001
    || (string) $currency->iso_code !== 'JPY'
    || (int) $orderCarrier->id !== $orderCarrierId
    || (int) $orderCarrier->id_order !== $orderId
    || (int) $orderCarrier->id_carrier !== $carrierId
    || (string) $orderCarrier->tracking_number !== $trackingNumber
    || !empty($carrier->url)
) {
    throw new RuntimeException('The native order and order-carrier records do not match the browser tracking readback.');
}

echo json_encode([
    'synthetic_ci_only' => true,
    'read_only_database_readback' => true,
    'native_order_loaded' => true,
    'native_order_carrier_loaded' => true,
    'order_id' => (int) $order->id,
    'order_reference_matches' => true,
    'carrier_id' => (int) $order->id_carrier,
    'order_carrier_id' => (int) $orderCarrier->id,
    'admin_route_class_before_update' => (string) $input['admin_route_class_before_update'],
    'admin_route_class_after_save' => (string) $input['admin_route_class_after_save'],
    'admin_route_class_after_fresh_get' => (string) $input['admin_route_class_after_fresh_get'],
    'customer_detail_route_class' => (string) $input['customer_detail_route_class'],
    'admin_origin_matches' => true,
    'admin_folder_matches' => true,
    'admin_order_id_matches' => true,
    'admin_post_save_order_id_matches' => true,
    'admin_fresh_get_order_id_matches' => true,
    'admin_fresh_get_method_get' => true,
    'customer_origin_matches' => true,
    'customer_order_id_matches' => true,
    'admin_and_customer_order_ids_match' => true,
    'admin_and_customer_tracking_number_matches' => true,
    'admin_fresh_document_readback' => true,
    'customer_same_order_detail_readback' => true,
    'admin_order_state_id_before' => (int) $input['admin_order_state_id_before'],
    'admin_order_state_id_after' => (int) $input['admin_order_state_id_after'],
    'admin_order_state_preserved' => true,
    'admin_order_total' => (int) $input['admin_order_total'],
    'admin_shipping_total' => 0,
    'order_carrier_order_id_matches' => (int) $orderCarrier->id_order === (int) $order->id,
    'tracking_number' => (string) $orderCarrier->tracking_number,
    'tracking_number_matches_browser' => (string) $orderCarrier->tracking_number === $trackingNumber,
    'order_state_id' => (int) $order->current_state,
    'order_state_paid' => (bool) $state->paid,
    'total_paid_real' => (float) $order->total_paid_real,
    'total_paid_tax_incl' => (float) $order->total_paid_tax_incl,
    'total_shipping_tax_excl' => (float) $order->total_shipping_tax_excl,
    'total_shipping_tax_incl' => (float) $order->total_shipping_tax_incl,
    'currency' => (string) $currency->iso_code,
    'payment_module' => (string) $order->module,
    'carrier_tracking_destination_configured' => !empty($carrier->url),
    'same_order_and_tracking_persisted' => true,
    'physical_dispatch_performed' => false,
    'carrier_scan_performed' => false,
], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDERR, sprintf(
    "PASS: native Order #%d and OrderCarrier #%d persist the same unpaid synthetic tracking number and ¥0 shipping.\n",
    (int) $order->id,
    (int) $orderCarrier->id
));
