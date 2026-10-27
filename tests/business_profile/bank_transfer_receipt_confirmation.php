<?php

declare(strict_types=1);

require_once __DIR__ . '/../../modules/kuraneabusinessprofile/autoload.php';

use Kuranea\BusinessProfile\Domain\BankTransferInstruction;
use Kuranea\BusinessProfile\Domain\BankTransferInstructionRepositoryInterface;
use Kuranea\BusinessProfile\Domain\BankTransferReceipt;
use Kuranea\BusinessProfile\Domain\BankTransferReceiptRepositoryInterface;
use Kuranea\BusinessProfile\Domain\JpyAmount;
use Kuranea\BusinessProfile\Infrastructure\BankTransferReceiptConfirmer;
use Kuranea\BusinessProfile\Admin\AdminAccessPolicy;

if (!function_exists('pSQL')) {
    function pSQL(string $value, bool $htmlOK = false): string
    {
        return addslashes($value);
    }
}

function assertReceiptSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertReceiptTrue(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

function assertReceiptThrows(callable $callback, string $message): void
{
    try {
        $callback();
    } catch (RuntimeException | InvalidArgumentException) {
        return;
    }

    throw new RuntimeException($message);
}

if (defined('_PS_VERSION_')) {
    throw new RuntimeException('Synthetic receipt contract must run outside a bootstrapped production PrestaShop process.');
}

if (!defined('_DB_PREFIX_')) {
    define('_DB_PREFIX_', 'ps_');
}

final class FakeTransferReceiptDb
{
    /** @var array<int, array<string, mixed>> */
    public array $orders = [];
    /** @var list<array<string, mixed>> */
    public array $payments = [];
    /** @var list<array<string, mixed>> */
    public array $histories = [];
    public bool $failPayment = false;
    public bool $failHistory = false;
    /** @var array<string, mixed>|null */
    private ?array $snapshot = null;
    private int $nextPaymentId = 1;
    private int $nextHistoryId = 1;

    public function execute(string $sql): bool
    {
        if ($sql === 'START TRANSACTION') {
            $this->snapshot = [
                'orders' => $this->orders,
                'payments' => $this->payments,
                'histories' => $this->histories,
                'nextPaymentId' => $this->nextPaymentId,
                'nextHistoryId' => $this->nextHistoryId,
            ];
            return true;
        }
        if ($sql === 'COMMIT') {
            $this->snapshot = null;
            return true;
        }
        if ($sql === 'ROLLBACK') {
            if ($this->snapshot !== null) {
                $this->orders = $this->snapshot['orders'];
                $this->payments = $this->snapshot['payments'];
                $this->histories = $this->snapshot['histories'];
                $this->nextPaymentId = $this->snapshot['nextPaymentId'];
                $this->nextHistoryId = $this->snapshot['nextHistoryId'];
                $this->snapshot = null;
            }
            return true;
        }

        return true;
    }

    public function getValue(string $sql, bool $useCache = true): mixed
    {
        if (str_contains($sql, 'SELECT `id_order` FROM `ps_orders`')) {
            preg_match('/`id_order` = ([0-9]+)/', $sql, $orderMatch);
            preg_match('/`id_shop` = ([0-9]+)/', $sql, $shopMatch);
            $orderId = (int) ($orderMatch[1] ?? 0);
            return isset($this->orders[$orderId]) && (int) $this->orders[$orderId]['id_shop'] === (int) ($shopMatch[1] ?? 0)
                ? $orderId
                : 0;
        }
        if (str_contains($sql, 'SELECT COUNT(*) FROM `ps_order_payment`')) {
            preg_match('/o\.`id_order` = ([0-9]+)/', $sql, $orderMatch);
            preg_match("/op\.`transaction_id` = '([^']+)'/", $sql, $transactionMatch);
            $orderId = (int) ($orderMatch[1] ?? 0);
            $transactionId = $transactionMatch[1] ?? null;
            return count(array_filter($this->payments, static function (array $payment) use ($orderId, $transactionId): bool {
                return (int) $payment['id_order'] === $orderId
                    && ($transactionId === null || (string) $payment['transaction_id'] === $transactionId);
            }));
        }

        return 0;
    }

    /** @return list<array<string, mixed>> */
    public function executeS(string $sql, bool $array = true, bool $useCache = true): array
    {
        if (str_contains($sql, 'SELECT `id_order` FROM `ps_orders`')) {
            preg_match('/`id_order` = ([0-9]+)/', $sql, $orderMatch);
            preg_match('/`id_shop` = ([0-9]+)/', $sql, $shopMatch);
            $orderId = (int) ($orderMatch[1] ?? 0);
            return isset($this->orders[$orderId]) && (int) $this->orders[$orderId]['id_shop'] === (int) ($shopMatch[1] ?? 0)
                ? [['id_order' => $orderId]]
                : [];
        }
        if (str_contains($sql, 'FROM `ps_order_payment`')) {
            preg_match('/o\.`id_order` = ([0-9]+)/', $sql, $orderMatch);
            preg_match('/op\.`id_order_payment` = ([0-9]+)/', $sql, $paymentIdMatch);
            preg_match("/op\.`transaction_id` = '([^']+)'/", $sql, $transactionMatch);
            $orderId = (int) ($orderMatch[1] ?? 0);
            $paymentId = isset($paymentIdMatch[1]) ? (int) $paymentIdMatch[1] : null;
            $transactionId = $transactionMatch[1] ?? null;
            return array_values(array_filter($this->payments, static function (array $payment) use ($orderId, $paymentId, $transactionId): bool {
                return (int) $payment['id_order'] === $orderId
                    && ($paymentId === null || (int) $payment['id_order_payment'] === $paymentId)
                    && ($transactionId === null || (string) $payment['transaction_id'] === $transactionId);
            }));
        }
        if (str_contains($sql, 'FROM `ps_order_history`')) {
            preg_match('/`id_order` = ([0-9]+)/', $sql, $orderMatch);
            preg_match('/`id_order_history` = ([0-9]+)/', $sql, $historyMatch);
            $orderId = (int) ($orderMatch[1] ?? 0);
            $historyId = (int) ($historyMatch[1] ?? 0);
            return array_values(array_filter($this->histories, static fn (array $history): bool =>
                (int) $history['id_order'] === $orderId && (int) $history['id_order_history'] === $historyId
            ));
        }
        if (str_contains($sql, 'FROM `ps_orders` o')) {
            preg_match('/o\.`id_order` = ([0-9]+)/', $sql, $orderMatch);
            preg_match('/o\.`id_shop` = ([0-9]+)/', $sql, $shopMatch);
            $orderId = (int) ($orderMatch[1] ?? 0);
            $row = $this->orders[$orderId] ?? null;
            if (!is_array($row) || (int) $row['id_shop'] !== (int) ($shopMatch[1] ?? 0)) {
                return [];
            }
            return [[
                'id_shop' => $row['id_shop'],
                'reference' => $row['reference'],
                'total_paid_tax_incl' => $row['total_paid_tax_incl'],
                'total_paid_real' => $row['total_paid_real'],
                'current_state' => $row['current_state'],
                'currency_iso' => $row['currency_iso'],
                'state_paid' => (int) $row['current_state'] === 1 ? 1 : 0,
            ]];
        }

        return [];
    }

    public function nextPaymentId(): int
    {
        return $this->nextPaymentId++;
    }

    public function nextHistoryId(): int
    {
        return $this->nextHistoryId++;
    }
}

final class Db
{
    public static function getInstance(): FakeTransferReceiptDb
    {
        return $GLOBALS['ordenowa_fake_receipt_db'];
    }
}

final class Currency
{
    public int $id;
    public string $iso_code;
    public float $conversion_rate = 1.0;

    public function __construct(int $id)
    {
        $this->id = $id;
        $this->iso_code = $id === 1 ? 'JPY' : 'USD';
    }
}

final class OrderState
{
    public int $id;
    public bool $paid;

    public function __construct(int $id, int $languageId = 1)
    {
        $this->id = $id;
        $this->paid = $id === 1;
    }
}

final class Order
{
    public int $id;
    public int $id_shop;
    public int $id_customer;
    public int $id_currency;
    public int $id_lang;
    public string $reference;
    public string $total_paid_tax_incl;
    public string $total_paid_real;
    public string $module;
    public int $current_state;
    public string $payment = 'Bank transfer';
    public bool $valid = false;

    public function __construct(int $id)
    {
        $row = Db::getInstance()->orders[$id] ?? [];
        $this->id = $id;
        $this->id_shop = (int) ($row['id_shop'] ?? 0);
        $this->id_customer = (int) ($row['id_customer'] ?? 0);
        $this->id_currency = (int) ($row['id_currency'] ?? 0);
        $this->id_lang = 1;
        $this->reference = (string) ($row['reference'] ?? '');
        $this->total_paid_tax_incl = (string) ($row['total_paid_tax_incl'] ?? '0');
        $this->total_paid_real = (string) ($row['total_paid_real'] ?? '0');
        $this->module = (string) ($row['module'] ?? '');
        $this->current_state = (int) ($row['current_state'] ?? 0);
    }

    public function getInvoicesCollection(): array
    {
        return [];
    }

    public function addOrderPayment(
        $amountPaid,
        $paymentMethod = null,
        $transactionId = null,
        $currency = null,
        $date = null,
        $orderInvoice = null,
        ?int $employeeId = null
    ): bool {
        $database = Db::getInstance();
        if ($database->failPayment) {
            return false;
        }
        $payment = [
            'id_order_payment' => $database->nextPaymentId(),
            'id_order' => $this->id,
            'order_reference' => $this->reference,
            'id_currency' => $currency->id,
            'amount' => number_format((float) $amountPaid, 6, '.', ''),
            'id_employee' => $employeeId,
            'transaction_id' => (string) $transactionId,
        ];
        $database->payments[] = $payment;
        $this->total_paid_real = $payment['amount'];
        $database->orders[$this->id]['total_paid_real'] = $this->total_paid_real;

        return true;
    }
}

final class OrderHistory
{
    public int $id = 0;
    public int $id_order = 0;
    public int $id_employee = 0;
    public int $id_order_state = 0;
    private ?Order $order = null;

    public function changeIdOrderState(int $newOrderState, $idOrder, bool $useExistingPayment = false): void
    {
        $this->id_order_state = $newOrderState;
        $this->order = $idOrder instanceof Order ? $idOrder : new Order((int) $idOrder);
        $this->order->current_state = $newOrderState;
        $this->order->valid = true;
    }

    public function add(): bool
    {
        $database = Db::getInstance();
        if ($database->failHistory || $this->order === null) {
            return false;
        }
        $this->id = $database->nextHistoryId();
        $database->histories[] = [
            'id_order_history' => $this->id,
            'id_order' => $this->id_order,
            'id_order_state' => $this->id_order_state,
            'id_employee' => $this->id_employee,
        ];
        $database->orders[$this->id_order]['current_state'] = $this->id_order_state;
        $database->orders[$this->id_order]['total_paid_real'] = $this->order->total_paid_real;

        return true;
    }
}

final class Configuration
{
    public static function get(string $key): int
    {
        return match ($key) {
            'PS_OS_PAYMENT' => 1,
            'PS_OS_CANCELED' => 3,
            default => 0,
        };
    }
}

final class Validate
{
    public static function isLoadedObject(mixed $object): bool
    {
        return is_object($object) && (int) ($object->id ?? 0) > 0;
    }
}

final class InMemoryReceiptInstructionRepository implements BankTransferInstructionRepositoryInterface
{
    /** @var array<string, BankTransferInstruction> */
    public array $instructions = [];

    public function findForOrder(int $shopId, int $orderId): ?BankTransferInstruction
    {
        return $this->instructions[$shopId . ':' . $orderId] ?? null;
    }

    public function insertIfAbsent(BankTransferInstruction $instruction): bool
    {
        $key = $instruction->shopId . ':' . $instruction->orderId;
        if (isset($this->instructions[$key])) {
            return false;
        }

        $this->instructions[$key] = $instruction;
        return true;
    }
}

final class InMemoryReceiptLedger implements BankTransferReceiptRepositoryInterface
{
    /** @var array<string, BankTransferReceipt> */
    public array $byOrder = [];
    /** @var array<string, int> */
    public array $byReference = [];
    public bool $failInsert = false;
    public ?BankTransferReceipt $raceReceipt = null;

    public function findForOrder(int $shopId, int $orderId): ?BankTransferReceipt
    {
        return $this->byOrder[$shopId . ':' . $orderId] ?? null;
    }

    public function findByStatementReference(int $shopId, string $accountId, string $referenceDigest): ?BankTransferReceipt
    {
        $orderId = $this->byReference[$shopId . ':' . $accountId . ':' . $referenceDigest] ?? 0;
        return $orderId > 0 ? $this->findForOrder($shopId, $orderId) : null;
    }

    public function insertIfAbsent(BankTransferReceipt $receipt): bool
    {
        if ($this->raceReceipt !== null) {
            $racingReceipt = $this->raceReceipt;
            $this->raceReceipt = null;
            $orderKey = $racingReceipt->shopId . ':' . $racingReceipt->orderId;
            $referenceKey = $racingReceipt->shopId . ':' . $racingReceipt->accountId . ':' . $racingReceipt->referenceDigest;
            $this->byOrder[$orderKey] = $racingReceipt;
            $this->byReference[$referenceKey] = $racingReceipt->orderId;
            return false;
        }
        if ($this->failInsert) {
            return false;
        }
        $orderKey = $receipt->shopId . ':' . $receipt->orderId;
        $referenceKey = $receipt->shopId . ':' . $receipt->accountId . ':' . $receipt->referenceDigest;
        if (isset($this->byOrder[$orderKey]) || isset($this->byReference[$referenceKey])) {
            return false;
        }
        $this->byOrder[$orderKey] = $receipt;
        $this->byReference[$referenceKey] = $receipt->orderId;

        return true;
    }
}

function setReceiptIsolatedCi(bool $enabled): void
{
    foreach ([
        'CI' => $enabled ? 'true' : '',
        'GITHUB_ACTIONS' => $enabled ? 'true' : '',
        'KURANEA_ISOLATED_CI' => $enabled ? '1' : '',
        'GITHUB_RUN_ID' => $enabled ? '987654321' : '',
        'GITHUB_RUN_ATTEMPT' => $enabled ? '1' : '',
        'KURANEA_CI_PROJECT_NAME' => $enabled ? 'kuranea-ci-987654321-1' : '',
    ] as $key => $value) {
        putenv($key . '=' . $value);
    }
}

function makeReceiptFixtureOrder(int $orderId, int $shopId = 4, int $currencyId = 1): array
{
    return [
        'id_order' => $orderId,
        'id_shop' => $shopId,
        'id_customer' => 100 + $orderId,
        'id_currency' => $currencyId,
        'currency_iso' => $currencyId === 1 ? 'JPY' : 'USD',
        'module' => 'ps_checkpayment',
        'reference' => 'CIREF' . $orderId,
        'total_paid_tax_incl' => '1100.000000',
        'total_paid_real' => '0.000000',
        'current_state' => 2,
    ];
}

$database = new FakeTransferReceiptDb();
$GLOBALS['ordenowa_fake_receipt_db'] = $database;
$instructions = new InMemoryReceiptInstructionRepository();
$receipts = new InMemoryReceiptLedger();
$accountId = 'a1b2c3d4e5f678901234567890abcdef';
$order = makeReceiptFixtureOrder(81);
$database->orders[81] = $order;
$instructions->instructions['4:81'] = new BankTransferInstruction(
    4, 81, 'CIREF81', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
$confirmer = new BankTransferReceiptConfirmer($instructions, $receipts, $database);
$statementReference = 'ORDENOWA-CI-RECEIPT-987654321-81';
$confirmedAt = '2026-10-26 11:00:00';

setReceiptIsolatedCi(false);
assertReceiptSame(true, AdminAccessPolicy::canConfirmBankTransferReceipt(['view' => 1, 'edit' => 1]), 'The receipt confirmer must accept the dedicated view+edit permission.');
assertReceiptSame(false, AdminAccessPolicy::canConfirmBankTransferReceipt(['view' => 1, 'edit' => 0]), 'A view-only employee must not confirm receipts.');
assertReceiptSame(false, AdminAccessPolicy::canConfirmBankTransferReceipt(['view' => 0, 'edit' => 1]), 'An employee without view access must not confirm receipts.');
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 81, '1100', $statementReference, true, 9, $confirmedAt, true),
    'A synthetic CI statement reference must be rejected outside the exact isolated CI gate.'
);
assertReceiptSame([], $database->payments, 'A synthetic reference outside CI must not create a native payment.');
assertReceiptSame([], $database->histories, 'A synthetic reference outside CI must not change order history.');
assertReceiptSame([], $receipts->byOrder, 'A synthetic reference outside CI must not create a receipt row.');

$noGateOrder = makeReceiptFixtureOrder(80);
$database->orders[80] = $noGateOrder;
$instructions->instructions['4:80'] = new BankTransferInstruction(
    4, 80, 'CIREF80', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 80, '1100', 'BANK-STATEMENT-80', true, 9, $confirmedAt, false),
    'A real receipt must not be created when the live seller gate is closed.'
);
assertReceiptSame([], array_values(array_filter($database->payments, static fn (array $payment): bool => (int) $payment['id_order'] === 80)), 'A closed seller gate must leave the order unpaid.');

setReceiptIsolatedCi(true);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 81, '1100', $statementReference, false, 9, $confirmedAt, true),
    'Without a positive staff attestation, no receipt may be recorded.'
);
assertReceiptSame([], $database->payments, 'Missing attestation must leave native payment records untouched.');

assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 81, '1099', $statementReference, true, 9, $confirmedAt, true),
    'A partial payment must not be confirmed.'
);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 81, '1101', $statementReference, true, 9, $confirmedAt, true),
    'An overpayment must not be confirmed.'
);
assertReceiptSame([], $database->payments, 'Mismatched amounts must not create native payment records.');

$success = $confirmer->confirm(4, 81, '1100.000000', $statementReference, true, 9, $confirmedAt, true);
assertReceiptSame(true, $success->created, 'The first exact, attested synthetic transfer should be recorded.');
assertReceiptSame(1, count($database->payments), 'Confirmation should create exactly one native OrderPayment record.');
assertReceiptSame(1, count($database->histories), 'Confirmation should create exactly one native OrderHistory record.');
assertReceiptSame(1, (int) $database->orders[81]['current_state'], 'The native order should move to the payment state.');
assertReceiptSame('1100.000000', $database->orders[81]['total_paid_real'], 'The native total paid must equal the exact order total.');
assertReceiptSame(hash('sha256', $statementReference), $success->receipt->referenceDigest, 'Only the digest of the bank statement reference is persisted.');
assertReceiptSame(true, $success->receipt->synthetic, 'The isolated fixture must be labeled synthetic.');
assertReceiptTrue(!property_exists($success->receipt, 'bankStatementReference'), 'The receipt entity must not retain the raw bank statement reference.');

$repeat = $confirmer->confirm(4, 81, '1100', $statementReference, true, 10, '2026-10-26 12:00:00', true);
assertReceiptSame(false, $repeat->created, 'An identical retry should return the original receipt record.');
assertReceiptSame(1, count($database->payments), 'An identical retry must not create another OrderPayment.');
assertReceiptSame(1, count($database->histories), 'An identical retry must not create another order history entry.');
assertReceiptSame(9, $repeat->receipt->confirmedByEmployeeId, 'An identical retry must preserve the original actor.');

assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 81, '1100', 'ORDENOWA-CI-RECEIPT-DIFFERENT', true, 10, $confirmedAt, true),
    'A conflicting reference retry must fail closed.'
);
assertReceiptSame(1, count($database->payments), 'A conflicting retry must not create another payment.');
assertReceiptSame(1, count($database->histories), 'A conflicting retry must not create another order history entry.');

$secondOrder = makeReceiptFixtureOrder(82);
$database->orders[82] = $secondOrder;
$instructions->instructions['4:82'] = new BankTransferInstruction(
    4, 82, 'CIREF82', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 82, '1100', $statementReference, true, 9, $confirmedAt, true),
    'The same bank statement reference must never confirm a second order on the same account.'
);
assertReceiptSame([], array_values(array_filter($database->payments, static fn (array $payment): bool => (int) $payment['id_order'] === 82)), 'Cross-order reference replay must not create a second native payment.');
assertReceiptSame(2, $database->orders[82]['current_state'], 'Cross-order reference replay must leave the second order unpaid.');

$rollbackOrder = makeReceiptFixtureOrder(83);
$database->orders[83] = $rollbackOrder;
$instructions->instructions['4:83'] = new BankTransferInstruction(
    4, 83, 'CIREF83', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
$database->failHistory = true;
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 83, '1100', 'ORDENOWA-CI-RECEIPT-987654321-83', true, 9, $confirmedAt, true),
    'A failed native history write must roll back payment and order changes.'
);
$database->failHistory = false;
assertReceiptSame([], array_values(array_filter($database->payments, static fn (array $payment): bool => (int) $payment['id_order'] === 83)), 'History failure must roll back the native payment.');
assertReceiptSame(2, $database->orders[83]['current_state'], 'History failure must preserve the unpaid order status.');

$ledgerFailureOrder = makeReceiptFixtureOrder(84);
$database->orders[84] = $ledgerFailureOrder;
$instructions->instructions['4:84'] = new BankTransferInstruction(
    4, 84, 'CIREF84', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
$receipts->failInsert = true;
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 84, '1100', 'ORDENOWA-CI-RECEIPT-987654321-84', true, 9, $confirmedAt, true),
    'A receipt-ledger write failure must roll back native payment and status writes.'
);
$receipts->failInsert = false;
assertReceiptSame([], array_values(array_filter($database->payments, static fn (array $payment): bool => (int) $payment['id_order'] === 84)), 'Ledger failure must roll back the native payment.');
assertReceiptSame(2, $database->orders[84]['current_state'], 'Ledger failure must preserve the unpaid order status.');

$database->failPayment = true;
$paymentFailureOrder = makeReceiptFixtureOrder(85);
$database->orders[85] = $paymentFailureOrder;
$instructions->instructions['4:85'] = new BankTransferInstruction(
    4, 85, 'CIREF85', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 85, '1100', 'ORDENOWA-CI-RECEIPT-987654321-85', true, 9, $confirmedAt, true),
    'A failed native payment write must leave the order unpaid.'
);
$database->failPayment = false;
assertReceiptSame(2, $database->orders[85]['current_state'], 'Native payment failure must preserve the order state.');
assertReceiptSame([], array_values(array_filter($database->payments, static fn (array $payment): bool => (int) $payment['id_order'] === 85)), 'Native payment failure must not create a payment row.');

$partialPaidOrder = makeReceiptFixtureOrder(89);
$partialPaidOrder['total_paid_real'] = '0.500000';
$database->orders[89] = $partialPaidOrder;
$instructions->instructions['4:89'] = new BankTransferInstruction(
    4, 89, 'CIREF89PARTIAL', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 89, '1100', 'ORDENOWA-CI-RECEIPT-PARTIAL-89', true, 9, $confirmedAt, true),
    'A native order with any positive partial paid amount must not be confirmed as a full transfer.'
);
assertReceiptSame(2, $database->orders[89]['current_state'], 'A partial native paid amount must leave the unpaid order status unchanged.');

$existingPaymentOrder = makeReceiptFixtureOrder(90);
$database->orders[90] = $existingPaymentOrder;
$instructions->instructions['4:90'] = new BankTransferInstruction(
    4, 90, 'CIREF90EXISTING', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
$database->payments[] = [
    'id_order_payment' => 900,
    'id_order' => 90,
    'order_reference' => 'CIREF90EXISTING',
    'id_currency' => 1,
    'amount' => '1.000000',
    'id_employee' => 9,
    'transaction_id' => 'pre-existing',
];
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 90, '1100', 'ORDENOWA-CI-RECEIPT-EXISTING-90', true, 9, $confirmedAt, true),
    'An unpaid order with a pre-existing payment row must not be confirmed again.'
);
assertReceiptSame(2, $database->orders[90]['current_state'], 'A pre-existing payment row must not change the order state.');

$racingOrder = makeReceiptFixtureOrder(88);
$database->orders[88] = $racingOrder;
$instructions->instructions['4:88'] = new BankTransferInstruction(
    4, 88, 'CIREF88', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
$racingReference = 'ORDENOWA-CI-RECEIPT-RACE-88';
$receipts->raceReceipt = new BankTransferReceipt(
    4, 89, 'CIREF89', $accountId, '1100', 'JPY', hash('sha256', $racingReference),
    9, $confirmedAt, 989, 989, true
);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 88, '1100', $racingReference, true, 9, $confirmedAt, true),
    'A concurrent receipt with the same account-scoped digest must not confirm a second order.'
);
assertReceiptSame([], array_values(array_filter($database->payments, static fn (array $payment): bool => (int) $payment['id_order'] === 88)), 'A concurrent digest collision must roll back the second native payment.');
assertReceiptSame(2, $database->orders[88]['current_state'], 'A concurrent digest collision must preserve the second unpaid order.');

$wrongShopOrder = makeReceiptFixtureOrder(86, 5);
$database->orders[86] = $wrongShopOrder;
$instructions->instructions['4:86'] = new BankTransferInstruction(
    5, 86, 'CIREF86', '1100.000000', 'JPY', 22, $accountId, 9, '2026-10-26 10:00:00'
);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 86, '1100', 'ORDENOWA-CI-RECEIPT-987654321-86', true, 9, $confirmedAt, true),
    'A different shop order must not be loaded or confirmed.'
);

$wrongCurrencyOrder = makeReceiptFixtureOrder(87, 4, 2);
$database->orders[87] = $wrongCurrencyOrder;
$instructions->instructions['4:87'] = new BankTransferInstruction(
    4, 87, 'CIREF87', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 87, '1100', 'ORDENOWA-CI-RECEIPT-987654321-87', true, 9, $confirmedAt, true),
    'A non-JPY native order must not be confirmed.'
);

$wrongPaymentMethodOrder = makeReceiptFixtureOrder(91);
$wrongPaymentMethodOrder['module'] = 'ps_wirepayment';
$database->orders[91] = $wrongPaymentMethodOrder;
$instructions->instructions['4:91'] = new BankTransferInstruction(
    4, 91, 'CIREF91', '1100.000000', 'JPY', 21, $accountId, 9, '2026-10-26 10:00:00'
);
assertReceiptThrows(
    static fn () => $confirmer->confirm(4, 91, '1100', 'ORDENOWA-CI-RECEIPT-987654321-91', true, 9, $confirmedAt, true),
    'A JPY order placed through a different payment module must not be confirmed as a bank transfer.'
);
assertReceiptSame(2, $database->orders[91]['current_state'], 'A different payment method must leave the order unpaid.');
assertReceiptSame([], array_values(array_filter($database->payments, static fn (array $payment): bool => (int) $payment['id_order'] === 91)), 'A different payment method must not create a native payment.');

assertReceiptTrue(JpyAmount::normalizePositive('1100.000000') === '1100', 'Zero precision padding must normalize without float conversion.');
assertReceiptSame(null, JpyAmount::normalizePositive('1100.500000'), 'Fractional JPY must be rejected.');

echo "PASS: bank receipt confirmation is exact, one-use, idempotent, and transactional in the synthetic fixture\n";
