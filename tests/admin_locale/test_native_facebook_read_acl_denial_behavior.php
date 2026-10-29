<?php

declare(strict_types=1);

require_once __DIR__ . '/native_facebook_read_acl_denial.php';

$check = static function (bool $ok, string $reason): void {
    if (!$ok) throw new RuntimeException($reason);
};
$fixture = static function (bool $rejectInsert = false): array {
    $state = (object) [
        'employee' => [['id_employee' => '17', 'id_profile' => '4']],
        'role' => [['id_authorization_role' => '29']],
        'access' => [['id_profile' => '4', 'id_authorization_role' => '29']],
        'writes' => [],
    ];
    $query = static function (string $sql) use ($state): array {
        if (str_contains($sql, '`id_employee`, `id_profile`')) return $state->employee;
        if (str_contains($sql, 'FROM `ps_authorization_role`')) return $state->role;
        if (str_contains($sql, 'FROM `ps_access`')) return $state->access;
        throw new RuntimeException('unexpected_fixture_query');
    };
    $execute = static function (string $sql) use ($state, $rejectInsert): bool {
        $state->writes[] = $sql;
        if (str_starts_with($sql, 'DELETE FROM')) {
            $state->access = [];
            return true;
        }
        if (str_starts_with($sql, 'INSERT INTO')) {
            if ($rejectInsert) return false;
            $state->access = [['id_profile' => '4', 'id_authorization_role' => '29']];
            return true;
        }
        throw new RuntimeException('unexpected_fixture_write');
    };
    return [$state, $query, static fn (string $value): string => addslashes($value), $execute];
};

[$state, $query, $escape, $execute] = $fixture();
$result = NativeFacebookReadAclDenial::run(
    'ci-admin@example.invalid', 'ROLE_MOD_TAB_ADMINPSFACEBOOKMODULE_READ', 'ps_', $query, $escape, $execute,
    static function (int $employeeId, int $profileId) use ($state): string {
        if ($employeeId !== 17 || $profileId !== 4) throw new RuntimeException('existing_identity_not_passed');
        if ($state->access !== []) throw new RuntimeException('grant_not_removed_during_request');
        return '403';
    }
);
$check($result['request_result'] === '403', 'request_result_not_returned');
$check($result['read_permission_row_removed_before_request'] && $result['read_permission_row_restored'], 'lifecycle_not_proven');
$check(count($state->access) === 1, 'row_not_restored_after_request');
$check(count($state->writes) === 2 && str_starts_with($state->writes[0], 'DELETE FROM') && str_starts_with($state->writes[1], 'INSERT INTO'), 'unexpected_write_count_or_order');
$check(str_contains($state->writes[0], '`id_profile` = 4 AND `id_authorization_role` = 29'), 'delete_not_exact_composite_key');

[$state, $query, $escape, $execute] = $fixture();
try {
    NativeFacebookReadAclDenial::run(
        'ci-admin@example.invalid', 'ROLE_MOD_TAB_ADMINPSFACEBOOKMODULE_READ', 'ps_', $query, $escape, $execute,
        static function (int $employeeId, int $profileId): never { throw new RuntimeException('simulated_request_failure'); }
    );
    throw new RuntimeException('request_exception_not_propagated');
} catch (RuntimeException $error) {
    $check($error->getMessage() === 'simulated_request_failure', 'restore_changed_request_exception');
}
$check(count($state->access) === 1, 'row_not_restored_after_request_exception');

[$state, $query, $escape, $execute] = $fixture(true);
try {
    NativeFacebookReadAclDenial::run(
        'ci-admin@example.invalid', 'ROLE_MOD_TAB_ADMINPSFACEBOOKMODULE_READ', 'ps_', $query, $escape, $execute,
        static fn (int $employeeId, int $profileId): string => '403'
    );
    throw new RuntimeException('restore_failure_not_fatal');
} catch (RuntimeException $error) {
    $check($error->getMessage() === 'facebook_read_acl_restore_insert_failed', 'restore_failure_reason_mismatch');
}

[$state, $query, $escape, $execute] = $fixture();
$state->employee[] = ['id_employee' => '18', 'id_profile' => '5'];
try {
    NativeFacebookReadAclDenial::run(
        'ci-admin@example.invalid', 'ROLE_MOD_TAB_ADMINPSFACEBOOKMODULE_READ', 'ps_', $query, $escape, $execute,
        static fn (int $employeeId, int $profileId): string => '403'
    );
    throw new RuntimeException('duplicate_employee_not_rejected');
} catch (RuntimeException $error) {
    $check($error->getMessage() === 'facebook_read_acl_employee_not_unique', 'duplicate_employee_reason_mismatch');
}
$check(count($state->writes) === 0, 'mismatch_mutated_acl');
echo "native Facebook ACL denial helper behavior: PASS\n";
