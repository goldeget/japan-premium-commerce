<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Admin;

use Kuranea\BusinessProfile\Domain\ProfileVersion;

/** A Korean, non-sensitive summary of the fields changed between profile versions. */
final class ProfileChangeSet
{
    private const LABELS = [
        'brand' => '브랜드',
        'company_reference' => '회사 참고정보',
        'seller' => '판매자 정보',
        'customer_support' => '고객센터',
        'bank_accounts' => '은행 계좌 정보',
        'payment' => '결제 설정',
        'payment_methods' => '결제 수단',
        'bank_transfer' => '은행 이체',
        'shipping' => '배송 안내',
        'refund' => '반품·환불 정책',
        'content' => '고객 콘텐츠',
        'localization' => '다국어 설정',
        'seo' => 'SEO 설정',
        'pwa' => 'PWA 설정',
        'name' => '이름',
        'description' => '설명',
        'slogan' => '슬로건',
        'sources' => '공식 원본 이미지',
        'assets' => '브랜드 이미지',
        'primary_logo' => '로고 원본',
        'favicon_symbol' => '파비콘 원본',
        'pwa_icon' => 'PWA 아이콘 원본',
        'header_desktop' => 'PC 헤더 로고',
        'header_mobile' => '모바일 헤더 로고',
        'admin_login' => '관리자 로그인 로고',
        'email_logo' => '이메일 로고',
        'og_image' => 'OG 이미지',
        'favicon' => '파비콘',
        'favicon_16' => '16px 파비콘',
        'favicon_32' => '32px 파비콘',
        'apple_touch' => 'Apple Touch Icon',
        'pwa_192' => '192px PWA 아이콘',
        'pwa_512' => '512px PWA 아이콘',
        'pwa_maskable_512' => '마스크형 PWA 아이콘',
        'legal_name' => '법인명',
        'corporate_number' => '법인번호',
        'postal_code' => '우편번호',
        'address' => '주소',
        'phone' => '전화번호',
        'email' => '이메일',
        'hours' => '운영 시간',
        'support' => '지원 연락처',
        'source_url' => '참고 출처 URL',
        'verification_status' => '검증 상태',
        'authorization_status' => '판매자 승인 상태',
        'responsible_person' => '담당자',
        'representative' => '대표자',
        'enabled' => '활성화',
        'bank_account_id' => '연결 계좌',
        'default_locale' => '기본 고객 언어',
        'enabled_locales' => '사용 언어',
        'company_profile' => '회사소개',
        'terms' => '이용약관',
        'privacy' => '개인정보 처리방침',
        'specified_commercial_act' => '특정상거래법 표시',
        'title' => '제목',
        'short_name' => '짧은 이름',
        'theme_color' => '테마 색상',
        'background_color' => '배경 색상',
        'ja-JP' => '일본어',
        'en-US' => '영어',
        'ko-KR' => '한국어',
    ];

    /** @return list<array{label:string,previous:string,current:string}> */
    public static function between(?ProfileVersion $previous, ProfileVersion $current): array
    {
        $before = self::flatten($previous?->profile ?? []);
        $after = self::flatten($current->profile);
        $paths = array_unique([...array_keys($before), ...array_keys($after)]);
        sort($paths, SORT_STRING);

        $changes = [];
        foreach ($paths as $path) {
            $hasBefore = array_key_exists($path, $before);
            $hasAfter = array_key_exists($path, $after);
            $previousValue = $hasBefore ? $before[$path] : null;
            $currentValue = $hasAfter ? $after[$path] : null;
            if ($previousValue === $currentValue) {
                continue;
            }

            if ($path === 'bank_accounts') {
                $changes[] = [
                    'label' => self::label($path),
                    'previous' => self::hasBankAccounts($previousValue) ? '은행 계좌 정보 변경 전' : '등록된 계좌 없음',
                    'current' => self::hasBankAccounts($currentValue) ? '은행 계좌 정보 변경 후' : '등록된 계좌 없음',
                ];
                continue;
            }

            $changes[] = [
                'label' => self::label($path),
                'previous' => self::formatValue($path, $previousValue),
                'current' => self::formatValue($path, $currentValue),
            ];
        }

        return $changes;
    }

    /** @param array<string|int,mixed> $profile
     *  @return array<string,mixed>
     */
    private static function flatten(array $profile, string $prefix = ''): array
    {
        $fields = [];
        foreach ($profile as $key => $value) {
            $segment = (string) $key;
            $path = $prefix === '' ? $segment : $prefix . '.' . $segment;

            if ($segment === 'bank_accounts') {
                // Never expose account numbers, account holders, or bank snapshots in general history.
                $fields[$path] = is_array($value) ? $value : [];
                continue;
            }

            if ($path === 'localization.enabled_locales' && is_array($value)) {
                $fields[$path] = self::formatLocaleList($value);
                continue;
            }

            if ($segment === 'assets' && is_array($value)) {
                foreach ($value as $assetKey => $assetPath) {
                    $fields[$path . '.' . (string) $assetKey] = self::assetVersion($assetPath);
                }
                continue;
            }

            if ($segment === 'sources' && is_array($value)) {
                foreach ($value as $assetKey => $metadata) {
                    $assetPath = is_array($metadata) ? ($metadata['path'] ?? null) : $metadata;
                    $fields[$path . '.' . (string) $assetKey] = self::assetVersion($assetPath);
                }
                continue;
            }

            if (is_array($value)) {
                $fields += self::flatten($value, $path);
                continue;
            }

            $fields[$path] = self::formatValue($path, $value);
        }

        return $fields;
    }

    private static function label(string $path): string
    {
        return implode(' · ', array_map(
            static fn (string $segment): string => self::LABELS[$segment] ?? str_replace('_', ' ', $segment),
            explode('.', $path)
        ));
    }

    private static function formatValue(string $path, mixed $value): string
    {
        if ($path === 'localization.default_locale') {
            $locale = (string) $value;

            return self::LABELS[$locale] ?? '설정되지 않음';
        }

        $segments = explode('.', $path);
        $leaf = (string) end($segments);
        if ($leaf === 'bank_account_id') {
            return is_string($value) && $value !== '' ? '계좌 연결됨' : '계좌 미연결';
        }
        if ($leaf === 'authorization_status') {
            return match ((string) $value) {
                'approved' => '승인',
                'rejected' => '거절',
                default => '승인 대기',
            };
        }
        if ($leaf === 'verification_status') {
            return match ((string) $value) {
                'verified' => '검증됨',
                'user_provided_reference' => '사용자 제공 참고정보',
                'unverified' => '미확인',
                default => is_scalar($value) ? (string) $value : '설정되지 않음',
            };
        }
        if ($value === null || $value === '') {
            return '설정되지 않음';
        }
        if (is_bool($value)) {
            return $value ? '사용' : '사용 안 함';
        }

        return is_scalar($value) ? (string) $value : '설정값';
    }

    /** @param list<mixed> $locales */
    private static function formatLocaleList(array $locales): string
    {
        $labels = [];
        foreach ($locales as $locale) {
            $locale = (string) $locale;
            $labels[] = self::LABELS[$locale] ?? $locale;
        }

        return implode(', ', $labels);
    }

    private static function assetVersion(mixed $path): string
    {
        if (!is_string($path) || trim($path) === '') {
            return '등록 안 됨';
        }
        if (preg_match('~(?:versions/|source/[^/]+/)([a-f0-9]{64})(?:/|\.)~i', $path, $matches) === 1) {
            return '이미지 버전 ' . substr($matches[1], 0, 12);
        }

        return '등록된 이미지';
    }

    private static function hasBankAccounts(mixed $value): bool
    {
        return is_array($value) && $value !== [];
    }
}
