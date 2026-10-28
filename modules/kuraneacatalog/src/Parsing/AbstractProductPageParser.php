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
use Kuranea\Catalog\Fetching\ProductUrlPolicy;
use Kuranea\Catalog\Fetching\PublicAddressPolicy;
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
        if (strlen($html) > \Kuranea\Catalog\Fetching\PublicProductFetcher::MAX_DECODED_BYTES) {
            throw new CatalogParseException('원본 HTML 스냅샷이 허용 크기를 초과했습니다.');
        }
        try { $html = HtmlDocumentEncoding::utf8($html); } catch (Throwable $error) {
            throw new CatalogParseException('원본 HTML 문자 인코딩을 확인할 수 없습니다.', 0, $error);
        }
        $xpath = $this->loadHtml($html);
        $this->rejectAccessChallenge($html);
        $documents = $this->structuredDocuments($xpath);
        $product = $this->selectStructuredProduct($documents, $sourceUrl);
        $product = $this->resolveReferences($product, $documents);
        if ($product === []) {
            $product = $this->htmlProduct($xpath);
        }

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

        foreach ($this->breadcrumbCategories($documents, $sourceUrl, $name) as $path) {
            if (!in_array($path, $categories, true)) $categories[] = $path;
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
        try {
            $target = ProductUrlPolicy::canonicalize(trim($sourceUrl));
            if ($target['provider'] !== static::PROVIDER) throw new \RuntimeException();
            return $target['url'];
        } catch (Throwable $error) {
            throw new CatalogParseException('원본 URL이 지원하는 HTTPS 상품 주소가 아닙니다.', 0, $error);
        }
    }

    private function rejectAccessChallenge(string $html): void
    {
        if (preg_match('~(?:validateCaptcha|captchaContainer|captcha\.amazon\.com|robot\s+check|画像認証|アクセスを確認してください|不正なアクセスを検知)~iu', $html) === 1
            || \Kuranea\Catalog\Fetching\AuthenticationPage::present($html)) {
            throw new CatalogParseException('원본 사이트의 접근 제한 또는 로그인 화면입니다.');
        }
    }

    /** Only explicit public product fields, never scripts requiring execution or guessed values. */
    protected function htmlProduct(DOMXPath $xpath): array
    {
        $nodes = $xpath->query('//*[@itemscope and (@itemtype="https://schema.org/Product" or @itemtype="http://schema.org/Product")]');
        if ($nodes === false || $nodes->length === 0) return [];
        if ($nodes->length !== 1) throw new CatalogParseException('HTML에 여러 상품이 있어 원본 상품을 확정할 수 없습니다.');
        $scope = $nodes->item(0);
        $data = [];
        foreach (['name', 'description', 'category', 'brand'] as $key) {
            $data[$key] = $this->nodeValue($xpath, './/*[@itemprop="' . $key . '"]', $scope);
        }
        $data['offers'] = [
            'price' => $this->nodeValue($xpath, './/*[@itemprop="price"]', $scope),
            'priceCurrency' => $this->nodeValue($xpath, './/*[@itemprop="priceCurrency"]', $scope),
            'availability' => $this->nodeValue($xpath, './/*[@itemprop="availability"]', $scope),
        ];
        $data['image'] = [];
        foreach ($xpath->query('.//*[@itemprop="image"]', $scope) ?: [] as $image) {
            if ($image instanceof DOMElement) $data['image'][] = $image->getAttribute('content') ?: $image->getAttribute('src') ?: $image->getAttribute('href');
        }
        return $data;
    }

    protected function nodeValue(DOMXPath $xpath, string $query, ?\DOMNode $context = null): string
    {
        $node = $xpath->query($query, $context)?->item(0);
        if (!$node instanceof DOMElement) return '';
        return $this->cleanText($node->getAttribute('content') ?: $node->getAttribute('value') ?: $node->getAttribute('href') ?: ($node->ownerDocument?->saveHTML($node) ?: $node->textContent));
    }

    private function loadHtml(string $html): DOMXPath
    {
        if ($html === '' || strlen($html) > \Kuranea\Catalog\Fetching\PublicProductFetcher::MAX_DECODED_BYTES) {
            throw new CatalogParseException('분석할 HTML 스냅샷이 비어 있거나 허용 크기를 초과했습니다.');
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

    /** @return list<array> */
    private function structuredDocuments(DOMXPath $xpath): array
    {
        $documents = [];
        foreach ($xpath->query('//script') ?: [] as $script) {
            if (!$script instanceof DOMElement || !str_contains(strtolower($script->getAttribute('type')), 'application/ld+json')) continue;
            try {
                $data = json_decode(trim($script->textContent), true, 64, JSON_THROW_ON_ERROR | JSON_BIGINT_AS_STRING);
                if (is_array($data)) $documents[] = $data;
            } catch (Throwable) { /* Other page metadata may contain malformed unrelated JSON-LD. */ }
        }
        return $documents;
    }

    private function selectStructuredProduct(array $documents, string $sourceUrl): array
    {
        $products = [];
        foreach ($documents as $document) $products = array_merge($products, $this->findProducts($document));
        if ($products === []) return [];
        $matched = [];
        foreach ($products as $product) {
            $url = $product['url'] ?? $product['@id'] ?? null;
            if (is_array($url)) $url = $url['@id'] ?? null;
            if (is_string($url) && str_starts_with($url, 'https://')) {
                try {
                    if (ProductUrlPolicy::canonicalize($url)['url'] === $sourceUrl) $matched[] = $product;
                } catch (Throwable) { /* A non-product @id is not an explicit product identity. */ }
            }
        }
        if (count($matched) === 1) return $matched[0];
        if (count($products) === 1 && $matched === []) {
            $product = $products[0];
            foreach (['url', '@id'] as $field) {
                $url = $product[$field] ?? null;
                if (is_array($url)) $url = $url['@id'] ?? null;
                if (!is_string($url) || !str_starts_with($url, 'https://')) continue;
                try { $other = ProductUrlPolicy::canonicalize($url); } catch (Throwable $error) {
                    if ($field === 'url') throw new CatalogParseException('구조화 상품 URL이 요청한 원본 상품과 다릅니다.', 0, $error);
                    continue;
                }
                if ($other['url'] !== $sourceUrl) throw new CatalogParseException('구조화 상품 식별자가 요청한 원본 상품과 다릅니다.');
            }
            return $product;
        }
        throw new CatalogParseException('여러 구조화 상품 중 원본 상품을 확정할 수 없습니다.');
    }

    private function resolveReferences(array $product, array $documents): array
    {
        $index = [];
        $collect = function (mixed $value) use (&$collect, &$index): void {
            if (!is_array($value)) return;
            if (is_string($value['@id'] ?? null) && count($value) > 1) $index[$value['@id']] = $value;
            foreach ($value as $child) if (is_array($child)) $collect($child);
        };
        foreach ($documents as $document) $collect($document);
        $resolve = function (mixed $value, array $seen = [], int $depth = 0) use (&$resolve, $index): mixed {
            if (!is_array($value) || $depth > 16) return $value;
            $id = $value['@id'] ?? null;
            if (is_string($id) && isset($index[$id]) && !isset($seen[$id])) {
                $seen[$id] = true;
                $value = array_replace($index[$id], $value);
            }
            foreach ($value as $key => $child) if (is_array($child)) $value[$key] = $resolve($child, $seen, $depth + 1);
            return $value;
        };
        return $resolve($product);
    }

    /** Source breadcrumb paths stay provenance; staff choose native shop categories separately. */
    private function breadcrumbCategories(array $documents, string $sourceUrl, string $productName): array
    {
        $paths = [];
        $walk = function (mixed $value) use (&$walk, &$paths, $sourceUrl, $productName): void {
            if (!is_array($value)) return;
            if ($this->hasSchemaType($value, 'BreadcrumbList')) {
                $labels = [];
                foreach ($this->asList($value['itemListElement'] ?? null) as $item) {
                    if (!is_array($item) || !is_scalar($item['position'] ?? null) || preg_match('/\A[1-9][0-9]{0,2}\z/D', (string) $item['position']) !== 1) return;
                    $position = (int) $item['position'];
                    if (isset($labels[$position])) return;
                    $data = $item['item'] ?? [];
                    $label = $this->cleanText($item['name'] ?? (is_array($data) ? ($data['name'] ?? '') : ''));
                    if ($label === '') return;
                    $url = is_string($data) ? $data : ($data['@id'] ?? $data['url'] ?? '');
                    if ($label === $productName || (is_string($url) && rtrim($url, '/') === rtrim($sourceUrl, '/'))) continue;
                    $labels[$position] = $label;
                }
                ksort($labels, SORT_NUMERIC);
                if ($labels !== []) $paths[] = implode(' > ', $labels);
                return;
            }
            foreach ($value as $child) if (is_array($child)) $walk($child);
        };
        foreach ($documents as $document) $walk($document);
        return array_values(array_unique($paths));
    }

    /** @return list<array<string, mixed>> */
    private function findProducts(mixed $value): array
    {
        if (!is_array($value)) {
            return [];
        }

        if ($this->hasSchemaType($value, 'Product')) {
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

    private function hasSchemaType(array $value, string $type): bool
    {
        $types = $this->asList($value['@type'] ?? null);
        foreach ([$type, 'http://schema.org/' . $type, 'https://schema.org/' . $type] as $expected) {
            if (in_array($expected, $types, true)) return true;
        }
        return false;
    }

    /** @return array{amount: string, currency: string, availability: ?string} */
    private function extractPrice(array $product, DOMXPath $xpath): array
    {
        $offers = $this->asList($product['offers'] ?? null);
        $firstUsableOffer = null;
        $jpyOffer = null;
        foreach ($offers as $offer) {
            if (!is_array($offer)) {
                continue;
            }

            $currency = strtoupper($this->cleanText($offer['priceCurrency'] ?? ''));
            $amount = $offer['price'] ?? $offer['lowPrice'] ?? null;
            if ($currency === '' || (!is_string($amount) && !is_int($amount) && !is_float($amount))) {
                continue;
            }

            if (is_float($amount)) throw new CatalogParseException('정확한 정수 엔 가격을 확인할 수 없습니다. 소수 JSON 숫자는 지원하지 않습니다.');
            $candidate = [
                'amount' => (string) $amount,
                'currency' => $currency,
                'availability' => $this->nullableText($offer['availability'] ?? null),
            ];
            $firstUsableOffer ??= $candidate;
            if ($currency === 'JPY') {
                if ($jpyOffer !== null && $this->toJpyAmount($jpyOffer['amount']) !== $this->toJpyAmount($candidate['amount'])) {
                    throw new CatalogParseException('옵션 또는 판매자별 가격이 달라 단일 참고 가격을 확정할 수 없습니다.');
                }
                $jpyOffer = $candidate;
            }
        }

        if ($jpyOffer !== null) return $jpyOffer;

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
        // Parse decimal text exactly: float conversion silently rounds fractional yen and large integers.
        $amount = trim($amount);
        $amount = preg_replace('/\A[¥￥]\s*/u', '', $amount) ?? '';
        if (preg_match('/\A(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)(?:\.0+)?\z/D', $amount) !== 1) {
            throw new CatalogParseException('JPY 가격은 0보다 큰 정수 엔 단위여야 합니다.');
        }
        $integer = ltrim(explode('.', str_replace(',', '', $amount), 2)[0], '0');
        $maximum = (string) PHP_INT_MAX;
        if ($integer === '' || strlen($integer) > strlen($maximum) || (strlen($integer) === strlen($maximum) && strcmp($integer, $maximum) > 0)) {
            throw new CatalogParseException('JPY 가격이 지원하는 정수 범위를 벗어났습니다.');
        }
        return (int) $integer;
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
        $host = strtolower((string) ($parts['host'] ?? ''));
        if (filter_var($url, FILTER_VALIDATE_URL) === false
            || !in_array(strtolower((string) ($parts['scheme'] ?? '')), ['https', 'http'], true)
            || !str_contains($host, '.') || isset($parts['user']) || isset($parts['pass'])
            || (isset($parts['port']) && !in_array($parts['port'], [80, 443], true))) return false;
        if (filter_var(trim($host, '[]'), FILTER_VALIDATE_IP) !== false) {
            try { PublicAddressPolicy::validate([trim($host, '[]')]); } catch (Throwable) { return false; }
        }
        return !preg_match('/(?:^|\.)(?:localhost|local|internal|test.invalid)$/i', $host);
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

    protected function cleanText(mixed $value): string
    {
        if (!is_scalar($value)) {
            return '';
        }

        $text = html_entity_decode((string) $value, ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $text = preg_replace('~<(script|style)\b[^>]*>.*?</\1\s*>~is', '', $text) ?? $text;
        $text = preg_replace('~</?(?:p|div|li|ul|ol|br|h[1-6]|section|table|tr|td)\b[^>]*>~i', ' ', $text) ?? $text;
        $text = strip_tags($text);
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
