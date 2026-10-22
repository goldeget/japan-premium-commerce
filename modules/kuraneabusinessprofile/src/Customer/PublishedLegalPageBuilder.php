<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

use Kuranea\BusinessProfile\Domain\ProfileDefaults;

/** Builds the public legal and operating-information page from one published profile version. */
final class PublishedLegalPageBuilder
{
    /** @var array<string, array<string, string>> */
    private const COPY = [
        'ja-JP' => [
            'title' => '会社情報・お取引に関する表示',
            'closed_title' => '販売・お取引について',
            'closed_notice' => '販売事業者情報の公開および運営承認が確認されるまで、販売とお取引は受け付けていません。',
            'company' => '会社概要',
            'seller' => '販売事業者',
            'legal_name' => '販売事業者名',
            'corporate_number' => '法人番号',
            'address' => '所在地',
            'representative' => '代表者',
            'responsible_person' => '販売責任者',
            'seller_phone' => '販売事業者の電話番号',
            'seller_email' => '販売事業者のメールアドレス',
            'support' => 'お問い合わせ窓口',
            'phone' => '電話番号',
            'email' => 'メールアドレス',
            'hours' => '受付時間',
            'payment' => 'お支払い方法・条件',
            'shipping' => '配送・お届けについて',
            'refund' => '返品・交換・返金について',
            'terms' => '利用規約',
            'privacy' => 'プライバシーポリシー',
            'specified_commercial_act' => '特定商取引法に基づく表記',
            'bank' => '銀行振込先',
            'branch' => '支店',
            'account_type' => '口座種別',
            'account_number' => '口座番号',
            'account_holder' => '口座名義',
            'ordinary' => '普通',
            'current' => '当座',
            'savings' => '貯蓄',
        ],
        'en-US' => [
            'title' => 'Company and transaction information',
            'closed_title' => 'Sales and transactions',
            'closed_notice' => 'Sales and transactions are unavailable until the seller information and operating authorization are confirmed.',
            'company' => 'Company profile',
            'seller' => 'Seller',
            'legal_name' => 'Seller legal name',
            'corporate_number' => 'Corporate number',
            'address' => 'Address',
            'representative' => 'Representative',
            'responsible_person' => 'Sales contact',
            'seller_phone' => 'Seller phone',
            'seller_email' => 'Seller email',
            'support' => 'Customer support',
            'phone' => 'Phone',
            'email' => 'Email',
            'hours' => 'Hours',
            'payment' => 'Payment methods and terms',
            'shipping' => 'Shipping and delivery',
            'refund' => 'Returns, exchanges and refunds',
            'terms' => 'Terms of service',
            'privacy' => 'Privacy policy',
            'specified_commercial_act' => 'Specified Commercial Transactions Act disclosure',
            'bank' => 'Bank transfer account',
            'branch' => 'Branch',
            'account_type' => 'Account type',
            'account_number' => 'Account number',
            'account_holder' => 'Account holder',
            'ordinary' => 'Ordinary',
            'current' => 'Current',
            'savings' => 'Savings',
        ],
        'ko-KR' => [
            'title' => '회사 정보 및 거래 안내',
            'closed_title' => '판매 및 거래 안내',
            'closed_notice' => '판매자 정보 공개와 운영 승인이 확인될 때까지 판매 및 거래를 접수하지 않습니다.',
            'company' => '회사 소개',
            'seller' => '판매사업자',
            'legal_name' => '판매 법인명',
            'corporate_number' => '법인번호',
            'address' => '사업자 주소',
            'representative' => '대표자',
            'responsible_person' => '판매 책임자',
            'seller_phone' => '판매사업자 전화번호',
            'seller_email' => '판매사업자 이메일',
            'support' => '고객센터',
            'phone' => '전화번호',
            'email' => '이메일',
            'hours' => '운영시간',
            'payment' => '결제 방법 및 조건',
            'shipping' => '배송 및 수령 안내',
            'refund' => '반품·교환·환불 안내',
            'terms' => '이용약관',
            'privacy' => '개인정보 처리방침',
            'specified_commercial_act' => '특정상거래법 표시',
            'bank' => '은행 계좌 안내',
            'branch' => '지점',
            'account_type' => '계좌 종류',
            'account_number' => '계좌번호',
            'account_holder' => '예금주',
            'ordinary' => '보통',
            'current' => '당좌',
            'savings' => '저축',
        ],
    ];

    /** @param array<string, mixed> $profile */
    public static function title(array $profile): string
    {
        $locale = self::locale($profile);

        return self::copy($locale, 'title');
    }

    /** @param array<string, mixed> $profile */
    public static function footerLink(array $profile, string $url): string
    {
        return '<p class="ordenowa-legal-page-link"><a href="' . self::escape($url) . '">'
            . self::escape(self::title($profile)) . '</a></p>';
    }

    /** @param array<string, mixed> $profile */
    public static function build(array $profile, bool $commerceEnabled): string
    {
        $locale = self::locale($profile);
        $brand = (string) ($profile['brand']['name'][$locale] ?? $profile['brand']['name']['ja-JP'] ?? 'ORDENOWA');
        $html = '<article class="ordenowa-legal-page" lang="' . self::escape($locale) . '">';
        $html .= '<header><p class="ordenowa-legal-page__brand">' . self::escape($brand) . '</p>';
        $html .= self::paragraph($profile['brand']['description'][$locale] ?? '');
        $html .= self::paragraph($profile['brand']['slogan'][$locale] ?? '') . '</header>';

        if (!$commerceEnabled) {
            $html .= '<section class="ordenowa-legal-page__closed" role="status"><h2>'
                . self::escape(self::copy($locale, 'closed_title')) . '</h2><p>'
                . self::escape(self::copy($locale, 'closed_notice')) . '</p></section></article>';

            return $html;
        }

        // Company reference data is deliberately not emitted as seller identity.
        // Only the separately configured seller record is shown after the fail-closed gate passes.
        $html .= self::section(self::copy($locale, 'company'), $profile['content']['company_profile'][$locale] ?? '');
        $seller = (array) ($profile['seller'] ?? []);
        $sellerRows = [
            'legal_name' => $seller['legal_name'][$locale] ?? '',
            'corporate_number' => $seller['corporate_number'] ?? '',
            'address' => $seller['address'][$locale] ?? '',
            'representative' => $seller['representative'][$locale] ?? '',
            'responsible_person' => $seller['responsible_person'][$locale] ?? '',
            'seller_phone' => $seller['support']['phone'] ?? '',
            'seller_email' => $seller['support']['email'] ?? '',
        ];
        $html .= self::definitionSection(self::copy($locale, 'seller'), $sellerRows, $locale);

        $support = (array) ($profile['customer_support'] ?? []);
        $html .= self::definitionSection(self::copy($locale, 'support'), [
            'phone' => $support['phone'] ?? '',
            'email' => $support['email'] ?? '',
            'hours' => $support['hours'][$locale] ?? '',
        ], $locale);

        foreach ([
            'payment' => $profile['payment'][$locale] ?? '',
            'shipping' => $profile['shipping'][$locale] ?? '',
            'refund' => $profile['refund'][$locale] ?? '',
            'terms' => $profile['content']['terms'][$locale] ?? '',
            'privacy' => $profile['content']['privacy'][$locale] ?? '',
            'specified_commercial_act' => $profile['content']['specified_commercial_act'][$locale] ?? '',
        ] as $key => $content) {
            $html .= self::section(self::copy($locale, $key), $content);
        }

        $html .= self::bankSection((array) ($profile['bank_accounts'] ?? []), $locale);

        return $html . '</article>';
    }

    /** @param array<string, mixed> $profile */
    private static function locale(array $profile): string
    {
        $locale = (string) ($profile['_resolved_locale'] ?? $profile['localization']['default_locale'] ?? 'ja-JP');

        return in_array($locale, ProfileDefaults::LOCALES, true) ? $locale : 'ja-JP';
    }

    private static function copy(string $locale, string $key): string
    {
        return self::COPY[$locale][$key] ?? self::COPY['ja-JP'][$key] ?? $key;
    }

    private static function section(string $title, mixed $content): string
    {
        if (!is_scalar($content) || trim((string) $content) === '') {
            return '';
        }

        return '<section><h2>' . self::escape($title) . '</h2><p>'
            . nl2br(self::escape((string) $content), false) . '</p></section>';
    }

    /** @param array<string, mixed> $rows */
    private static function definitionSection(string $title, array $rows, string $locale): string
    {
        $html = '';
        foreach ($rows as $key => $value) {
            if (!is_scalar($value) || trim((string) $value) === '') {
                continue;
            }
            $html .= '<div><dt>' . self::escape(self::copy($locale, (string) $key)) . '</dt><dd>'
                . self::escape((string) $value) . '</dd></div>';
        }
        if ($html === '') {
            return '';
        }

        return '<section><h2>' . self::escape($title) . '</h2><dl>' . $html . '</dl></section>';
    }

    /** @param list<array<string, mixed>> $accounts */
    private static function bankSection(array $accounts, string $locale): string
    {
        $active = array_values(array_filter(
            $accounts,
            static fn ($account): bool => is_array($account) && !empty($account['active'])
        ));
        if ($active === []) {
            return '';
        }

        $html = '<section><h2>' . self::escape(self::copy($locale, 'bank')) . '</h2><ul>';
        foreach ($active as $account) {
            $items = array_filter([
                (string) ($account['bank_name'] ?? ''),
                self::copy($locale, 'branch') . ': ' . (string) ($account['branch_name'] ?? ''),
                self::copy($locale, 'account_type') . ': ' . self::copy($locale, (string) ($account['account_type'] ?? '')),
                self::copy($locale, 'account_number') . ': ' . (string) ($account['account_number'] ?? ''),
                self::copy($locale, 'account_holder') . ': ' . (string) ($account['account_holder'] ?? ''),
            ], static fn (string $value): bool => trim($value) !== '');
            $html .= '<li>' . self::escape(implode(' · ', $items)) . '</li>';
        }

        return $html . '</ul></section>';
    }

    private static function paragraph(mixed $content): string
    {
        if (!is_scalar($content) || trim((string) $content) === '') {
            return '';
        }

        return '<p>' . self::escape((string) $content) . '</p>';
    }

    private static function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
