<?php

declare(strict_types=1);

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

use Kuranea\Catalog\Domain\CatalogParseException;
use Kuranea\Catalog\Parsing\AmazonJapanHtmlParser;
use Kuranea\Catalog\Parsing\RakutenHtmlParser;

// Synthetic observations exercise supported document shapes, never claim marketplace compatibility.
$failures = [];
$count = 0;
function qualityCase(string $label, callable $test): void {
    global $failures, $count;
    ++$count;
    try { $test(); } catch (Throwable $error) { $failures[] = $label . ': ' . $error->getMessage(); }
}
function qualitySame(mixed $expected, mixed $actual): void {
    if ($expected !== $actual) throw new RuntimeException('Expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
}
function qualityReject(callable $operation): void {
    try { $operation(); } catch (CatalogParseException) { return; }
    throw new RuntimeException('Unsafe or ambiguous source was accepted.');
}
function qualityHtml(array $data): string {
    return '<html><head><script type="application/ld+json">' . json_encode($data, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR) . '</script></head></html>';
}
$parser = new AmazonJapanHtmlParser();
$url = 'https://www.amazon.co.jp/dp/B0KURANEA1';
$product = ['@type' => 'Product', 'name' => '合成の調理器具', 'offers' => ['@type' => 'Offer', 'price' => '2,480.00', 'priceCurrency' => 'JPY']];
qualityCase('select target Product rather than recommendation', function () use ($parser, $url, $product): void {
    $recommendation = array_replace($product, ['name' => 'unrelated', 'url' => 'https://www.amazon.co.jp/dp/B0KURANEA2']);
    $target = array_replace($product, ['url' => $url]);
    qualitySame('合成の調理器具', $parser->parse(qualityHtml(['@graph' => [$recommendation, $target]]), $url)->name);
});
qualityCase('ambiguous Product list is rejected', fn () => qualityReject(fn () => $parser->parse(qualityHtml([$product, array_replace($product, ['name' => 'other'])]), $url)));
qualityCase('mismatched sole Product is rejected', fn () => qualityReject(fn () => $parser->parse(qualityHtml(array_replace($product, ['url' => 'https://www.amazon.co.jp/dp/B0KURANEA2'])), $url)));
qualityCase('direct parser uses canonical product URL without tracking', fn () => qualitySame($url, $parser->parse(qualityHtml($product), $url . '?tag=tracking#fragment')->sourceUrl));
qualityCase('non-product provider URL is rejected', fn () => qualityReject(fn () => $parser->parse(qualityHtml($product), 'https://www.amazon.co.jp/ap/signin')));
qualityCase('graph references resolve offers and images', function () use ($parser, $url, $product): void {
    $graph = ['@graph' => [array_replace($product, ['offers' => ['@id' => '#offer'], 'image' => ['@id' => '#image']]), ['@id' => '#offer', '@type' => 'Offer', 'price' => '2480', 'priceCurrency' => 'JPY'], ['@id' => '#image', '@type' => 'ImageObject', 'contentUrl' => 'https://images.example.test/front.jpg', 'caption' => '前面']]];
    $snapshot = $parser->parse(qualityHtml($graph), $url);
    qualitySame(2480, $snapshot->priceJpy);
    qualitySame('https://images.example.test/front.jpg', $snapshot->images[0]->url ?? null);
});
qualityCase('JPY decimal fraction never rounds into an integer', fn () => qualityReject(fn () => $parser->parse(qualityHtml(array_replace($product, ['offers' => ['price' => '999999999.000000001', 'priceCurrency' => 'JPY']])), $url)));
qualityCase('JPY integer overflow is rejected', fn () => qualityReject(fn () => $parser->parse(qualityHtml(array_replace($product, ['offers' => ['price' => (string) PHP_INT_MAX . '0', 'priceCurrency' => 'JPY']])), $url)));
qualityCase('scientific notation is rejected', fn () => qualityReject(fn () => $parser->parse(qualityHtml(array_replace($product, ['offers' => ['price' => '1e3', 'priceCurrency' => 'JPY']])), $url)));
qualityCase('malformed thousands separator is rejected', fn () => qualityReject(fn () => $parser->parse(qualityHtml(array_replace($product, ['offers' => ['price' => '2,4,80', 'priceCurrency' => 'JPY']])), $url)));
qualityCase('zero-only decimal JPY accepted exactly', fn () => qualitySame(2480, $parser->parse(qualityHtml($product), $url)->priceJpy));
qualityCase('missing price does not become zero', fn () => qualityReject(fn () => $parser->parse(qualityHtml(['@type' => 'Product', 'name' => '合成']), $url)));
qualityCase('auth form retaining structured data is blocked', fn () => qualityReject(fn () => $parser->parse(qualityHtml($product) . '<form action="/ap/signin"><input type="password" name="password"></form>', $url)));
qualityCase('CAPTCHA retaining structured data is blocked', fn () => qualityReject(fn () => $parser->parse(qualityHtml($product) . '<form action="/errors/validateCaptcha"></form>', $url)));
qualityCase('image URLs reject script, credentials and private literal destinations', function () use ($parser, $url, $product): void {
    $snapshot = $parser->parse(qualityHtml(array_replace($product, ['image' => ['javascript:alert(1)', 'https://user:secret@example.test/a.jpg', 'http://127.0.0.1/a.jpg', 'http://169.254.169.254/a.jpg', 'https://localhost/a.jpg', 'https://images.example.test/front.jpg']])), $url);
    qualitySame(['https://images.example.test/front.jpg'], array_map(fn ($image) => $image->url, $snapshot->images));
});
qualityCase('breadcrumb source path sorted by position excluding product', function () use ($parser, $url, $product): void {
    $breadcrumbs = ['@type' => 'BreadcrumbList', 'itemListElement' => [['@type' => 'ListItem', 'position' => 2, 'item' => ['name' => '調理器具']], ['@type' => 'ListItem', 'position' => 1, 'item' => ['name' => 'キッチン']], ['@type' => 'ListItem', 'position' => 3, 'item' => ['name' => $product['name'], '@id' => $url]]]];
    qualitySame(['キッチン > 調理器具'], $parser->parse(qualityHtml(['@graph' => [$product, $breadcrumbs]]), $url)->categories);
});
qualityCase('Amazon rendered public HTML title price images detail and option values', function () use ($parser, $url): void {
    $snapshot = $parser->parse(file_get_contents(__DIR__ . '/fixtures/amazon-jp-rendered.synthetic.html'), $url);
    qualitySame('合成 HTML 調理器具', $snapshot->name);
    qualitySame(3480, $snapshot->priceJpy);
    qualitySame('軽量 & 丈夫 洗いやすい', $snapshot->description);
    qualitySame(['https://images.example.test/front.jpg', 'https://images.example.test/back.jpg'], array_map(fn ($image) => $image->url, $snapshot->images));
    qualitySame(['M', 'L'], $snapshot->options[0]->values ?? null);
});
qualityCase('Rakuten explicit Product microdata metadata', function (): void {
    $snapshot = (new RakutenHtmlParser())->parse(file_get_contents(__DIR__ . '/fixtures/rakuten-microdata.synthetic.html'), 'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/');
    qualitySame('合成 HTML ケース', $snapshot->name);
    qualitySame(1280, $snapshot->priceJpy);
    qualitySame('日本語の詳細説明', $snapshot->description);
    qualitySame(['生活用品 > 収納'], $snapshot->categories);
});
qualityCase('JSON numeric fractional price is never accepted after float rounding', fn () => qualityReject(fn () => $parser->parse('<script type="application/ld+json">{"@type":"Product","name":"synthetic","offers":{"price":999999999.000000001,"priceCurrency":"JPY"}}</script>', $url)));
qualityCase('conflicting JPY variant offers require review instead of picking first', fn () => qualityReject(fn () => $parser->parse(qualityHtml(array_replace($product, ['offers' => [['price' => '2000', 'priceCurrency' => 'JPY'], ['price' => '2500', 'priceCurrency' => 'JPY']]])), $url)));
qualityCase('unrelated external Product URL is rejected', fn () => qualityReject(fn () => $parser->parse(qualityHtml(array_replace($product, ['url' => 'https://unrelated.example.test/product'])), $url)));
qualityCase('source snapshot larger than fetch limit is rejected directly', fn () => qualityReject(fn () => $parser->parse(qualityHtml($product) . str_repeat(' ', 2097152), $url)));
qualityCase('Product category array and BreadcrumbList coexist without inventing a taxonomy', function () use ($parser, $url, $product): void {
    $snapshot = $parser->parse(qualityHtml(array_replace($product, ['category' => ['Kitchen', 'Tools']])), $url);
    qualitySame(['Kitchen', 'Tools'], $snapshot->categories);
});
qualityCase('declared Shift-JIS snapshot preserves Japanese text exactly', function () use ($parser, $url): void {
    $html = '<html><head><meta charset="Shift_JIS"><meta property="og:title" content="合成の収納用品"><meta property="product:price:amount" content="1280"><meta property="product:price:currency" content="JPY"></head></html>';
    qualitySame('合成の収納用品', $parser->parse(mb_convert_encoding($html, 'SJIS-win', 'UTF-8'), $url)->name);
});
qualityCase('invalid undeclared source bytes fail without replacement characters', fn () => qualityReject(fn () => $parser->parse("<meta property=\"og:title\" content=\"bad\xFF\"><meta property=\"product:price:amount\" content=\"1280\"><meta property=\"product:price:currency\" content=\"JPY\">", $url)));
qualityCase('description block boundaries and encoded markup normalize to plain text', function () use ($parser, $url, $product): void {
    $snapshot = $parser->parse(qualityHtml(array_replace($product, ['description' => '&lt;p&gt;軽量&lt;/p&gt;&lt;p&gt;洗いやすい&lt;/p&gt;<script>unrelated()</script>'])), $url);
    qualitySame('軽量 洗いやすい', $snapshot->description);
});
qualityCase('fully qualified schema Product type is supported', fn () => qualitySame('合成の調理器具', $parser->parse(qualityHtml(array_replace($product, ['@type' => 'https://schema.org/Product'])), $url)->name));
if ($failures !== []) { foreach ($failures as $failure) fwrite(STDERR, "FAIL: $failure\n"); exit(1); }
echo 'PASS: ' . $count . " parser quality behaviors (synthetic, offline)\n";
