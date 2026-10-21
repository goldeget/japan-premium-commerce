<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Domain;

final class ImportSummary
{
    public function __construct(
        public readonly int $imported,
        public readonly int $skipped
    ) {
    }
}
