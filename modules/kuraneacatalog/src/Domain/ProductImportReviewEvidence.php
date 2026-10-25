<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

/** Staff-reviewed commercial fields kept separate from source snapshot values. */
final class ProductImportReviewEvidence
{
    /** @param list<int> $categoryIds
     *  @param list<string> $translationReviews
     */
    public function __construct(
        public readonly int $salePriceJpy,
        public readonly int $taxRulesGroupId,
        public readonly string $taxTreatment,
        public readonly ?string $taxEvidenceReference,
        public readonly int $ownStock,
        public readonly array $categoryIds,
        public readonly bool $optionsSupported,
        public readonly array $translationReviews,
        public readonly ?string $sourceContentHash = null
    ) {
        if ($salePriceJpy < 1 || $taxRulesGroupId < 0 || $ownStock < 0
            || !in_array($taxTreatment, ['taxable', 'explicitly_exempt'], true)
            || ($taxTreatment === 'taxable' && $taxRulesGroupId < 1)
            || ($taxTreatment === 'explicitly_exempt'
                && ($taxRulesGroupId !== 0 || trim((string) $taxEvidenceReference) === ''))
            || ($taxEvidenceReference !== null
                && (strlen($taxEvidenceReference) > 512 || preg_match('/[\x00-\x1f\x7f]/', $taxEvidenceReference) === 1))
            || ($sourceContentHash !== null && preg_match('/\A[a-f0-9]{64}\z/D', $sourceContentHash) !== 1)
            || !array_is_list($categoryIds)
            || $categoryIds === []
            || count($categoryIds) > 100
            || !array_is_list($translationReviews)) {
            throw new \InvalidArgumentException('상품 가져오기 검수 기록이 올바르지 않습니다.');
        }
        foreach ($categoryIds as $categoryId) {
            if (!is_int($categoryId) || $categoryId < 1) {
                throw new \InvalidArgumentException('검수 카테고리 ID가 올바르지 않습니다.');
            }
        }
        foreach ($translationReviews as $language) {
            if (!is_string($language) || !in_array($language, ['en', 'ko'], true)) {
                throw new \InvalidArgumentException('번역 검수 언어가 올바르지 않습니다.');
            }
        }
        if (count(array_unique($categoryIds)) !== count($categoryIds)
            || count(array_unique($translationReviews)) !== count($translationReviews)) {
            throw new \InvalidArgumentException('상품 검수 기록에 중복 항목이 있습니다.');
        }
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'salePriceJpy' => $this->salePriceJpy,
            'taxRulesGroupId' => $this->taxRulesGroupId,
            'taxTreatment' => $this->taxTreatment,
            'taxEvidenceReference' => $this->taxEvidenceReference,
            'ownStock' => $this->ownStock,
            'categoryIds' => $this->categoryIds,
            'optionsSupported' => $this->optionsSupported,
            'translationReviews' => $this->translationReviews,
            'sourceContentHash' => $this->sourceContentHash,
        ];
    }

    /** @param array<string, mixed> $data */
    public static function fromArray(array $data): self
    {
        $salePrice = $data['salePriceJpy'] ?? null;
        $taxRulesGroupId = $data['taxRulesGroupId'] ?? null;
        $taxTreatment = $data['taxTreatment'] ?? null;
        $taxEvidenceReference = $data['taxEvidenceReference'] ?? null;
        $ownStock = $data['ownStock'] ?? null;
        $categoryIds = $data['categoryIds'] ?? null;
        $optionsSupported = $data['optionsSupported'] ?? null;
        $translationReviews = $data['translationReviews'] ?? null;
        $sourceContentHash = $data['sourceContentHash'] ?? null;
        if (!is_int($salePrice) || !is_int($taxRulesGroupId) || !is_string($taxTreatment)
            || ($taxEvidenceReference !== null && !is_string($taxEvidenceReference))
            || ($sourceContentHash !== null && !is_string($sourceContentHash))
            || !is_int($ownStock) || !is_array($categoryIds) || !is_bool($optionsSupported)
            || !is_array($translationReviews)) {
            throw new \UnexpectedValueException('Persisted product import review evidence is invalid.');
        }

        return new self(
            $salePrice,
            $taxRulesGroupId,
            $taxTreatment,
            $taxEvidenceReference,
            $ownStock,
            $categoryIds,
            $optionsSupported,
            $translationReviews,
            $sourceContentHash
        );
    }
}
