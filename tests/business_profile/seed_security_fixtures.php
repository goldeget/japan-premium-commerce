<?php

declare(strict_types=1);

function securityFixtureRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$runId = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$composeProject = (string) getenv('CI_COMPOSE_PROJECT_NAME');
$adminEmail = trim((string) getenv('ADMIN_MAIL'));
securityFixtureRequire(
    getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1',
    'The security fixture can only run inside isolated GitHub Actions CI.'
);
securityFixtureRequire(
    preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $attempt) === 1,
    'The isolated security fixture requires numeric run-scoped identifiers.'
);
securityFixtureRequire(
    $composeProject === sprintf('kuranea-ci-%s-%s', $runId, $attempt),
    'The isolated security fixture requires the exact run-scoped Compose project.'
);
securityFixtureRequire(
    filter_var($adminEmail, FILTER_VALIDATE_EMAIL) !== false,
    'The isolated security fixture requires the CI administrator account.'
);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';

require_once '/var/www/html/config/config.inc.php';

$suffix = bin2hex(random_bytes(4));
$emails = [
    'admin' => sprintf('ordenowa-security-view-%s-%s-%s@example.invalid', $runId, $attempt, $suffix),
    'replay' => sprintf('ordenowa-reset-token-replay-%s-%s-%s@example.invalid', $runId, $attempt, $suffix),
    'expired' => sprintf('ordenowa-reset-token-expired-%s-%s-%s@example.invalid', $runId, $attempt, $suffix),
];

$profile = null;
$employee = null;
$customers = [];

try {
    $admin = new Employee();
    securityFixtureRequire($admin->getByEmail($adminEmail) !== false, 'The CI administrator employee could not be loaded.');

    $languageNames = [];
    foreach (Language::getLanguages(false) as $language) {
        $languageId = (int) ($language['id_lang'] ?? 0);
        if ($languageId > 0) {
            $languageNames[$languageId] = 'ORDENOWA CI View Only';
        }
    }
    securityFixtureRequire($languageNames !== [], 'No active language is available for the test profile.');

    $profile = new Profile();
    $profile->name = $languageNames;
    securityFixtureRequire((bool) $profile->add(), 'The isolated view-only profile could not be created.');

    $access = new Access();
    foreach (['AdminBusinessProfile', 'AdminDashboard', 'ShopParameters'] as $className) {
        $tabId = (int) Tab::getIdFromClassName($className);
        securityFixtureRequire($tabId > 0, 'A required isolated Back Office tab is missing.');
        securityFixtureRequire(
            $access->updateLgcAccess((int) $profile->id, $tabId, 'view', true, false) === 'ok',
            'The isolated view-only profile could not receive read permission.'
        );
    }

    $businessProfileTabId = (int) Tab::getIdFromClassName('AdminBusinessProfile');
    foreach (['view' => 'READ', 'edit' => 'UPDATE', 'add' => 'CREATE', 'delete' => 'DELETE'] as $action => $authorization) {
        $role = sprintf(
            '%s%s_%s',
            \PrestaShop\PrestaShop\Core\Security\Permission::PREFIX_TAB,
            strtoupper('AdminBusinessProfile'),
            $authorization
        );
        $granted = Access::isGranted($role, (int) $profile->id);
        securityFixtureRequire(
            $action === 'view' ? $granted : !$granted,
            'The isolated employee permission profile does not have the expected read-only access.'
        );
    }

    $employee = new Employee();
    $employee->firstname = 'ORDENOWA';
    $employee->lastname = 'CI View Only';
    $employee->email = $emails['admin'];
    $employee->id_lang = (int) $admin->id_lang;
    $employee->passwd = (string) $admin->passwd;
    $employee->active = true;
    $employee->id_profile = (int) $profile->id;
    $employee->default_tab = (int) Tab::getIdFromClassName('AdminBusinessProfile');
    $employee->bo_color = (string) ($admin->bo_color ?: '#6f42c1');
    $employee->bo_theme = (string) ($admin->bo_theme ?: 'default');
    $employee->bo_css = (string) ($admin->bo_css ?: 'theme.css');
    $employee->bo_width = max(0, (int) $admin->bo_width);
    $employee->bo_menu = (bool) $admin->bo_menu;
    securityFixtureRequire((bool) $employee->add(), 'The isolated view-only employee could not be created.');

    $shopId = max(1, (int) Shop::getContextShopID());
    $defaultGroup = (int) Configuration::get('PS_CUSTOMER_GROUP');
    foreach (['replay', 'expired'] as $kind) {
        $customer = new Customer();
        $customer->firstname = 'ORDENOWA';
        $customer->lastname = 'CI Reset Security';
        $customer->email = $emails[$kind];
        $customer->passwd = Tools::hash(bin2hex(random_bytes(32)));
        $customer->id_lang = max(1, (int) Language::getIdByIso('ja', true));
        $customer->id_default_group = $defaultGroup;
        $customer->id_shop = $shopId;
        $customer->secure_key = bin2hex(random_bytes(16));
        $customer->active = 1;
        securityFixtureRequire((bool) $customer->add(), 'An isolated reset-token customer could not be created.');
        $customers[] = $customer;
    }

    echo 'ORDENOWA_SECURITY_FIXTURE=' . json_encode(
        [
            'view_only_employee_email' => $emails['admin'],
            'reset_replay_customer_email' => $emails['replay'],
            'reset_expired_customer_email' => $emails['expired'],
        ],
        JSON_HEX_TAG | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_HEX_AMP | JSON_THROW_ON_ERROR
    ) . PHP_EOL;
} catch (Throwable $exception) {
    foreach ($customers as $customer) {
        if ($customer instanceof Customer && (int) $customer->id > 0) {
            $customer->delete();
        }
    }
    if ($employee instanceof Employee && (int) $employee->id > 0) {
        $employee->delete();
    }
    if ($profile instanceof Profile && (int) $profile->id > 0) {
        $profile->delete();
    }

    throw $exception;
}
