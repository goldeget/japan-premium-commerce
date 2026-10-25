<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Integration;

final class NativeImportedDraftResult
{
    public function __construct(
        public readonly int $productId,
        public readonly bool $created
    ) {
        if ($productId < 1) {
            throw new \InvalidArgumentException('Imported native product identity must be positive.');
        }
    }
}
