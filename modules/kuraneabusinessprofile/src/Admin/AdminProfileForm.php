<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Admin;

use Kuranea\BusinessProfile\Domain\ProfileDefaults;
use Kuranea\BusinessProfile\Domain\ProfileVersion;

final class AdminProfileForm
{
    private const LOCALE_LABELS = [
        'ja-JP' => '일본어',
        'en-US' => '영어',
        'ko-KR' => '한국어',
    ];

    /** @return list<array{key: string, title: string, fields: list<array<string, mixed>>, description?: string}> */
    public static function sections(): array
    {
        $localized = static function (array $prefix, string $label, string $type): array {
            $fields = [];
            foreach (ProfileDefaults::LOCALES as $locale) {
                $fields[] = [
                    'path' => [...$prefix, $locale],
                    'label' => $label . ' · ' . self::LOCALE_LABELS[$locale],
                    'type' => $type,
                ];
            }

            return $fields;
        };
        $field = static fn (array $path, string $label, string $type = 'text', array $options = []): array => [
            'path' => $path,
            'label' => $label,
            'type' => $type,
            'options' => $options,
        ];
        $locales = ['ja-JP' => '일본어', 'en-US' => '영어', 'ko-KR' => '한국어'];
        $authorizationOptions = ['pending' => '확인 대기', 'approved' => '승인 확인', 'rejected' => '승인되지 않음'];
        $verificationOptions = ['user_provided_reference' => '사용자 제공 참고정보', 'verified' => '공식 자료 확인', 'unverified' => '미확인'];

        return [
            [
                'key' => 'basic',
                'title' => '기본 정보',
                'fields' => [
                    ...$localized(['brand', 'name'], '쇼핑몰 이름', 'text'),
                    ...$localized(['brand', 'description'], '서비스 설명', 'text'),
                ],
            ],
            [
                'key' => 'brand',
                'title' => '브랜드·로고',
                'description' => '공식 ORDENOWA PNG·JPEG·WebP 원본을 등록하면 비율을 유지한 PC·모바일·관리자·이메일·파비콘·PWA·OG 파생 이미지를 만듭니다. 기존 원본과 버전은 보존됩니다.',
                'fields' => [
                    ...$localized(['brand', 'slogan'], '슬로건', 'text'),
                    $field(['brand', 'assets', 'header_desktop'], '공식 로고 원본 · PC/모바일/관리자/이메일/OG', 'image_upload', ['slot' => 'primary_logo']),
                    $field(['brand', 'assets', 'favicon'], '파비콘용 공식 심벌 원본', 'image_upload', ['slot' => 'favicon_symbol']),
                    $field(['brand', 'assets', 'pwa_512'], 'PWA 앱 아이콘 공식 원본', 'image_upload', ['slot' => 'pwa_icon']),
                ],
            ],
            [
                'key' => 'company',
                'title' => '사업자 정보',
                'fields' => [
                    ...$localized(['company_reference', 'name'], '회사 참고정보 법인명', 'text'),
                    $field(['company_reference', 'corporate_number'], '회사 참고정보 법인번호'),
                    $field(['company_reference', 'postal_code'], '회사 참고정보 우편번호'),
                    $field(['company_reference', 'address'], '회사 참고정보 주소'),
                    $field(['company_reference', 'phone'], '회사 대표전화'),
                    $field(['company_reference', 'representative'], '회사 대표자'),
                    $field(['company_reference', 'source_url'], '회사 참고정보 출처 URL', 'url'),
                    $field(['company_reference', 'verification_status'], '회사 참고정보 확인 상태', 'select', $verificationOptions),
                    $field(['seller', 'authorization_status'], '판매사업 운영 승인 상태', 'readonly', $authorizationOptions),
                    ...$localized(['seller', 'legal_name'], '실제 판매자 법인명', 'text'),
                    $field(['seller', 'corporate_number'], '실제 판매자 법인번호'),
                    ...$localized(['seller', 'address'], '실제 판매사업 주소', 'text'),
                    ...$localized(['seller', 'representative'], '판매자 대표자', 'text'),
                    ...$localized(['seller', 'responsible_person'], '판매 운영 책임자', 'text'),
                ],
            ],
            [
                'key' => 'support',
                'title' => '고객센터',
                'fields' => [
                    $field(['customer_support', 'phone'], '쇼핑몰 고객센터 전화번호', 'tel'),
                    $field(['customer_support', 'email'], '쇼핑몰 고객센터 이메일', 'email'),
                    ...$localized(['customer_support', 'hours'], '고객센터 운영시간', 'text'),
                    $field(['seller', 'support', 'phone'], '법정 판매자 연락처 전화번호', 'tel'),
                    $field(['seller', 'support', 'email'], '법정 판매자 연락처 이메일', 'email'),
                ],
            ],
            [
                'key' => 'banks',
                'title' => '은행 계좌',
                'description' => '계좌번호와 예금주 정보는 별도 권한이 있는 관리자 화면에서만 조회·변경할 수 있습니다.',
                'fields' => [],
            ],
            ['key' => 'payment', 'title' => '결제 설정', 'fields' => $localized(['payment'], '결제 조건 및 안내', 'textarea')],
            ['key' => 'shipping', 'title' => '배송 설정', 'fields' => $localized(['shipping'], '배송 조건 및 안내', 'textarea')],
            ['key' => 'refund', 'title' => '반품·환불', 'fields' => $localized(['refund'], '반품·교환·환불 정책', 'textarea')],
            [
                'key' => 'terms',
                'title' => '이용약관',
                'fields' => [
                    ...$localized(['content', 'terms'], '이용약관', 'textarea'),
                    ...$localized(['content', 'privacy'], '개인정보 처리방침', 'textarea'),
                    ...$localized(['content', 'company_profile'], '회사소개', 'textarea'),
                ],
            ],
            [
                'key' => 'specified_commercial_act',
                'title' => '특정상거래법 표시',
                'fields' => $localized(['content', 'specified_commercial_act'], '특정상거래법 표시', 'textarea'),
            ],
            [
                'key' => 'localization',
                'title' => '다국어',
                'fields' => [
                    $field(['localization', 'default_locale'], '기본 고객 언어', 'select', $locales),
                    $field(['localization', 'enabled_locales'], '사용 언어', 'checkbox_group', $locales),
                ],
            ],
            [
                'key' => 'seo_pwa',
                'title' => 'SEO·PWA',
                'fields' => [
                    ...$localized(['seo', 'title'], '검색 결과 제목', 'text'),
                    ...$localized(['seo', 'description'], '검색 결과 설명', 'textarea'),
                    ...$localized(['pwa', 'name'], 'PWA 앱 이름', 'text'),
                    ...$localized(['pwa', 'short_name'], 'PWA 짧은 이름', 'text'),
                    $field(['pwa', 'theme_color'], 'PWA 테마 색상'),
                    $field(['pwa', 'background_color'], 'PWA 배경 색상'),
                ],
            ],
        ];
    }

    public static function apply(array $profile, array $submitted): array
    {
        $next = $profile;
        foreach (self::sections() as $section) {
            foreach ($section['fields'] as $definition) {
                $type = (string) $definition['type'];
                if (in_array($type, ['readonly', 'image_upload'], true)) {
                    continue;
                }

                $value = self::getPath($submitted, $definition['path']);
                if ($value === null) {
                    continue;
                }

                if ($type === 'checkbox_group') {
                    if (!is_array($value)) {
                        continue;
                    }
                    $allowed = array_keys($definition['options']);
                    $value = array_values(array_intersect($allowed, array_map('strval', $value)));
                } elseif ($type === 'select') {
                    if (!is_scalar($value) || !array_key_exists((string) $value, $definition['options'])) {
                        continue;
                    }
                    $value = (string) $value;
                } else {
                    if (!is_scalar($value)) {
                        continue;
                    }
                    $value = trim((string) $value);
                    $maxLength = $type === 'textarea' ? 20000 : 1000;
                    if (mb_strlen($value) > $maxLength) {
                        $value = mb_substr($value, 0, $maxLength);
                    }
                }

                self::setPath($next, $definition['path'], $value);
            }
        }

        $enabled = $next['localization']['enabled_locales'] ?? [];
        if (!in_array($next['localization']['default_locale'] ?? '', $enabled, true)) {
            $next['localization']['enabled_locales'] = array_values(array_unique([
                ...$enabled,
                (string) ($next['localization']['default_locale'] ?? 'ja-JP'),
            ]));
        }

        return $next;
    }

    public static function render(
        array $profile,
        string $actionUrl,
        string $token,
        bool $canPublish = false,
        string $bankUrl = '',
        string $assetBaseUrl = ''
    ): string
    {
        $html = '<form method="post" enctype="multipart/form-data" action="' . self::escape($actionUrl) . '" class="ordenowa-profile-settings">';
        $html .= '<input type="hidden" name="token" value="' . self::escape($token) . '">';
        $html .= '<nav class="ordenowa-settings-nav" aria-label="쇼핑몰 운영 설정">';
        foreach (self::sections() as $section) {
            $html .= '<a href="#ordenowa-' . self::escape($section['key']) . '">' . self::escape($section['title']) . '</a>';
        }
        $html .= '</nav>';

        foreach (self::sections() as $section) {
            $html .= '<section class="panel ordenowa-settings-section" id="ordenowa-' . self::escape($section['key']) . '">';
            $html .= '<h2>' . self::escape($section['title']) . '</h2>';
            if (!empty($section['description'])) {
                $html .= '<p>' . self::escape($section['description']) . '</p>';
            }
            if ($section['key'] === 'banks') {
                $html .= '<a class="btn btn-default" href="' . self::escape($bankUrl) . '">은행 계좌 관리</a>';
            }

            foreach ($section['fields'] as $definition) {
                $html .= self::renderField($definition, self::getPath($profile, $definition['path']), $assetBaseUrl);
            }

            $html .= '</section>';
        }

        $html .= '<div class="panel-footer">';
        $html .= '<button class="btn btn-default" type="submit" name="submitOrdenowaSaveDraft" value="1">초안 저장</button>';
        $html .= '<button class="btn btn-default" type="submit" name="submitOrdenowaPreview" value="1">초안 미리보기</button>';
        if ($canPublish) {
            $html .= '<button class="btn btn-primary" type="submit" name="submitOrdenowaPublish" value="1">변경사항 게시</button>';
        }
        $html .= '</div></form>';

        return $html;
    }

    /** @param list<ProfileVersion> $versions */
    public static function renderHistory(
        array $versions,
        int $draftVersionId,
        int $publishedVersionId,
        string $actionUrl,
        string $token,
        bool $canRestore = true
    ): string
    {
        $html = '<section class="panel ordenowa-profile-history"><h2>변경 이력</h2>';
        if ($versions === []) {
            return $html . '<p>저장된 변경 이력이 없습니다.</p></section>';
        }

        $html .= '<div class="table-responsive"><table class="table"><thead><tr><th>버전</th><th>변경자 ID</th><th>변경일시</th><th>상태</th><th>작업</th></tr></thead><tbody>';
        foreach ($versions as $version) {
            $state = [];
            if ($version->id === $draftVersionId) {
                $state[] = '현재 초안';
            }
            if ($version->id === $publishedVersionId) {
                $state[] = '게시 중';
            }
            $stateLabel = $state === [] ? '이전 버전' : implode(' · ', $state);
            $html .= '<tr><td>#' . $version->id . '</td><td>' . $version->employeeId . '</td><td>'
                . self::escape($version->createdAt) . '</td><td>' . self::escape($stateLabel) . '</td><td>';
            $html .= '<form method="post" action="' . self::escape($actionUrl) . '" class="ordenowa-history-action">'
                . '<input type="hidden" name="token" value="' . self::escape($token) . '">'
                . '<input type="hidden" name="preview_version_id" value="' . $version->id . '">'
                . '<button class="btn btn-default btn-sm" type="submit" name="submitOrdenowaPreview" value="1">미리보기</button></form> ';
            if ($canRestore) {
                $html .= '<form method="post" action="' . self::escape($actionUrl) . '" class="ordenowa-history-action">'
                    . '<input type="hidden" name="token" value="' . self::escape($token) . '">'
                    . '<input type="hidden" name="restore_version_id" value="' . $version->id . '">'
                    . '<button class="btn btn-default btn-sm" type="submit" name="submitOrdenowaRestore" value="1"'
                    . ($version->id === $draftVersionId ? ' disabled' : '') . '>이 버전을 초안으로 복원</button></form>';
            }
            $html .= '</td></tr>';
        }

        return $html . '</tbody></table></div><p>변경 이력에는 계좌번호와 예금주를 표시하지 않습니다.</p></section>';
    }

    /** Render a read-only, escaped preview within the authenticated admin page. */
    public static function renderPreview(array $profile, string $assetBaseUrl = ''): string
    {
        $locale = (string) ($profile['localization']['default_locale'] ?? 'ja-JP');
        $brandName = (string) ($profile['brand']['name'][$locale] ?? '');
        $html = '<section class="panel ordenowa-profile-preview"><h2>고객 화면 미리보기 · '
            . self::escape(self::LOCALE_LABELS[$locale] ?? $locale) . '</h2><h3>' . self::escape($brandName) . '</h3>';
        $assets = (array) ($profile['brand']['assets'] ?? []);
        foreach ([
            'header_desktop' => 'PC 헤더 로고',
            'header_mobile' => '모바일 헤더 로고',
            'email_logo' => '이메일 로고',
            'favicon_32' => '브라우저 파비콘',
            'apple_touch' => 'Apple Touch Icon',
            'pwa_512' => 'PWA 아이콘',
            'og_image' => '공유용 OG 이미지',
        ] as $assetKey => $label) {
            $path = $assets[$assetKey] ?? null;
            if (!is_string($path) || preg_match('~\\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/[A-Za-z0-9._-]+\\.(?:png|ico)\\z~D', $path) !== 1) {
                continue;
            }
            $src = rtrim($assetBaseUrl, '/') . '/' . $path;
            $html .= '<figure class="ordenowa-preview-asset"><img src="' . self::escape($src) . '" alt="'
                . self::escape($label) . '" loading="lazy"><figcaption>' . self::escape($label) . '</figcaption></figure>';
        }

        foreach ([
            '설명' => $profile['brand']['description'][$locale] ?? '',
            '슬로건' => $profile['brand']['slogan'][$locale] ?? '',
            '고객센터' => $profile['customer_support']['phone'] ?? '',
            '결제 안내' => $profile['payment'][$locale] ?? '',
            '배송 안내' => $profile['shipping'][$locale] ?? '',
            '반품·환불' => $profile['refund'][$locale] ?? '',
            '특정상거래법 표시' => $profile['content']['specified_commercial_act'][$locale] ?? '',
        ] as $label => $value) {
            if (!is_scalar($value) || trim((string) $value) === '') {
                continue;
            }
            $html .= '<article><h4>' . self::escape($label) . '</h4><p>'
                . nl2br(self::escape((string) $value), false) . '</p></article>';
        }

        return $html . '<p class="help-block">이 미리보기는 관리자 전용입니다. 게시 또는 판매 활성화를 의미하지 않습니다.</p></section>';
    }

    private static function renderField(array $definition, mixed $value, string $assetBaseUrl = ''): string
    {
        $path = $definition['path'];
        $name = 'profile';
        foreach ($path as $part) {
            $name .= '[' . $part . ']';
        }
        $id = 'ordenowa-' . implode('-', array_map(static fn ($part): string => preg_replace('/[^A-Za-z0-9_-]/', '-', (string) $part) ?? '', $path));
        $label = self::escape((string) $definition['label']);
        $type = (string) $definition['type'];
        $html = '<div class="form-group ordenowa-profile-field"><label for="' . self::escape($id) . '">' . $label . '</label>';

        if ($type === 'readonly') {
            $display = $definition['options'][(string) $value] ?? '확인 대기';
            $html .= '<p id="' . self::escape($id) . '" class="form-control-static">' . self::escape((string) $display) . '</p>';
        } elseif ($type === 'image_upload') {
            $slot = (string) ($definition['options']['slot'] ?? '');
            $html .= '<input class="form-control" type="file" id="' . self::escape($id) . '" name="brand_uploads['
                . self::escape($slot) . ']" accept="image/png,image/jpeg,image/webp">';
            $html .= '<p class="help-block">원본 파일은 10MiB 이하, 각 변 32~8192px이어야 합니다.</p>';
            if (is_string($value) && preg_match('~\\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/[A-Za-z0-9._-]+\\.(?:png|ico)\\z~D', $value) === 1) {
                $previewUrl = rtrim($assetBaseUrl, '/') . '/' . $value;
                $html .= '<img class="ordenowa-asset-preview" src="' . self::escape($previewUrl) . '" alt="'
                    . self::escape((string) $definition['label']) . ' 미리보기" loading="lazy">';
            } else {
                $html .= '<p class="text-muted">등록된 공식 원본이 없습니다.</p>';
            }
        } elseif ($type === 'textarea') {
            $html .= '<textarea class="form-control" id="' . self::escape($id) . '" name="' . self::escape($name) . '" rows="5">'
                . self::escape((string) $value) . '</textarea>';
        } elseif ($type === 'select') {
            $html .= '<select class="form-control" id="' . self::escape($id) . '" name="' . self::escape($name) . '">';
            foreach ($definition['options'] as $optionValue => $optionLabel) {
                $selected = (string) $value === (string) $optionValue ? ' selected' : '';
                $html .= '<option value="' . self::escape((string) $optionValue) . '"' . $selected . '>'
                    . self::escape((string) $optionLabel) . '</option>';
            }
            $html .= '</select>';
        } elseif ($type === 'checkbox_group') {
            $selectedValues = is_array($value) ? $value : [];
            foreach ($definition['options'] as $optionValue => $optionLabel) {
                $checkboxId = $id . '-' . self::escape((string) $optionValue);
                $checked = in_array($optionValue, $selectedValues, true) ? ' checked' : '';
                $html .= '<div class="checkbox"><label for="' . $checkboxId . '"><input type="checkbox" id="' . $checkboxId
                    . '" name="' . self::escape($name) . '[]" value="' . self::escape((string) $optionValue) . '"' . $checked . '> '
                    . self::escape((string) $optionLabel) . '</label></div>';
            }
        } else {
            $html .= '<input class="form-control" type="' . self::escape($type) . '" id="' . self::escape($id)
                . '" name="' . self::escape($name) . '" value="' . self::escape((string) $value) . '">';
        }

        $html .= '</div>';

        return $html;
    }

    private static function getPath(array $source, array $path): mixed
    {
        $value = $source;
        foreach ($path as $key) {
            if (!is_array($value) || !array_key_exists($key, $value)) {
                return null;
            }
            $value = $value[$key];
        }

        return $value;
    }

    private static function setPath(array &$target, array $path, mixed $value): void
    {
        $cursor = &$target;
        foreach ($path as $index => $key) {
            if ($index === count($path) - 1) {
                $cursor[$key] = $value;
                return;
            }
            if (!isset($cursor[$key]) || !is_array($cursor[$key])) {
                $cursor[$key] = [];
            }
            $cursor = &$cursor[$key];
        }
    }

    private static function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
