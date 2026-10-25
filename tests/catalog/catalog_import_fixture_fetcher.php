<?php

declare(strict_types=1);

use Kuranea\Catalog\Fetching\FetchException;
use Kuranea\Catalog\Fetching\FetchedProduct;
use Kuranea\Catalog\Fetching\ProductPageFetcherInterface;
use Kuranea\Catalog\Fetching\ProductUrlPolicy;

/** Fixture-only adapter loaded only after the module's isolated CI guard. */
final class ORDENOWACatalogImportFixtureFetcher implements ProductPageFetcherInterface
{
    public function fetch(string $url): FetchedProduct
    {
        $canonical = ProductUrlPolicy::canonicalize($url);
        $path = (string) parse_url($canonical['url'], PHP_URL_PATH);
        if ($canonical['provider'] === 'amazon_jp' && $path === '/dp/B0KURANEA1') {
            $file = '/tmp/ordenowa-ci-catalog-import-amazon.synthetic.html';
        } elseif ($canonical['provider'] === 'rakuten_ichiba'
            && $canonical['url'] === 'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/') {
            $file = '/tmp/ordenowa-ci-catalog-import-rakuten.synthetic.html';
        } elseif ($canonical['provider'] === 'amazon_jp' && $path === '/dp/B0KURANEA2') {
            throw new FetchException('Synthetic fixture response blocked.', FetchException::FAILURE_ACCESS_BLOCKED);
        } else {
            throw new FetchException('No synthetic fixture is mapped for this product URL.');
        }

        $body = @file_get_contents($file);
        if (!is_string($body) || $body === '' || strlen($body) > 2097152) {
            throw new FetchException('Synthetic product fixture is unavailable.');
        }

        return new FetchedProduct(
            $canonical['url'],
            $body,
            new DateTimeImmutable('now', new DateTimeZone('UTC')),
            0
        );
    }
}
