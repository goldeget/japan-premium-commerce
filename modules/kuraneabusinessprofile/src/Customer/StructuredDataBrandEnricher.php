<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

final class StructuredDataBrandEnricher
{
    /** @param array<string|int, mixed> $structuredData
     *  @return array<string|int, mixed>
     */
    public static function apply(array $structuredData, string $brandName, string $brandLogoUrl = ''): array
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
            if ($type === 'Organization') {
                // Replace the complete core PS_LOGO image: its dimensions belong to a different asset.
                unset($element['logo']);
                if ($brandLogoUrl !== '') {
                    $element['logo'] = ['@type' => 'ImageObject', 'url' => $brandLogoUrl];
                }
            }
        }
        unset($element);

        return $structuredData;
    }
}
