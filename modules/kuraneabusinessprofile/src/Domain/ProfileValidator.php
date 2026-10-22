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

        // This additive field may be absent in profiles saved before bank-transfer
        // linkage was introduced; absence is treated as disabled for compatibility.
        if (array_key_exists('payment_methods', $profile)) {
            $methods = $profile['payment_methods'];
            if (!is_array($methods)) {
                $errors[] = '결제수단 설정 형식이 올바르지 않습니다.';
            } elseif (array_key_exists('bank_transfer', $methods)) {
                $bankTransfer = $methods['bank_transfer'];
                if (!is_array($bankTransfer)) {
                    $errors[] = '계좌이체 설정 형식이 올바르지 않습니다.';
                } else {
                    if (array_key_exists('enabled', $bankTransfer) && !is_bool($bankTransfer['enabled'])) {
                        $errors[] = '계좌이체 사용 여부 설정이 올바르지 않습니다.';
                    }
                    if (array_key_exists('bank_account_id', $bankTransfer) && !is_string($bankTransfer['bank_account_id'])) {
                        $errors[] = '계좌이체 연결 계좌 설정이 올바르지 않습니다.';
                    }
                }
            }
        }

        $companyReference = is_array($profile['company_reference'] ?? null) ? $profile['company_reference'] : [];
        $companyNumber = $companyReference['corporate_number'] ?? '';
        if (!is_string($companyNumber) || preg_match('/\A[0-9]{13}\z/D', $companyNumber) !== 1) {
            $errors[] = '회사 참고 법인번호는 숫자 13자리로 입력해 주세요.';
        }

        $customerSupport = is_array($profile['customer_support'] ?? null) ? $profile['customer_support'] : [];
        $seller = is_array($profile['seller'] ?? null) ? $profile['seller'] : [];
        $sellerSupport = is_array($seller['support'] ?? null) ? $seller['support'] : [];
        foreach ([
            [$customerSupport['email'] ?? '', '고객센터 이메일 주소를 확인해 주세요.'],
            [$sellerSupport['email'] ?? '', '판매자 연락 이메일 주소를 확인해 주세요.'],
        ] as [$email, $message]) {
            if ($email !== '' && (!is_string($email) || filter_var(trim($email), FILTER_VALIDATE_EMAIL) === false)) {
                $errors[] = $message;
            }
        }

        $sourceUrl = $companyReference['source_url'] ?? '';
        if ($sourceUrl !== '') {
            $urlParts = is_string($sourceUrl) ? parse_url(trim($sourceUrl)) : false;
            $scheme = is_array($urlParts) ? strtolower((string) ($urlParts['scheme'] ?? '')) : '';
            $host = is_array($urlParts) ? (string) ($urlParts['host'] ?? '') : '';
            if (!is_string($sourceUrl)
                || filter_var(trim($sourceUrl), FILTER_VALIDATE_URL) === false
                || !in_array($scheme, ['http', 'https'], true)
                || $host === ''
            ) {
                $errors[] = '회사 참고정보 출처 URL은 http 또는 https 주소로 입력해 주세요.';
            }
        }

        if (!isset($profile['brand']['assets']) || !is_array($profile['brand']['assets'])
            || !isset($profile['brand']['sources']) || !is_array($profile['brand']['sources'])
        ) {
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

        // Brand identity can be published before the seller relationship is
        // approved. Transactional disclosures and seller assets remain hidden
        // behind CommerceGate until both approvals are confirmed.
        if (($profile['seller']['authorization_status'] ?? 'pending') !== 'approved') {
            return [];
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

        foreach ([
            'header_desktop', 'header_mobile', 'admin_login', 'email_logo',
            'favicon', 'favicon_16', 'favicon_32', 'apple_touch',
            'pwa_192', 'pwa_512', 'pwa_maskable_512', 'og_image',
        ] as $asset) {
            if (!isset($profile['brand']['assets'][$asset]) || !is_string($profile['brand']['assets'][$asset]) || trim($profile['brand']['assets'][$asset]) === '') {
                $errors[] = '공식 로고·파비콘·PWA 이미지 세트를 등록해 주세요.';
                break;
            }
        }

        if (trim((string) ($profile['seller']['support']['phone'] ?? '')) === '' || trim((string) ($profile['seller']['support']['email'] ?? '')) === '') {
            $errors[] = '판매사업 전용 고객센터 전화번호와 이메일을 입력해 주세요.';
        }

        $bankTransfer = $profile['payment_methods']['bank_transfer'] ?? null;
        if (is_array($bankTransfer)
            && ($bankTransfer['enabled'] ?? false) === true
            && BankTransferPayment::selectedActiveAccount($profile) === null
        ) {
            $errors[] = '은행 계좌이체 결제에는 게시할 활성 계좌를 연결해야 합니다.';
        }

        return array_values(array_unique($errors));
    }
}
