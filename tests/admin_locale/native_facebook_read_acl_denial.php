<?php

declare(strict_types=1);

/**
 * Test-only access-control fixture. Temporarily removes one exact READ grant
 * from the configured, already-authenticated admin's existing profile, runs
 * one request, and restores that same row before returning.
 */
final class NativeFacebookReadAclDenial
{
    /**
     * @return array{request_result:mixed, read_permission_row_removed_before_request:bool, read_permission_row_restored:bool}
     */
    public static function run(
        string $employeeEmail,
        string $roleSlug,
        string $tablePrefix,
        callable $queryRows,
        callable $escape,
        callable $execute,
        callable $request
    ): array {
        if ($employeeEmail === '' || strlen($employeeEmail) > 254 || preg_match('/[\r\n\x00]/', $employeeEmail)
            || $roleSlug !== 'ROLE_MOD_TAB_ADMINPSFACEBOOKMODULE_READ'
            || preg_match('/\A[a-zA-Z0-9_]{1,64}\z/D', $tablePrefix) !== 1) {
            throw new RuntimeException('facebook_read_acl_fixture_input_invalid');
        }
        $escapedEmail = $escape($employeeEmail);
        if (!is_string($escapedEmail)) {
            throw new RuntimeException('facebook_read_acl_email_escape_invalid');
        }
        $employees = $queryRows(
            'SELECT `id_employee`, `id_profile` FROM `' . $tablePrefix . 'employee`'
            . ' WHERE `email` = "' . $escapedEmail . '" AND `active` = 1 LIMIT 2'
        );
        if (!is_array($employees) || count($employees) !== 1
            || !is_array($employees[0]) || !isset($employees[0]['id_employee'], $employees[0]['id_profile'])) {
            throw new RuntimeException('facebook_read_acl_employee_not_unique');
        }
        $employeeId = self::positiveId($employees[0]['id_employee']);
        $profileId = self::positiveId($employees[0]['id_profile']);
        if ($employeeId === null || $profileId === null) {
            throw new RuntimeException('facebook_read_acl_employee_profile_invalid');
        }
        $escapedRole = $escape($roleSlug);
        if (!is_string($escapedRole)) {
            throw new RuntimeException('facebook_read_acl_role_escape_invalid');
        }
        $roles = $queryRows(
            'SELECT `id_authorization_role` FROM `' . $tablePrefix . 'authorization_role`'
            . ' WHERE `slug` = "' . $escapedRole . '" LIMIT 2'
        );
        if (!is_array($roles) || count($roles) !== 1 || !is_array($roles[0])
            || !isset($roles[0]['id_authorization_role'])) {
            throw new RuntimeException('facebook_read_acl_role_not_unique');
        }
        $roleId = self::positiveId($roles[0]['id_authorization_role']);
        if ($roleId === null) {
            throw new RuntimeException('facebook_read_acl_role_id_invalid');
        }
        $where = ' WHERE `id_profile` = ' . $profileId . ' AND `id_authorization_role` = ' . $roleId;
        $accessRows = $queryRows('SELECT `id_profile`, `id_authorization_role` FROM `'
            . $tablePrefix . 'access`' . $where . ' LIMIT 2');
        if (!self::hasExactlyOneRow($accessRows, $profileId, $roleId)) {
            throw new RuntimeException('facebook_read_acl_grant_not_unique');
        }

        $removedBeforeRequest = false;
        $restored = false;
        $requestResult = null;
        try {
            if ($execute('DELETE FROM `' . $tablePrefix . 'access`' . $where) !== true) {
                throw new RuntimeException('facebook_read_acl_delete_failed');
            }
            $remaining = $queryRows('SELECT `id_profile`, `id_authorization_role` FROM `'
                . $tablePrefix . 'access`' . $where . ' LIMIT 2');
            if (!is_array($remaining) || $remaining !== []) {
                throw new RuntimeException('facebook_read_acl_delete_not_exact');
            }
            $removedBeforeRequest = true;
            $requestResult = $request($employeeId, $profileId);
        } finally {
            $current = $queryRows('SELECT `id_profile`, `id_authorization_role` FROM `'
                . $tablePrefix . 'access`' . $where . ' LIMIT 2');
            if (!is_array($current)) {
                throw new RuntimeException('facebook_read_acl_restore_read_failed');
            }
            if ($current === []) {
                if ($execute('INSERT INTO `' . $tablePrefix . 'access` (`id_profile`, `id_authorization_role`)'
                    . ' VALUES (' . $profileId . ', ' . $roleId . ')') !== true) {
                    throw new RuntimeException('facebook_read_acl_restore_insert_failed');
                }
            } elseif (!self::hasExactlyOneRow($current, $profileId, $roleId)) {
                throw new RuntimeException('facebook_read_acl_restore_state_invalid');
            }
            $restoredRows = $queryRows('SELECT `id_profile`, `id_authorization_role` FROM `'
                . $tablePrefix . 'access`' . $where . ' LIMIT 2');
            if (!self::hasExactlyOneRow($restoredRows, $profileId, $roleId)) {
                throw new RuntimeException('facebook_read_acl_restore_not_verified');
            }
            $restored = true;
        }
        if (!$removedBeforeRequest || !$restored) {
            throw new RuntimeException('facebook_read_acl_lifecycle_not_verified');
        }

        return [
            'request_result' => $requestResult,
            'read_permission_row_removed_before_request' => true,
            'read_permission_row_restored' => true,
        ];
    }

    private static function positiveId(mixed $value): ?int
    {
        if (is_int($value)) return $value > 0 ? $value : null;
        if (!is_string($value) || preg_match('/\A[1-9][0-9]{0,9}\z/D', $value) !== 1) return null;
        $number = (int) $value;
        return $number > 0 && $number <= 4294967295 ? $number : null;
    }

    private static function hasExactlyOneRow(mixed $rows, int $profileId, int $roleId): bool
    {
        if (!is_array($rows) || count($rows) !== 1 || !is_array($rows[0])
            || !isset($rows[0]['id_profile'], $rows[0]['id_authorization_role'])) return false;
        return self::positiveId($rows[0]['id_profile']) === $profileId
            && self::positiveId($rows[0]['id_authorization_role']) === $roleId;
    }
}