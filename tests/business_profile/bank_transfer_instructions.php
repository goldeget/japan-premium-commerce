<?php

declare(strict_types=1);

require_once __DIR__ . '/../../modules/kuraneabusinessprofile/autoload.php';

use Kuranea\BusinessProfile\Domain\BankTransferInstruction;
use Kuranea\BusinessProfile\Domain\BankTransferInstructionIssue;
use Kuranea\BusinessProfile\Domain\BankTransferInstructionIssuer;
use Kuranea\BusinessProfile\Domain\BankTransferInstructionRepositoryInterface;
use Kuranea\BusinessProfile\Domain\ProfileDefaults;
use Kuranea\BusinessProfile\Domain\ProfileVersion;
use Kuranea\BusinessProfile\Customer\BankTransferInstructionPresenter;
use Kuranea\BusinessProfile\Admin\AdminAccessPolicy;

function assertTransferSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertTransferTrue(bool $actual, string $message): void
{
    if (!$actual) {
        throw new RuntimeException($message);
    }
}

function assertTransferThrows(callable $callback, string $message): void
{
    try {
        $callback();
    } catch (InvalidArgumentException | RuntimeException) {
        return;
    }

    throw new RuntimeException($message);
}

final class InMemoryBankTransferInstructionRepository implements BankTransferInstructionRepositoryInterface
{
    /** @var array<string, BankTransferInstruction> */
    private array $byOrder = [];

    public function findForOrder(int $shopId, int $orderId): ?BankTransferInstruction
    {
        $item = $this->byOrder[$shopId . ':' . $orderId] ?? null;
        return $item instanceof BankTransferInstruction ? $item : null;
    }

    public function insertIfAbsent(BankTransferInstruction $instruction): bool
    {
        $key = $instruction->shopId . ':' . $instruction->orderId;
        if (isset($this->byOrder[$key])) {
            return false;
        }
        $this->byOrder[$key] = $instruction;

        return true;
    }
}

$profile = ProfileDefaults::initial();
$accountId = 'a1b2c3d4e5f678901234567890abcdef';
$profile['seller']['authorization_status'] = 'approved';
$profile['seller']['legal_name']['ja-JP'] = 'ORDENOWA CI 合成販売者';
$profile['payment_methods']['bank_transfer'] = ['enabled' => true, 'bank_account_id' => $accountId];
$profile['bank_accounts'] = [[
    'id' => $accountId,
    'bank_name' => 'ORDENOWA CI 合成銀行',
    'branch_name' => 'テスト支店',
    'account_type' => 'ordinary',
    'account_number' => '1234567',
    'account_holder' => 'ORDENOWA CI',
    'active' => true,
]];
$published = new ProfileVersion(21, 4, $profile, 5, 20, '2026-10-26 10:00:00');
$repository = new InMemoryBankTransferInstructionRepository();
$issuer = new BankTransferInstructionIssuer($repository);

$result = $issuer->issue(4, 81, 'A1B2C3D4E', '1100.000000', 'JPY', $published, 9, '2026-10-26 10:30:00');
assertTransferTrue($result instanceof BankTransferInstructionIssue, 'Issuance should return an explicit result.');
assertTransferSame(true, $result->created, 'The first staff issuance should create one immutable instruction record.');
assertTransferSame(81, $result->instruction->orderId, 'The instruction must bind to the native order id.');
assertTransferSame('A1B2C3D4E', $result->instruction->orderReference, 'The instruction must bind to the native order reference.');
assertTransferSame('1100.000000', $result->instruction->totalPaid, 'The native unpaid total must be stored without float conversion.');
assertTransferSame('JPY', $result->instruction->currencyIso, 'The instruction must store the native order currency.');
assertTransferSame(21, $result->instruction->profileVersionId, 'The instruction must reference the published immutable profile version.');
assertTransferSame($accountId, $result->instruction->accountId, 'The instruction must bind to the selected account id.');
assertTransferSame(9, $result->instruction->issuedByEmployeeId, 'The staff actor must be stored.');
assertTransferSame('2026-10-26 10:30:00', $result->instruction->issuedAtUtc, 'The UTC issuance time must be stored.');
assertTransferSame(true, AdminAccessPolicy::canIssueBankTransferInstructions(['view' => 1, 'add' => 1]), 'An employee with the dedicated view and add rights can issue instructions.');
assertTransferSame(false, AdminAccessPolicy::canIssueBankTransferInstructions(['view' => 1, 'add' => 0]), 'A view-only employee cannot issue instructions.');
assertTransferSame(false, AdminAccessPolicy::canIssueBankTransferInstructions(['view' => 0, 'add' => 1]), 'An employee without read access cannot issue instructions.');

$presented = BankTransferInstructionPresenter::render($result->instruction, $profile, 'ja-JP', '¥1,100');
assertTransferTrue(str_contains($presented, 'A1B2C3D4E'), 'The customer view should include the bound order reference.');
assertTransferTrue(str_contains($presented, '¥1,100'), 'The customer view should include the bound order amount.');
assertTransferTrue(str_contains($presented, 'ORDENOWA CI 合成販売者'), 'The customer view should include the seller from the bound profile version.');
assertTransferTrue(str_contains($presented, '1234567'), 'The customer view should include the selected account from the bound profile version.');
assertTransferTrue(str_contains($presented, '未払い'), 'The customer view should state that the order is still unpaid.');

$unsafeProfile = $profile;
$unsafeProfile['seller']['legal_name']['ja-JP'] = '<script>seller</script>';
$unsafe = BankTransferInstructionPresenter::render($result->instruction, $unsafeProfile, 'ja-JP', '¥1,100');
assertTransferTrue(str_contains($unsafe, '&lt;script&gt;seller&lt;/script&gt;'), 'Seller-provided text must be escaped.');
assertTransferTrue(!str_contains($unsafe, '<script>seller</script>'), 'Seller-provided markup must never render as HTML.');

$unsafeAccountProfile = $profile;
$unsafeAccountProfile['bank_accounts'][0]['bank_name'] = '<script>bank</script>';
$unsafeAccountOutput = BankTransferInstructionPresenter::render($result->instruction, $unsafeAccountProfile, 'ja-JP', '¥1,100');
assertTransferTrue(str_contains($unsafeAccountOutput, '&lt;script&gt;bank&lt;/script&gt;'), 'Bank fields must be escaped.');
$mismatchedAccountProfile = $profile;
$mismatchedAccountProfile['bank_accounts'][0]['id'] = 'c1b2c3d4e5f678901234567890abcdef';
assertTransferSame('', BankTransferInstructionPresenter::render($result->instruction, $mismatchedAccountProfile, 'ja-JP', '¥1,100'), 'A customer view must not substitute another account when the bound account is unavailable.');

$changed = $profile;
$changedAccountId = 'b1b2c3d4e5f678901234567890abcdef';
$changed['payment_methods']['bank_transfer']['bank_account_id'] = $changedAccountId;
$changed['bank_accounts'][0]['id'] = $changedAccountId;
$laterPublished = new ProfileVersion(22, 4, $changed, 6, 21, '2026-10-26 11:00:00');
$repeat = $issuer->issue(4, 81, 'A1B2C3D4E', '1100.000000', 'JPY', $laterPublished, 10, '2026-10-26 11:30:00');
assertTransferSame(false, $repeat->created, 'Repeated issuance must not create or replace an existing instruction.');
assertTransferSame(21, $repeat->instruction->profileVersionId, 'Changing the published profile must not alter instructions already issued for an order.');
assertTransferSame($accountId, $repeat->instruction->accountId, 'Changing the selected bank account must not alter the old order binding.');
assertTransferSame(9, $repeat->instruction->issuedByEmployeeId, 'Repeated issuance must retain the original issuer.');

assertTransferThrows(
    static fn () => $issuer->issue(4, 81, 'A1B2C3D4E', '1200.000000', 'JPY', $laterPublished, 10, '2026-10-26 11:30:00'),
    'If native order amount changes after issuance, the existing instruction must not be silently replaced.'
);
assertTransferThrows(
    static fn () => $issuer->issue(4, 82, 'A1B2C3D4F', '1100.000000', 'USD', $published, 9, '2026-10-26 10:30:00'),
    'Bank transfer issuance must remain limited to the platform JPY orders.'
);
assertTransferThrows(
    static fn () => $issuer->issue(4, 84, 'A1B2C3D4H', '1100.500000', 'JPY', $published, 9, '2026-10-26 10:30:00'),
    'Fractional JPY orders must not receive transfer instructions that cannot be reconciled exactly.'
);
assertTransferSame(null, $repository->findForOrder(4, 84), 'A fractional JPY instruction must not be persisted.');
$disabled = $profile;
$disabled['payment_methods']['bank_transfer']['enabled'] = false;
$disabledVersion = new ProfileVersion(23, 4, $disabled, 5, 22, '2026-10-26 12:00:00');
assertTransferThrows(
    static fn () => $issuer->issue(4, 83, 'A1B2C3D4G', '1100.000000', 'JPY', $disabledVersion, 9, '2026-10-26 12:30:00'),
    'An unpublished or disabled account must not receive a new issuance.'
);
assertTransferThrows(
    static fn () => $issuer->issue(5, 81, 'A1B2C3D4E', '1100.000000', 'JPY', $laterPublished, 10, '2026-10-26 11:30:00'),
    'A profile version from another shop must not be used to read or issue order instructions.'
);
assertTransferTrue($repository->findForOrder(5, 81) === null, 'An instruction must not be readable through a different shop id.');

$instructionSql = \Kuranea\BusinessProfile\Infrastructure\DatabaseSchema::createBankTransferInstructionTableSql('ps_');
$receiptLedgerSql = \Kuranea\BusinessProfile\Infrastructure\DatabaseSchema::createBankTransferReceiptLedgerTableSql('ps_');
assertTransferTrue(str_contains($instructionSql, 'PRIMARY KEY (`id_order`)'), 'Each native order should have no more than one immutable instruction binding.');
assertTransferTrue(str_contains($instructionSql, '`profile_version_id` INT UNSIGNED'), 'The instruction row should reference the immutable profile snapshot.');
assertTransferTrue(str_contains($instructionSql, '`issued_by_employee_id` INT UNSIGNED'), 'The instruction row should record its staff issuer.');
assertTransferTrue(str_contains($receiptLedgerSql, '`receipt_reference_sha256` CHAR(64)'), 'Future receipt confirmation should use a separate, redacted ledger reference.');
assertTransferTrue(str_contains($receiptLedgerSql, 'UNIQUE KEY `one_confirmation_per_order`'), 'Receipt confirmation should be idempotent per order.');
assertTransferTrue(!str_contains(strtoupper($instructionSql . $receiptLedgerSql), 'DROP TABLE'), 'The new schema must not delete existing module or order data.');

echo "PASS: staff-issued bank instructions are immutable, order-bound, and unpaid\n";
