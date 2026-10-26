<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

use InvalidArgumentException;

/** Immutable issue-time binding for one native, still-unpaid order. */
final class BankTransferInstruction
{
    public function __construct(
        public readonly int $shopId,
        public readonly int $orderId,
        public readonly string $orderReference,
        public readonly string $totalPaid,
        public readonly string $currencyIso,
        public readonly int $profileVersionId,
        public readonly string $accountId,
        public readonly int $issuedByEmployeeId,
        public readonly string $issuedAtUtc,
    ) {
        if ($shopId < 1 || $orderId < 1 || $profileVersionId < 1 || $issuedByEmployeeId < 1) {
            throw new InvalidArgumentException('주문 계좌 안내의 연결 정보가 올바르지 않습니다.');
        }
        if (preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $orderReference) !== 1) {
            throw new InvalidArgumentException('주문 번호 형식이 올바르지 않습니다.');
        }
        if (JpyAmount::normalizePositive($totalPaid) === null) {
            throw new InvalidArgumentException('주문 금액 형식이 올바르지 않습니다.');
        }
        if (preg_match('/\A[A-Z]{3}\z/D', $currencyIso) !== 1) {
            throw new InvalidArgumentException('통화 형식이 올바르지 않습니다.');
        }
        if (preg_match('/\A[a-f0-9]{32}\z/iD', $accountId) !== 1) {
            throw new InvalidArgumentException('은행 계좌 연결 정보가 올바르지 않습니다.');
        }
        if (preg_match('/\A[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\z/D', $issuedAtUtc) !== 1) {
            throw new InvalidArgumentException('발급 시각 형식이 올바르지 않습니다.');
        }
    }
}
