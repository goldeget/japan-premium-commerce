<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

final class ProfileValidator
{
    private const REQUIRED_SELLER_LOCALE_FIELDS = ['legal_name', 'address', 'representative', 'responsible_person'];
    private const REQUIRED_CONTENT_FIELDS = ['payment', 'shipping', 'refund'];

    /** @return list<string> Korean validation messages */
    public function validateDraft(array $profile): array
    {
        $errors = [];

        if (!isset($profile['brand']['name']) || !is_array($profile['brand']['name'])) {
            return ['브랜드 이름을 입력해 주세요.'];
        }

        foreach (ProfileDefaults::LOCALES as $locale) {
            $name = $profile['brand']['name'][$locale] ?? null;
            if (!is_string($name) || trim($name) === '' || mb_strlen($name) > 120) {
                $errors[] = '브랜드 이름(' . $locale . ')은 1~120자로 입력해 주세요.';
            }
        }

        $status = $profile['seller']['authorization_status'] ?? null;
        if (!in_array($status, ['pending', 'approved', 'rejected'], true)) {
            $errors[] = '판매사업 승인 상태가 올바르지 않습니다.';
        }

        foreach (['brand', 'company_reference', 'seller', 'customer_support', 'bank_accounts', 'payment', 'shipping', 'refund', 'content', 'localization', 'seo', 'pwa'] as $section) {
            if (!array_key_exists($section, $profile) || !is_array($profile[$section])) {
                $errors[] = '필수 설정 섹션이 올바르지 않습니다: ' . $section;
            }
        }

        $companyNumber = $profile['company_reference']['corporate_number'] ?? '';
        if (!is_string($companyNumber) || preg_match('/\A[0-9]{13}\z/D', $companyNumber) !== 1) {
            $errors[] = '회사 참고 법인번호는 숫자 13자리로 입력해 주세요.';
        }

        if (!isset($profile['brand']['assets']) || !is_array($profile['brand']['assets'])) {
            $errors[] = '브랜드 이미지 설정 형식이 올바르지 않습니다.';
        }

        return array_values(array_unique($errors));
    }

    /** @return list<string> Korean validation messages */
    public function validateForPublish(array $profile): array
    {
        $errors = $this->validateDraft($profile);
        if ($errors !== []) {
            return $errors;
        }

        if (($profile['seller']['authorization_status'] ?? 'pending') !== 'approved') {
            $errors[] = '판매사업 운영 승인이 확인되지 않았습니다.';
        }

        foreach (self::REQUIRED_SELLER_LOCALE_FIELDS as $field) {
            foreach (ProfileDefaults::LOCALES as $locale) {
                $value = $profile['seller'][$field][$locale] ?? '';
                if (!is_string($value) || trim($value) === '') {
                    $errors[] = '판매자 정보(' . $locale . ') 중 필수 항목이 비어 있습니다.';
                    break;
                }
            }
        }

        foreach (ProfileDefaults::LOCALES as $locale) {
            foreach (self::REQUIRED_CONTENT_FIELDS as $field) {
                if (trim((string) ($profile[$field][$locale] ?? '')) === '') {
                    $errors[] = '결제·배송·환불 정책을 일본어·영어·한국어로 입력해 주세요.';
                    break 2;
                }
            }

            foreach (['terms', 'privacy', 'specified_commercial_act'] as $field) {
                if (trim((string) ($profile['content'][$field][$locale] ?? '')) === '') {
                    $errors[] = '이용약관·개인정보·특정상거래법 표시를 일본어·영어·한국어로 입력해 주세요.';
                    break 2;
                }
            }
        }

        foreach (['header_desktop', 'header_mobile', 'favicon', 'apple_touch', 'pwa_192', 'pwa_512', 'pwa_maskable_512', 'og_image'] as $asset) {
            if (!isset($profile['brand']['assets'][$asset]) || !is_string($profile['brand']['assets'][$asset]) || trim($profile['brand']['assets'][$asset]) === '') {
                $errors[] = '공식 로고·파비콘·PWA 이미지 세트를 등록해 주세요.';
                break;
            }
        }

        if (trim((string) ($profile['seller']['support']['phone'] ?? '')) === '' || trim((string) ($profile['seller']['support']['email'] ?? '')) === '') {
            $errors[] = '판매사업 전용 고객센터 전화번호와 이메일을 입력해 주세요.';
        }

        return array_values(array_unique($errors));
    }
}
