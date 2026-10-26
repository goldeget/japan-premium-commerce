<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

interface BankTransferReceiptRepositoryInterface
{
    public function findForOrder(int $shopId, int $orderId): ?BankTransferReceipt;

    public function findByStatementReference(int $shopId, string $accountId, string $referenceDigest): ?BankTransferReceipt;

    /** Insert one immutable row; the order unique key prevents duplicate confirmation. */
    public function insertIfAbsent(BankTransferReceipt $receipt): bool;
}
