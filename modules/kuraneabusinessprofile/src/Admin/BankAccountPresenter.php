<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Admin;

final class BankAccountPresenter
{
    /** @param array<string, mixed> $account
     *  @return array<string, mixed>
     */
    public static function mask(array $account): array
    {
        $masked = $account;
        $number = preg_replace('/[^0-9]/', '', (string) ($account['account_number'] ?? '')) ?? '';
        $masked['account_number'] = $number === ''
            ? ''
            : str_repeat('•', max(6, strlen($number) - 4)) . substr($number, -4);

        if (array_key_exists('account_holder', $masked)) {
            $masked['account_holder'] = '••••';
        }

        return $masked;
    }
}
