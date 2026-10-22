<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

final class ProfileDefaults
{
    public const LOCALES = ['ja-JP', 'en-US', 'ko-KR'];

    public static function initial(): array
    {
        $emptyLocales = array_fill_keys(self::LOCALES, '');
        $logoVersion = '1ce6b0a015ed6748ef904cdff095ff0f38ab72c9c51fe189c33d19dc797f23fd';
        $faviconVersion = 'c357fde8a2942e5ed0483b78d3c1a1a134163a7e5197a80072f30f75b90d72f2';
        $pwaVersion = 'eae5c30405dcd420f03929a3a5fc882d94e057f75e26cf0a564aa7d5cbab3ea8';

        return [
            'brand' => [
                'name' => [
                    'ja-JP' => 'オーデノワ',
                    'en-US' => 'ORDENOWA',
                    'ko-KR' => '오데노와',
                ],
                'description' => [
                    'ja-JP' => '法人向け商品調達・受発注サービス',
                    'en-US' => 'Corporate product sourcing and purchase order service',
                    'ko-KR' => '법인 대상 상품 조달 및 발주 서비스',
                ],
                'slogan' => [
                    'ja-JP' => '企業と商品をつなぐ、次世代のB2B調達プラットフォーム',
                    'en-US' => 'The next-generation B2B procurement platform connecting businesses and products',
                    'ko-KR' => '기업과 상품을 연결하는 차세대 B2B 조달 플랫폼',
                ],
                'sources' => [
                    'primary_logo' => [
                        'path' => 'source/primary_logo/' . $logoVersion . '.png',
                        'sha256' => $logoVersion,
                        'mime' => 'image/png',
                        'width' => 2172,
                        'height' => 724,
                    ],
                    'favicon_symbol' => [
                        'path' => 'source/favicon_symbol/' . $faviconVersion . '.png',
                        'sha256' => $faviconVersion,
                        'mime' => 'image/png',
                        'width' => 1254,
                        'height' => 1254,
                    ],
                    'pwa_icon' => [
                        'path' => 'source/pwa_icon/' . $pwaVersion . '.png',
                        'sha256' => $pwaVersion,
                        'mime' => 'image/png',
                        'width' => 1254,
                        'height' => 1254,
                    ],
                ],
                'assets' => [
                    'header_desktop' => 'img/ordenowa/versions/' . $logoVersion . '/official-header-desktop.png',
                    'header_mobile' => 'img/ordenowa/versions/' . $logoVersion . '/official-header-mobile.png',
                    'admin_login' => 'img/ordenowa/versions/' . $logoVersion . '/official-admin-login.png',
                    'email_logo' => 'img/ordenowa/versions/' . $logoVersion . '/official-email-logo.png',
                    'og_image' => 'img/ordenowa/versions/' . $logoVersion . '/official-og-brand.png',
                    'favicon' => 'img/ordenowa/versions/' . $faviconVersion . '/official-favicon.ico',
                    'favicon_16' => 'img/ordenowa/versions/' . $faviconVersion . '/official-favicon-16.png',
                    'favicon_32' => 'img/ordenowa/versions/' . $faviconVersion . '/official-favicon-32.png',
                    'apple_touch' => 'img/ordenowa/versions/' . $pwaVersion . '/official-apple-touch-icon.png',
                    'pwa_192' => 'img/ordenowa/versions/' . $pwaVersion . '/official-pwa-192.png',
                    'pwa_512' => 'img/ordenowa/versions/' . $pwaVersion . '/official-pwa-512.png',
                    'pwa_maskable_512' => 'img/ordenowa/versions/' . $pwaVersion . '/official-pwa-maskable-512.png',
                ],
            ],
            'company_reference' => [
                'name' => [
                    'ja-JP' => 'ロジスティード株式会社',
                    'en-US' => 'LOGISTEED, Ltd.',
                    'ko-KR' => '로지스티드 주식회사',
                ],
                'corporate_number' => '4010001226242',
                'postal_code' => '104-8350',
                'address' => '東京都中央区京橋二丁目9番2号 ロジスティードビル',
                'phone' => '03-6263-2800',
                'representative' => '中谷 康夫',
                'source_url' => 'https://www.logisteed.com/jp/profile/outline/',
                'verification_status' => 'user_provided_reference',
            ],
            'seller' => [
                'authorization_status' => 'pending',
                'legal_name' => $emptyLocales,
                'corporate_number' => '',
                'address' => $emptyLocales,
                'representative' => $emptyLocales,
                'responsible_person' => $emptyLocales,
                'support' => ['phone' => '', 'email' => ''],
            ],
            'customer_support' => [
                'phone' => '',
                'email' => '',
                'hours' => $emptyLocales,
            ],
            'bank_accounts' => [],
            'payment' => $emptyLocales,
            'payment_methods' => [
                'bank_transfer' => [
                    'enabled' => false,
                    'bank_account_id' => '',
                ],
            ],
            'shipping' => $emptyLocales,
            'refund' => $emptyLocales,
            'content' => [
                'company_profile' => $emptyLocales,
                'terms' => $emptyLocales,
                'privacy' => $emptyLocales,
                'specified_commercial_act' => $emptyLocales,
            ],
            'localization' => [
                'default_locale' => 'ja-JP',
                'enabled_locales' => self::LOCALES,
            ],
            'seo' => [
                'title' => [
                    'ja-JP' => 'オーデノワ',
                    'en-US' => 'ORDENOWA',
                    'ko-KR' => '오데노와',
                ],
                'description' => $emptyLocales,
            ],
            'pwa' => [
                'name' => [
                    'ja-JP' => 'オーデノワ',
                    'en-US' => 'ORDENOWA',
                    'ko-KR' => '오데노와',
                ],
                'short_name' => [
                    'ja-JP' => 'オーデノワ',
                    'en-US' => 'ORDENOWA',
                    'ko-KR' => '오데노와',
                ],
                'theme_color' => '#10243a',
                'background_color' => '#ffffff',
            ],
        ];
    }
}
