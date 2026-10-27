<?php

declare(strict_types=1);

function ordenowaBankReadbackRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$runId = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$project = (string) getenv('CI_COMPOSE_PROJECT_NAME');
$orderIdText = (string) getenv('KURANEA_CI_ORDER_ID');
$expectedProject = sprintf('kuranea-ci-%s-%s', $runId, $attempt);
ordenowaBankReadbackRequire(
    getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1'
        && preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $attempt) === 1
        && $project === $expectedProject
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject
        && preg_match('/\A[1-9][0-9]{0,9}\z/D', $orderIdText) === 1,
    'Synthetic transfer readback requires its exact disposable Actions project and order.'
);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';

$shopId = (int) Shop::getContextShopID();
$orderId = (int) $orderIdText;
$order = new Order($orderId);
$currency = new Currency((int) $order->id_currency);
$paymentStateId = (int) Configuration::get('PS_OS_PAYMENT');
$state = new OrderState((int) $order->current_state, (int) $order->id_lang);
$prefix = _DB_PREFIX_;

ordenowaBankReadbackRequire(
    Validate::isLoadedObject($order)
        && (int) $order->id_shop === $shopId
        && Validate::isLoadedObject($currency)
        && strtoupper((string) $currency->iso_code) === 'JPY'
        && Validate::isLoadedObject($state)
        && (bool) $state->paid
        && (int) $order->current_state === $paymentStateId
        && preg_match('/\A[0-9]+(?:\.0{1,6})?\z/D', (string) $order->total_paid_real) === 1
        && (float) $order->total_paid_real > 0
        && (float) $order->total_paid_real === (float) $order->total_paid_tax_incl,
    'Native order did not persist its paid state and exact full JPY total.'
);

$database = Db::getInstance();
$instructionRows = $database->executeS(
    'SELECT `id_order`, `id_shop`, `order_reference`, `total_paid`, `currency_iso`, `profile_version_id`, `bank_account_id`'
    . ' FROM `' . $prefix . 'kuraneabusinessprofile_bank_transfer_instruction`'
    . ' WHERE `id_order` = ' . (int) $orderId . ' AND `id_shop` = ' . (int) $shopId . ' LIMIT 2'
);
$receiptRows = $database->executeS(
    'SELECT `id_shop`, `id_order`, `order_reference`, `received_amount`, `currency_iso`, `bank_account_id`'
    . ', `receipt_reference_sha256`, `confirmed_by_employee_id`, `id_order_payment`, `id_order_history`, `is_synthetic`'
    . ' FROM `' . $prefix . 'kuraneabusinessprofile_bank_transfer_receipt`'
    . ' WHERE `id_order` = ' . (int) $orderId . ' AND `id_shop` = ' . (int) $shopId . ' LIMIT 2'
);
ordenowaBankReadbackRequire(
    is_array($instructionRows)
        && count($instructionRows) === 1
        && is_array($receiptRows)
        && count($receiptRows) === 1,
    'Exactly one same-order instruction and receipt ledger record must persist.'
);
$instruction = $instructionRows[0];
$receipt = $receiptRows[0];
ordenowaBankReadbackRequire(
    (int) $instruction['id_order'] === $orderId
        && (int) $instruction['id_shop'] === $shopId
        && (string) $instruction['order_reference'] === (string) $order->reference
        && (string) $instruction['total_paid'] === (string) $order->total_paid_tax_incl
        && (string) $instruction['currency_iso'] === 'JPY'
        && (int) $instruction['profile_version_id'] > 0
        && preg_match('/\A[a-f0-9]{32}\z/iD', (string) $instruction['bank_account_id']) === 1,
    'The immutable transfer instruction does not match the native order and profile snapshot.'
);
ordenowaBankReadbackRequire(
    (int) $receipt['id_order'] === $orderId
        && (int) $receipt['id_shop'] === $shopId
        && (string) $receipt['order_reference'] === (string) $order->reference
        && (string) $receipt['received_amount'] === (string) $order->total_paid_tax_incl
        && (string) $receipt['currency_iso'] === 'JPY'
        && (string) $receipt['bank_account_id'] === (string) $instruction['bank_account_id']
        && preg_match('/\A[a-f0-9]{64}\z/D', (string) $receipt['receipt_reference_sha256']) === 1
        && (int) $receipt['confirmed_by_employee_id'] > 0
        && (int) $receipt['id_order_payment'] > 0
        && (int) $receipt['id_order_history'] > 0
        && (int) $receipt['is_synthetic'] === 1,
    'The synthetic receipt ledger does not match the order, account, actor, or native rows.'
);

$payments = $database->executeS(
    'SELECT `id_order_payment`, `id_currency`, `amount`, `id_employee`, `transaction_id`, `payment_method`'
    . ' FROM `' . $prefix . 'order_payment`'
    . ' WHERE `order_reference` = "' . pSQL((string) $order->reference) . '" LIMIT 2'
);
ordenowaBankReadbackRequire(
    is_array($payments)
        && count($payments) === 1
        && (int) $payments[0]['id_order_payment'] === (int) $receipt['id_order_payment']
        && (int) $payments[0]['id_currency'] === (int) $order->id_currency
        && (float) $payments[0]['amount'] === (float) $order->total_paid_tax_incl
        && (int) $payments[0]['id_employee'] === (int) $receipt['confirmed_by_employee_id']
        && preg_match('/\AORDENOWA-BT-[0-9a-f]{32}\z/D', (string) $payments[0]['transaction_id']) === 1
        && (string) $payments[0]['payment_method'] === 'ORDENOWA bank transfer (staff confirmed)',
    'Exactly one native order payment with the synthetic staff-confirmation marker must persist.'
);

$history = $database->getRow(
    'SELECT `id_order_history`, `id_order_state`, `id_employee` FROM `' . $prefix . 'order_history`'
    . ' WHERE `id_order_history` = ' . (int) $receipt['id_order_history']
    . ' AND `id_order` = ' . (int) $orderId
);
$paidHistoryRows = $database->executeS(
    'SELECT `id_order_history`, `id_employee` FROM `' . $prefix . 'order_history`'
    . ' WHERE `id_order` = ' . (int) $orderId
    . ' AND `id_order_state` = ' . (int) $paymentStateId . ' LIMIT 2'
);
ordenowaBankReadbackRequire(
    is_array($history)
        && (int) $history['id_order_state'] === $paymentStateId
        && (int) $history['id_employee'] === (int) $receipt['confirmed_by_employee_id']
        && is_array($paidHistoryRows)
        && count($paidHistoryRows) === 1
        && (int) $paidHistoryRows[0]['id_order_history'] === (int) $receipt['id_order_history']
        && (int) $paidHistoryRows[0]['id_employee'] === (int) $receipt['confirmed_by_employee_id'],
    'The native payment-state history row is missing or has a different employee.'
);

echo json_encode([
    'status' => 'success',
    'order_id' => $orderId,
    'order_reference_match' => true,
    'instruction_count' => 1,
    'receipt_count' => 1,
    'payment_count' => 1,
    'paid_history_count' => 1,
    'history_match' => true,
    'paid' => true,
    'currency_jpy' => true,
    'synthetic' => true,
], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . PHP_EOL;
