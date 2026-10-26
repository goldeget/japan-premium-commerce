<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

final class BankTransferInstructionIssue
{
    public function __construct(
        public readonly BankTransferInstruction $instruction,
        public readonly bool $created,
    ) {
    }
}
