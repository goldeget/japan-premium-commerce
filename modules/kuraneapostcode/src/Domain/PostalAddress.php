<?php

declare(strict_types=1);

namespace Kuranea\Postcode\Domain;

final class PostalAddress
{
    public readonly string $candidateId;

    public function __construct(
        public readonly string $postcode,
        public readonly string $jisCode,
        public readonly string $prefecture,
        public readonly string $municipality,
        public readonly string $town
    ) {
        $this->candidateId = hash('sha256', implode("\0", [
            $postcode,
            $jisCode,
            $prefecture,
            $municipality,
            $town,
        ]));
    }

    /**
     * Map a selected Japan Post address into PrestaShop's native address fields.
     * State IDs are keyed by the two-digit JIS prefecture code (01 through 47).
     * A missing state mapping returns null so callers can keep manual entry open.
     *
     * @param array<string|int, int> $prefectureStateIds
     * @return array{postcode:string,id_state:int,city:string,address1:string,address2:string}|null
     */
    public function toNativeAddressFields(array $prefectureStateIds, string $building = ''): ?array
    {
        $prefectureCode = substr($this->jisCode, 0, 2);
        $stateId = $prefectureStateIds[$prefectureCode] ?? null;
        if (!is_int($stateId) || $stateId < 1) {
            return null;
        }

        return [
            'postcode' => $this->postcode,
            'id_state' => $stateId,
            'city' => $this->municipality,
            'address1' => $this->town,
            'address2' => $building,
        ];
    }
}
