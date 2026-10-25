<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$sourceOrderIdValue = trim((string) getenv('KURANEA_CI_PAID_LIKE_SOURCE_ORDER_ID'));
$unpaidOrderIdValue = trim((string) getenv('KURANEA_CI_UNPAID_ORDER_ID'));
$sourceOrderId = (int) $sourceOrderIdValue;
$unpaidOrderId = (int) $unpaidOrderIdValue;
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || preg_match('/\A[0-9]+\z/D', $sourceOrderIdValue) !== 1
    || preg_match('/\A[0-9]+\z/D', $unpaidOrderIdValue) !== 1
    || $sourceOrderId < 1
    || $unpaidOrderId < 1
    || $sourceOrderId === $unpaidOrderId
    || $projectName !== $expectedProjectName
) {
    fwrite(STDERR, "BLOCKED: paid-like order preparation requires two distinct run-scoped browser orders in their matching isolated GitHub Actions project.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $exceptionType = preg_replace('/[^A-Za-z0-9_]/', '', get_class($exception)) ?: 'Exception';
    $diagnostic = sprintf('KURANEA_ORDER_LIFECYCLE_PREP_STAGE=%s; exception=%s', $stage, $exceptionType);
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA synthetic paid-like fixture::' . $annotation . PHP_EOL);
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

$stage = 'isolated shop context';
$shop = new Shop(1);
if (!Validate::isLoadedObject($shop) || Shop::getTotalShops() !== 1) {
    throw new RuntimeException('The native fixture preparer requires the isolated single-shop CI installation.');
}
$context = Context::getContext();
$context->shop = $shop;
Shop::setContext(Shop::CONTEXT_SHOP, (int) $shop->id);
$context->employee = new Employee(1);
if (!Validate::isLoadedObject($context->employee)) {
    throw new RuntimeException('The isolated Back Office employee could not be loaded.');
}

$stage = 'second run-scoped offline browser order preflight';
$sourceOrder = new Order($sourceOrderId);
$unpaidOrder = new Order($unpaidOrderId);
if (!Validate::isLoadedObject($sourceOrder) || !Validate::isLoadedObject($unpaidOrder)) {
    throw new RuntimeException('One of the supplied run-scoped browser orders does not exist.');
}
$sourceCustomer = new Customer((int) $sourceOrder->id_customer);
$unpaidCustomer = new Customer((int) $unpaidOrder->id_customer);
$expectedSourceEmail = sprintf('qa-ordenowa-checkout-%s-%s-mobile@example.invalid', $runId, $runAttempt);
$expectedUnpaidEmail = sprintf('qa-ordenowa-checkout-%s-%s-desktop@example.invalid', $runId, $runAttempt);
if (!Validate::isLoadedObject($sourceCustomer)
    || strtolower((string) $sourceCustomer->email) !== $expectedSourceEmail
    || !Validate::isLoadedObject($unpaidCustomer)
    || strtolower((string) $unpaidCustomer->email) !== $expectedUnpaidEmail
    || (string) $sourceOrder->module !== 'ps_checkpayment'
    || (string) $unpaidOrder->module !== 'ps_checkpayment'
    || (int) $sourceOrder->id_shop !== (int) $shop->id
    || (int) $unpaidOrder->id_shop !== (int) $shop->id
) {
    throw new RuntimeException('The fixture source must be the second, mobile, run-scoped ps_checkpayment browser order.');
}

$context->language = new Language((int) $sourceOrder->id_lang);
$context->currency = new Currency((int) $sourceOrder->id_currency);
$sourceProducts = $sourceOrder->getProducts();
if (!is_array($sourceProducts) || count($sourceProducts) !== 1) {
    throw new RuntimeException('The mobile fixture source must contain exactly one product line.');
}
$sourceProductRow = reset($sourceProducts);
$sourceProductId = (int) ($sourceProductRow['product_id'] ?? 0);
$sourceProduct = $sourceProductId > 0
    ? new Product($sourceProductId, false, (int) $sourceOrder->id_lang, (int) $sourceOrder->id_shop)
    : false;
if (!($sourceProduct instanceof Product)
    || !Validate::isLoadedObject($sourceProduct)
    || !str_starts_with((string) $sourceProduct->reference, 'KURANEA-CI-')
    || (int) ($sourceProductRow['product_quantity'] ?? 0) !== 1
) {
    throw new RuntimeException('The mobile fixture source must contain one unit of a run-scoped CI product.');
}
$currentState = new OrderState((int) $sourceOrder->current_state, (int) $sourceOrder->id_lang);
$deliveredStateId = (int) Configuration::get('PS_OS_DELIVERED');
$deliveredState = $deliveredStateId > 0 ? new OrderState($deliveredStateId, (int) $sourceOrder->id_lang) : false;
$paymentStateId = (int) Configuration::get('PS_OS_PAYMENT');
$webservicePaymentStateId = (int) Configuration::get('PS_OS_WS_PAYMENT');
if (!Validate::isLoadedObject($currentState)
    || (bool) $currentState->paid
    || $sourceOrder->hasBeenPaid()
    || (float) $sourceOrder->total_paid_real !== 0.0
    || $sourceOrder->current_state === $deliveredStateId
    || !($deliveredState instanceof OrderState)
    || !Validate::isLoadedObject($deliveredState)
    || !(bool) $deliveredState->paid
    || !(bool) $deliveredState->shipped
    || !(bool) $deliveredState->invoice
    || !(bool) $deliveredState->delivery
    || $deliveredStateId === $paymentStateId
    || $deliveredStateId === $webservicePaymentStateId
    || (int) $sourceOrder->invoice_number !== 0
    || (float) $sourceOrder->total_paid_tax_incl <= 0.0
) {
    throw new RuntimeException('The native delivered state or unpaid mobile order cannot safely create a synthetic paid-like fixture.');
}
$existingPayments = $sourceOrder->getOrderPaymentCollection();
if ($existingPayments->count() !== 0) {
    throw new RuntimeException('The mobile source order already has a native payment ledger entry.');
}
$existingReturns = OrderReturn::getOrdersReturn((int) $sourceOrder->id_customer, (int) $sourceOrder->id, false);
$existingSlips = OrderSlip::getOrdersSlip((int) $sourceOrder->id_customer, (int) $sourceOrder->id);
if ((is_array($existingReturns) && $existingReturns !== []) || (is_array($existingSlips) && $existingSlips !== [])) {
    throw new RuntimeException('The mobile source order already has return or credit-slip records.');
}

$markerName = 'KURANEA_CI_ORDER_RETURN_BACKUP';
$shopId = (int) $shop->id;
$markerExisting = Configuration::get($markerName, null, null, $shopId);
if ($markerExisting !== false && $markerExisting !== null && $markerExisting !== '') {
    throw new RuntimeException('A prior order-return configuration backup is still present in this CI project.');
}
$previousOrderReturn = (bool) Configuration::get('PS_ORDER_RETURN', null, null, $shopId);
$marker = [
    'run_id' => $runId,
    'run_attempt' => $runAttempt,
    'shop_id' => $shopId,
    'source_order_id' => $sourceOrderId,
    'paid_like_order_id' => 0,
    'previous_order_return' => $previousOrderReturn,
];
$markerJson = json_encode($marker, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
$restoreConfig = static function () use ($markerName, $shopId, $runId, $runAttempt): bool {
    $raw = Configuration::get($markerName, null, null, $shopId);
    if (!is_string($raw) || $raw === '') {
        return true;
    }
    $saved = json_decode($raw, true);
    if (!is_array($saved)
        || (string) ($saved['run_id'] ?? '') !== $runId
        || (string) ($saved['run_attempt'] ?? '') !== $runAttempt
        || (int) ($saved['shop_id'] ?? 0) !== $shopId
        || !array_key_exists('previous_order_return', $saved)
    ) {
        return false;
    }
    if (!Configuration::updateValue('PS_ORDER_RETURN', (bool) $saved['previous_order_return'], false, null, $shopId)) {
        return false;
    }
    Configuration::deleteByName($markerName);

    return (bool) Configuration::get('PS_ORDER_RETURN', null, null, $shopId)
        === (bool) $saved['previous_order_return'];
};
$prepared = false;
register_shutdown_function(static function () use (&$prepared, $restoreConfig): void {
    if ($prepared) {
        return;
    }
    try {
        if (!$restoreConfig()) {
            fwrite(STDERR, "ERROR: the failed fixture preparation could not restore PS_ORDER_RETURN.\n");
        }
    } catch (Throwable $exception) {
        fwrite(STDERR, "ERROR: the failed fixture preparation could not restore PS_ORDER_RETURN.\n");
    }
});

$stage = 'enable isolated native returns';
if (!Configuration::updateValue($markerName, $markerJson, false, null, $shopId)) {
    throw new RuntimeException('The run-scoped PS_ORDER_RETURN backup could not be saved.');
}
if (!Configuration::updateValue('PS_ORDER_RETURN', true, false, null, $shopId)) {
    throw new RuntimeException('PS_ORDER_RETURN could not be enabled in the isolated shop.');
}

$stage = 'native synthetic paid-like state transition';
$history = new OrderHistory();
$history->id_order = (int) $sourceOrder->id;
$history->id_employee = (int) $context->employee->id;
$history->changeIdOrderState($deliveredStateId, $sourceOrder);
if (!$history->add()) {
    throw new RuntimeException('PrestaShop could not persist the native delivered-state history entry.');
}
Order::cleanHistoryCache();
$preparedOrder = new Order($sourceOrderId);
$preparedState = new OrderState((int) $preparedOrder->current_state, (int) $preparedOrder->id_lang);
if (!Validate::isLoadedObject($preparedOrder)
    || !Validate::isLoadedObject($preparedState)
    || (int) $preparedOrder->current_state !== $deliveredStateId
    || !(bool) $preparedState->paid
    || !(bool) $preparedState->shipped
    || !$preparedOrder->hasBeenPaid()
    || (float) $preparedOrder->total_paid_real <= 0.0
    || $preparedOrder->delivery_date === '0000-00-00 00:00:00'
    || !$preparedOrder->isReturnable()
) {
    throw new RuntimeException('The native delivered-state transition did not produce a return-eligible synthetic order.');
}

$stage = 'load native invoice payment association';
$paymentRow = Db::getInstance()->getRow(
    'SELECT op.`id_order_payment`, op.`order_reference` FROM `' . _DB_PREFIX_ . 'order_payment` op'
    . ' INNER JOIN `' . _DB_PREFIX_ . 'order_invoice_payment` oip ON oip.`id_order_payment` = op.`id_order_payment`'
    . ' WHERE oip.`id_order` = ' . (int) $preparedOrder->id
    . ' ORDER BY op.`id_order_payment` DESC LIMIT 1'
);
$payment = is_array($paymentRow) ? new OrderPayment((int) ($paymentRow['id_order_payment'] ?? 0)) : false;
$stage = 'validate native payment ledger row';
if (!($payment instanceof OrderPayment)
    || !Validate::isLoadedObject($payment)
    || (string) $payment->order_reference !== (string) $preparedOrder->reference
    || (float) $payment->amount <= 0.0
) {
    throw new RuntimeException('The native state transition did not create an order-linked payment ledger row.');
}
$stage = 'label native payment ledger as synthetic';
$payment->payment_method = 'CI ONLY synthetic paid-like test; no funds captured';
if (!$payment->update() || (string) $payment->payment_method !== 'CI ONLY synthetic paid-like test; no funds captured') {
    throw new RuntimeException('The native order payment ledger row could not be labeled as synthetic CI data.');
}
$marker['paid_like_order_id'] = (int) $preparedOrder->id;
$markerJson = json_encode($marker, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
$stage = 'persist native return configuration marker';
if (!Configuration::updateValue($markerName, $markerJson, false, null, $shopId)) {
    throw new RuntimeException('The prepared paid-like order ID could not be recorded for configuration restoration.');
}

$prepared = true;
echo json_encode([
    'status' => 'prepared',
    'paid_like_order_id' => (int) $preparedOrder->id,
    'KURANEA_CI_PAID_LIKE_ORDER_ID' => (int) $preparedOrder->id,
    'synthetic CI-only' => true,
    'provider_call' => false,
    'cash_refund' => 'not_requested',
    'PS_ORDER_RETURN' => 'enabled until verifier restores saved value',
], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDOUT, sprintf(
    "PASS: mobile run-scoped ps_checkpayment order #%d now has a clearly labeled synthetic CI-only paid-like ledger entry; no funds were captured.\n",
    (int) $preparedOrder->id
));
