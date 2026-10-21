<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Domain;

final class PostalAddressIndex implements PostalAddressLookup
{
    /** @var array<string, list<PostalAddress>> */
    private array $byPostcode = [];

    /** @var array<string, PostalAddress> */
    private array $byCandidateId = [];

    /** @param iterable<PostalAddress> $addresses */
    public function __construct(iterable $addresses)
    {
        foreach ($addresses as $address) {
            if (isset($this->byCandidateId[$address->candidateId])) {
                continue;
            }

            $this->byCandidateId[$address->candidateId] = $address;
            $this->byPostcode[$address->postcode][] = $address;
        }
    }

    /** @return list<PostalAddress> */
    public function lookupByPostcode(string $postcode, int $limit = 20): array
    {
        $normalized = ZipCode::normalize($postcode);

        return $normalized === null ? [] : array_slice($this->byPostcode[$normalized] ?? [], 0, max(0, $limit));
    }

    public function searchJapaneseAddress(string $query, int $limit = 20): array
    {
        return $this->search($query, $limit);
    }

    /** @return list<PostalAddress> */
    public function search(string $query, int $limit = 20): array
    {
        $query = trim($query);
        if ($query === '' || $limit < 1) {
            return [];
        }

        $postcode = ZipCode::normalize($query);
        if ($postcode !== null) {
            return array_slice($this->byPostcode[$postcode] ?? [], 0, $limit);
        }

        $matches = [];
        foreach ($this->byCandidateId as $address) {
            $searchable = $address->prefecture . $address->municipality . $address->town;
            $position = function_exists('mb_stripos')
                ? mb_stripos($searchable, $query, 0, 'UTF-8')
                : stripos($searchable, $query);

            if ($position !== false) {
                $matches[] = $address;
                if (count($matches) >= $limit) {
                    break;
                }
            }
        }

        return $matches;
    }

    public function select(string $candidateId): ?PostalAddress
    {
        return $this->byCandidateId[$candidateId] ?? null;
    }
}
