<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

final class SubscriptionValidator
{
    public static function validate(array $subscription): array
    {
        self::fields($subscription, ['endpoint', 'keys']);
        $endpoint = $subscription['endpoint'] ?? null;
        if (!is_string($endpoint) || strlen($endpoint) > 2048 || preg_match('/[\x00-\x20\x7f\\\\]/', $endpoint)) {
            throw new \InvalidArgumentException('Invalid subscription.');
        }
        $url = parse_url($endpoint);
        if (!is_array($url) || ($url['scheme'] ?? '') !== 'https'
            || isset($url['user']) || isset($url['pass']) || isset($url['fragment'])
            || (isset($url['port']) && $url['port'] !== 443)) {
            throw new \InvalidArgumentException('Invalid subscription.');
        }
        $host = strtolower((string) ($url['host'] ?? ''));
        // A lexical provider allowlist only: never resolve DNS or fetch an endpoint.
        $allowed = in_array($host, ['fcm.googleapis.com', 'android.googleapis.com', 'push.services.mozilla.com', 'web.push.apple.com'], true)
            || preg_match('/\A[a-z0-9-]+(?:\.[a-z0-9-]+)*\.push\.services\.mozilla\.com\z/D', $host) === 1
            || preg_match('/\A[a-z0-9-]+(?:\.[a-z0-9-]+)*\.push\.apple\.com\z/D', $host) === 1;
        if (!$allowed || filter_var($host, FILTER_VALIDATE_IP)) {
            throw new \InvalidArgumentException('Invalid subscription.');
        }
        $keys = $subscription['keys'] ?? null;
        if (!is_array($keys)) {
            throw new \InvalidArgumentException('Invalid subscription.');
        }
        self::fields($keys, ['p256dh', 'auth']);
        $publicKey = self::decodeKey($keys['p256dh'] ?? null, 65);
        self::decodeKey($keys['auth'] ?? null, 16);
        if (ord($publicKey[0]) !== 4) {
            throw new \InvalidArgumentException('Invalid subscription.');
        }
        return $subscription;
    }

    public static function fields(array $input, array $allowed): void
    {
        if (array_diff(array_keys($input), $allowed) !== []) {
            throw new \InvalidArgumentException('Invalid request.');
        }
    }

    private static function decodeKey(mixed $value, int $length): string
    {
        if (!is_string($value) || strlen($value) > 100 || preg_match('/\A[A-Za-z0-9_-]+\z/D', $value) !== 1) {
            throw new \InvalidArgumentException('Invalid subscription.');
        }
        $decoded = base64_decode(strtr($value, '-_', '+/'), true);
        if ($decoded === false || strlen($decoded) !== $length
            || rtrim(strtr(base64_encode($decoded), '+/', '-_'), '=') !== $value) {
            throw new \InvalidArgumentException('Invalid subscription.');
        }
        return $decoded;
    }
}
