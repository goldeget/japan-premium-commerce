<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Domain;

use InvalidArgumentException;

/** Validated values submitted by the Korean native-product manager. */
final class ProductAdminDraft
{
    /**
     * @param list<int> $categoryIds
     * @param list<array{name:string, values:list<string>}> $optionGroups
     * @param array<int, int> $combinationQuantities
     */
    private function __construct(
        public readonly string $nameJa,
        public readonly string $nameKo,
        public readonly int $priceJpy,
        public readonly int $quantity,
        public readonly array $categoryIds,
        public readonly string $descriptionJa,
        public readonly string $descriptionKo,
        public readonly array $optionGroups,
        public readonly array $combinationQuantities
    ) {
    }

    /** @param array<string, mixed> $values */
    public static function fromArray(array $values): self
    {
        $nameJa = self::text($values['name_ja'] ?? null, '일본어 상품명', 128, true, true);
        $nameKo = self::text($values['name_ko'] ?? null, '한국어 상품명', 128, false, true);
        if ($nameKo === '') {
            $nameKo = $nameJa;
        }

        $rawPrice = $values['price_jpy'] ?? null;
        if (!is_string($rawPrice) && !is_int($rawPrice)) {
            throw new InvalidArgumentException('JPY 가격은 1 이상 정수로 입력해 주세요.');
        }
        $priceValue = trim((string) $rawPrice);
        if (preg_match('/\A[0-9]{1,9}\z/', $priceValue) !== 1 || (int) $priceValue < 1) {
            throw new InvalidArgumentException('JPY 가격은 1 이상 정수로 입력해 주세요.');
        }

        $rawQuantity = $values['quantity'] ?? null;
        if (!is_string($rawQuantity) && !is_int($rawQuantity)) {
            throw new InvalidArgumentException('재고는 0 이상 정수로 입력해 주세요.');
        }
        $quantityValue = trim((string) $rawQuantity);
        if (preg_match('/\A[0-9]{1,7}\z/', $quantityValue) !== 1) {
            throw new InvalidArgumentException('재고는 0 이상 정수로 입력해 주세요.');
        }

        $rawCategories = $values['category_ids'] ?? [];
        if (!is_array($rawCategories)) {
            throw new InvalidArgumentException('카테고리를 하나 이상 선택해 주세요.');
        }
        $categoryIds = [];
        foreach ($rawCategories as $rawCategoryId) {
            if (!is_string($rawCategoryId) && !is_int($rawCategoryId)) {
                throw new InvalidArgumentException('카테고리 선택값이 올바르지 않습니다.');
            }
            $categoryValue = trim((string) $rawCategoryId);
            if (preg_match('/\A[1-9][0-9]{0,8}\z/', $categoryValue) !== 1) {
                throw new InvalidArgumentException('카테고리 선택값이 올바르지 않습니다.');
            }
            $categoryIds[] = (int) $categoryValue;
        }
        $categoryIds = array_values(array_unique($categoryIds));
        if ($categoryIds === []) {
            throw new InvalidArgumentException('카테고리를 하나 이상 선택해 주세요.');
        }

        $descriptionJa = self::text($values['description_ja'] ?? null, '일본어 상세 설명', 20000, false);
        $descriptionKo = self::text($values['description_ko'] ?? null, '한국어 상세 설명', 20000, false);
        if ($descriptionKo === '') {
            $descriptionKo = $descriptionJa;
        }

        return new self(
            $nameJa,
            $nameKo,
            (int) $priceValue,
            (int) $quantityValue,
            $categoryIds,
            $descriptionJa,
            $descriptionKo,
            self::parseOptionGroups($values['options'] ?? ''),
            self::parseCombinationQuantities($values['combination_quantities'] ?? [])
        );
    }

    /** @return array<int, int> */
    private static function parseCombinationQuantities(mixed $rawQuantities): array
    {
        if (!is_array($rawQuantities) || count($rawQuantities) > 40) {
            throw new InvalidArgumentException('옵션 조합별 재고 입력값을 확인해 주세요.');
        }

        $quantities = [];
        foreach ($rawQuantities as $rawCombinationId => $rawQuantity) {
            if (is_int($rawCombinationId)) {
                $combinationId = $rawCombinationId;
            } elseif (is_string($rawCombinationId)
                && preg_match('/\A[1-9][0-9]{0,8}\z/D', $rawCombinationId) === 1) {
                $combinationId = (int) $rawCombinationId;
            } else {
                throw new InvalidArgumentException('옵션 조합별 재고 항목이 올바르지 않습니다.');
            }
            if ($combinationId < 1 || $combinationId > 999999999
                || (!is_string($rawQuantity) && !is_int($rawQuantity))) {
                throw new InvalidArgumentException('옵션 조합별 재고 항목이 올바르지 않습니다.');
            }

            $quantityValue = trim((string) $rawQuantity);
            if (preg_match('/\A[0-9]{1,7}\z/D', $quantityValue) !== 1) {
                throw new InvalidArgumentException('옵션 조합별 재고는 0 이상 정수로 입력해 주세요.');
            }
            $quantities[$combinationId] = (int) $quantityValue;
        }

        ksort($quantities, SORT_NUMERIC);

        return $quantities;
    }

    /** @return list<array{name:string, values:list<string>}> */
    private static function parseOptionGroups(mixed $rawOptions): array
    {
        if (!is_string($rawOptions)) {
            throw new InvalidArgumentException('상품 옵션 입력값을 확인해 주세요.');
        }
        $rawOptions = trim($rawOptions);
        if ($rawOptions === '') {
            return [];
        }

        $lines = preg_split('/\R/u', $rawOptions) ?: [];
        if (count($lines) > 3) {
            throw new InvalidArgumentException('옵션 그룹은 최대 3개까지 등록할 수 있습니다.');
        }

        $groups = [];
        $seenNames = [];
        $combinationCount = 1;
        foreach ($lines as $line) {
            $parts = explode(':', $line, 2);
            if (count($parts) !== 2) {
                throw new InvalidArgumentException('옵션은 그룹명:값1|값2 형식으로 한 줄씩 입력해 주세요.');
            }
            $groupName = trim($parts[0]);
            $groupKey = mb_strtolower($groupName, 'UTF-8');
            if ($groupName === '' || mb_strlen($groupName, 'UTF-8') > 64 || isset($seenNames[$groupKey])) {
                throw new InvalidArgumentException('옵션 그룹명은 비어 있거나 중복될 수 없습니다.');
            }
            $seenNames[$groupKey] = true;

            $values = [];
            foreach (explode('|', $parts[1]) as $rawValue) {
                $optionValue = trim($rawValue);
                if ($optionValue === '' || mb_strlen($optionValue, 'UTF-8') > 128) {
                    throw new InvalidArgumentException('옵션 값은 1~128자 범위로 입력해 주세요.');
                }
                $values[] = $optionValue;
            }
            $values = array_values(array_unique($values));
            if ($values === [] || count($values) !== count(explode('|', $parts[1]))) {
                throw new InvalidArgumentException('같은 옵션 그룹 안에 비어 있거나 중복된 값이 있습니다.');
            }
            $combinationCount *= count($values);
            if ($combinationCount > 40) {
                throw new InvalidArgumentException('옵션 조합은 최대 40개까지 등록할 수 있습니다.');
            }
            $groups[] = ['name' => $groupName, 'values' => $values];
        }

        return $groups;
    }

    private static function text(mixed $value, string $label, int $maxLength, bool $required, bool $countCharacters = false): string
    {
        if (!is_string($value) && !is_numeric($value)) {
            throw new InvalidArgumentException($label . '을(를) 확인해 주세요.');
        }
        $text = trim((string) $value);
        $length = $countCharacters ? mb_strlen($text, 'UTF-8') : strlen($text);
        if (($required && $text === '') || $length > $maxLength || str_contains($text, "\0")) {
            throw new InvalidArgumentException($label . ' 입력값을 확인해 주세요.');
        }

        return $text;
    }
}
