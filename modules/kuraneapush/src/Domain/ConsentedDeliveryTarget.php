<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

final class ConsentedDeliveryTarget
{
    /** A fresh save changes the random AEAD envelope even when notice/time/digest are unchanged. */
    public static function generation(array $row): string
    {
        return hash('sha256', json_encode([
            (string)($row['id_subscription'] ?? ''), $row['consent_notice_version'],
            $row['consent_locale'], $row['consent_accepted_at'], hash('sha256',$row['encrypted_subscription']),
        ], JSON_THROW_ON_ERROR));
    }

    public static function eligible(mixed $row, int $shop, int $customer): bool
    {
        if (!is_array($row) || !self::sameOwner($row['id_shop'] ?? null, $shop)
            || !self::sameOwner($row['id_customer'] ?? null, $customer)) {
            return false;
        }
        $digest = $row['endpoint_digest'] ?? null;
        $envelope = $row['encrypted_subscription'] ?? null;
        $version = $row['consent_notice_version'] ?? null;
        $locale = $row['consent_locale'] ?? null;
        $acceptedAt = $row['consent_accepted_at'] ?? null;
        return is_string($digest) && preg_match('/\A[a-f0-9]{64}\z/D', $digest) === 1
            && is_string($envelope) && strlen($envelope) > 0 && strlen($envelope) <= 8192
            && is_string($version) && ConsentNoticeVersion::isValid($version)
            && is_string($locale) && in_array($locale, ['ja', 'en', 'ko'], true)
            && self::validConsentTimestamp($acceptedAt);
    }

    private static function validConsentTimestamp(mixed $value): bool
    {
        if (!is_string($value) || preg_match('/\A([0-9]{4})-([0-9]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2})\z/D', $value, $parts) !== 1) {
            return false;
        }
        return checkdate((int) $parts[2], (int) $parts[3], (int) $parts[1])
            && (int) $parts[4] <= 23 && (int) $parts[5] <= 59 && (int) $parts[6] <= 59;
    }

    private static function sameOwner(mixed $value, int $expected): bool
    {
        if (is_int($value)) {
            return $value === $expected;
        }
        return is_string($value) && preg_match('/\A[1-9][0-9]*\z/D', $value) === 1
            && strlen($value) <= 10 && (int) $value === $expected;
    }
}
