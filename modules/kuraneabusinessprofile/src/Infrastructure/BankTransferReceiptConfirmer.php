<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Infrastructure;

use Kuranea\BusinessProfile\Customer\CommerceGate;
use Kuranea\BusinessProfile\Domain\BankTransferInstruction;
use Kuranea\BusinessProfile\Domain\BankTransferInstructionRepositoryInterface;
use Kuranea\BusinessProfile\Domain\BankTransferReceipt;
use Kuranea\BusinessProfile\Domain\BankTransferReceiptConfirmation;
use Kuranea\BusinessProfile\Domain\BankTransferReceiptRepositoryInterface;
use Kuranea\BusinessProfile\Domain\JpyAmount;
use RuntimeException;
use Throwable;

/**
 * Reconciles one explicitly verified bank receipt to native PrestaShop payment and status records.
 * All persistent writes use PrestaShop's master Db connection and are enclosed in one transaction.
 */
final class BankTransferReceiptConfirmer
{
    private object $database;

    public function __construct(
        private readonly BankTransferInstructionRepositoryInterface $instructionRepository,
        private readonly BankTransferReceiptRepositoryInterface $receiptRepository,
        ?object $database = null
    ) {
        if ($database === null) {
            if (!class_exists('Db')) {
                throw new RuntimeException('PrestaShop database service is not available.');
            }
            $database = \Db::getInstance();
        }

        $this->database = $database;
    }

    public function confirm(
        int $shopId,
        int $orderId,
        string $receivedAmount,
        string $bankStatementReference,
        bool $verifiedTransfer,
        int $employeeId,
        string $confirmedAtUtc,
        bool $commerceEnabled
    ): BankTransferReceiptConfirmation {
        if (!$verifiedTransfer) {
            throw new RuntimeException('은행 거래내역에서 입금 사실을 확인한 뒤 처리해 주세요.');
        }
        if ($shopId < 1 || $orderId < 1 || $employeeId < 1) {
            throw new RuntimeException('주문 입금 확인 권한 또는 대상이 올바르지 않습니다.');
        }

        $normalizedAmount = JpyAmount::normalizePositive($receivedAmount);
        if ($normalizedAmount === null) {
            throw new RuntimeException('입금액은 0보다 큰 엔화 정수여야 합니다.');
        }
        $statementReference = $this->normalizeStatementReference($bankStatementReference);
        $referenceDigest = hash('sha256', $statementReference);
        $synthetic = CommerceGate::isIsolatedCiCheckoutEnabled();
        if (!$synthetic && preg_match('/\\AORDENOWA-CI-RECEIPT-[A-Za-z0-9_-]{1,64}\\z/D', $statementReference) === 1) {
            throw new RuntimeException('격리 QA용 합성 거래번호는 격리 CI에서만 처리할 수 있습니다.');
        }
        if (preg_match('/\\A[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\\z/D', $confirmedAtUtc) !== 1) {
            throw new RuntimeException('입금 확인 시각 형식이 올바르지 않습니다.');
        }

        if (!$this->database->execute('START TRANSACTION')) {
            throw new RuntimeException('입금 확인을 위한 데이터베이스 트랜잭션을 시작하지 못했습니다.');
        }

        try {
            $lockedOrders = $this->database->executeS(
                'SELECT `id_order` FROM `' . _DB_PREFIX_ . 'orders`'
                . ' WHERE `id_order` = ' . (int) $orderId
                . ' AND `id_shop` = ' . (int) $shopId
                . ' LIMIT 1 FOR UPDATE',
                true,
                false
            );
            $lockedOrderId = is_array($lockedOrders) && isset($lockedOrders[0]['id_order'])
                ? (int) $lockedOrders[0]['id_order']
                : 0;
            if ($lockedOrderId !== $orderId) {
                throw new RuntimeException('선택한 쇼핑몰의 주문을 찾을 수 없습니다.');
            }

            // Load after acquiring the row lock so no stale unpaid snapshot can be confirmed.
            $order = new \Order($orderId);
            $currency = new \Currency((int) $order->id_currency);
            if (!\Validate::isLoadedObject($order)
                || (int) $order->id_shop !== $shopId
                || !\Validate::isLoadedObject($currency)
                || strtoupper((string) $currency->iso_code) !== 'JPY'
            ) {
                throw new RuntimeException('같은 쇼핑몰의 유효한 엔화 주문만 확인할 수 있습니다.');
            }

            $instruction = $this->instructionRepository->findForOrder($shopId, $orderId);
            if ($instruction === null) {
                throw new RuntimeException('먼저 이 주문의 입금 안내를 발급해야 합니다.');
            }
            $this->assertSameNativeOrder($instruction, $order);
            if (JpyAmount::normalizePositive($instruction->totalPaid) !== $normalizedAmount) {
                throw new RuntimeException('실제 입금액이 주문 금액과 다릅니다. 부분 입금이나 초과 입금은 확인할 수 없습니다.');
            }

            $referenceUse = $this->receiptRepository->findByStatementReference(
                $shopId,
                $instruction->accountId,
                $referenceDigest
            );
            if ($referenceUse !== null && $referenceUse->orderId !== $orderId) {
                throw new RuntimeException('이 은행 거래 참고번호는 다른 주문에 이미 연결되어 있습니다. 기존 입금 기록을 확인해 주세요.');
            }

            $existing = $this->receiptRepository->findForOrder($shopId, $orderId);
            if ($existing !== null) {
                // An idempotent retry only verifies the original native records; it never calls payment or history APIs again.
                if (!$existing->sameReceipt(
                    $shopId,
                    $orderId,
                    (string) $order->reference,
                    $instruction->accountId,
                    $normalizedAmount,
                    (string) $currency->iso_code,
                    $referenceDigest,
                    $synthetic
                )) {
                    throw new RuntimeException('이미 확인된 주문 입금 내역과 일치하지 않습니다. 기존 기록은 변경하지 않았습니다.');
                }

                $this->assertNativeReadback($existing, $order, $currency, false);
                $this->commit();

                return new BankTransferReceiptConfirmation($existing, false);
            }

            if (!$commerceEnabled) {
                throw new RuntimeException('판매자 승인과 주문 운영 설정을 확인한 후 처리해 주세요.');
            }
            $this->assertUnpaidOrder($order);
            if ($this->nativePaymentCount($orderId) !== 0) {
                throw new RuntimeException('이미 결제 내역이 있는 주문입니다. 기존 내역을 먼저 확인해 주세요.');
            }

            $paymentStateId = (int) \Configuration::get('PS_OS_PAYMENT');
            $paymentState = new \OrderState($paymentStateId, (int) $order->id_lang);
            if ($paymentStateId < 1 || !\Validate::isLoadedObject($paymentState) || !(bool) $paymentState->paid) {
                throw new RuntimeException('PrestaShop 결제완료 상태 설정을 확인할 수 없습니다.');
            }

            $transactionId = $this->nativeTransactionId($shopId, $orderId);
            if ($this->nativePaymentCount($orderId, $transactionId) !== 0) {
                throw new RuntimeException('입금 확인 이전에 내부 결제 기록이 발견되었습니다. 수동 검토가 필요합니다.');
            }

            $orderInvoice = null;
            foreach ($order->getInvoicesCollection() as $existingInvoice) {
                $orderInvoice = $existingInvoice;
                break;
            }
            if (!$order->addOrderPayment(
                $normalizedAmount,
                'ORDENOWA bank transfer (staff confirmed)',
                $transactionId,
                $currency,
                $confirmedAtUtc,
                $orderInvoice,
                $employeeId
            )) {
                throw new RuntimeException('PrestaShop 결제 기록을 저장하지 못했습니다.');
            }

            $paymentRow = $this->nativePaymentByTransaction($orderId, $transactionId);
            if ($paymentRow === null
                || JpyAmount::normalizePositive((string) ($paymentRow['amount'] ?? '')) !== $normalizedAmount
                || (int) ($paymentRow['id_currency'] ?? 0) !== (int) $order->id_currency
                || (int) ($paymentRow['id_employee'] ?? 0) !== $employeeId
            ) {
                throw new RuntimeException('PrestaShop 결제 기록을 다시 읽어 확인하지 못했습니다.');
            }

            $history = new \OrderHistory();
            $history->id_order = $orderId;
            $history->id_employee = $employeeId;
            // Native OrderHistory updates invoice/payment links using the existing payment; do not send mail here.
            $history->changeIdOrderState($paymentStateId, $order, true);
            if ((int) $history->id_order_state !== $paymentStateId || !$history->add() || (int) $history->id < 1) {
                throw new RuntimeException('PrestaShop 주문 상태 이력을 저장하지 못했습니다.');
            }

            $receipt = new BankTransferReceipt(
                $shopId,
                $orderId,
                (string) $order->reference,
                $instruction->accountId,
                $normalizedAmount,
                'JPY',
                $referenceDigest,
                $employeeId,
                $confirmedAtUtc,
                (int) $paymentRow['id_order_payment'],
                (int) $history->id,
                $synthetic
            );
            if (!$this->receiptRepository->insertIfAbsent($receipt)) {
                $referenceUse = $this->receiptRepository->findByStatementReference(
                    $shopId,
                    $instruction->accountId,
                    $referenceDigest
                );
                if ($referenceUse !== null && $referenceUse->orderId !== $orderId) {
                    throw new RuntimeException('이 은행 거래 참고번호는 다른 주문에 이미 연결되어 있습니다. 기존 입금 기록을 확인해 주세요.');
                }
                throw new RuntimeException('입금 확인 기록이 동시에 변경되었습니다. 주문을 다시 조회해 주세요.');
            }

            $stored = $this->receiptRepository->findForOrder($shopId, $orderId);
            if ($stored === null || !$stored->sameReceipt(
                $shopId,
                $orderId,
                (string) $order->reference,
                $instruction->accountId,
                $normalizedAmount,
                'JPY',
                $referenceDigest,
                $synthetic
            )) {
                throw new RuntimeException('입금 확인 기록을 다시 읽어 확인하지 못했습니다.');
            }

            $this->assertNativeReadback($stored, $order, $currency, true);
            $this->commit();

            return new BankTransferReceiptConfirmation($stored, true);
        } catch (Throwable $exception) {
            $this->database->execute('ROLLBACK');
            throw $exception;
        }
    }

    private function assertSameNativeOrder(BankTransferInstruction $instruction, object $order): void
    {
        if ($instruction->orderId !== (int) $order->id
            || $instruction->shopId !== (int) $order->id_shop
            || $instruction->orderReference !== (string) $order->reference
            || (string) ($order->module ?? '') !== 'ps_checkpayment'
            || JpyAmount::normalizePositive($instruction->totalPaid) === null
            || JpyAmount::normalizePositive((string) $order->total_paid_tax_incl) !== JpyAmount::normalizePositive($instruction->totalPaid)
            || $instruction->currencyIso !== 'JPY'
        ) {
            throw new RuntimeException('입금 안내와 현재 주문 정보가 일치하지 않습니다.');
        }
    }

    private function assertUnpaidOrder(object $order): void
    {
        $orderState = new \OrderState((int) $order->current_state, (int) $order->id_lang);
        if (!\Validate::isLoadedObject($orderState)
            || (bool) $orderState->paid
            || (int) $order->current_state === (int) \Configuration::get('PS_OS_CANCELED')
            || !$this->isZeroAmount((string) $order->total_paid_real)
        ) {
            throw new RuntimeException('미결제 상태이며 입금 내역이 없는 주문만 확인할 수 있습니다.');
        }
    }

    private function assertNativeReadback(
        BankTransferReceipt $receipt,
        object $order,
        object $currency,
        bool $requireCurrentPaidState
    ): void {
        $payment = $this->nativePaymentById($receipt->orderId, $receipt->orderPaymentId);
        if ($payment === null
            || JpyAmount::normalizePositive((string) ($payment['amount'] ?? '')) !== JpyAmount::normalizePositive($receipt->receivedAmount)
            || (int) ($payment['id_currency'] ?? 0) !== (int) $currency->id
            || (int) ($payment['id_employee'] ?? 0) !== $receipt->confirmedByEmployeeId
            || (string) ($payment['transaction_id'] ?? '') !== $this->nativeTransactionId($receipt->shopId, $receipt->orderId)
        ) {
            throw new RuntimeException('저장된 PrestaShop 결제 내역을 재조회하지 못했습니다.');
        }

        $historyRows = $this->database->executeS(
            'SELECT `id_order_history`, `id_order_state`, `id_employee` FROM `' . _DB_PREFIX_ . 'order_history`'
            . ' WHERE `id_order` = ' . (int) $receipt->orderId
            . ' AND `id_order_history` = ' . (int) $receipt->orderHistoryId . ' LIMIT 1'
        );
        if (!is_array($historyRows) || !isset($historyRows[0])
            || (int) $historyRows[0]['id_employee'] !== $receipt->confirmedByEmployeeId
        ) {
            throw new RuntimeException('저장된 PrestaShop 주문 이력을 재조회하지 못했습니다.');
        }

        $orderRows = $this->database->executeS(
            'SELECT o.`id_shop`, o.`reference`, o.`total_paid_tax_incl`, o.`total_paid_real`, o.`current_state`'
            . ', c.`iso_code` AS `currency_iso`, os.`paid` AS `state_paid`'
            . ' FROM `' . _DB_PREFIX_ . 'orders` o'
            . ' INNER JOIN `' . _DB_PREFIX_ . 'currency` c ON c.`id_currency` = o.`id_currency`'
            . ' INNER JOIN `' . _DB_PREFIX_ . 'order_state` os ON os.`id_order_state` = o.`current_state`'
            . ' WHERE o.`id_order` = ' . (int) $receipt->orderId
            . ' AND o.`id_shop` = ' . (int) $receipt->shopId . ' LIMIT 1'
        );
        if (!is_array($orderRows) || !isset($orderRows[0])) {
            throw new RuntimeException('PrestaShop 주문 결제 상태를 재조회하지 못했습니다.');
        }

        $row = $orderRows[0];
        if ((string) $row['reference'] !== $receipt->orderReference
            || (string) $row['currency_iso'] !== 'JPY'
            || JpyAmount::normalizePositive((string) $row['total_paid_tax_incl']) !== JpyAmount::normalizePositive($receipt->receivedAmount)
            || ($requireCurrentPaidState
                ? $this->nativePaymentCount($receipt->orderId) !== 1
                : $this->nativePaymentCount($receipt->orderId, $this->nativeTransactionId($receipt->shopId, $receipt->orderId)) !== 1)
        ) {
            throw new RuntimeException('주문·금액·결제 기록의 저장 결과가 일치하지 않습니다.');
        }
        if ($requireCurrentPaidState
            && ((int) $row['state_paid'] !== 1
                || $this->isZeroAmount((string) $row['total_paid_real'])
                || JpyAmount::normalizePositive((string) $row['total_paid_real']) !== JpyAmount::normalizePositive($receipt->receivedAmount)
                || (int) $row['current_state'] !== (int) \Configuration::get('PS_OS_PAYMENT')
                || (int) $historyRows[0]['id_order_state'] !== (int) $row['current_state']
            )
        ) {
            throw new RuntimeException('결제 완료 상태와 주문 이력을 재조회하지 못했습니다.');
        }
    }

    /** @return array<string, mixed>|null */
    private function nativePaymentByTransaction(int $orderId, string $transactionId): ?array
    {
        $rows = $this->database->executeS(
            'SELECT op.`id_order_payment`, op.`id_currency`, op.`amount`, op.`id_employee`, op.`transaction_id`'
            . ' FROM `' . _DB_PREFIX_ . 'order_payment` op'
            . ' INNER JOIN `' . _DB_PREFIX_ . 'orders` o ON o.`reference` = op.`order_reference`'
            . ' WHERE o.`id_order` = ' . (int) $orderId
            . " AND op.`transaction_id` = '" . pSQL($transactionId) . "' LIMIT 2"
        );

        return is_array($rows) && count($rows) === 1 ? $rows[0] : null;
    }

    /** @return array<string, mixed>|null */
    private function nativePaymentById(int $orderId, int $paymentId): ?array
    {
        $rows = $this->database->executeS(
            'SELECT op.`id_order_payment`, op.`id_currency`, op.`amount`, op.`id_employee`, op.`transaction_id`'
            . ' FROM `' . _DB_PREFIX_ . 'order_payment` op'
            . ' INNER JOIN `' . _DB_PREFIX_ . 'orders` o ON o.`reference` = op.`order_reference`'
            . ' WHERE o.`id_order` = ' . (int) $orderId
            . ' AND op.`id_order_payment` = ' . (int) $paymentId . ' LIMIT 1'
        );

        return is_array($rows) && isset($rows[0]) ? $rows[0] : null;
    }

    private function nativePaymentCount(int $orderId, ?string $transactionId = null): int
    {
        $transactionClause = $transactionId === null
            ? ''
            : " AND op.`transaction_id` = '" . pSQL($transactionId) . "'";
        return (int) $this->database->getValue(
            'SELECT COUNT(*) FROM `' . _DB_PREFIX_ . 'order_payment` op'
            . ' INNER JOIN `' . _DB_PREFIX_ . 'orders` o ON o.`reference` = op.`order_reference`'
            . ' WHERE o.`id_order` = ' . (int) $orderId . $transactionClause
        );
    }

    private function normalizeStatementReference(string $reference): string
    {
        $reference = trim($reference);
        if ($reference === '' || strlen($reference) > 256
            || preg_match('//u', $reference) !== 1
            || preg_match('/[\\x00-\\x1F\\x7F]/u', $reference) === 1
        ) {
            throw new RuntimeException('은행 거래내역 참고번호를 확인해 주세요.');
        }

        return $reference;
    }

    private function isZeroAmount(string $amount): bool
    {
        return preg_match('/\\A0(?:\\.0{1,6})?\\z/D', $amount) === 1;
    }

    private function nativeTransactionId(int $shopId, int $orderId): string
    {
        return 'ORDENOWA-BT-' . substr(hash('sha256', 'bank-transfer:' . $shopId . ':' . $orderId), 0, 32);
    }

    private function commit(): void
    {
        if (!$this->database->execute('COMMIT')) {
            throw new RuntimeException('입금 확인 트랜잭션을 저장하지 못했습니다.');
        }
    }
}
