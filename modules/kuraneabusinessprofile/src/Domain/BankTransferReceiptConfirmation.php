<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

final class BankTransferReceiptConfirmation
{
    public function __construct(
        public readonly BankTransferReceipt $receipt,
        public readonly bool $created,
    ) {
    }
}
