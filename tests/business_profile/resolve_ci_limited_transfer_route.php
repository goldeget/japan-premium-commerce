<?php

declare(strict_types=1);

function ordenowaLimitedRouteRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$runId = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$project = (string) getenv('CI_COMPOSE_PROJECT_NAME');
$email = strtolower(trim((string) getenv('VIEW_ONLY_EMAIL')));
$expectedProject = sprintf('kuranea-ci-%s-%s', $runId, $attempt);
ordenowaLimitedRouteRequire(
    getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1'
        && preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $attempt) === 1
        && $project === $expectedProject
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject
        && preg_match('/\Aordenowa-security-view-' . preg_quote($runId, '/') . '-' . preg_quote($attempt, '/') . '-[a-f0-9]+@example\.invalid\z/D', $email) === 1,
    'Limited transfer route requires the exact run-scoped isolated employee.'
);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';

$employee = new Employee();
ordenowaLimitedRouteRequire($employee->getByEmail($email) !== false && (int) $employee->id > 1, 'The run-scoped limited employee could not be loaded.');
ordenowaLimitedRouteRequire((bool) $employee->active, 'The run-scoped limited employee is inactive.');
$tabId = (int) Tab::getIdFromClassName('AdminBusinessProfileTransfers');
ordenowaLimitedRouteRequire($tabId > 0, 'The bank-transfer Back Office tab is missing.');
$profileAccess = Profile::getProfileAccesses((int) $employee->id_profile);
$tabAccess = is_array($profileAccess) ? ($profileAccess[$tabId] ?? []) : [];
$canView = ($tabAccess['view'] ?? '0') === '1';
$canIssue = ($tabAccess['add'] ?? '0') === '1';
$canConfirm = ($tabAccess['edit'] ?? '0') === '1';
ordenowaLimitedRouteRequire(
    $canView && !$canIssue && !$canConfirm,
    'The run-scoped transfer employee must have read-only, not issue or confirmation, permission.'
);

Context::getContext()->employee = $employee;
$generated = (string) Context::getContext()->link->getAdminLink('AdminBusinessProfileTransfers');
$parts = parse_url($generated);
parse_str((string) ($parts['query'] ?? ''), $query);
$controllerValues = $query['controller'] ?? null;
$tokenValues = $query['token'] ?? null;
$path = (string) ($parts['path'] ?? '');
ordenowaLimitedRouteRequire(
    preg_match('/\A\/admin-kuranea\/index\.php\z/D', $path) === 1
        && $controllerValues === 'AdminBusinessProfileTransfers'
        && is_string($tokenValues)
        && $tokenValues !== ''
        && strlen($tokenValues) <= 256
        && preg_match('/\s/', $tokenValues) !== 1,
    'The limited employee did not receive a valid same-admin controller token route.'
);

// The caller captures this tokenized URL in memory only. It must never go to logs or artifacts.
echo json_encode([
    'status' => 'success',
    'route' => $path . '?' . (string) $parts['query'],
    'employee_found' => true,
    'view_allowed' => true,
    'issue_denied' => true,
    'confirm_denied' => true,
], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . PHP_EOL;
