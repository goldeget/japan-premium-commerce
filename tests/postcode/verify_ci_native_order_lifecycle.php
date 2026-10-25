<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$unpaidOrderIdValue = trim((string) getenv('KURANEA_CI_UNPAID_ORDER_ID'));
$paidLikeOrderIdValue = trim((string) getenv('KURANEA_CI_PAID_LIKE_ORDER_ID'));
$unpaidOrderId = (int) $unpaidOrderIdValue;
$paidLikeOrderId = (int) $paidLikeOrderIdValue;
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || preg_match('/\A[0-9]+\z/D', $unpaidOrderIdValue) !== 1
    || ($paidLikeOrderIdValue !== '' && preg_match('/\A[0-9]+\z/D', $paidLikeOrderIdValue) !== 1)
    || $projectName !== $expectedProjectName
    || $unpaidOrderId < 1
    || ($paidLikeOrderId > 0 && $paidLikeOrderId === $unpaidOrderId)
) {
    fwrite(STDERR, "BLOCKED: native order lifecycle QA requires its matching isolated GitHub Actions project and run-scoped order IDs.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $exceptionType = preg_replace('/[^A-Za-z0-9_]/', '', get_class($exception)) ?: 'Exception';
    $diagnostic = sprintf('KURANEA_ORDER_LIFECYCLE_STAGE=%s; exception=%s', $stage, $exceptionType);
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDOUT, '::error title=ORDENOWA native order lifecycle::' . $annotation . PHP_EOL);
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
if (!Validate::isLoadedObject($shop)) {
    throw new RuntimeException('The isolated shop could not be loaded.');
}
$context = Context::getContext();
$context->shop = $shop;
Shop::setContext(Shop::CONTEXT_SHOP, (int) $shop->id);
$context->employee = new Employee(1);
if (!Validate::isLoadedObject($context->employee)) {
    throw new RuntimeException('The isolated Back Office employee could not be loaded.');
}

$returnConfigMarkerName = 'KURANEA_CI_ORDER_RETURN_BACKUP';
$returnConfigRestored = false;
$restoreReturnConfiguration = static function () use (
    $returnConfigMarkerName,
    $runId,
    $runAttempt,
    $paidLikeOrderId,
    $shop
): bool {
    $rawMarker = Configuration::get($returnConfigMarkerName, null, null, (int) $shop->id);
    if ($rawMarker === false || $rawMarker === null || $rawMarker === '') {
        return true;
    }
    if (!is_string($rawMarker)) {
        return false;
    }
    $saved = json_decode($rawMarker, true);
    if (!is_array($saved)
        || (string) ($saved['run_id'] ?? '') !== $runId
        || (string) ($saved['run_attempt'] ?? '') !== $runAttempt
        || (int) ($saved['shop_id'] ?? 0) !== (int) $shop->id
        || !array_key_exists('previous_order_return', $saved)
    ) {
        return false;
    }
    if (!Configuration::updateValue('PS_ORDER_RETURN', (bool) $saved['previous_order_return'], false, null, (int) $shop->id)) {
        return false;
    }
    Configuration::deleteByName($returnConfigMarkerName);

    $remainingMarker = Configuration::get($returnConfigMarkerName, null, null, (int) $shop->id);

    return ((bool) Configuration::get('PS_ORDER_RETURN', null, null, (int) $shop->id)
        === (bool) $saved['previous_order_return'])
        && ($remainingMarker === false || $remainingMarker === null || $remainingMarker === '');
};
register_shutdown_function(static function () use (&$returnConfigRestored, $restoreReturnConfiguration): void {
    if ($returnConfigRestored) {
        return;
    }
    try {
        if ($restoreReturnConfiguration()) {
            $returnConfigRestored = true;
        } else {
            fwrite(STDERR, "ERROR: the run-scoped PS_ORDER_RETURN setting could not be restored.\n");
        }
    } catch (Throwable $exception) {
        fwrite(STDERR, "ERROR: the run-scoped PS_ORDER_RETURN setting could not be restored.\n");
    }
});
$returnConfigMarker = Configuration::get($returnConfigMarkerName, null, null, (int) $shop->id);
if ($paidLikeOrderId > 0) {
    $savedReturnConfig = is_string($returnConfigMarker) ? json_decode($returnConfigMarker, true) : null;
    if (!is_array($savedReturnConfig)
        || (string) ($savedReturnConfig['run_id'] ?? '') !== $runId
        || (string) ($savedReturnConfig['run_attempt'] ?? '') !== $runAttempt
        || (int) ($savedReturnConfig['shop_id'] ?? 0) !== (int) $shop->id
        || (int) ($savedReturnConfig['paid_like_order_id'] ?? 0) !== $paidLikeOrderId
    ) {
        throw new RuntimeException('The paid-like order was not prepared by this run-scoped CI fixture helper.');
    }
}

$stage = 'run-scoped order preflight';
$runScopedEmails = [
    sprintf('qa-ordenowa-checkout-%s-%s-desktop@example.invalid', $runId, $runAttempt),
    sprintf('qa-ordenowa-checkout-%s-%s-mobile@example.invalid', $runId, $runAttempt),
];
$loadTestOrder = static function (int $orderId, string $role) use ($runScopedEmails): array {
    $order = new Order($orderId);
    if (!Validate::isLoadedObject($order)) {
        throw new RuntimeException(sprintf('The supplied %s order does not exist.', $role));
    }
    $customer = new Customer((int) $order->id_customer);
    if (!Validate::isLoadedObject($customer) || !in_array(strtolower((string) $customer->email), $runScopedEmails, true)) {
        throw new RuntimeException(sprintf('The supplied %s order is not linked to this run\'s synthetic checkout customer.', $role));
    }
    if ((string) $order->module !== 'ps_checkpayment') {
        throw new RuntimeException(sprintf('The supplied %s order is not an offline ps_checkpayment order.', $role));
    }

    $context = Context::getContext();
    $context->language = new Language((int) $order->id_lang);
    $context->currency = new Currency((int) $order->id_currency);
    $products = $order->getProducts();
    if (!is_array($products) || count($products) !== 1) {
        throw new RuntimeException(sprintf('The supplied %s order must contain one test product line.', $role));
    }
    $productRow = reset($products);
    $productId = (int) ($productRow['product_id'] ?? 0);
    $product = $productId > 0 ? new Product($productId, false, (int) $order->id_lang, (int) $order->id_shop) : false;
    if (!($product instanceof Product)
        || !Validate::isLoadedObject($product)
        || !str_starts_with((string) $product->reference, 'KURANEA-CI-')
        || (int) ($productRow['product_quantity'] ?? 0) !== 1
    ) {
        throw new RuntimeException(sprintf('The supplied %s order is not a single-unit run-scoped CI product order.', $role));
    }

    return [$order, $customer, $products];
};

[$unpaidOrder, $unpaidCustomer] = $loadTestOrder($unpaidOrderId, 'unpaid');
$unpaidState = new OrderState((int) $unpaidOrder->current_state, (int) $unpaidOrder->id_lang);
$cancelledStateId = (int) Configuration::get('PS_OS_CANCELED');
$cancelledState = $cancelledStateId > 0 ? new OrderState($cancelledStateId, (int) $unpaidOrder->id_lang) : false;
if (!Validate::isLoadedObject($unpaidState)
    || (bool) $unpaidState->paid
    || $unpaidOrder->hasBeenPaid()
    || (float) $unpaidOrder->total_paid_real !== 0.0
    || !($cancelledState instanceof OrderState)
    || !Validate::isLoadedObject($cancelledState)
    || (bool) $cancelledState->paid
    || (bool) $cancelledState->logable
) {
    throw new RuntimeException('The supplied cancellation order or native canceled state is not eligible for the unpaid cancellation check.');
}

$returnSupported = false;
$unsupportedReason = '';
$paidLikeOrder = null;
$paidLikeCustomer = null;
$paidLikeProducts = [];
$initialReturnStateId = 0;
if ($paidLikeOrderId < 1) {
    $unsupportedReason = 'no separate run-scoped paid-like order was supplied';
} elseif (!(bool) Configuration::get('PS_ORDER_RETURN', null, null, (int) $shop->id)) {
    $unsupportedReason = 'PrestaShop customer returns are disabled in this isolated shop';
} else {
    [$paidLikeOrder, $paidLikeCustomer, $paidLikeProducts] = $loadTestOrder($paidLikeOrderId, 'paid-like');
    $paidLikeState = new OrderState((int) $paidLikeOrder->current_state, (int) $paidLikeOrder->id_lang);
    if (!Validate::isLoadedObject($paidLikeState)
        || !(bool) $paidLikeState->paid
        || !(bool) $paidLikeState->shipped
        || (float) $paidLikeOrder->total_paid_tax_incl <= 0.0
        || !$paidLikeOrder->hasBeenPaid()
        || $paidLikeOrder->delivery_date === '0000-00-00 00:00:00'
        || !$paidLikeOrder->isReturnable()
    ) {
        $unsupportedReason = 'the supplied paid-like order is not currently eligible for native returns';
        $paidLikeOrder = null;
        $paidLikeCustomer = null;
    } else {
        $initialReturnStateId = 1;
        $initialReturnState = $initialReturnStateId > 0 ? new OrderReturnState($initialReturnStateId) : false;
        if (!($initialReturnState instanceof OrderReturnState)
            || !Validate::isLoadedObject($initialReturnState)
            || (bool) $initialReturnState->is_cancelling_return
        ) {
            $unsupportedReason = 'the native return-state catalog has no request-eligible state';
            $paidLikeOrder = null;
            $paidLikeCustomer = null;
        } else {
            $existingReturns = OrderReturn::getOrdersReturn((int) $paidLikeOrder->id_customer, (int) $paidLikeOrder->id, false);
            $existingSlips = OrderSlip::getOrdersSlip((int) $paidLikeOrder->id_customer, (int) $paidLikeOrder->id);
            if (is_array($existingReturns) && $existingReturns !== []) {
                throw new RuntimeException('The supplied paid-like order already has a native RMA record.');
            }
            if (is_array($existingSlips) && $existingSlips !== []) {
                throw new RuntimeException('The supplied paid-like order already has a credit slip.');
            }
            $returnSupported = true;
        }
    }
}

$stage = 'Back Office unpaid cancellation readback';
$database = Db::getInstance();
$cancelledOrder = new Order((int) $unpaidOrder->id);
$savedCancelledState = new OrderState((int) $cancelledOrder->current_state, (int) $cancelledOrder->id_lang);
$unpaidHistory = $database->executeS(
    'SELECT `id_order_state`, `id_employee` FROM `' . _DB_PREFIX_ . 'order_history`'
    . ' WHERE `id_order` = ' . (int) $cancelledOrder->id
    . ' ORDER BY `date_add` DESC, `id_order_history` DESC LIMIT 2'
);
if (!Validate::isLoadedObject($cancelledOrder)
    || !Validate::isLoadedObject($savedCancelledState)
    || (int) $cancelledOrder->current_state !== $cancelledStateId
    || !is_array($unpaidHistory)
    || count($unpaidHistory) < 2
    || (int) ($unpaidHistory[0]['id_order_state'] ?? 0) !== $cancelledStateId
    || (int) ($unpaidHistory[0]['id_employee'] ?? 0) < 1
    || (int) ($unpaidHistory[1]['id_order_state'] ?? 0) === $cancelledStateId
    || (bool) $savedCancelledState->paid
    || (float) $cancelledOrder->total_paid_real !== 0.0
    || $cancelledOrder->hasBeenPaid()
) {
    throw new RuntimeException('The Back Office did not persist a new canceled status history entry for the still-unpaid order.');
}

$report = [
    'status' => 'passed',
    'unpaid_cancellation' => 'passed',
    'return_request' => 'unsupported',
    'credit_slip' => 'unsupported',
    'cash_refund' => 'not_requested',
    'unpaid_order_id' => (int) $cancelledOrder->id,
    'paid_like_order_id' => $paidLikeOrderId > 0 ? $paidLikeOrderId : null,
];

if ($returnSupported && $paidLikeOrder instanceof Order && $paidLikeCustomer instanceof Customer) {
    $stage = 'native return request';
    $orderDetailId = (int) array_key_first($paidLikeProducts);
    if ($orderDetailId < 1) {
        throw new RuntimeException('The paid-like order has no native order-detail line for its return fixture.');
    }
    $orderDetail = new OrderDetail($orderDetailId);
    if (!Validate::isLoadedObject($orderDetail)
        || (int) $orderDetail->id_order !== (int) $paidLikeOrder->id
        || (int) $orderDetail->product_quantity < 1
    ) {
        throw new RuntimeException('The paid-like order product line is not valid for a native return request.');
    }
    $orderDetailList = [$orderDetailId => $orderDetailId];
    $productQuantityList = [$orderDetailId => 1];
    $returnProbe = new OrderReturn();
    $returnProbe->id_order = (int) $paidLikeOrder->id;
    if (!$returnProbe->checkEnoughProduct($orderDetailList, $productQuantityList)) {
        throw new RuntimeException('PrestaShop rejected the synthetic return quantity for the paid-like order.');
    }
    $orderReturn = new OrderReturn();
    $orderReturn->id_customer = (int) $paidLikeCustomer->id;
    $orderReturn->id_order = (int) $paidLikeOrder->id;
    $orderReturn->state = (string) $initialReturnStateId;
    $orderReturn->question = '[CI ONLY] Synthetic return request; no physical package or payment is involved.';
    if (!$orderReturn->add()) {
        throw new RuntimeException('PrestaShop could not persist the native synthetic return request.');
    }
    $orderReturn->addReturnDetail($orderDetailList, $productQuantityList);
    $savedReturnDetails = OrderReturn::getOrdersReturnDetail((int) $orderReturn->id);
    if (!is_array($savedReturnDetails)
        || count($savedReturnDetails) !== 1
        || (int) $savedReturnDetails[0]['id_order_detail'] !== $orderDetailId
        || (int) $savedReturnDetails[0]['product_quantity'] !== 1
        || (int) $savedReturnDetails[0]['cancelled'] !== 0
    ) {
        throw new RuntimeException('The native return request did not retain its synthetic product quantity.');
    }
    $report['return_request'] = 'passed';
    $report['return_id'] = (int) $orderReturn->id;

    $stage = 'native credit slip';
    $paidBeforeSlip = (float) $paidLikeOrder->total_paid_real;
    $productRows = array_values($paidLikeOrder->getProducts());
    if (count($productRows) !== 1) {
        throw new RuntimeException('The paid-like order must contain one product row for a focused credit-slip check.');
    }
    $slipProduct = $productRows[0];
    $slipProduct['quantity'] = 1;
    if (!OrderSlip::create($paidLikeOrder, [$slipProduct], false, 0, false, true)) {
        throw new RuntimeException('PrestaShop could not create the native synthetic credit slip.');
    }
    $savedSlips = OrderSlip::getOrdersSlip((int) $paidLikeCustomer->id, (int) $paidLikeOrder->id);
    $savedSlip = is_array($savedSlips) && isset($savedSlips[0]) ? $savedSlips[0] : null;
    $slipDetailRows = is_array($savedSlip) && (int) ($savedSlip['id_order_slip'] ?? 0) > 0
        ? OrderSlip::getOrdersSlipDetail((int) $savedSlip['id_order_slip'])
        : false;
    $savedOrderDetail = new OrderDetail($orderDetailId);
    $paidLikeAfterSlip = new Order((int) $paidLikeOrder->id);
    if (!is_array($savedSlips)
        || count($savedSlips) !== 1
        || !is_array($slipDetailRows)
        || count($slipDetailRows) !== 1
        || (int) ($slipDetailRows[0]['id_order_detail'] ?? 0) !== $orderDetailId
        || (int) ($slipDetailRows[0]['product_quantity'] ?? 0) !== 1
        || !Validate::isLoadedObject($savedOrderDetail)
        || (int) $savedOrderDetail->product_quantity_refunded !== 1
        || !Validate::isLoadedObject($paidLikeAfterSlip)
        || (float) $paidLikeAfterSlip->total_paid_real !== $paidBeforeSlip
    ) {
        throw new RuntimeException('The native credit slip was not recorded without changing payment totals.');
    }
    $report['credit_slip'] = 'passed';
    $report['credit_slip_id'] = (int) $savedSlip['id_order_slip'];
    $report['status'] = 'passed';
} else {
    $report['status'] = 'partial';
    $report['unsupported_reason'] = $unsupportedReason;
}

if (!$restoreReturnConfiguration()) {
    throw new RuntimeException('The run-scoped PS_ORDER_RETURN setting could not be restored after order lifecycle QA.');
}
$returnConfigRestored = true;
$report['return_config_restored'] = true;

echo json_encode($report, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
if ($report['status'] === 'partial') {
    fwrite(STDOUT, 'UNSUPPORTED: native RMA/credit-slip checks were not run: ' . $unsupportedReason . PHP_EOL);
}
fwrite(STDOUT, sprintf(
    "PASS: run-scoped unpaid order #%d was canceled through the native Back Office status form; cash refund was not requested.\n",
    (int) $cancelledOrder->id
));
if ($report['return_request'] === 'passed' && $report['credit_slip'] === 'passed') {
    fwrite(STDOUT, sprintf(
        "PASS: synthetic paid-like order #%d persisted a native RMA and credit slip; total_paid_real remained unchanged.\n",
        $paidLikeOrderId
    ));
}
