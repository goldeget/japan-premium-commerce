<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

/** Resolves the single bank account explicitly selected for bank-transfer payments. */
final class BankTransferPayment
{
    /** @param array<string, mixed> $profile
     *  @return array<string, mixed>|null
     */
    public static function selectedActiveAccount(array $profile): ?array
    {
        $configuration = $profile['payment_methods']['bank_transfer'] ?? null;
        if (!is_array($configuration) || ($configuration['enabled'] ?? false) !== true) {
            return null;
        }

        $selectedId = $configuration['bank_account_id'] ?? null;
        if (!is_string($selectedId) || preg_match('/\A[a-f0-9]{32}\z/iD', $selectedId) !== 1) {
            return null;
        }

        $accounts = $profile['bank_accounts'] ?? null;
        if (!is_array($accounts)) {
            return null;
        }

        foreach ($accounts as $account) {
            if (!is_array($account)
                || ($account['id'] ?? null) !== $selectedId
                || ($account['active'] ?? false) !== true
                || !self::isCompleteAccount($account)
            ) {
                continue;
            }

            return $account;
        }

        return null;
    }

    /** @param array<string, mixed> $account */
    public static function isCompleteAccount(array $account): bool
    {
        if (!is_string($account['id'] ?? null) || preg_match('/\A[a-f0-9]{32}\z/iD', $account['id']) !== 1) {
            return false;
        }

        foreach (['bank_name', 'branch_name', 'account_number', 'account_holder'] as $field) {
            if (!is_string($account[$field] ?? null) || trim($account[$field]) === '') {
                return false;
            }
        }

        return in_array($account['account_type'] ?? null, ['ordinary', 'current', 'savings'], true)
            && preg_match('/\A[0-9]{4,12}\z/D', $account['account_number']) === 1;
    }
}
