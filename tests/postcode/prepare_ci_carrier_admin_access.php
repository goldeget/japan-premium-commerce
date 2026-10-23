<?php

declare(strict_types=1);

function requireCarrierAdminFixture(bool $condition, string $message): void
{
    if (!$condition) {
        global $carrierAccessFailureReason;
        $carrierAccessFailureReason = $message;
        throw new RuntimeException($message);
    }
}

$carrierAccessStage = 'run_scope';
$carrierAccessFailureReason = '';
set_exception_handler(static function (Throwable $exception) use (&$carrierAccessStage, &$carrierAccessFailureReason): void {
    $stage = preg_replace('/[^a-z0-9_]/i', '', $carrierAccessStage) ?: 'unknown';
    $reason = $carrierAccessFailureReason !== '' ? $carrierAccessFailureReason : get_class($exception);
    $safeReason = preg_replace('/[^A-Za-z0-9 .:_-]/', '', $reason) ?: get_class($exception);
    fwrite(STDERR, '::error title=ORDENOWA isolated carrier access fixture::stage=' . $stage . '; reason=' . $safeReason . PHP_EOL);
    exit(1);
});

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;

requireCarrierAdminFixture(
    getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1'
        && preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $runAttempt) === 1
        && $projectName === $expectedProjectName,
    'Carrier admin permission setup requires its matching disposable GitHub Actions checkout.'
);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
$carrierAccessStage = 'bootstrap_prestashop';
require_once '/var/www/html/config/config.inc.php';

$carrierAccessStage = 'verify_database_scope';
$dbServer = defined('_DB_SERVER_') ? (string) _DB_SERVER_ : '';
$dbServerMatches = in_array($dbServer, ['mariadb', 'mariadb:3306'], true)
    && getenv('DB_SERVER') === 'mariadb'
    && getenv('DB_PORT') === '3306';
$dbNameMatches = defined('_DB_NAME_') && (string) _DB_NAME_ === 'prestashop';
$activeDatabaseMatches = $dbNameMatches
    && (string) Db::getInstance()->getValue('SELECT DATABASE()') === (string) _DB_NAME_;
requireCarrierAdminFixture(
    $dbServerMatches && $dbNameMatches && $activeDatabaseMatches,
    'Carrier admin permission setup refused a database outside the isolated CI Compose checkout.'
);

$carrierAccessStage = 'load_ci_employee';
$adminEmail = trim((string) getenv('ADMIN_MAIL'));
$admin = new Employee();
requireCarrierAdminFixture(
    filter_var($adminEmail, FILTER_VALIDATE_EMAIL) !== false
        && $admin->getByEmail($adminEmail) !== false
        && (int) $admin->id_profile > 0,
    'The isolated CI administrator profile could not be loaded.'
);

$carrierAccessStage = 'load_admin_carriers_tab';
$carrierTabId = (int) Tab::getIdFromClassName('AdminCarriers');
requireCarrierAdminFixture($carrierTabId > 0, 'The native AdminCarriers tab is missing.');
$access = new Access();
$permissions = [
    'view' => 'READ',
    'add' => 'CREATE',
    'edit' => 'UPDATE',
];
foreach ($permissions as $legacyPermission => $authorization) {
    $carrierAccessStage = 'grant_' . strtolower($authorization);
    $role = \PrestaShop\PrestaShop\Core\Security\Permission::PREFIX_TAB
        . strtoupper('AdminCarriers') . '_' . $authorization;
    if (!Access::isGranted($role, (int) $admin->id_profile)) {
        requireCarrierAdminFixture(
            $access->updateLgcAccess((int) $admin->id_profile, $carrierTabId, $legacyPermission, true, false) === 'ok',
            'The isolated CI administrator profile could not receive AdminCarriers ' . $authorization . ' access.'
        );
    }
    requireCarrierAdminFixture(
        Access::isGranted($role, (int) $admin->id_profile),
        'The isolated CI administrator profile did not retain AdminCarriers ' . $authorization . ' access.'
    );
}

$carrierAccessStage = 'emit_result';
echo json_encode([
    'admin_profile_id' => (int) $admin->id_profile,
    'carrier_tab_id' => $carrierTabId,
    'read' => true,
    'create' => true,
    'update' => true,
    'delete_permission_changed' => false,
    'fixture_scope' => 'run-scoped isolated GitHub Actions disposable checkout database',
], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDERR, "PASS: isolated CI admin can read, create, and update AdminCarriers; delete access was not changed.\n");
