<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

final class PwaManifestBuilder
{
    /** @return array<string, mixed> */
    public static function build(array $profile, string $baseUrl): array
    {
        $locale = (string) ($profile['_resolved_locale'] ?? $profile['localization']['default_locale'] ?? 'ja-JP');
        $assets = (array) ($profile['brand']['assets'] ?? []);
        $icons = [];
        foreach ([
            ['pwa_192', '192x192', 'any'],
            ['pwa_512', '512x512', 'any'],
            ['pwa_maskable_512', '512x512', 'maskable'],
        ] as [$key, $size, $purpose]) {
            $path = $assets[$key] ?? null;
            if (!is_string($path) || preg_match('~\\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/[A-Za-z0-9._-]+\\.png\\z~D', $path) !== 1) {
                continue;
            }

            $icons[] = [
                'src' => rtrim($baseUrl, '/') . '/' . $path,
                'sizes' => $size,
                'type' => 'image/png',
                'purpose' => $purpose,
            ];
        }

        $brandName = (string) ($profile['brand']['name'][$locale] ?? 'ORDENOWA');
        $name = (string) ($profile['pwa']['name'][$locale] ?? $brandName);

        return [
            'id' => '/',
            'name' => $name,
            'short_name' => (string) ($profile['pwa']['short_name'][$locale] ?? $name),
            'description' => (string) ($profile['brand']['description'][$locale] ?? ''),
            'lang' => $locale,
            'start_url' => '/',
            'scope' => '/',
            'display' => 'standalone',
            'display_override' => ['standalone', 'minimal-ui'],
            'orientation' => 'any',
            'background_color' => self::color((string) ($profile['pwa']['background_color'] ?? ''), '#ffffff'),
            'theme_color' => self::color((string) ($profile['pwa']['theme_color'] ?? ''), '#10243a'),
            'icons' => $icons,
        ];
    }

    private static function color(string $value, string $fallback): string
    {
        return preg_match('/\\A#[0-9A-Fa-f]{6}\\z/D', $value) === 1 ? $value : $fallback;
    }
}
