<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

final class FetchedProduct
{
    public function __construct(
        public readonly string $canonicalUrl,
        public readonly string $body,
        public readonly \DateTimeImmutable $fetchedAt,
        public readonly int $redirectCount
    ) {
    }
}
