<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

use InvalidArgumentException;

/** Immutable record of one staff-confirmed transfer and its native PrestaShop records. */
final class BankTransferReceipt
{
    public function __construct(
        public readonly int $shopId,
        public readonly int $orderId,
        public readonly string $orderReference,
        public readonly string $accountId,
        public readonly string $receivedAmount,
        public readonly string $currencyIso,
        public readonly string $referenceDigest,
        public readonly int $confirmedByEmployeeId,
        public readonly string $confirmedAtUtc,
        public readonly int $orderPaymentId,
        public readonly int $orderHistoryId,
        public readonly bool $synthetic,
    ) {
        if ($shopId < 1 || $orderId < 1 || $confirmedByEmployeeId < 1 || $orderPaymentId < 1 || $orderHistoryId < 1) {
            throw new InvalidArgumentException('입금 확인 기록의 연결 정보가 올바르지 않습니다.');
        }
        if (preg_match('/\\A[A-Za-z0-9_-]{1,64}\\z/D', $orderReference) !== 1) {
            throw new InvalidArgumentException('주문 번호 형식이 올바르지 않습니다.');
        }
        if (preg_match('/\\A[a-f0-9]{32}\\z/iD', $accountId) !== 1) {
            throw new InvalidArgumentException('은행 계좌 연결 정보가 올바르지 않습니다.');
        }
        if (JpyAmount::normalizePositive($receivedAmount) === null || $currencyIso !== 'JPY') {
            throw new InvalidArgumentException('입금 금액 또는 통화가 올바르지 않습니다.');
        }
        if (preg_match('/\\A[a-f0-9]{64}\\z/D', $referenceDigest) !== 1) {
            throw new InvalidArgumentException('거래 참고번호 요약값이 올바르지 않습니다.');
        }
        if (preg_match('/\\A[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\\z/D', $confirmedAtUtc) !== 1) {
            throw new InvalidArgumentException('입금 확인 시각 형식이 올바르지 않습니다.');
        }
    }

    public function sameReceipt(
        int $shopId,
        int $orderId,
        string $orderReference,
        string $accountId,
        string $amount,
        string $currencyIso,
        string $referenceDigest,
        bool $synthetic
    ): bool {
        $storedAmount = JpyAmount::normalizePositive($this->receivedAmount);
        $requestedAmount = JpyAmount::normalizePositive($amount);

        return $this->shopId === $shopId
            && $this->orderId === $orderId
            && $this->orderReference === $orderReference
            && hash_equals($this->accountId, $accountId)
            && $storedAmount !== null
            && $requestedAmount !== null
            && $storedAmount === $requestedAmount
            && $this->currencyIso === $currencyIso
            && hash_equals($this->referenceDigest, $referenceDigest)
            && $this->synthetic === $synthetic;
    }
}
