<?php

declare(strict_types=1);

function ordenowaLimitedRouteResult(string $status, string $failureStage, array $checks, ?string $route = null): never
{
    $payload = [
        'status' => $status,
        'failure_stage' => $failureStage,
        'checks' => $checks,
    ];
    if ($route !== null) {
        // The caller uses this tokenized route in memory only. It must never enter logs or artifacts.
        $payload['route'] = $route;
    }
    echo json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . PHP_EOL;
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
    'issue_denied' => false,
    'confirm_denied' => false,
    'admin_link_generated' => false,
    'route_path_valid' => false,
    'route_controller_valid' => false,
    'route_credential_present' => false,
    'route_credential_bounded' => false,
    'route_credential_whitespace_free' => false,
];
$failureStage = 'scope_validation';

if (!$checks['ci_scope_valid'] || !$checks['identity_shape_valid']) {
    ordenowaLimitedRouteResult('failure', $failureStage, $checks);
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
        ordenowaLimitedRouteResult('failure', $failureStage, $checks);
    }

    $failureStage = 'employee_active';
    $checks['employee_active'] = (bool) $employee->active;
    if (!$checks['employee_active']) {
        ordenowaLimitedRouteResult('failure', $failureStage, $checks);
    }

    $failureStage = 'transfer_tab_acl';
    $tabId = (int) Tab::getIdFromClassName('AdminBusinessProfileTransfers');
    $checks['transfer_tab_present'] = $tabId > 0;
    if (!$checks['transfer_tab_present']) {
        ordenowaLimitedRouteResult('failure', $failureStage, $checks);
    }
    $profileAccess = Profile::getProfileAccesses((int) $employee->id_profile);
    $tabAccess = is_array($profileAccess) ? ($profileAccess[$tabId] ?? []) : [];
    $checks['view_allowed'] = ($tabAccess['view'] ?? '0') === '1';
    $checks['issue_denied'] = ($tabAccess['add'] ?? '0') !== '1';
    $checks['confirm_denied'] = ($tabAccess['edit'] ?? '0') !== '1';
    if (!$checks['view_allowed'] || !$checks['issue_denied'] || !$checks['confirm_denied']) {
        ordenowaLimitedRouteResult('failure', $failureStage, $checks);
    }

    $failureStage = 'admin_link_generation';
    Context::getContext()->employee = $employee;
    $generated = (string) Context::getContext()->link->getAdminLink('AdminBusinessProfileTransfers');
    $checks['admin_link_generated'] = $generated !== '';
    if (!$checks['admin_link_generated']) {
        ordenowaLimitedRouteResult('failure', $failureStage, $checks);
    }

    $failureStage = 'route_validation';
    $parts = parse_url($generated);
    if (!is_array($parts)) {
        ordenowaLimitedRouteResult('failure', $failureStage, $checks);
    }
    parse_str((string) ($parts['query'] ?? ''), $query);
    $controllerValues = $query['controller'] ?? null;
    $credentialValues = $query['token'] ?? null;
    $path = (string) ($parts['path'] ?? '');
    $checks['route_path_valid'] = preg_match('/\A\/admin-kuranea\/index\.php\z/D', $path) === 1;
    $checks['route_controller_valid'] = $controllerValues === 'AdminBusinessProfileTransfers';
    $checks['route_credential_present'] = is_string($credentialValues) && $credentialValues !== '';
    $checks['route_credential_bounded'] = is_string($credentialValues)
        && strlen($credentialValues) <= 256;
    $checks['route_credential_whitespace_free'] = is_string($credentialValues)
        && preg_match('/\s/', $credentialValues) !== 1;
    if (!$checks['route_path_valid']
            || !$checks['route_controller_valid']
            || !$checks['route_credential_present']
            || !$checks['route_credential_bounded']
            || !$checks['route_credential_whitespace_free']) {
        ordenowaLimitedRouteResult('failure', $failureStage, $checks);
    }

    ordenowaLimitedRouteResult('success', 'none', $checks, $path . '?' . (string) $parts['query']);
} catch (Throwable) {
    ordenowaLimitedRouteResult('failure', $failureStage, $checks);
}
