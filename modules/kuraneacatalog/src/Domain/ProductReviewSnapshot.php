<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

final class ProductReviewSnapshot
{
    public function __construct(
        public readonly string $origin,
        public readonly string $provider,
        public readonly ?string $author,
        public readonly ?string $body,
        public readonly ?float $rating,
        public readonly ?string $publishedAt,
        public readonly bool $publishable = false
    ) {
    }
}
