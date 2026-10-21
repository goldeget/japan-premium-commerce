<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Domain;

final class ZipCode
{
    public static function normalize(string $value): ?string
    {
        $value = trim($value);
        if (function_exists('mb_convert_kana')) {
            $value = mb_convert_kana($value, 'as', 'UTF-8');
        }

        // Keep this deterministic even when mbstring is unavailable in a CLI
        // import environment.
        $value = strtr($value, [
            '０' => '0', '１' => '1', '２' => '2', '３' => '3', '４' => '4',
            '５' => '5', '６' => '6', '７' => '7', '８' => '8', '９' => '9',
            '‐' => '-', '‑' => '-', '‒' => '-', '–' => '-', '—' => '-',
            '−' => '-', '－' => '-',
        ]);
        $value = preg_replace('/^[\s\p{Z}]+|[\s\p{Z}]+$/u', '', $value) ?? '';

        if (preg_match('/^[0-9]{7}$/D', $value)) {
            $digits = $value;
        } elseif (preg_match('/^([0-9]{3})-([0-9]{4})$/D', $value, $matches)) {
            $digits = $matches[1] . $matches[2];
        } else {
            return null;
        }

        return substr($digits, 0, 3) . '-' . substr($digits, 3, 4);
    }

    public static function digits(string $value): ?string
    {
        $normalized = self::normalize($value);

        return $normalized === null ? null : str_replace('-', '', $normalized);
    }

    public static function isValid(string $value): bool
    {
        return self::normalize($value) !== null;
    }
}
