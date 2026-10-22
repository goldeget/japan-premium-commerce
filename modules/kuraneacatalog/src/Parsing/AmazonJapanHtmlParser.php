<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Parsing;

final class AmazonJapanHtmlParser extends AbstractProductPageParser
{
    protected const PROVIDER = 'amazon_jp';
    protected const ALLOWED_HOSTS = ['amazon.co.jp', 'www.amazon.co.jp'];

    protected function extractProductId(array $product, string $sourceUrl): string
    {
        $path = (string) (parse_url($sourceUrl, PHP_URL_PATH) ?: '');
        if (preg_match('~/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)~i', $path, $matches) === 1) {
            return strtoupper($matches[1]);
        }

        foreach (['asin', 'productID', 'sku', 'mpn'] as $key) {
            $value = trim((string) ($product[$key] ?? ''));
            if ($value !== '') {
                return strtoupper($value);
            }
        }

        return '';
    }
}
