<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

final class SitemapUrlPolicy
{
    public const MAX_URL_BYTES = 2048;
    public const MAX_URLS_PER_SITEMAP = 10000;
    public const MAX_SITEMAPS_PER_INDEX = 10000;
    public const MAX_XML_BYTES = 50 * 1024 * 1024;

    /** @param array<string, mixed> $shopUrl */
    public static function configuredBaseUrl(array $shopUrl, bool $sslEnabled): ?string
    {
        $authority = trim((string) ($sslEnabled ? ($shopUrl['domain_ssl'] ?? '') : ($shopUrl['domain'] ?? '')));
        if ($authority === '' || !self::validAuthority($authority)) {
            return null;
        }

        $physical = self::pathSegments((string) ($shopUrl['physical_uri'] ?? '/'));
        $virtual = self::pathSegments((string) ($shopUrl['virtual_uri'] ?? ''));
        if ($physical === null || $virtual === null) {
            return null;
        }

        $segments = array_values(array_filter([$physical, $virtual], static fn (string $value): bool => $value !== ''));
        $path = '/' . implode('/', $segments);
        if ($path !== '/') {
            $path .= '/';
        }

        return ($sslEnabled ? 'https://' : 'http://') . strtolower($authority) . $path;
    }

    public static function canonicalizeNativeUrl(
        string $nativeUrl,
        string $configuredBaseUrl,
        string $kind,
        int $id,
        int $idLang,
        ?string $iso = null,
        ?int $page = null
    ): ?string {
        $base = parse_url($configuredBaseUrl);
        $native = parse_url($nativeUrl);
        if (!is_array($base) || !is_array($native)
            || !isset($base['scheme'], $base['host'], $base['path'])
            || !isset($native['scheme'], $native['host'], $native['path'])
            || isset($native['user']) || isset($native['pass']) || isset($native['fragment'])
            || !in_array(strtolower((string) $native['scheme']), ['http', 'https'], true)
            || strcasecmp((string) $native['host'], (string) $base['host']) !== 0
            || (int) ($native['port'] ?? 0) !== (int) ($base['port'] ?? 0)
        ) {
            return null;
        }

        $basePath = (string) $base['path'];
        $path = (string) $native['path'];
        $decodedBasePath = rawurldecode($basePath);
        $decodedPath = rawurldecode($path);
        if (!str_starts_with($path, $basePath)
            || !str_starts_with($decodedPath, $decodedBasePath)
            || str_contains($path, '\\')
            || str_contains($decodedPath, '\\')
            || preg_match('/[\x00-\x20\x7f]/', $decodedPath) === 1
            || self::containsDotSegment($decodedPath)
        ) {
            return null;
        }

        $query = [];
        $rawQuery = (string) ($native['query'] ?? '');
        if ($rawQuery !== '' && !self::parseUniqueQuery($rawQuery, $query)) {
            return null;
        }
        if ($kind === 'module') {
            $expectedRouteSuffix = '/sitemap-' . $iso . '-' . $page . '.xml';
            if ($rawQuery === '' && !str_ends_with($path, $expectedRouteSuffix)) {
                return null;
            }
            if ($rawQuery !== '' && !str_ends_with($path, '/index.php')) {
                return null;
            }
        }

        $allowed = match ($kind) {
            'home' => self::validatedQuery($query, ['controller' => 'index'], $idLang, false),
            'product' => self::validatedQuery($query, ['controller' => 'product', 'id_product' => (string) $id], $idLang),
            'category' => self::validatedQuery($query, ['controller' => 'category', 'id_category' => (string) $id], $idLang),
            'module' => self::validatedQuery($query, [
                'fc' => 'module',
                'module' => 'kuraneabusinessprofile',
                'controller' => 'sitemappage',
                'iso' => (string) $iso,
                'page' => (string) $page,
            ], $idLang),
            default => null,
        };
        if ($allowed === null) {
            return null;
        }

        $url = self::origin($base) . $path;
        if ($allowed !== []) {
            $url .= '?' . http_build_query($allowed, '', '&', PHP_QUERY_RFC3986);
        }

        return strlen($url) <= self::MAX_URL_BYTES ? $url : null;
    }

    public static function isSafeAbsoluteSitemapUrl(string $url): bool
    {
        if (strlen($url) > self::MAX_URL_BYTES) {
            return false;
        }

        $parts = parse_url($url);
        return is_array($parts)
            && in_array(strtolower((string) ($parts['scheme'] ?? '')), ['http', 'https'], true)
            && isset($parts['host'], $parts['path'])
            && self::validAuthority((string) $parts['host'] . (isset($parts['port']) ? ':' . (int) $parts['port'] : ''))
            && !isset($parts['user']) && !isset($parts['pass'])
            && !isset($parts['query']) && !isset($parts['fragment'])
            && str_ends_with((string) $parts['path'], '/sitemap.xml')
            && preg_match('/[\x00-\x20\x7f]/', $url) !== 1;
    }

    /** @param array<string, mixed> $parts */
    private static function origin(array $parts): string
    {
        return strtolower((string) $parts['scheme']) . '://'
            . strtolower((string) $parts['host'])
            . (isset($parts['port']) ? ':' . (int) $parts['port'] : '');
    }

    private static function validAuthority(string $authority): bool
    {
        if (strlen($authority) > 255 || preg_match('/[\x00-\x20\x7f\/\\\\?#@]/', $authority) === 1) {
            return false;
        }

        $parts = parse_url('http://' . $authority);
        if (!is_array($parts) || !isset($parts['host'])
            || isset($parts['user']) || isset($parts['pass']) || isset($parts['path'])
            || isset($parts['query']) || isset($parts['fragment'])
            || preg_match('/\A[a-z0-9.-]+\z/i', (string) $parts['host']) !== 1
        ) {
            return false;
        }

        $host = (string) $parts['host'];
        $singleLabelHost = preg_match('/\\A[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\z/iD', $host) === 1;
        if (filter_var($host, FILTER_VALIDATE_IP) === false
            && filter_var($host, FILTER_VALIDATE_DOMAIN, FILTER_FLAG_HOSTNAME) === false
            && !$singleLabelHost
        ) {
            return false;
        }

        return !isset($parts['port']) || ((int) $parts['port'] >= 1 && (int) $parts['port'] <= 65535);
    }

    private static function containsDotSegment(string $path): bool
    {
        foreach (explode('/', $path) as $segment) {
            if ($segment === '.' || $segment === '..') {
                return true;
            }
        }

        return false;
    }

    private static function pathSegments(string $path): ?string
    {
        $trimmed = trim($path, '/');
        if ($trimmed === '') {
            return '';
        }

        $segments = explode('/', $trimmed);
        foreach ($segments as $segment) {
            if ($segment === '' || $segment === '.' || $segment === '..'
                || preg_match('/\A[A-Za-z0-9._~-]+\z/D', $segment) !== 1
            ) {
                return null;
            }
        }

        return implode('/', $segments);
    }

    /** @param array<string, string> $query */
    private static function parseUniqueQuery(string $rawQuery, array &$query): bool
    {
        foreach (explode('&', $rawQuery) as $pair) {
            if ($pair === '') {
                return false;
            }
            $parts = explode('=', $pair, 2);
            $key = rawurldecode($parts[0]);
            $value = rawurldecode($parts[1] ?? '');
            if ($key === '' || array_key_exists($key, $query) || str_contains($key, '[') || str_contains($key, ']')) {
                return false;
            }
            $query[$key] = $value;
        }

        return true;
    }

    /** @param array<string, string> $query
     *  @param array<string, string> $required
     *  @return array<string, string>|null
     */
    private static function validatedQuery(array $query, array $required, int $idLang, bool $requireAll = true): ?array
    {
        if ($query === []) {
            return [];
        }

        if (isset($query['id_lang']) && $query['id_lang'] !== (string) $idLang) {
            return null;
        }
        foreach ($query as $key => $value) {
            if (!array_key_exists($key, $required) && $key !== 'id_lang') {
                return null;
            }
            if (array_key_exists($key, $required) && $required[$key] !== $value) {
                return null;
            }
        }
        foreach ($required as $key => $value) {
            if (array_key_exists($key, $query) && $query[$key] !== $value) {
                return null;
            }
            if ($requireAll && !array_key_exists($key, $query)) {
                return null;
            }
        }

        $validated = array_intersect_key($required, $query);
        if (isset($query['id_lang'])) {
            $validated['id_lang'] = $query['id_lang'];
        }

        return $validated;
    }
}
