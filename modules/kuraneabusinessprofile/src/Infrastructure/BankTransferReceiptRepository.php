<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Infrastructure;

use Kuranea\BusinessProfile\Domain\BankTransferReceipt;
use Kuranea\BusinessProfile\Domain\BankTransferReceiptRepositoryInterface;
use RuntimeException;

final class BankTransferReceiptRepository implements BankTransferReceiptRepositoryInterface
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
    }

    public function findForOrder(int $shopId, int $orderId): ?BankTransferReceipt
    {
        if ($shopId < 1 || $orderId < 1) {
            return null;
        }

        $rows = $this->database->executeS(
            'SELECT `id_shop`, `id_order`, `order_reference`, `bank_account_id`, `received_amount`, `currency_iso`'
            . ', `receipt_reference_sha256`, `confirmed_by_employee_id`, `confirmed_at_utc`'
            . ', `id_order_payment`, `id_order_history`, `is_synthetic`'
            . ' FROM `' . $this->prefix . 'kuraneabusinessprofile_bank_transfer_receipt`'
            . ' WHERE `id_shop` = ' . (int) $shopId . ' AND `id_order` = ' . (int) $orderId . ' LIMIT 1',
            true,
            false
        );

        return is_array($rows) && isset($rows[0]) ? $this->fromRow($rows[0]) : null;
    }

    public function findByStatementReference(int $shopId, string $accountId, string $referenceDigest): ?BankTransferReceipt
    {
        if ($shopId < 1
            || preg_match('/\\A[a-f0-9]{32}\\z/iD', $accountId) !== 1
            || preg_match('/\\A[a-f0-9]{64}\\z/D', $referenceDigest) !== 1
        ) {
            return null;
        }

        $rows = $this->database->executeS(
            'SELECT `id_shop`, `id_order`, `order_reference`, `bank_account_id`, `received_amount`, `currency_iso`'
            . ', `receipt_reference_sha256`, `confirmed_by_employee_id`, `confirmed_at_utc`'
            . ', `id_order_payment`, `id_order_history`, `is_synthetic`'
            . ' FROM `' . $this->prefix . 'kuraneabusinessprofile_bank_transfer_receipt`'
            . ' WHERE `id_shop` = ' . (int) $shopId
            . " AND `bank_account_id` = '" . pSQL($accountId) . "'"
            . " AND `receipt_reference_sha256` = '" . pSQL($referenceDigest) . "' LIMIT 1 FOR UPDATE",
            true,
            false
        );

        return is_array($rows) && isset($rows[0]) ? $this->fromRow($rows[0]) : null;
    }

    public function insertIfAbsent(BankTransferReceipt $receipt): bool
    {
        $sql = 'INSERT IGNORE INTO `' . $this->prefix . 'kuraneabusinessprofile_bank_transfer_receipt`'
            . ' (`id_order`, `id_shop`, `order_reference`, `received_amount`, `currency_iso`'
            . ', `bank_account_id`, `receipt_reference_sha256`, `confirmed_by_employee_id`, `confirmed_at_utc`'
            . ', `id_order_payment`, `id_order_history`, `is_synthetic`) VALUES ('
            . (int) $receipt->orderId . ', '
            . (int) $receipt->shopId . ', '
            . "'" . pSQL($receipt->orderReference) . "', "
            . "'" . pSQL($receipt->receivedAmount) . "', "
            . "'" . pSQL($receipt->currencyIso) . "', "
            . "'" . pSQL($receipt->accountId) . "', "
            . "'" . pSQL($receipt->referenceDigest) . "', "
            . (int) $receipt->confirmedByEmployeeId . ', '
            . "'" . pSQL($receipt->confirmedAtUtc) . "', "
            . (int) $receipt->orderPaymentId . ', '
            . (int) $receipt->orderHistoryId . ', '
            . ($receipt->synthetic ? '1' : '0') . ')';

        if (!$this->database->execute($sql)) {
            throw new RuntimeException('입금 확인 기록을 저장하지 못했습니다.');
        }

        return (int) $this->database->Affected_Rows() === 1;
    }

    /** @param array<string, mixed> $row */
    private function fromRow(array $row): BankTransferReceipt
    {
        return new BankTransferReceipt(
            (int) $row['id_shop'],
            (int) $row['id_order'],
            (string) $row['order_reference'],
            (string) $row['bank_account_id'],
            (string) $row['received_amount'],
            (string) $row['currency_iso'],
            (string) $row['receipt_reference_sha256'],
            (int) $row['confirmed_by_employee_id'],
            (string) $row['confirmed_at_utc'],
            (int) $row['id_order_payment'],
            (int) $row['id_order_history'],
            (bool) $row['is_synthetic']
        );
    }
}
