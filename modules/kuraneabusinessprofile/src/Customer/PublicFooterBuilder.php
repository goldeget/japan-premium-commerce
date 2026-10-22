<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

use Kuranea\BusinessProfile\Domain\ProfileDefaults;

final class PublicFooterBuilder
{
    /** @var array<string, array<string, string>> */
    private const LABELS = [
        'ja-JP' => [
            'company' => '会社情報',
            'seller' => '販売事業者情報',
            'legal_name' => '販売事業者',
            'corporate_number' => '法人番号',
            'address' => '所在地',
            'representative' => '代表者',
            'responsible_person' => '販売責任者',
            'seller_phone' => '販売事業者電話番号',
            'seller_email' => '販売事業者メールアドレス',
            'support' => 'お問い合わせ窓口',
            'payment' => 'お支払い方法',
            'shipping' => '配送について',
            'refund' => '返品・返金について',
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
            'company' => 'Company information',
            'seller' => 'Seller information',
            'legal_name' => 'Legal name',
            'corporate_number' => 'Corporate number',
            'address' => 'Address',
            'representative' => 'Representative',
            'responsible_person' => 'Sales contact',
            'seller_phone' => 'Seller phone',
            'seller_email' => 'Seller email',
            'support' => 'Customer support',
            'payment' => 'Payment',
            'shipping' => 'Shipping',
            'refund' => 'Returns and refunds',
            'terms' => 'Terms of service',
            'privacy' => 'Privacy policy',
            'specified_commercial_act' => 'Specified Commercial Transactions Act',
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
            'company' => '회사 정보',
            'seller' => '판매사업자 정보',
            'legal_name' => '판매 법인명',
            'corporate_number' => '법인번호',
            'address' => '사업자 주소',
            'representative' => '대표자',
            'responsible_person' => '판매 운영 책임자',
            'seller_phone' => '판매사업자 전화번호',
            'seller_email' => '판매사업자 이메일',
            'support' => '고객센터',
            'payment' => '결제 안내',
            'shipping' => '배송 안내',
            'refund' => '반품·환불 안내',
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
    public static function build(array $profile, bool $commerceEnabled): string
    {
        $locale = self::locale($profile);
        $brandName = (string) ($profile['brand']['name'][$locale] ?? $profile['brand']['name']['ja-JP'] ?? 'ORDENOWA');
        $html = '<section class="ordenowa-public-brand" aria-label="' . self::escape($brandName) . '">';
        $html .= '<h2>' . self::escape($brandName) . '</h2>';
        $html .= self::paragraph($profile['brand']['description'][$locale] ?? '');
        $html .= self::paragraph($profile['brand']['slogan'][$locale] ?? '');
        $html .= '</section>';

        if (!$commerceEnabled) {
            return $html;
        }

        $html .= self::section(self::label($locale, 'company'), $profile['content']['company_profile'][$locale] ?? '');
        $seller = $profile['seller'] ?? [];
        $html .= '<section class="ordenowa-public-seller"><h3>' . self::escape(self::label($locale, 'seller')) . '</h3><dl>';
        foreach ([
            'legal_name' => $seller['legal_name'][$locale] ?? '',
            'corporate_number' => $seller['corporate_number'] ?? '',
            'address' => $seller['address'][$locale] ?? '',
            'representative' => $seller['representative'][$locale] ?? '',
            'responsible_person' => $seller['responsible_person'][$locale] ?? '',
            'seller_phone' => $seller['support']['phone'] ?? '',
            'seller_email' => $seller['support']['email'] ?? '',
        ] as $field => $value) {
            if (!is_scalar($value) || trim((string) $value) === '') {
                continue;
            }
            $html .= '<div><dt>' . self::escape(self::label($locale, $field)) . '</dt><dd>' . self::escape((string) $value) . '</dd></div>';
        }
        $html .= '</dl></section>';

        $support = $profile['customer_support'] ?? [];
        $supportText = implode(' · ', array_filter([
            (string) ($support['phone'] ?? ''),
            (string) ($support['email'] ?? ''),
            (string) ($support['hours'][$locale] ?? ''),
        ]));
        $html .= self::section(self::label($locale, 'support'), $supportText);

        foreach ([
            'payment' => $profile['payment'][$locale] ?? '',
            'shipping' => $profile['shipping'][$locale] ?? '',
            'refund' => $profile['refund'][$locale] ?? '',
            'terms' => $profile['content']['terms'][$locale] ?? '',
            'privacy' => $profile['content']['privacy'][$locale] ?? '',
            'specified_commercial_act' => $profile['content']['specified_commercial_act'][$locale] ?? '',
        ] as $key => $content) {
            $html .= self::section(self::label($locale, $key), $content);
        }

        $bankAccounts = self::activeBankAccounts($profile);
        if ($bankAccounts !== []) {
            $html .= '<section class="ordenowa-public-bank"><h3>' . self::escape(self::label($locale, 'bank')) . '</h3><ul>';
            foreach ($bankAccounts as $account) {
                $type = (string) ($account['account_type'] ?? '');
                $html .= '<li>' . self::escape((string) ($account['bank_name'] ?? ''))
                    . ' · ' . self::escape(self::label($locale, 'branch')) . ': ' . self::escape((string) ($account['branch_name'] ?? ''))
                    . ' · ' . self::escape(self::label($locale, 'account_type')) . ': ' . self::escape(self::label($locale, $type))
                    . ' · ' . self::escape(self::label($locale, 'account_number')) . ': ' . self::escape((string) ($account['account_number'] ?? ''))
                    . ' · ' . self::escape(self::label($locale, 'account_holder')) . ': ' . self::escape((string) ($account['account_holder'] ?? ''))
                    . '</li>';
            }
            $html .= '</ul></section>';
        }

        return $html;
    }

    /** @param array<string, mixed> $profile */
    public static function bankDetailsText(array $profile, string $locale): string
    {
        $lines = [];
        foreach (self::activeBankAccounts($profile) as $account) {
            $lines[] = implode(' / ', array_filter([
                (string) ($account['bank_name'] ?? ''),
                (string) ($account['branch_name'] ?? ''),
                self::label($locale, (string) ($account['account_type'] ?? '')),
                (string) ($account['account_number'] ?? ''),
                (string) ($account['account_holder'] ?? ''),
            ]));
        }

        return implode("\n", $lines);
    }

    /** @param array<string, mixed> $profile
     *  @return list<array<string, mixed>>
     */
    private static function activeBankAccounts(array $profile): array
    {
        $accounts = $profile['bank_accounts'] ?? [];
        if (!is_array($accounts)) {
            return [];
        }

        return array_values(array_filter($accounts, static fn ($account): bool => is_array($account) && !empty($account['active'])));
    }

    /** @param array<string, mixed> $profile */
    private static function locale(array $profile): string
    {
        $locale = (string) ($profile['_resolved_locale'] ?? $profile['localization']['default_locale'] ?? 'ja-JP');

        return in_array($locale, ProfileDefaults::LOCALES, true) ? $locale : 'ja-JP';
    }

    private static function label(string $locale, string $key): string
    {
        return self::LABELS[$locale][$key] ?? self::LABELS['ja-JP'][$key] ?? $key;
    }

    private static function section(string $title, mixed $content): string
    {
        if (!is_scalar($content) || trim((string) $content) === '') {
            return '';
        }

        return '<section><h3>' . self::escape($title) . '</h3><p>'
            . nl2br(self::escape((string) $content), false) . '</p></section>';
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
