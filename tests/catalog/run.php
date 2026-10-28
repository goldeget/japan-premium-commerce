<?php

declare(strict_types=1);

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

use Kuranea\Catalog\Domain\CatalogParseException;
use Kuranea\Catalog\Domain\ProductReviewQueue;
use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;
use Kuranea\Catalog\Parsing\RakutenHtmlParser;

function assertCatalogSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertCatalogTrue(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

function assertCatalogThrows(callable $callback, string $message): void
{
    try {
        $callback();
    } catch (CatalogParseException) {
        return;
    }

    throw new RuntimeException($message);
}

function fixture(string $name): string
{
    $path = __DIR__ . '/fixtures/' . $name;
    $contents = file_get_contents($path);
    if ($contents === false) {
        throw new RuntimeException('Could not read the local synthetic fixture: ' . $name);
    }

    return $contents;
}

$fetchedAt = new DateTimeImmutable('2026-10-22T12:30:00+00:00');
$amazonUrl = 'https://www.amazon.co.jp/dp/B0KURANEA1';
$amazonParser = new AmazonJapanHtmlParser();
$amazon = $amazonParser->parse(fixture('amazon-jp-product.synthetic.html'), $amazonUrl, $fetchedAt);

assertCatalogSame('amazon_jp', $amazon->source, 'Amazon parser should retain the source provider.');
assertCatalogSame('B0KURANEA1', $amazon->sourceProductId, 'Amazon ASIN in the product URL should be the source identity.');
assertCatalogSame('amazon_jp:B0KURANEA1', $amazon->deduplicationKey, 'Source plus product ID should form a stable deduplication key.');
assertCatalogSame('[TEST FIXTURE] 合成キッチンツール A', $amazon->name, 'Amazon product name should be parsed from JSON-LD.');
assertCatalogSame('KURANEA Fixture Lab', $amazon->brand, 'Brand objects should normalize to their name.');
assertCatalogSame(['生活用品 > キッチン用品'], $amazon->categories, 'Product categories should be retained.');
assertCatalogSame(5980, $amazon->priceJpy, 'JPY price should normalize to an integer yen amount.');
assertCatalogSame('JPY', $amazon->currency, 'Japanese source price should preserve its validated currency.');
assertCatalogSame(2, count($amazon->images), 'All supplied product images should be retained.');
assertCatalogSame('合成メイン画像', $amazon->images[0]->altText, 'ImageObject captions should normalize into image metadata.');
assertCatalogSame('amazon_jp', $amazon->images[0]->source, 'Image source should be traceable to the provider.');
assertCatalogSame('藍色', $amazon->options[0]->values[0], 'Product option values should be retained.');
assertCatalogSame(['M', 'L'], $amazon->options[1]->values, 'Repeated property names should combine their values.');
$amazonReviewFixture = $amazonParser->parse(
    fixture('amazon-jp-review-single-option.synthetic.html'),
    $amazonUrl,
    $fetchedAt
);
assertCatalogSame(1, count($amazonReviewFixture->options), 'The browser approval fixture should expose one supported option group.');
assertCatalogSame('サイズ', $amazonReviewFixture->options[0]->name, 'The approval option group should retain its source label.');
assertCatalogSame(['M', 'L'], $amazonReviewFixture->options[0]->values, 'The approval option values should remain distinct and ordered.');
assertCatalogSame('pending', $amazon->approvalStatus, 'Parsed products should require manual review.');
assertCatalogSame('2026-10-22T12:30:00+00:00', $amazon->fetchedAt->format(DateTimeInterface::ATOM), 'Fetch time should be recorded.');
assertCatalogTrue((bool) preg_match('/\A[a-f0-9]{64}\z/', $amazon->contentHash), 'Normalized content should have a SHA-256 update fingerprint.');
assertCatalogSame('source_site', $amazon->reviews[0]->origin, 'Imported source reviews must be marked as source-site reviews.');
assertCatalogSame(false, $amazon->reviews[0]->publishable, 'Source-site reviews must not be publishable by default.');
assertCatalogSame(4.5, $amazon->sourceRating, 'Aggregate product ratings should be attributed to the source.');
assertCatalogSame(2, $amazon->sourceReviewCount, 'Aggregate review counts should be attributed to the source.');

$reviewQueue = new ProductReviewQueue();
$queueEntry = $reviewQueue->enqueue($amazon, $fetchedAt);
assertCatalogSame('amazon_jp:B0KURANEA1', $queueEntry->idempotencyKey, 'The review queue should use the provider product identity.');
assertCatalogSame(ProductReviewQueueEntry::STATUS_PENDING, $queueEntry->status, 'New catalog entries must await review.');
assertCatalogSame(1, count($reviewQueue->pending()), 'A new product should appear once in the pending review queue.');
assertCatalogTrue($reviewQueue->enqueue($amazon, $fetchedAt) === $queueEntry, 'Re-importing identical content should be idempotent.');

$amazonPriceChangedHtml = str_replace('"price": "5980"', '"price": "5990"', fixture('amazon-jp-product.synthetic.html'));
$amazonPriceChanged = $amazonParser->parse($amazonPriceChangedHtml, $amazonUrl, $fetchedAt->modify('+1 second'));
assertCatalogSame($amazon->deduplicationKey, $amazonPriceChanged->deduplicationKey, 'Price updates should not create a duplicate source product.');
assertCatalogTrue($amazon->contentHash !== $amazonPriceChanged->contentHash, 'Product changes should update the content fingerprint.');
$updatedQueueEntry = $reviewQueue->enqueue($amazonPriceChanged, $amazonPriceChanged->fetchedAt);
assertCatalogSame(1, count($reviewQueue->pending()), 'Changed source content should update, not duplicate, a pending review entry.');
assertCatalogSame($amazonPriceChanged->contentHash, $updatedQueueEntry->snapshot->contentHash, 'A changed snapshot should replace the queued content.');

$rakutenParser = new RakutenHtmlParser();
$rakutenUrl = 'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/';
assertCatalogThrows(
    static fn () => $rakutenParser->parse(fixture('rakuten-product.synthetic.html'), $rakutenUrl, $fetchedAt),
    'An aggregate price range must be rejected rather than reported as an exact minimum price.'
);
// Keep the historical unequal-range fixture as a rejection case. A separate
// observed equal-bound document supplies an unambiguous price for identity tests.
$exactRakutenFixture = static fn (string $html): string => str_replace('"highPrice": "2980"', '"highPrice": "2480"', $html);
$rakuten = $rakutenParser->parse(
    $exactRakutenFixture(fixture('rakuten-product.synthetic.html')),
    'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/',
    $fetchedAt
);
assertCatalogSame('rakuten_ichiba', $rakuten->source, 'Rakuten parser should retain the source provider.');
assertCatalogSame('fixture-shop:synthetic-case-b', $rakuten->sourceProductId, 'Rakuten product ID should remain provider-specific.');
assertCatalogSame('rakuten_ichiba:fixture-shop:synthetic-case-b', $rakuten->deduplicationKey, 'Rakuten deduplication identity should include provider and product code.');
assertCatalogSame(2480, $rakuten->priceJpy, 'Equal aggregate bounds establish one exact JPY reference price.');
assertCatalogSame('生成り', $rakuten->options[0]->values[0], 'Rakuten options should normalize from structured properties.');
assertCatalogSame([], $rakuten->reviews, 'Missing provider reviews should remain empty rather than fabricated.');

// Merchant identifiers must not replace the URL identity used by batch imports.
$rakutenMerchantIdentifiers = (new RakutenHtmlParser())->parse(
    $exactRakutenFixture(fixture('rakuten-merchant-identifiers.synthetic.html')),
    'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/',
    $fetchedAt
);
assertCatalogSame('fixture-shop:synthetic-case-b', $rakutenMerchantIdentifiers->sourceProductId, 'Rakuten URL identity must take precedence over unrelated JSON-LD productID and SKU.');
assertCatalogSame('rakuten_ichiba:fixture-shop:synthetic-case-b', $rakutenMerchantIdentifiers->deduplicationKey, 'Merchant identifiers must not change the Rakuten deduplication key.');
assertCatalogSame($rakuten->toArray(), $rakutenMerchantIdentifiers->toArray(), 'Changing merchant identifiers alone must preserve the normalized source metadata and content fingerprint.');
$rakutenSkuOnly = (new RakutenHtmlParser())->parse(
    str_replace('"productID": "SYNTHETIC-MERCHANT-PRODUCT-ID",', '', $exactRakutenFixture(fixture('rakuten-merchant-identifiers.synthetic.html'))),
    'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/',
    $fetchedAt
);
assertCatalogSame('fixture-shop:synthetic-case-b', $rakutenSkuOnly->sourceProductId, 'A merchant SKU without productID must not replace the Rakuten URL identity.');

$ogFallback = $amazonParser->parse(
    fixture('amazon-jp-og-fallback.synthetic.html'),
    'https://www.amazon.co.jp/gp/product/B0KURANEA1',
    $fetchedAt
);
assertCatalogSame('[TEST FIXTURE] 合成オープングラフ商品', $ogFallback->name, 'Open Graph metadata should provide a clearly limited fallback when JSON-LD is absent.');
assertCatalogSame(1200, $ogFallback->priceJpy, 'Product price metadata should be accepted when JSON-LD is absent.');
assertCatalogSame('合成フォールバック画像', $ogFallback->images[0]->altText, 'Open Graph image alt metadata should be retained.');
assertCatalogSame([], $ogFallback->reviews, 'Fallback metadata must not invent review data.');

assertCatalogThrows(
    static fn () => $amazonParser->parse(fixture('amazon-jp-product.synthetic.html'), 'https://evil.example.invalid/dp/B0KURANEA1', $fetchedAt),
    'Amazon parser should reject source URLs outside its provider domain.'
);
assertCatalogThrows(
    static fn () => $amazonParser->parse(str_replace('"priceCurrency": "JPY"', '"priceCurrency": "USD"', fixture('amazon-jp-product.synthetic.html')), $amazonUrl, $fetchedAt),
    'Unsupported source currency should be rejected rather than silently treated as JPY.'
);
assertCatalogThrows(
    static fn () => $amazonParser->parse('<html><body>no product metadata</body></html>', $amazonUrl, $fetchedAt),
    'Pages without product metadata should return an actionable parse failure.'
);

require __DIR__ . '/review_queue_and_approval.php';
require __DIR__ . '/native_product_registrar_lock.php';
require __DIR__ . '/admin_review_contract.php';
require __DIR__ . '/admin_review_controller.php';
require __DIR__ . '/product_admin_draft.php';
require __DIR__ . '/security_fetcher.php';
require __DIR__ . '/import_batch_repository.php';
require __DIR__ . '/review_rejection.php';
require __DIR__ . '/review_queue_persistence.php';
require __DIR__ . '/review_queue_limits.php';
require __DIR__ . '/product_image_rights_evidence.php';
require __DIR__ . '/catalog_import_service.php';
require __DIR__ . '/parser_quality.php';

echo "PASS: offline Amazon JP and Rakuten synthetic catalog parser, fetch, persistence, and review checks\n";
