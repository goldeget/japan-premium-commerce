<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

use InvalidArgumentException;
use RuntimeException;

/** Creates a single immutable instruction binding after staff confirms an unpaid native order. */
final class BankTransferInstructionIssuer
{
    public function __construct(private readonly BankTransferInstructionRepositoryInterface $repository)
    {
    }

    public function issue(
        int $shopId,
        int $orderId,
        string $orderReference,
        string $totalPaid,
        string $currencyIso,
        ProfileVersion $publishedVersion,
        int $employeeId,
        string $issuedAtUtc
    ): BankTransferInstructionIssue {
        if ($publishedVersion->shopId !== $shopId) {
            throw new InvalidArgumentException('게시된 은행 계좌 설정을 찾을 수 없습니다.');
        }

        $existing = $this->repository->findForOrder($shopId, $orderId);
        if ($existing !== null) {
            $this->assertSameNativeOrder($existing, $orderReference, $totalPaid, $currencyIso);

            return new BankTransferInstructionIssue($existing, false);
        }

        if ($currencyIso !== 'JPY') {
            throw new InvalidArgumentException('엔화 주문에만 입금 안내를 발급할 수 있습니다.');
        }

        $account = BankTransferPayment::selectedActiveAccount($publishedVersion->profile);
        if ($account === null) {
            throw new InvalidArgumentException('게시된 은행 계좌가 비활성 상태이거나 선택되지 않았습니다.');
        }

        $candidate = new BankTransferInstruction(
            $shopId,
            $orderId,
            $orderReference,
            $totalPaid,
            $currencyIso,
            $publishedVersion->id,
            (string) $account['id'],
            $employeeId,
            $issuedAtUtc
        );

        $created = $this->repository->insertIfAbsent($candidate);
        $stored = $this->repository->findForOrder($shopId, $orderId);
        if ($stored === null) {
            throw new RuntimeException('주문 입금 안내를 저장하지 못했습니다.');
        }
        $this->assertSameNativeOrder($stored, $orderReference, $totalPaid, $currencyIso);

        return new BankTransferInstructionIssue($stored, $created);
    }

    private function assertSameNativeOrder(
        BankTransferInstruction $instruction,
        string $orderReference,
        string $totalPaid,
        string $currencyIso
    ): void {
        if ($instruction->orderReference !== $orderReference
            || $instruction->totalPaid !== $totalPaid
            || $instruction->currencyIso !== $currencyIso
        ) {
            throw new RuntimeException('이미 발급된 입금 안내와 현재 주문 정보가 다릅니다.');
        }
    }
}
