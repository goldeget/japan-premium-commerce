<?php

declare(strict_types=1);

use Kuranea\BusinessProfile\Domain\JpyAmount;
use Kuranea\BusinessProfile\Infrastructure\BankTransferInstructionRepository;
use Kuranea\BusinessProfile\Infrastructure\BankTransferReceiptRepository;
use Kuranea\BusinessProfile\Infrastructure\DatabaseSchema;

function ordenowaBankUnpaidRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$runId = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$project = (string) getenv('CI_COMPOSE_PROJECT_NAME');
$orderIdText = (string) getenv('KURANEA_CI_ORDER_ID');
$viewport = (string) getenv('KURANEA_CI_VIEWPORT');
$orderReference = (string) getenv('KURANEA_CI_ORDER_REFERENCE');
$productIdText = (string) getenv('KURANEA_CI_PRODUCT_ID');
$expectation = (string) getenv('KURANEA_CI_TRANSFER_EXPECTATION');
$expectedProject = sprintf('kuranea-ci-%s-%s', $runId, $attempt);
ordenowaBankUnpaidRequire(
    getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1'
        && preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $attempt) === 1
        && $project === $expectedProject
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject
        && preg_match('/\A[1-9][0-9]{0,9}\z/D', $orderIdText) === 1
        && preg_match('/\A[1-9][0-9]{0,9}\z/D', $productIdText) === 1
        && $viewport === 'bank'
        && preg_match('/\A[A-Z0-9]{8,16}\z/D', $orderReference) === 1
        && in_array($expectation, ['unissued', 'issued'], true),
    'Unpaid transfer readback requires its exact isolated run, checkout order, and expected state.'
);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';
require_once '/var/www/html/modules/kuraneabusinessprofile/autoload.php';

ordenowaBankUnpaidRequire(
    \Kuranea\BusinessProfile\Customer\CommerceGate::isIsolatedCiCheckoutEnabled(),
    'Unpaid transfer readback is outside the exact disposable commerce gate.'
);

$shopId = (int) Shop::getContextShopID();
$orderId = (int) $orderIdText;
$productId = (int) $productIdText;
$order = new Order($orderId);
$customer = Validate::isLoadedObject($order) ? new Customer((int) $order->id_customer) : false;
$currency = Validate::isLoadedObject($order) ? new Currency((int) $order->id_currency) : false;
$state = Validate::isLoadedObject($order) ? new OrderState((int) $order->current_state, (int) $order->id_lang) : false;
$expectedEmail = sprintf(
    'qa-ordenowa-checkout-%s-%s-%s@example.invalid',
    $runId,
    $attempt,
    $viewport
);
$amount = Validate::isLoadedObject($order)
    ? JpyAmount::normalizePositive((string) $order->total_paid_tax_incl)
    : null;
ordenowaBankUnpaidRequire(
    Shop::getTotalShops() === 1
        && $shopId > 0
        && Validate::isLoadedObject($order)
        && (int) $order->id_shop === $shopId
        && (string) $order->reference === $orderReference
        && Validate::isLoadedObject($customer)
        && strtolower((string) $customer->email) === strtolower($expectedEmail)
        && !(bool) $customer->is_guest
        && (string) $order->module === 'ps_checkpayment'
        && Validate::isLoadedObject($currency)
        && strtoupper((string) $currency->iso_code) === 'JPY'
        && Validate::isLoadedObject($state)
        && !(bool) $state->paid
        && (float) $order->total_paid_real === 0.0
        && $amount !== null,
    'Checkout order identity, ownership, unpaid state, offline method, or positive integer JPY total is invalid.'
);

$prefix = _DB_PREFIX_;
$database = Db::getInstance();
$productLines = $database->executeS(
    'SELECT `product_id`, `product_name`, `product_quantity`, `total_price_tax_incl` FROM `' . $prefix . 'order_detail`'
    . ' WHERE `id_order` = ' . (int) $orderId . ' ORDER BY `id_order_detail`'
);
ordenowaBankUnpaidRequire(
    is_array($productLines)
        && count($productLines) === 1
        && (int) $productLines[0]['product_id'] === $productId
        && (int) $productLines[0]['product_quantity'] === 1
        && is_string($productLines[0]['product_name'] ?? null)
        && str_contains((string) $productLines[0]['product_name'], '[CI ONLY]')
        && JpyAmount::normalizePositive((string) $productLines[0]['total_price_tax_incl']) !== null,
    'The same isolated bank order must contain exactly its one run-scoped CI-only product line.'
);
ordenowaBankUnpaidRequire(
    $database->execute(DatabaseSchema::createBankTransferInstructionTableSql($prefix))
        && $database->execute(DatabaseSchema::createBankTransferReceiptLedgerTableSql($prefix)),
    'The isolated bank-transfer tables could not be ensured for native readback.'
);
$instruction = (new BankTransferInstructionRepository())->findForOrder($shopId, $orderId);
$receipt = (new BankTransferReceiptRepository())->findForOrder($shopId, $orderId);
$expectedInstructionCount = $expectation === 'issued' ? 1 : 0;
$expectedReceiptCount = 0;
$paymentCount = (int) $database->getValue(
    'SELECT COUNT(*) FROM `' . $prefix . 'order_payment`'
    . ' WHERE `order_reference` = "' . pSQL((string) $order->reference) . '"'
);
ordenowaBankUnpaidRequire(
    ($instruction === null ? 0 : 1) === $expectedInstructionCount
        && $receipt === null
        && $paymentCount === 0
        && ($instruction === null
            || ($instruction->shopId === $shopId
                && $instruction->orderId === $orderId
                && $instruction->orderReference === (string) $order->reference
                && JpyAmount::normalizePositive($instruction->totalPaid) === $amount
                && $instruction->currencyIso === 'JPY'
                && $instruction->profileVersionId > 0
                && preg_match('/\A[a-f0-9]{32}\z/iD', $instruction->accountId) === 1
                && $instruction->issuedByEmployeeId > 0)),
    'Instruction/receipt/payment state did not match the expected unpaid checkout stage.'
);

echo json_encode([
    'status' => 'success',
    'order_id' => $orderId,
    'product_id' => $productId,
    'product_name' => (string) $productLines[0]['product_name'],
    'product_quantity' => (int) $productLines[0]['product_quantity'],
    'product_total' => JpyAmount::normalizePositive((string) $productLines[0]['total_price_tax_incl']),
    'reference_match' => true,
    'owner_matches' => true,
    'amount' => $amount,
    'unpaid' => true,
    'currency_jpy' => true,
    'offline_method' => true,
    'instruction_count' => $expectedInstructionCount,
    'receipt_count' => $expectedReceiptCount,
    'payment_count' => 0,
], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . PHP_EOL;
