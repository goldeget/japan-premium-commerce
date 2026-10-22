<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

final class ProfileDefaults
{
    public const LOCALES = ['ja-JP', 'en-US', 'ko-KR'];

    public static function initial(): array
    {
        $emptyLocales = array_fill_keys(self::LOCALES, '');

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
                'assets' => [],
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
            'shipping' => $emptyLocales,
            'refund' => $emptyLocales,
            'content' => [
                'company_profile' => $emptyLocales,
                'terms' => $emptyLocales,
                'privacy' => $emptyLocales,
                'specified_commercial_act' => $emptyLocales,
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
