<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

final class ConsentNoticeVersion
{
    private const LOCALES = ['ja', 'en', 'ko'];

    public static function forNotice(string $notice, string $locale): string
    {
        $notice = trim($notice);
        if (!in_array($locale, self::LOCALES, true) || trim($notice) === '') {
            return '';
        }

        return hash('sha256', $locale . "\0" . $notice);
    }

    public static function isValid(string $version): bool
    {
        return preg_match('/\A[a-f0-9]{64}\z/D', $version) === 1;
    }
}
