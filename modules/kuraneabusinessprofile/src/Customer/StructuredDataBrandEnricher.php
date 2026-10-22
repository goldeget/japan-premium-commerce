<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

final class StructuredDataBrandEnricher
{
    /** @param array<string|int, mixed> $structuredData
     *  @return array<string|int, mixed>
     */
    public static function apply(array $structuredData, string $brandName): array
    {
        if (trim($brandName) === '') {
            return $structuredData;
        }

        foreach ($structuredData as &$element) {
            if (!is_array($element)) {
                continue;
            }

            $type = $element['@type'] ?? null;
            if (!in_array($type, ['Organization', 'WebSite'], true)) {
                continue;
            }

            $element['name'] = $brandName;
        }
        unset($element);

        return $structuredData;
    }
}
