<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Infrastructure;

use Kuranea\BusinessProfile\Domain\BankTransferInstruction;
use Kuranea\BusinessProfile\Domain\BankTransferInstructionRepositoryInterface;
use RuntimeException;

final class BankTransferInstructionRepository implements BankTransferInstructionRepositoryInterface
{
    private object $database;
    private string $prefix;

    public function __construct(?object $database = null, ?string $prefix = null)
    {
        if ($database === null) {
            if (!class_exists('Db')) {
                throw new RuntimeException('PrestaShop database service is not available.');
            }
            $database = \Db::getInstance();
        }

        $this->database = $database;
        $this->prefix = $prefix ?? (defined('_DB_PREFIX_') ? (string) _DB_PREFIX_ : '');
        DatabaseSchema::createBankTransferInstructionTableSql($this->prefix);
    }

    public function findForOrder(int $shopId, int $orderId): ?BankTransferInstruction
    {
        if ($shopId < 1 || $orderId < 1) {
            return null;
        }

        $rows = $this->database->executeS(
            'SELECT `id_shop`, `id_order`, `order_reference`, `total_paid`, `currency_iso`'
            . ', `profile_version_id`, `bank_account_id`, `issued_by_employee_id`, `issued_at_utc`'
            . ' FROM `' . $this->prefix . 'kuraneabusinessprofile_bank_transfer_instruction`'
            . ' WHERE `id_shop` = ' . (int) $shopId . ' AND `id_order` = ' . (int) $orderId . ' LIMIT 1'
        );

        return is_array($rows) && isset($rows[0]) ? $this->fromRow($rows[0]) : null;
    }

    public function insertIfAbsent(BankTransferInstruction $instruction): bool
    {
        $sql = 'INSERT IGNORE INTO `' . $this->prefix . 'kuraneabusinessprofile_bank_transfer_instruction`'
            . ' (`id_order`, `id_shop`, `order_reference`, `total_paid`, `currency_iso`, `profile_version_id`'
            . ', `bank_account_id`, `issued_by_employee_id`, `issued_at_utc`) VALUES ('
            . (int) $instruction->orderId . ', '
            . (int) $instruction->shopId . ', '
            . "'" . pSQL($instruction->orderReference) . "', "
            . "'" . pSQL($instruction->totalPaid) . "', "
            . "'" . pSQL($instruction->currencyIso) . "', "
            . (int) $instruction->profileVersionId . ', '
            . "'" . pSQL($instruction->accountId) . "', "
            . (int) $instruction->issuedByEmployeeId . ', '
            . "'" . pSQL($instruction->issuedAtUtc) . "')";

        if (!$this->database->execute($sql)) {
            throw new RuntimeException('주문 입금 안내를 저장하지 못했습니다.');
        }

        return (int) $this->database->Affected_Rows() === 1;
    }

    /** @param array<string, mixed> $row */
    private function fromRow(array $row): BankTransferInstruction
    {
        return new BankTransferInstruction(
            (int) $row['id_shop'],
            (int) $row['id_order'],
            (string) $row['order_reference'],
            (string) $row['total_paid'],
            (string) $row['currency_iso'],
            (int) $row['profile_version_id'],
            (string) $row['bank_account_id'],
            (int) $row['issued_by_employee_id'],
            (string) $row['issued_at_utc']
        );
    }
}
