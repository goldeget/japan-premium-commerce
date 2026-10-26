<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

/** Exact positive JPY normalization; fractional yen is not accepted. */
final class JpyAmount
{
    public static function normalizePositive(string $amount): ?string
    {
        if (preg_match('/\\A(0|[1-9][0-9]{0,13})(?:\\.([0-9]{1,6}))?\\z/D', $amount, $parts) !== 1) {
            return null;
        }

        $whole = (string) $parts[1];
        $fraction = (string) ($parts[2] ?? '');
        if ($whole === '0' || ($fraction !== '' && trim($fraction, '0') !== '')) {
            return null;
        }

        return $whole;
    }
}
