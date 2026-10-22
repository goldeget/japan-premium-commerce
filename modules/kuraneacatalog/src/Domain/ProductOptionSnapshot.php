<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

final class ProductOptionSnapshot
{
    /** @param list<string> $values */
    public function __construct(
        public readonly string $name,
        public readonly array $values
    ) {
    }
}
