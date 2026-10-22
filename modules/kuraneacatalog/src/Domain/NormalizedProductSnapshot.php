<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use DateTimeImmutable;

final class NormalizedProductSnapshot
{
    /**
     * @param list<string> $categories
     * @param list<ProductImageSnapshot> $images
     * @param list<ProductOptionSnapshot> $options
     * @param list<ProductReviewSnapshot> $reviews
     */
    public function __construct(
        public readonly string $source,
        public readonly string $sourceProductId,
        public readonly string $deduplicationKey,
        public readonly string $sourceUrl,
        public readonly string $name,
        public readonly ?string $brand,
        public readonly ?string $description,
        public readonly array $categories,
        public readonly int $priceJpy,
        public readonly string $currency,
        public readonly array $images,
        public readonly array $options,
        public readonly array $reviews,
        public readonly ?float $sourceRating,
        public readonly ?int $sourceReviewCount,
        public readonly ?string $availability,
        public readonly string $approvalStatus,
        public readonly DateTimeImmutable $fetchedAt,
        public readonly string $contentHash
    ) {
    }
}
