<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;

use Kuranea\Push\Domain\Readiness;

/** Browser subscription needs a secure native origin as well as server delivery configuration. */
final class LiveSubscriptionReadiness
{
    public static function canSubscribe(int $shop, string $notice, bool $storageReady): bool
    {
        if (!$storageReady || trim($notice) === '') return false;
        if (Readiness::canSubscribe(null, $notice, $storageReady)) return true;
        return self::secureNativeRequest($shop) && LivePushFactory::available($shop)
            && LivePushFactory::applicationServerKey($shop) !== '';
    }

    public static function secureNativeRequest(int $shop): bool
    {
        if ($shop < 1 || !class_exists('Configuration') || !class_exists('Context')
            || (string) \Configuration::get('PS_SSL_ENABLED', null, null, $shop) !== '1') return false;
        try {
            return self::isHttpsOrigin((string) \Context::getContext()->link->getBaseLink($shop), $_SERVER);
        } catch (\Throwable) {
            return false;
        }
    }

    /** Deliberately ignores client forwarded-proto headers and arbitrary HTTP flags. */
    public static function isHttpsOrigin(string $canonicalBase, array $server): bool
    {
        $secure = strtolower((string) ($server['HTTPS'] ?? ''));
        if (!in_array($secure, ['on', '1'], true)) return false;
        $parts = parse_url($canonicalBase);
        $authority = (string) ($server['HTTP_HOST'] ?? '');
        if (!is_array($parts) || strtolower((string) ($parts['scheme'] ?? '')) !== 'https'
            || empty($parts['host']) || isset($parts['user']) || isset($parts['pass'])
            || preg_match('/\A[A-Za-z0-9.-]+(?::[0-9]{1,5})?\z/D', $authority) !== 1) return false;
        $request = parse_url('https://' . $authority);
        return is_array($request) && strtolower((string) $request['host']) === strtolower((string) $parts['host'])
            && (int) ($request['port'] ?? 443) === (int) ($parts['port'] ?? 443);
    }
}
