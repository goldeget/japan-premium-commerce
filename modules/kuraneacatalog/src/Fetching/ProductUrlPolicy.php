<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

final class ProductUrlPolicy
{
    /** @return array{url:string,host:string,provider:string} */
    public static function canonicalize(string $url): array
    {
        if ($url === '' || strlen($url) > 4096 || preg_match('/[\x00-\x20\x7f\\\\]/', $url)) {
            throw new FetchException('Unsupported product URL.');
        }
        $parts = parse_url($url);
        if (!is_array($parts)
            || strtolower((string) ($parts['scheme'] ?? '')) !== 'https'
            || isset($parts['user']) || isset($parts['pass'])
            || (isset($parts['port']) && $parts['port'] !== 443)) {
            throw new FetchException('Unsupported product URL.');
        }
        $host = strtolower((string) ($parts['host'] ?? ''));
        $path = (string) ($parts['path'] ?? '');
        if (in_array($host, ['amazon.co.jp', 'www.amazon.co.jp'], true)
            && preg_match('~^/(?:[A-Za-z0-9_-]+/)?(?:dp|gp/product)/([A-Za-z0-9]{10})/?$~D', $path, $matches)) {
            return ['url' => 'https://www.amazon.co.jp/dp/' . strtoupper($matches[1]), 'host' => 'www.amazon.co.jp', 'provider' => 'amazon_jp'];
        }
        if ($host === 'item.rakuten.co.jp'
            && preg_match('~^/([A-Za-z0-9][A-Za-z0-9_-]{0,127})/([A-Za-z0-9][A-Za-z0-9_-]{0,127})/?$~D', $path, $matches)) {
            return ['url' => 'https://item.rakuten.co.jp/' . $matches[1] . '/' . $matches[2] . '/', 'host' => $host, 'provider' => 'rakuten_ichiba'];
        }
        throw new FetchException('Unsupported product URL.');
    }

    /** Resolve only absolute, origin-relative, or simple product-relative Locations. */
    public static function redirectUrl(string $currentUrl, string $location): string
    {
        if ($location === '' || strlen($location) > 4096 || preg_match('/[\x00-\x20\x7f\\\\]/', $location)) {
            throw new FetchException('Unsupported product redirect.');
        }
        if (str_starts_with($location, '//')) {
            return 'https:' . $location;
        }
        if (preg_match('/^[A-Za-z][A-Za-z0-9+.-]*:/', $location)) {
            return $location;
        }
        $host = (string) parse_url($currentUrl, PHP_URL_HOST);
        if (str_starts_with($location, '/')) {
            return 'https://' . $host . $location;
        }
        $path = (string) parse_url($currentUrl, PHP_URL_PATH);
        return 'https://' . $host . substr($path, 0, (int) strrpos($path, '/') + 1) . $location;
    }
}
