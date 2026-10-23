<?php

declare(strict_types=1);

function requireCarrierAdminFixture(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

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
require_once '/var/www/html/config/config.inc.php';

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

$adminEmail = trim((string) getenv('ADMIN_MAIL'));
$admin = new Employee();
requireCarrierAdminFixture(
    filter_var($adminEmail, FILTER_VALIDATE_EMAIL) !== false
        && $admin->getByEmail($adminEmail) !== false
        && (int) $admin->id_profile > 0,
    'The isolated CI administrator profile could not be loaded.'
);

$carrierTabId = (int) Tab::getIdFromClassName('AdminCarriers');
requireCarrierAdminFixture($carrierTabId > 0, 'The native AdminCarriers tab is missing.');
$access = new Access();
$permissions = [
    'view' => 'READ',
    'add' => 'CREATE',
    'edit' => 'UPDATE',
];
foreach ($permissions as $legacyPermission => $authorization) {
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
