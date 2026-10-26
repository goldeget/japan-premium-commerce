<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;

final class PushSettings
{
    public const EVENTS = ['ORDER', 'DELIVERY', 'SUPPORT'];
    public const LOCALES = ['ja', 'en', 'ko'];

    public static function initialize(int $shop): bool
    {
        $ok = true;
        foreach (self::EVENTS as $event) {
            $key = 'ORDENOWA_PUSH_EVENT_' . $event;
            if (!\Configuration::hasKey($key, null, null, $shop)) {
                $ok = \Configuration::updateValue($key, 0, false, null, $shop) && $ok;
            }
        }
        foreach (self::LOCALES as $locale) {
            $key = 'ORDENOWA_PUSH_CONSENT_NOTICE_' . strtoupper($locale);
            if (!\Configuration::hasKey($key, null, null, $shop)) {
                $ok = \Configuration::updateValue($key, '', false, null, $shop) && $ok;
            }
        }
        return $ok;
    }

    public static function notice(int $shop, string $locale): string
    {
        if (!in_array($locale, self::LOCALES, true)) {
            return '';
        }
        return (string) \Configuration::get('ORDENOWA_PUSH_CONSENT_NOTICE_' . strtoupper($locale), null, null, $shop);
    }
}
