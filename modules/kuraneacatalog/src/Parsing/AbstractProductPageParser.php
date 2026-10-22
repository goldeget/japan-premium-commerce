<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Parsing;

use DateTimeImmutable;
use DateTimeZone;
use DOMDocument;
use DOMElement;
use DOMXPath;
use Kuranea\Catalog\Domain\CatalogParseException;
use Kuranea\Catalog\Domain\NormalizedProductSnapshot;
use Kuranea\Catalog\Domain\ProductImageSnapshot;
use Kuranea\Catalog\Domain\ProductOptionSnapshot;
use Kuranea\Catalog\Domain\ProductReviewSnapshot;
use Throwable;

abstract class AbstractProductPageParser implements ProductPageParserInterface
{
    protected const PROVIDER = '';

    /** @var list<string> */
    protected const ALLOWED_HOSTS = [];

    final public function parse(
        string $html,
        string $sourceUrl,
        ?DateTimeImmutable $fetchedAt = null
    ): NormalizedProductSnapshot {
        $sourceUrl = $this->validateSourceUrl($sourceUrl);
        $xpath = $this->loadHtml($html);
        $product = $this->firstStructuredProduct($xpath);

        $name = $this->cleanText($product['name'] ?? '')
            ?: $this->firstMeta($xpath, ['og:title', 'twitter:title', 'name']);
        if ($name === '') {
            throw new CatalogParseException('상품명 JSON-LD 또는 Open Graph 정보를 찾지 못했습니다.');
        }

        $sourceProductId = $this->extractProductId($product, $sourceUrl);
        if ($sourceProductId === '') {
            throw new CatalogParseException('원본 상품 식별자를 확인하지 못했습니다.');
        }

        $price = $this->extractPrice($product, $xpath);
        $priceJpy = $this->toJpyAmount($price['amount']);
        $currency = strtoupper($price['currency']);
        if ($currency !== 'JPY') {
            throw new CatalogParseException('지원하지 않는 원본 통화입니다. 일본 상품은 JPY 가격만 허용됩니다.');
        }

        $brand = $this->normalizeBrand($product['brand'] ?? null)
            ?: $this->firstMeta($xpath, ['product:brand', 'brand']);
        $description = $this->cleanText($product['description'] ?? '')
            ?: $this->firstMeta($xpath, ['og:description', 'description']);
        $categories = $this->normalizeCategories($product['category'] ?? null);
        if ($categories === []) {
            $category = $this->firstMeta($xpath, ['product:category', 'category']);
            $categories = $category === '' ? [] : [$category];
        }

        $images = $this->normalizeImages($product['image'] ?? null, $xpath);
        $options = $this->normalizeOptions($product['additionalProperty'] ?? null);
        $reviews = $this->normalizeReviews($product['review'] ?? null);
        $aggregateRating = is_array($product['aggregateRating'] ?? null) ? $product['aggregateRating'] : [];
        $rating = $this->normalizeRating($aggregateRating['ratingValue'] ?? null);
        $reviewCount = $this->normalizeCount($aggregateRating['reviewCount'] ?? $aggregateRating['ratingCount'] ?? null);

        $snapshotData = [
            'source' => static::PROVIDER,
            'sourceProductId' => $sourceProductId,
            'sourceUrl' => $sourceUrl,
            'name' => $name,
            'brand' => $brand,
            'description' => $description,
            'categories' => $categories,
            'priceJpy' => $priceJpy,
            'currency' => $currency,
            'images' => array_map(static fn (ProductImageSnapshot $image): array => [
                'url' => $image->url,
                'altText' => $image->altText,
                'position' => $image->position,
                'source' => $image->source,
            ], $images),
            'options' => array_map(static fn (ProductOptionSnapshot $option): array => [
                'name' => $option->name,
                'values' => $option->values,
            ], $options),
            'reviews' => array_map(static fn (ProductReviewSnapshot $review): array => [
                'origin' => $review->origin,
                'provider' => $review->provider,
                'author' => $review->author,
                'body' => $review->body,
                'rating' => $review->rating,
                'publishedAt' => $review->publishedAt,
                'publishable' => $review->publishable,
            ], $reviews),
            'sourceRating' => $rating,
            'sourceReviewCount' => $reviewCount,
            'availability' => $price['availability'],
        ];

        try {
            $contentHash = hash('sha256', json_encode(
                $snapshotData,
                JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR
            ));
        } catch (Throwable $exception) {
            throw new CatalogParseException('상품 스냅샷 지문을 생성하지 못했습니다.', 0, $exception);
        }

        return new NormalizedProductSnapshot(
            static::PROVIDER,
            $sourceProductId,
            static::PROVIDER . ':' . $sourceProductId,
            $sourceUrl,
            $name,
            $brand === '' ? null : $brand,
            $description === '' ? null : $description,
            $categories,
            $priceJpy,
            $currency,
            $images,
            $options,
            $reviews,
            $rating,
            $reviewCount,
            $price['availability'],
            'pending',
            $fetchedAt ?? new DateTimeImmutable('now', new DateTimeZone('UTC')),
            $contentHash
        );
    }

    abstract protected function extractProductId(array $product, string $sourceUrl): string;

    private function validateSourceUrl(string $sourceUrl): string
    {
        $sourceUrl = trim($sourceUrl);
        $parts = parse_url($sourceUrl);
        $scheme = strtolower((string) ($parts['scheme'] ?? ''));
        $host = strtolower(rtrim((string) ($parts['host'] ?? ''), '.'));

        if ($scheme !== 'https'
            || !in_array($host, static::ALLOWED_HOSTS, true)
            || isset($parts['user'])
            || isset($parts['pass'])
            || (isset($parts['port']) && (int) $parts['port'] !== 443)) {
            throw new CatalogParseException('원본 URL이 지원하는 HTTPS 상품 도메인이 아닙니다.');
        }

        return $sourceUrl;
    }

    private function loadHtml(string $html): DOMXPath
    {
        if ($html === '') {
            throw new CatalogParseException('분석할 HTML 스냅샷이 비어 있습니다.');
        }

        $document = new DOMDocument('1.0', 'UTF-8');
        $previous = libxml_use_internal_errors(true);
        try {
            $loaded = $document->loadHTML(
                '<?xml encoding="UTF-8">' . $html,
                LIBXML_NONET | LIBXML_NOWARNING | LIBXML_NOERROR | LIBXML_COMPACT
            );
        } finally {
            libxml_clear_errors();
            libxml_use_internal_errors($previous);
        }

        if (!$loaded) {
            throw new CatalogParseException('HTML 스냅샷을 분석할 수 없습니다.');
        }

        return new DOMXPath($document);
    }

    private function firstStructuredProduct(DOMXPath $xpath): array
    {
        foreach ($xpath->query('//script') ?: [] as $script) {
            if (!$script instanceof DOMElement
                || !str_contains(strtolower((string) $script->getAttribute('type')), 'application/ld+json')) {
                continue;
            }

            try {
                $data = json_decode(trim($script->textContent), true, 512, JSON_THROW_ON_ERROR);
            } catch (Throwable) {
                continue;
            }

            $products = $this->findProducts($data);
            if ($products !== []) {
                return $products[0];
            }
        }

        return [];
    }

    /** @return list<array<string, mixed>> */
    private function findProducts(mixed $value): array
    {
        if (!is_array($value)) {
            return [];
        }

        $types = $value['@type'] ?? [];
        $types = is_array($types) ? $types : [$types];
        if (in_array('Product', $types, true)) {
            return [$value];
        }

        $products = [];
        foreach ($value as $child) {
            if (is_array($child)) {
                $products = array_merge($products, $this->findProducts($child));
            }
        }

        return $products;
    }

    /** @return array{amount: string, currency: string, availability: ?string} */
    private function extractPrice(array $product, DOMXPath $xpath): array
    {
        $offers = $this->asList($product['offers'] ?? null);
        $firstUsableOffer = null;
        foreach ($offers as $offer) {
            if (!is_array($offer)) {
                continue;
            }

            $currency = strtoupper($this->cleanText($offer['priceCurrency'] ?? ''));
            $amount = $offer['price'] ?? $offer['lowPrice'] ?? null;
            if ($currency === '' || $amount === null) {
                continue;
            }

            $candidate = [
                'amount' => (string) $amount,
                'currency' => $currency,
                'availability' => $this->nullableText($offer['availability'] ?? null),
            ];
            $firstUsableOffer ??= $candidate;
            if ($currency === 'JPY') {
                return $candidate;
            }
        }

        if ($firstUsableOffer !== null) {
            return $firstUsableOffer;
        }

        return [
            'amount' => $this->firstMeta($xpath, ['product:price:amount', 'og:price:amount']),
            'currency' => strtoupper($this->firstMeta($xpath, ['product:price:currency', 'og:price:currency'])),
            'availability' => $this->nullableText($this->firstMeta($xpath, ['product:availability', 'og:availability'])),
        ];
    }

    private function toJpyAmount(string $amount): int
    {
        $amount = str_replace([',', ' ', '¥', '￥'], '', trim($amount));
        if ($amount === '' || !is_numeric($amount)) {
            throw new CatalogParseException('상품 가격을 확인하지 못했습니다.');
        }

        $numericAmount = (float) $amount;
        if ($numericAmount <= 0 || $numericAmount > PHP_INT_MAX || floor($numericAmount) !== $numericAmount) {
            throw new CatalogParseException('JPY 가격은 0보다 큰 정수 엔 단위여야 합니다.');
        }

        return (int) $numericAmount;
    }

    private function normalizeBrand(mixed $brand): string
    {
        if (is_string($brand)) {
            return $this->cleanText($brand);
        }
        if (is_array($brand)) {
            return $this->cleanText($brand['name'] ?? '');
        }

        return '';
    }

    /** @return list<string> */
    private function normalizeCategories(mixed $category): array
    {
        $categories = [];
        foreach ($this->asList($category) as $item) {
            $name = is_array($item) ? ($item['name'] ?? '') : $item;
            $name = $this->cleanText($name);
            if ($name !== '' && !in_array($name, $categories, true)) {
                $categories[] = $name;
            }
        }

        return $categories;
    }

    /** @return list<ProductImageSnapshot> */
    private function normalizeImages(mixed $images, DOMXPath $xpath): array
    {
        $items = $this->asList($images);
        if ($items === []) {
            $metaImage = $this->firstMeta($xpath, ['og:image', 'twitter:image']);
            if ($metaImage !== '') {
                $items[] = [
                    'url' => $metaImage,
                    'caption' => $this->firstMeta($xpath, ['og:image:alt', 'twitter:image:alt']),
                ];
            }
        }

        $normalized = [];
        $seen = [];
        foreach ($items as $item) {
            if (is_string($item)) {
                $url = trim($item);
                $alt = '';
            } elseif (is_array($item)) {
                $url = trim((string) ($item['url'] ?? $item['contentUrl'] ?? ''));
                $alt = $this->cleanText($item['caption'] ?? $item['name'] ?? $item['description'] ?? '');
            } else {
                continue;
            }

            if (!$this->isSafeAbsoluteImageUrl($url) || isset($seen[$url])) {
                continue;
            }

            $seen[$url] = true;
            $normalized[] = new ProductImageSnapshot($url, $alt, count($normalized), static::PROVIDER);
        }

        return $normalized;
    }

    private function isSafeAbsoluteImageUrl(string $url): bool
    {
        $parts = parse_url($url);
        return filter_var($url, FILTER_VALIDATE_URL) !== false
            && in_array(strtolower((string) ($parts['scheme'] ?? '')), ['https', 'http'], true)
            && trim((string) ($parts['host'] ?? '')) !== ''
            && !isset($parts['user'])
            && !isset($parts['pass']);
    }

    /** @return list<ProductOptionSnapshot> */
    private function normalizeOptions(mixed $properties): array
    {
        $groups = [];
        foreach ($this->asList($properties) as $property) {
            if (!is_array($property)) {
                continue;
            }

            $name = $this->cleanText($property['name'] ?? '');
            if ($name === '') {
                continue;
            }

            $values = $this->asList($property['value'] ?? $property['valueReference'] ?? null);
            foreach ($values as $value) {
                if (is_array($value)) {
                    $value = $value['name'] ?? $value['value'] ?? '';
                }
                $value = $this->cleanText($value);
                if ($value !== '' && !in_array($value, $groups[$name] ?? [], true)) {
                    $groups[$name][] = $value;
                }
            }
        }

        $options = [];
        foreach ($groups as $name => $values) {
            $options[] = new ProductOptionSnapshot($name, array_values($values));
        }

        return $options;
    }

    /** @return list<ProductReviewSnapshot> */
    private function normalizeReviews(mixed $reviews): array
    {
        $normalized = [];
        foreach ($this->asList($reviews) as $review) {
            if (!is_array($review)) {
                continue;
            }

            $author = $review['author']['name'] ?? $review['author'] ?? null;
            $ratingValue = $review['reviewRating']['ratingValue'] ?? null;
            $normalized[] = new ProductReviewSnapshot(
                'source_site',
                static::PROVIDER,
                $this->nullableText($author),
                $this->nullableText($review['reviewBody'] ?? $review['description'] ?? null),
                $this->normalizeRating($ratingValue),
                $this->nullableText($review['datePublished'] ?? null),
                false
            );
        }

        return $normalized;
    }

    private function normalizeRating(mixed $rating): ?float
    {
        if (!is_scalar($rating) || !is_numeric((string) $rating)) {
            return null;
        }

        return (float) $rating;
    }

    private function normalizeCount(mixed $count): ?int
    {
        if (!is_scalar($count) || preg_match('/\A\d+\z/', trim((string) $count)) !== 1) {
            return null;
        }

        return (int) $count;
    }

    private function firstMeta(DOMXPath $xpath, array $keys): string
    {
        foreach ($keys as $key) {
            $escapedKey = htmlspecialchars($key, ENT_QUOTES | ENT_XML1, 'UTF-8');
            $nodes = $xpath->query('//meta[@property="' . $escapedKey . '" or @name="' . $escapedKey . '" or @itemprop="' . $escapedKey . '"]/@content');
            if ($nodes !== false && $nodes->length > 0) {
                $value = $this->cleanText($nodes->item(0)?->nodeValue ?? '');
                if ($value !== '') {
                    return $value;
                }
            }
        }

        return '';
    }

    private function cleanText(mixed $value): string
    {
        if (!is_scalar($value)) {
            return '';
        }

        $text = html_entity_decode(strip_tags((string) $value), ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $text = preg_replace('/\s+/u', ' ', $text) ?? $text;
        return trim($text);
    }

    private function nullableText(mixed $value): ?string
    {
        $text = $this->cleanText($value);
        return $text === '' ? null : $text;
    }

    /** @return list<mixed> */
    private function asList(mixed $value): array
    {
        if ($value === null) {
            return [];
        }

        return is_array($value) && array_is_list($value) ? $value : [$value];
    }
}
