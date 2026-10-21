<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Domain;

interface PostalAddressLookup
{
    /** @return list<PostalAddress> */
    public function lookupByPostcode(string $postcode, int $limit = 20): array;

    /** @return list<PostalAddress> */
    public function searchJapaneseAddress(string $query, int $limit = 20): array;
}
