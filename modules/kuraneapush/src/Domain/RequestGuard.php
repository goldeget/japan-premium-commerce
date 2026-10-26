<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

final class RequestGuard
{
    public static function allows(string $method, string $origin, string $baseUrl, mixed $token, string $expected): bool
    {
        $url = parse_url($baseUrl);
        if ($method !== 'POST' || !is_array($url) || !isset($url['scheme'], $url['host'])
            || !in_array($url['scheme'], ['http', 'https'], true) || isset($url['user']) || isset($url['pass'])
            || !is_string($token) || $token === '' || $expected === '') {
            return false;
        }
        $port = (int) ($url['port'] ?? ($url['scheme'] === 'https' ? 443 : 80));
        $defaultPort = $url['scheme'] === 'https' ? 443 : 80;
        $configuredOrigin = $url['scheme'] . '://' . strtolower($url['host']) . ($port === $defaultPort ? '' : ':' . $port);
        return hash_equals($configuredOrigin, $origin) && hash_equals($expected, $token);
    }
}
