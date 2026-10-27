<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/modules/kuraneabusinessprofile/autoload.php';

use Kuranea\BusinessProfile\Customer\RobotsSitemapDirective;
use Kuranea\BusinessProfile\Customer\AnonymousGroupPolicy;
use Kuranea\BusinessProfile\Customer\SitemapUrlPolicy;
use Kuranea\BusinessProfile\Customer\SitemapXmlRenderer;

function sitemapAssert(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$base = SitemapUrlPolicy::configuredBaseUrl([
    'domain' => 'shop.example.test',
    'domain_ssl' => 'secure.example.test',
    'physical_uri' => '/store/',
    'virtual_uri' => 'jp/',
], true);
sitemapAssert($base === 'https://secure.example.test/store/jp/', 'Canonical base must use configured SSL ShopUrl.');

$productUrl = SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://secure.example.test/store/jp/ja/41-test-product.html',
    (string) $base,
    'product',
    41,
    1
);
sitemapAssert($productUrl === 'https://secure.example.test/store/jp/ja/41-test-product.html', 'Native same-shop routes should canonicalize to the configured origin.');
sitemapAssert(SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://secure.example.test/store/jp/ja/41-test-product.html?preview=1&adtoken=secret',
    (string) $base,
    'product',
    41,
    1
) === null, 'Preview or token query parameters must never enter the sitemap.');
sitemapAssert(SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://attacker.example/41-test-product.html',
    (string) $base,
    'product',
    41,
    1
) === null, 'Foreign origins must be rejected.');
sitemapAssert(SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://secure.example.test/store/jp/%2e%2e/private',
    (string) $base,
    'product',
    41,
    1
) === null, 'Encoded path traversal must be rejected.');
sitemapAssert(SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://secure.example.test/store/jp/login?controller=authentication',
    (string) $base,
    'product',
    41,
    1
) === null, 'Authentication and mismatched query routes must be rejected.');
sitemapAssert(SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://secure.example.test/store/jp/index.php?controller=product&id_product=41&id_lang=1',
    (string) $base,
    'product',
    41,
    1
) === 'https://secure.example.test/store/jp/index.php?controller=product&id_product=41&id_lang=1', 'Identifier-only native query routes should remain valid.');
$pageUrl = SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://secure.example.test/store/jp/ja/sitemap-ja-1.xml',
    (string) $base,
    'module',
    0,
    1,
    'ja',
    1
);
sitemapAssert($pageUrl === 'https://secure.example.test/store/jp/ja/sitemap-ja-1.xml', 'Native sitemap page routes should match their locale and page.');
sitemapAssert(SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://secure.example.test/store/jp/ja/sitemap-en-1.xml',
    (string) $base,
    'module',
    0,
    1,
    'ja',
    1
) === null, 'Sitemap page locale and page parameters must match the route.');
$queryPage = SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://secure.example.test/store/jp/index.php?fc=module&module=kuraneabusinessprofile&controller=sitemappage&iso=ja&page=1&id_lang=1',
    (string) $base,
    'module',
    0,
    1,
    'ja',
    1
);
sitemapAssert($queryPage === 'https://secure.example.test/store/jp/index.php?fc=module&module=kuraneabusinessprofile&controller=sitemappage&iso=ja&page=1&id_lang=1', 'Native PrestaShop query routes should remain valid when rewriting is disabled.');
sitemapAssert(SitemapUrlPolicy::canonicalizeNativeUrl(
    'https://secure.example.test/store/jp/index.php?fc=module&module=kuraneabusinessprofile&controller=sitemappage&iso=ja&page=1&token=synthetic',
    (string) $base,
    'module',
    0,
    1,
    'ja',
    1
) === null, 'Untrusted query parameters must be omitted from sitemap routes.');
sitemapAssert(SitemapUrlPolicy::configuredBaseUrl([
    'domain' => 'shop.example.test',
    'domain_ssl' => '',
    'physical_uri' => '/',
    'virtual_uri' => '',
], true) === null, 'Missing configured SSL domain must fail closed.');
sitemapAssert(SitemapUrlPolicy::configuredBaseUrl([
    'domain' => 'evil.example/path',
    'domain_ssl' => 'evil.example',
    'physical_uri' => '/',
    'virtual_uri' => '',
], false) === null, 'ShopUrl authorities must reject embedded paths.');
sitemapAssert(SitemapUrlPolicy::configuredBaseUrl([
    'domain' => 'localhost:8080',
    'domain_ssl' => '',
    'physical_uri' => '/',
    'virtual_uri' => '',
], false) === 'http://localhost:8080/', 'Configured local single-label hosts should remain testable.');

$robots = "User-agent: *\nDisallow: /cart\nDisallow: /authentication\n"
    . "Sitemap: https://core.example.test/1_index_sitemap.xml\n"
    . "Sitemap: https://manual.example.test/custom.xml\n"
    . "# ORDENOWA XML sitemap\nSitemap: https://old-shop.example.test/sitemap.xml\n";
$rewritten = RobotsSitemapDirective::rewriteContent($robots, 'https://shop.example.test/sitemap.xml');
sitemapAssert(str_contains($rewritten, 'Disallow: /cart'), 'Core cart protection must be preserved.');
sitemapAssert(str_contains($rewritten, 'Disallow: /authentication'), 'Core authentication protection must be preserved.');
sitemapAssert(str_contains($rewritten, 'Sitemap: https://core.example.test/1_index_sitemap.xml'), 'Core sitemap directives must be preserved.');
sitemapAssert(str_contains($rewritten, 'Sitemap: https://manual.example.test/custom.xml'), 'Manual sitemap directives must be preserved.');
sitemapAssert(!str_contains($rewritten, 'https://old-shop.example.test/sitemap.xml'), 'The previous ORDENOWA sitemap must be replaced.');
sitemapAssert(substr_count($rewritten, '# ORDENOWA XML sitemap') === 1, 'Only one owned sitemap marker should remain.');
sitemapAssert(substr_count($rewritten, 'Sitemap:') === 3, 'Only the ORDENOWA-owned directive should be replaced.');
sitemapAssert(str_contains($rewritten, 'Sitemap: https://shop.example.test/sitemap.xml'), 'Robots sitemap must use the configured origin.');
$closed = RobotsSitemapDirective::rewriteContent($robots, null);
sitemapAssert(str_contains($closed, 'Sitemap: https://core.example.test/1_index_sitemap.xml'), 'Null URL must preserve core sitemap directives.');
sitemapAssert(str_contains($closed, 'Sitemap: https://manual.example.test/custom.xml'), 'Null URL must preserve manual sitemap directives.');
sitemapAssert(!str_contains($closed, '# ORDENOWA XML sitemap'), 'Null URL must remove the owned marker.');
sitemapAssert(!str_contains($closed, 'https://old-shop.example.test/sitemap.xml'), 'Null URL must remove the owned sitemap directive.');
$uninstalled = RobotsSitemapDirective::rewriteContent($rewritten, null);
sitemapAssert(!str_contains($uninstalled, '# ORDENOWA XML sitemap'), 'Uninstall cleanup must remove the owned marker.');
sitemapAssert(str_contains($uninstalled, 'Sitemap: https://manual.example.test/custom.xml'), 'Uninstall cleanup must preserve third-party directives.');
sitemapAssert(SitemapUrlPolicy::isSafeAbsoluteSitemapUrl('https://shop.example.test/sitemap.xml'), 'Configured sitemap URL should be accepted.');
sitemapAssert(!SitemapUrlPolicy::isSafeAbsoluteSitemapUrl('https://shop.example.test/sitemap.xml?host=raw'), 'Query strings should not be accepted in robots sitemap URLs.');

sitemapAssert(AnonymousGroupPolicy::resolve(false, 0, 0, false) === [false, 0], 'Disabled group restrictions do not require guest-group resolution.');
sitemapAssert(AnonymousGroupPolicy::resolve(true, 3, 3, true) === [true, 3], 'The exact guest group associated to this shop should be accepted.');
sitemapAssert(AnonymousGroupPolicy::resolve(true, 3, 4, true) === null, 'A different loaded group must not replace the configured guest group.');
sitemapAssert(AnonymousGroupPolicy::resolve(true, 3, 3, false) === null, 'A guest group not associated to the current shop must fail closed.');
sitemapAssert(AnonymousGroupPolicy::resolve(true, 0, 0, false) === null, 'A missing guest group must fail closed.');

$xml = SitemapXmlRenderer::urlSet(['https://shop.example.test/p?a=1&b=2']);
sitemapAssert(is_string($xml) && str_contains($xml, '&amp;'), 'XML location values must be escaped.');
sitemapAssert(SitemapXmlRenderer::urlSet(array_fill(0, 10001, 'https://shop.example.test/p')) === null, 'URL set must honor the URL count limit.');
sitemapAssert(is_string(SitemapXmlRenderer::urlSet(array_fill(0, 10000, 'https://shop.example.test/p'))), 'URL set should accept the exact URL count limit.');
sitemapAssert(SitemapXmlRenderer::index(array_fill(0, 10001, 'https://shop.example.test/sitemap.xml')) === null, 'Sitemap index must honor its child count limit.');
sitemapAssert(is_string(SitemapXmlRenderer::index(array_fill(0, 10000, 'https://shop.example.test/sitemap.xml'))), 'Sitemap index should accept the exact child count limit.');
$urlPrefix = 'https://shop.example.test/';
sitemapAssert(is_string(SitemapXmlRenderer::urlSet([$urlPrefix . str_repeat('p', SitemapUrlPolicy::MAX_URL_BYTES - strlen($urlPrefix))])), 'URL set should accept a URL at the byte limit.');
sitemapAssert(SitemapXmlRenderer::urlSet([$urlPrefix . str_repeat('p', SitemapUrlPolicy::MAX_URL_BYTES - strlen($urlPrefix) + 1)]) === null, 'URL set must reject a URL over the byte limit.');

echo "Configured sitemap URL, robots ownership, guest-group policy and XML bounds passed.", PHP_EOL;
