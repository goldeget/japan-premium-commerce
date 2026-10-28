<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;

use Kuranea\Push\Domain\{PushDeliveryProvider, PushOutboxService};

/** Native binding remains unavailable until the shop explicitly enables verified HTTPS delivery. */
final class LivePushFactory
{
    public static function provider(int $shop): PushDeliveryProvider
    {
        if ($shop < 1 || !class_exists('Configuration')) return new DisabledPushDeliveryProvider();
        try {
            foreach (['ORDENOWA_PUSH_LIVE_ENABLED', 'ORDENOWA_PUSH_HTTPS_VALIDATED'] as $key) {
                if ((string) \Configuration::get($key, null, null, $shop) !== '1') return new DisabledPushDeliveryProvider();
            }
            $provider = new WebPushDeliveryProvider([
                'publicKey' => (string) getenv('ORDENOWA_PUSH_VAPID_PUBLIC_KEY'),
                'privateKey' => (string) getenv('ORDENOWA_PUSH_VAPID_PRIVATE_KEY'),
                'subject' => (string) getenv('ORDENOWA_PUSH_VAPID_SUBJECT'),
            ]);
            return $provider->available() ? $provider : new DisabledPushDeliveryProvider();
        } catch (\Throwable) {
            return new DisabledPushDeliveryProvider();
        }
    }

    public static function available(int $shop): bool
    {
        return self::provider($shop)->available();
    }

    public static function applicationServerKey(int $shop): string
    {
        return self::available($shop) ? (string) getenv('ORDENOWA_PUSH_VAPID_PUBLIC_KEY') : '';
    }

    public static function outbox(int $shop): PushOutboxService
    {
        if ($shop < 1 || !class_exists('Db') || !defined('_DB_PREFIX_')) throw new \RuntimeException('Push storage unavailable.');
        $database = \Db::getInstance();
        $provider = self::provider($shop);
        try { $cipher = new SubscriptionCipher(); } catch (\Throwable) { $cipher = null; }
        return new PushOutboxService(new PushOutboxRepository($database, _DB_PREFIX_),
            new SubscriptionRepository($database, _DB_PREFIX_), $cipher, $provider);
    }
}
