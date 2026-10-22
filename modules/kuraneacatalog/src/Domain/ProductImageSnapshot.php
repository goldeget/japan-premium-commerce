<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

final class ProductImageSnapshot
{
    public function __construct(
        public readonly string $url,
        public readonly string $altText,
        public readonly int $position,
        public readonly string $source
    ) {
    }
}
