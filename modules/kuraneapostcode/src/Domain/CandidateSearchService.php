<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Domain;

final class CandidateSearchService
{
    public function __construct(private readonly PostalAddressLookup $lookup)
    {
    }

    /** @return list<PostalAddress> */
    public function search(string $query, int $limit = 10): array
    {
        if (preg_match('//u', $query) !== 1) {
            return [];
        }

        $query = preg_replace('/[\s\p{Z}]+/u', '', trim($query)) ?? '';
        if ($query === '' || preg_match('/[\x00-\x1F\x7F%_\\\\]/u', $query) === 1
            || self::characterLength($query) > 128) {
            return [];
        }

        $limit = max(1, min(100, $limit));
        $postcode = ZipCode::normalize($query);
        if ($postcode !== null) {
            return $this->lookup->lookupByPostcode($postcode, $limit);
        }

        // Numeric or hyphen-only input is an invalid postcode, not a useful
        // Japanese address substring.
        if (preg_match('/^[0-9０-９\-‐‑‒–—−－]+$/u', $query) === 1 || self::characterLength($query) < 2) {
            return [];
        }

        return $this->lookup->searchJapaneseAddress($query, min(20, $limit));
    }

    private static function characterLength(string $value): int
    {
        if (function_exists('mb_strlen')) {
            return mb_strlen($value, 'UTF-8');
        }

        return preg_match_all('/./us', $value) ?: 0;
    }
}
