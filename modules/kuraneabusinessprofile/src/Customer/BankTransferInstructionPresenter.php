<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

use Kuranea\BusinessProfile\Domain\BankTransferInstruction;

final class BankTransferInstructionPresenter
{
    /** Render only the bank account in the immutable profile version bound to this order. */
    public static function render(
        BankTransferInstruction $instruction,
        array $profile,
        string $locale,
        string $formattedAmount
    ): string {
        if (!in_array($locale, ['ja-JP', 'en-US', 'ko-KR'], true)) {
            $locale = 'ja-JP';
        }

        $accounts = $profile['bank_accounts'] ?? null;
        if (!is_array($accounts)) {
            return '';
        }

        $account = null;
        foreach ($accounts as $candidate) {
            if (is_array($candidate)
                && ($candidate['id'] ?? null) === $instruction->accountId
                && ($candidate['active'] ?? false) === true
            ) {
                $account = $candidate;
                break;
            }
        }

        $sellerName = $profile['seller']['legal_name'][$locale] ?? '';
        if (!is_array($account) || !is_string($sellerName) || trim($sellerName) === '') {
            return '';
        }

        $labels = self::labels($locale);
        $accountType = $labels['account_type'][$account['account_type'] ?? ''] ?? '';
        $rows = [
            [$labels['seller'], $sellerName],
            [$labels['bank_name'], (string) ($account['bank_name'] ?? '')],
            [$labels['branch_name'], (string) ($account['branch_name'] ?? '')],
            [$labels['account_type_label'], $accountType],
            [$labels['account_number'], (string) ($account['account_number'] ?? '')],
            [$labels['account_holder'], (string) ($account['account_holder'] ?? '')],
            [$labels['order_reference'], $instruction->orderReference],
            [$labels['amount'], $formattedAmount],
        ];

        $html = '<section class="ordenowa-bank-transfer-instructions" aria-labelledby="ordenowa-bank-transfer-heading">'
            . '<h2 id="ordenowa-bank-transfer-heading">' . self::escape($labels['heading']) . '</h2>'
            . '<p>' . self::escape($labels['unpaid_notice']) . '</p>'
            . '<dl class="ordenowa-bank-transfer-instructions__details">';
        foreach ($rows as [$label, $value]) {
            if ($value === '') {
                return '';
            }
            $html .= '<div><dt>' . self::escape((string) $label) . '</dt><dd>' . self::escape((string) $value) . '</dd></div>';
        }

        return $html . '</dl></section>';
    }

    /** @return array<string, mixed> */
    private static function labels(string $locale): array
    {
        return match ($locale) {
            'en-US' => [
                'heading' => 'Bank transfer details for this order',
                'unpaid_notice' => 'This order remains unpaid until a staff member confirms receipt of the transfer.',
                'seller' => 'Seller',
                'bank_name' => 'Bank',
                'branch_name' => 'Branch',
                'account_type_label' => 'Account type',
                'account_number' => 'Account number',
                'account_holder' => 'Account holder',
                'order_reference' => 'Order reference',
                'amount' => 'Transfer amount',
                'account_type' => ['ordinary' => 'Ordinary', 'current' => 'Current', 'savings' => 'Savings'],
            ],
            'ko-KR' => [
                'heading' => '주문별 계좌이체 안내',
                'unpaid_notice' => '담당자가 입금 사실을 확인하기 전까지 이 주문은 미결제 상태입니다.',
                'seller' => '판매자',
                'bank_name' => '은행',
                'branch_name' => '지점',
                'account_type_label' => '계좌 종류',
                'account_number' => '계좌번호',
                'account_holder' => '예금주',
                'order_reference' => '주문번호',
                'amount' => '입금 금액',
                'account_type' => ['ordinary' => '보통', 'current' => '당좌', 'savings' => '저축'],
            ],
            default => [
                'heading' => 'この注文の銀行振込案内',
                'unpaid_notice' => '担当者が入金を確認するまで、この注文は未払いです。',
                'seller' => '販売者',
                'bank_name' => '銀行',
                'branch_name' => '支店',
                'account_type_label' => '預金種目',
                'account_number' => '口座番号',
                'account_holder' => '口座名義',
                'order_reference' => '注文番号',
                'amount' => '振込金額',
                'account_type' => ['ordinary' => '普通', 'current' => '当座', 'savings' => '貯蓄'],
            ],
        };
    }

    private static function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
