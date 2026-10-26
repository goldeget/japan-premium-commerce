<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Parsing;

final class RakutenHtmlParser extends AbstractProductPageParser
{
    protected const PROVIDER = 'rakuten_ichiba';
    protected const ALLOWED_HOSTS = ['item.rakuten.co.jp', 'rakuten.co.jp', 'www.rakuten.co.jp'];

    protected function extractProductId(array $product, string $sourceUrl): string
    {
        // Batch imports and source refreshes share the shop:item URL identity.
        $path = trim((string) (parse_url($sourceUrl, PHP_URL_PATH) ?: ''), '/');
        $segments = array_values(array_filter(array_map('rawurldecode', explode('/', $path)), static fn (string $segment): bool => $segment !== ''));
        if (count($segments) >= 2) {
            return $segments[count($segments) - 2] . ':' . $segments[count($segments) - 1];
        }

        foreach (['productID', 'productCode', 'sku', 'mpn'] as $key) {
            $value = trim((string) ($product[$key] ?? ''));
            if ($value !== '') {
                return $value;
            }
        }

        return '';
    }
}
