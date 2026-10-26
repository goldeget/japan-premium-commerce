<?php

declare(strict_types=1);

/** Read only: expose no employee identifiers, email, URL, token, or role slugs. */
$stage = 'config_load';
$result = [
    'readback_available' => false,
    'authorization_ready' => false,
    'failure_stage' => 'unknown',
    'exception_class' => 'unknown',
];

try {
    require_once '/var/www/html/config/config.inc.php';

    $stage = 'fixture_employee_selector';
    $email = trim((string) getenv('ADMIN_MAIL'));
    if ($email === '') {
        throw new RuntimeException('fixture employee selector is unavailable');
    }

    $stage = 'employee_profile_lookup';
    $database = Db::getInstance();
    $employee = new Employee();
    $employeeRecord = $employee->getByEmail($email);
    $employeeFound = $employeeRecord instanceof Employee && (int) $employeeRecord->id > 0;
    $employeeEmailMatches = $employeeFound
        && strtolower(trim((string) $employeeRecord->email)) === strtolower($email);
    $employeeActive = $employeeFound && (bool) $employeeRecord->active;
    $profileId = $employeeEmailMatches && $employeeActive ? (int) $employeeRecord->id_profile : 0;
    $stage = 'tab_lookup';
    $tabClass = 'AdminKuraneaCatalogReview';
    $tabId = (int) Tab::getIdFromClassName($tabClass);
    $tab = $tabId > 0 ? new Tab($tabId) : null;
    $roles = [];

    $stage = 'permission_role_readback';
    foreach (['read' => 'READ', 'create' => 'CREATE', 'update' => 'UPDATE'] as $label => $action) {
        $slug = Access::sluggifyTab(['class_name' => $tabClass], $action);
        $roleId = (int) $database->getValue(
            'SELECT id_authorization_role FROM ' . _DB_PREFIX_ . 'authorization_role WHERE slug = \'' . pSQL($slug) . '\' LIMIT 1'
        );
        $profileRow = $roleId > 0 && $profileId > 0
            ? (int) $database->getValue(
                'SELECT COUNT(*) FROM ' . _DB_PREFIX_ . 'access WHERE id_profile = ' . $profileId
                . ' AND id_authorization_role = ' . $roleId
            ) > 0
            : false;

        $roles[$label] = [
            'role_defined' => $roleId > 0,
            'profile_row' => $profileRow,
            'granted' => $roleId > 0 && $profileId > 0
                ? (bool) Access::isGranted($slug, $profileId)
                : false,
        ];
    }

    $stage = 'result_encoding';
    $tabFound = $tab instanceof Tab;
    $authorizationReady = $employeeFound
        && $employeeEmailMatches
        && $employeeActive
        && $profileId > 0
        && $tabFound
        && (string) $tab->class_name === $tabClass
        && (bool) $tab->active
        && (bool) ($roles['read']['granted'] ?? false)
        && (bool) ($roles['create']['granted'] ?? false)
        && (bool) ($roles['update']['granted'] ?? false);
    $result = [
        'readback_available' => true,
        'authorization_ready' => $authorizationReady,
        'employee_found' => $employeeFound,
        'employee_email_matches' => $employeeEmailMatches,
        'employee_active' => $employeeActive,
        'profile_is_superadmin' => $profileId === 1,
        'tab_found' => $tabFound,
        'tab_class_matches' => $tabFound && (string) $tab->class_name === $tabClass,
        'tab_active' => $tabFound && (bool) $tab->active,
        'read_granted' => (bool) ($roles['read']['granted'] ?? false),
        'create_granted' => (bool) ($roles['create']['granted'] ?? false),
        'update_granted' => (bool) ($roles['update']['granted'] ?? false),
        'permissions' => $roles,
    ];
} catch (Throwable $error) {
    // A diagnostic must never serialize exception text or request data.
    $allowedStages = ['config_load', 'fixture_employee_selector', 'employee_profile_lookup', 'tab_lookup', 'permission_role_readback', 'result_encoding'];
    $allowedExceptions = ['Error', 'Exception', 'PDOException', 'PrestaShopException', 'RuntimeException'];
    $class = (new ReflectionClass($error))->getShortName();
    $result = [
        'readback_available' => false,
        'authorization_ready' => false,
        'failure_stage' => in_array($stage, $allowedStages, true) ? $stage : 'unknown',
        'exception_class' => in_array($class, $allowedExceptions, true) ? $class : 'Exception',
    ];
}

$json = json_encode($result, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
echo 'ORDENOWA_CATALOG_ADMIN_ACCESS=' . $json . PHP_EOL;
if (($result['authorization_ready'] ?? false) !== true) {
    exit(2);
}
