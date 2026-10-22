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

    public function withApprovalStatus(string $approvalStatus): self
    {
        return new self(
            $this->source,
            $this->sourceProductId,
            $this->deduplicationKey,
            $this->sourceUrl,
            $this->name,
            $this->brand,
            $this->description,
            $this->categories,
            $this->priceJpy,
            $this->currency,
            $this->images,
            $this->options,
            $this->reviews,
            $this->sourceRating,
            $this->sourceReviewCount,
            $this->availability,
            $approvalStatus,
            $this->fetchedAt,
            $this->contentHash
        );
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'source' => $this->source,
            'sourceProductId' => $this->sourceProductId,
            'deduplicationKey' => $this->deduplicationKey,
            'sourceUrl' => $this->sourceUrl,
            'name' => $this->name,
            'brand' => $this->brand,
            'description' => $this->description,
            'categories' => $this->categories,
            'priceJpy' => $this->priceJpy,
            'currency' => $this->currency,
            'images' => array_map(static fn (ProductImageSnapshot $image): array => [
                'url' => $image->url,
                'altText' => $image->altText,
                'position' => $image->position,
                'source' => $image->source,
            ], $this->images),
            'options' => array_map(static fn (ProductOptionSnapshot $option): array => [
                'name' => $option->name,
                'values' => $option->values,
            ], $this->options),
            'reviews' => array_map(static fn (ProductReviewSnapshot $review): array => [
                'origin' => $review->origin,
                'provider' => $review->provider,
                'author' => $review->author,
                'body' => $review->body,
                'rating' => $review->rating,
                'publishedAt' => $review->publishedAt,
                'publishable' => $review->publishable,
            ], $this->reviews),
            'sourceRating' => $this->sourceRating,
            'sourceReviewCount' => $this->sourceReviewCount,
            'availability' => $this->availability,
            'approvalStatus' => $this->approvalStatus,
            'fetchedAt' => $this->fetchedAt->format(DATE_ATOM),
            'contentHash' => $this->contentHash,
        ];
    }

    /** @param array<string, mixed> $data */
    public static function fromArray(array $data): self
    {
        $images = [];
        foreach (self::arrayList($data, 'images') as $image) {
            if (!is_array($image)) {
                throw new \UnexpectedValueException('Persisted catalog image data is invalid.');
            }
            $images[] = new ProductImageSnapshot(
                self::requiredString($image, 'url'),
                self::requiredString($image, 'altText'),
                self::requiredInt($image, 'position'),
                self::requiredString($image, 'source')
            );
        }

        $options = [];
        foreach (self::arrayList($data, 'options') as $option) {
            if (!is_array($option)) {
                throw new \UnexpectedValueException('Persisted catalog option data is invalid.');
            }
            $values = $option['values'] ?? null;
            if (!is_array($values) || !array_is_list($values)) {
                throw new \UnexpectedValueException('Persisted catalog option values are invalid.');
            }
            foreach ($values as $value) {
                if (!is_string($value)) {
                    throw new \UnexpectedValueException('Persisted catalog option value is invalid.');
                }
            }
            $options[] = new ProductOptionSnapshot(self::requiredString($option, 'name'), $values);
        }

        $reviews = [];
        foreach (self::arrayList($data, 'reviews') as $review) {
            if (!is_array($review)) {
                throw new \UnexpectedValueException('Persisted catalog review data is invalid.');
            }
            $reviews[] = new ProductReviewSnapshot(
                self::requiredString($review, 'origin'),
                self::requiredString($review, 'provider'),
                self::nullableString($review, 'author'),
                self::nullableString($review, 'body'),
                self::nullableFloat($review, 'rating'),
                self::nullableString($review, 'publishedAt'),
                self::requiredBool($review, 'publishable')
            );
        }

        $categories = self::arrayList($data, 'categories');
        foreach ($categories as $category) {
            if (!is_string($category)) {
                throw new \UnexpectedValueException('Persisted catalog category is invalid.');
            }
        }
        $fetchedAt = self::requiredString($data, 'fetchedAt');
        try {
            $date = new DateTimeImmutable($fetchedAt);
        } catch (\Throwable $exception) {
            throw new \UnexpectedValueException('Persisted catalog fetch time is invalid.', 0, $exception);
        }

        return new self(
            self::requiredString($data, 'source'),
            self::requiredString($data, 'sourceProductId'),
            self::requiredString($data, 'deduplicationKey'),
            self::requiredString($data, 'sourceUrl'),
            self::requiredString($data, 'name'),
            self::nullableString($data, 'brand'),
            self::nullableString($data, 'description'),
            $categories,
            self::requiredInt($data, 'priceJpy'),
            self::requiredString($data, 'currency'),
            $images,
            $options,
            $reviews,
            self::nullableFloat($data, 'sourceRating'),
            self::nullableInt($data, 'sourceReviewCount'),
            self::nullableString($data, 'availability'),
            self::requiredString($data, 'approvalStatus'),
            $date,
            self::requiredString($data, 'contentHash')
        );
    }

    /** @return list<mixed> */
    private static function arrayList(array $data, string $key): array
    {
        $value = $data[$key] ?? null;
        if (!is_array($value) || !array_is_list($value)) {
            throw new \UnexpectedValueException('Persisted catalog list is invalid: ' . $key);
        }

        return $value;
    }

    private static function requiredString(array $data, string $key): string
    {
        $value = $data[$key] ?? null;
        if (!is_string($value)) {
            throw new \UnexpectedValueException('Persisted catalog text is invalid: ' . $key);
        }

        return $value;
    }

    private static function nullableString(array $data, string $key): ?string
    {
        $value = $data[$key] ?? null;
        if ($value !== null && !is_string($value)) {
            throw new \UnexpectedValueException('Persisted catalog optional text is invalid: ' . $key);
        }

        return $value;
    }

    private static function requiredInt(array $data, string $key): int
    {
        $value = $data[$key] ?? null;
        if (!is_int($value)) {
            throw new \UnexpectedValueException('Persisted catalog integer is invalid: ' . $key);
        }

        return $value;
    }

    private static function nullableInt(array $data, string $key): ?int
    {
        $value = $data[$key] ?? null;
        if ($value !== null && !is_int($value)) {
            throw new \UnexpectedValueException('Persisted catalog optional integer is invalid: ' . $key);
        }

        return $value;
    }

    private static function nullableFloat(array $data, string $key): ?float
    {
        $value = $data[$key] ?? null;
        if ($value !== null && !is_float($value) && !is_int($value)) {
            throw new \UnexpectedValueException('Persisted catalog optional number is invalid: ' . $key);
        }

        return $value === null ? null : (float) $value;
    }

    private static function requiredBool(array $data, string $key): bool
    {
        $value = $data[$key] ?? null;
        if (!is_bool($value)) {
            throw new \UnexpectedValueException('Persisted catalog boolean is invalid: ' . $key);
        }

        return $value;
    }
}
