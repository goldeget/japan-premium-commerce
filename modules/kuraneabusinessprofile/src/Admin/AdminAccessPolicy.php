<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Admin;

final class AdminAccessPolicy
{
    /** @param array<string, int|string|bool> $tabAccess */
    public static function canView(array $tabAccess): bool
    {
        return self::granted($tabAccess, 'view');
    }

    /** @param array<string, int|string|bool> $tabAccess */
    public static function canEdit(array $tabAccess): bool
    {
        return self::canView($tabAccess) && self::granted($tabAccess, 'edit');
    }

    /** @param array<string, int|string|bool> $tabAccess */
    public static function canPublish(array $tabAccess): bool
    {
        return self::canEdit($tabAccess) && self::granted($tabAccess, 'add');
    }

    /** @param array<string, int|string|bool> $bankTabAccess */
    public static function canViewBank(array $bankTabAccess): bool
    {
        return self::canView($bankTabAccess);
    }

    /** @param array<string, int|string|bool> $bankTabAccess */
    public static function canEditBank(array $bankTabAccess): bool
    {
        return self::canViewBank($bankTabAccess) && self::granted($bankTabAccess, 'edit');
    }

    /** Issuing order-bound payment details is a separate create permission. */
    public static function canIssueBankTransferInstructions(array $tabAccess): bool
    {
        return self::canView($tabAccess) && self::granted($tabAccess, 'add');
    }

    /** Confirming a matched deposit is an update permission, distinct from issuing instructions. */
    public static function canConfirmBankTransferReceipt(array $tabAccess): bool
    {
        return self::canView($tabAccess) && self::granted($tabAccess, 'edit');
    }

    public static function canApproveSeller(bool $isSuperAdmin): bool
    {
        return $isSuperAdmin;
    }

    /** @param array<string, int|string|bool> $tabAccess */
    private static function granted(array $tabAccess, string $permission): bool
    {
        return in_array($tabAccess[$permission] ?? false, [1, '1', true], true);
    }
}
