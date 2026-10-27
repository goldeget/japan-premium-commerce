<?php

declare(strict_types=1);

function ordenowaLimitedAccessResult(string $status, string $failureStage, array $checks): never
{
    echo json_encode([
        'status' => $status,
        'failure_stage' => $failureStage,
        'checks' => $checks,
    ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . PHP_EOL;
    exit(0);
}

$runId = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$project = (string) getenv('CI_COMPOSE_PROJECT_NAME');
$email = strtolower(trim((string) getenv('VIEW_ONLY_EMAIL')));
$expectedProject = sprintf('kuranea-ci-%s-%s', $runId, $attempt);
$checks = [
    'ci_scope_valid' => getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1'
        && preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $attempt) === 1
        && $project === $expectedProject
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject,
    'identity_shape_valid' => preg_match(
        '/\Aordenowa-security-view-' . preg_quote($runId, '/') . '-' . preg_quote($attempt, '/') . '-[a-f0-9]+@example\.invalid\z/D',
        $email
    ) === 1,
    'employee_found' => false,
    'employee_active' => false,
    'transfer_tab_present' => false,
    'view_allowed' => false,
    'orders_tab_present' => false,
    'orders_view_allowed' => false,
    'issue_denied' => false,
    'confirm_denied' => false,
];
$failureStage = 'scope_validation';

if (!$checks['ci_scope_valid'] || !$checks['identity_shape_valid']) {
    ordenowaLimitedAccessResult('failure', $failureStage, $checks);
}

try {
    $failureStage = 'bootstrap';
    $_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
    $_SERVER['REQUEST_URI'] = '/';
    $_SERVER['SCRIPT_NAME'] = '/index.php';
    require_once '/var/www/html/config/config.inc.php';

    $failureStage = 'employee_lookup';
    $employee = new Employee();
    $checks['employee_found'] = $employee->getByEmail($email) !== false && (int) $employee->id > 1;
    if (!$checks['employee_found']) {
        ordenowaLimitedAccessResult('failure', $failureStage, $checks);
    }

    $failureStage = 'employee_active';
    $checks['employee_active'] = (bool) $employee->active;
    if (!$checks['employee_active']) {
        ordenowaLimitedAccessResult('failure', $failureStage, $checks);
    }

    $failureStage = 'transfer_tab_acl';
    $tabId = (int) Tab::getIdFromClassName('AdminBusinessProfileTransfers');
    $checks['transfer_tab_present'] = $tabId > 0;
    if (!$checks['transfer_tab_present']) {
        ordenowaLimitedAccessResult('failure', $failureStage, $checks);
    }
    $profileAccess = Profile::getProfileAccesses((int) $employee->id_profile);
    $tabAccess = is_array($profileAccess) ? ($profileAccess[$tabId] ?? []) : [];
    $checks['view_allowed'] = ($tabAccess['view'] ?? '0') === '1';
    $checks['issue_denied'] = ($tabAccess['add'] ?? '0') !== '1';
    $checks['confirm_denied'] = ($tabAccess['edit'] ?? '0') !== '1';
    if (!$checks['view_allowed'] || !$checks['issue_denied'] || !$checks['confirm_denied']) {
        ordenowaLimitedAccessResult('failure', $failureStage, $checks);
    }

    $failureStage = 'orders_read_acl';
    $ordersTabId = (int) Tab::getIdFromClassName('AdminOrders');
    $checks['orders_tab_present'] = $ordersTabId > 0;
    $checks['orders_view_allowed'] = $ordersTabId > 0
        && is_array($profileAccess)
        && ($profileAccess[$ordersTabId]['view'] ?? '0') === '1';
    if (!$checks['orders_tab_present'] || !$checks['orders_view_allowed']) {
        ordenowaLimitedAccessResult('failure', $failureStage, $checks);
    }

    ordenowaLimitedAccessResult('success', 'none', $checks);
} catch (Throwable) {
    ordenowaLimitedAccessResult('failure', $failureStage, $checks);
}
