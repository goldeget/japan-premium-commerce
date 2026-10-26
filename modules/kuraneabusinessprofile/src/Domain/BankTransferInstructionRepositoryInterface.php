<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

interface BankTransferInstructionRepositoryInterface
{
    public function findForOrder(int $shopId, int $orderId): ?BankTransferInstruction;

    /** Insert only when the order has no issued instruction. Never update an existing row. */
    /** Return true only when this call inserted the row. */
    public function insertIfAbsent(BankTransferInstruction $instruction): bool;
}
