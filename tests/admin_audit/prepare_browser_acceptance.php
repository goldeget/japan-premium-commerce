<?php

declare(strict_types=1);

function adminAuditFixtureRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$runId = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$project = (string) getenv('CI_COMPOSE_PROJECT_NAME');
$adminEmail = trim((string) getenv('ADMIN_MAIL'));
$orderIdText = (string) getenv('KURANEA_CI_ORDER_ID');
$expectedProject = sprintf('kuranea-ci-%s-%s', $runId, $attempt);
adminAuditFixtureRequire(
    getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1'
        && preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $attempt) === 1
        && $project === $expectedProject
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject
        && filter_var($adminEmail, FILTER_VALIDATE_EMAIL) !== false
        && preg_match('/\A[1-9][0-9]{0,9}\z/D', $orderIdText) === 1,
    'Admin audit browser fixtures require the exact isolated Actions project and bank order.'
);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';
require_once _PS_MODULE_DIR_ . 'kuraneabackoffice/vendor/autoload.php';

$shopId = (int) Shop::getContextShopID();
$shop = $shopId > 0 ? new Shop($shopId) : false;
$admin = new Employee();
adminAuditFixtureRequire(
    Shop::getTotalShops() === 1
        && Shop::getContext() === Shop::CONTEXT_SHOP
        && Validate::isLoadedObject($shop)
        && $admin->getByEmail($adminEmail) !== false
        && Validate::isLoadedObject($admin)
        && (int) $admin->id === 1,
    'Admin audit browser fixture requires the primary CI employee in the single selected shop.'
);

$orderId = (int) $orderIdText;
$order = new Order($orderId);
$customer = Validate::isLoadedObject($order) ? new Customer((int) $order->id_customer) : false;
$expectedCustomerEmail = sprintf('qa-ordenowa-checkout-%s-%s-bank@example.invalid', $runId, $attempt);
adminAuditFixtureRequire(
    Validate::isLoadedObject($order)
        && (int) $order->id_shop === $shopId
        && Validate::isLoadedObject($customer)
        && strtolower((string) $customer->email) === $expectedCustomerEmail,
    'Admin audit browser fixture requires the same-run bank checkout order in the selected shop.'
);

$database = Db::getInstance();
$instruction = $database->getRow(
    'SELECT `id_order` FROM `' . _DB_PREFIX_ . 'kuraneabusinessprofile_bank_transfer_instruction`'
    . ' WHERE `id_order` = ' . $orderId . ' AND `id_shop` = ' . $shopId . ' LIMIT 1'
);
$receipt = $database->getRow(
    'SELECT `id_receipt`, `id_order_history` FROM `' . _DB_PREFIX_ . 'kuraneabusinessprofile_bank_transfer_receipt`'
    . ' WHERE `id_order` = ' . $orderId . ' AND `id_shop` = ' . $shopId . ' LIMIT 1'
);
$orderHistoryId = (int) ($receipt['id_order_history'] ?? 0);
$orderHistory = $orderHistoryId > 0
    ? $database->getRow(
        'SELECT oh.`id_order_history` FROM `' . _DB_PREFIX_ . 'order_history` oh'
        . ' INNER JOIN `' . _DB_PREFIX_ . 'orders` o ON o.`id_order` = oh.`id_order`'
        . ' WHERE oh.`id_order_history` = ' . $orderHistoryId
        . ' AND oh.`id_order` = ' . $orderId . ' AND o.`id_shop` = ' . $shopId . ' LIMIT 1'
    )
    : false;
adminAuditFixtureRequire(
    is_array($instruction)
        && is_array($receipt)
        && is_array($orderHistory)
        && (int) $receipt['id_receipt'] > 0,
    'The completed CI bank flow did not leave same-shop instruction, receipt, and native order-history rows.'
);

$tabs = [
    'audit' => 'AdminKuraneaEmployeeProfileAudit',
    'orders' => 'AdminOrders',
    'support' => 'AdminKuraneaSupportAssignments',
    'transfers' => 'AdminBusinessProfileTransfers',
];
$tabIds = [];
foreach ($tabs as $key => $className) {
    $tabId = (int) Tab::getIdFromClassName($className);
    $tab = $tabId > 0 ? new Tab($tabId) : false;
    adminAuditFixtureRequire(
        $tabId > 0 && Validate::isLoadedObject($tab) && (int) $tab->active === 1,
        'A required native audit or source tab is missing from the isolated install.'
    );
    $tabIds[$key] = $tabId;
}

$languageNames = [];
foreach (Language::getLanguages(false) as $language) {
    $languageId = (int) ($language['id_lang'] ?? 0);
    if ($languageId > 0) {
        $languageNames[$languageId] = 'ORDENOWA CI Audit ' . $runId . '-' . $attempt;
    }
}
adminAuditFixtureRequire($languageNames !== [], 'No active language is available for isolated audit profiles.');

$initialProfile = new Profile();
$initialProfile->name = $languageNames;
adminAuditFixtureRequire((bool) $initialProfile->add(), 'Could not create an isolated initial profile.');

$readerProfile = new Profile();
$readerProfile->name = array_map(static fn (string $name): string => $name . ' reader', $languageNames);
adminAuditFixtureRequire((bool) $readerProfile->add(), 'Could not create an isolated full-source reader profile.');

$limitedProfile = new Profile();
$limitedProfile->name = array_map(static fn (string $name): string => $name . ' limited', $languageNames);
adminAuditFixtureRequire((bool) $limitedProfile->add(), 'Could not create an isolated source-limited profile.');

$permissionTabs = [
    $tabIds['audit'],
    $tabIds['orders'],
    $tabIds['support'],
    $tabIds['transfers'],
];
foreach ($permissionTabs as $tabId) {
    adminAuditFixtureRequire(
        (new Access())->updateLgcAccess((int) $readerProfile->id, $tabId, 'view', true, false) === 'ok',
        'Could not grant read-only access to the isolated full-source profile.'
    );
}
adminAuditFixtureRequire(
    (new Access())->updateLgcAccess((int) $limitedProfile->id, $tabIds['audit'], 'view', true, false) === 'ok',
    'Could not grant audit-page-only access to the isolated source-limited profile.'
);
Profile::resetCacheAccesses();
$expectedRoles = [
    'ADMINORDERS_READ' => (int) $readerProfile->id,
    'ADMINKURANEASUPPORTASSIGNMENTS_READ' => (int) $readerProfile->id,
    'ADMINBUSINESSPROFILETRANSFERS_READ' => (int) $readerProfile->id,
];
foreach ($expectedRoles as $role => $profileId) {
    $permission = \PrestaShop\PrestaShop\Core\Security\Permission::PREFIX_TAB . $role;
    adminAuditFixtureRequire(Access::isGranted($permission, $profileId), 'A full-source native READ permission was not persisted.');
    adminAuditFixtureRequire(!Access::isGranted($permission, (int) $limitedProfile->id), 'The source-limited profile unexpectedly received a source READ permission.');
}
$auditRead = \PrestaShop\PrestaShop\Core\Security\Permission::PREFIX_TAB . 'ADMINKURANEAEMPLOYEEPROFILEAUDIT_READ';
adminAuditFixtureRequire(
    Access::isGranted($auditRead, (int) $readerProfile->id)
        && Access::isGranted($auditRead, (int) $limitedProfile->id),
    'The audit-tab READ permission was not persisted for both isolated readers.'
);

$englishLanguageId = (int) Language::getIdByIso('en', true);
adminAuditFixtureRequire($englishLanguageId > 0, 'The isolated audit readers require an active English language.');
$suffix = bin2hex(random_bytes(4));
$readerEmail = sprintf('ordenowa-admin-audit-%s-%s-%s@example.invalid', $runId, $attempt, $suffix);
$limitedEmail = sprintf('ordenowa-admin-audit-limited-%s-%s-%s@example.invalid', $runId, $attempt, $suffix);

$makeEmployee = static function (string $email, int $profileId, int $defaultTabId, string $lastname) use (
    $admin,
    $englishLanguageId
): Employee {
    $employee = new Employee();
    $employee->firstname = 'ORDENOWA';
    $employee->lastname = $lastname;
    $employee->email = $email;
    $employee->id_lang = $englishLanguageId;
    $employee->passwd = (string) $admin->passwd;
    $employee->active = true;
    $employee->id_profile = $profileId;
    $employee->default_tab = $defaultTabId;
    $employee->bo_color = (string) ($admin->bo_color ?: '#6f42c1');
    $employee->bo_theme = (string) ($admin->bo_theme ?: 'default');
    $employee->bo_css = (string) ($admin->bo_css ?: 'theme.css');
    $employee->bo_width = max(0, (int) $admin->bo_width);
    $employee->bo_menu = (bool) $admin->bo_menu;
    adminAuditFixtureRequire((bool) $employee->add(), 'Could not create a run-scoped audit reader.');

    return $employee;
};

$context = Context::getContext();
$context->shop = $shop;
$context->employee = $admin;
Shop::setContext(Shop::CONTEXT_SHOP, $shopId);
$reader = $makeEmployee($readerEmail, (int) $initialProfile->id, $tabIds['audit'], 'CI Audit Reader');
$reader->id_profile = (int) $readerProfile->id;
$reader->default_tab = $tabIds['audit'];
adminAuditFixtureRequire((bool) $reader->update(), 'Could not persist the isolated reader profile transition.');
$limitedReader = $makeEmployee($limitedEmail, (int) $limitedProfile->id, $tabIds['audit'], 'CI Audit Limited');

$profileEvent = $database->getRow(
    'SELECT `id_event`, `id_shop`, `actor_employee_id`, `target_employee_id`, `old_profile_id`, `new_profile_id`'
    . ' FROM `' . _DB_PREFIX_ . 'kuraneabackoffice_employee_profile_audit`'
    . ' WHERE `id_shop` = ' . $shopId
    . ' AND `actor_employee_id` = ' . (int) $admin->id
    . ' AND `target_employee_id` = ' . (int) $reader->id
    . ' AND `old_profile_id` = ' . (int) $initialProfile->id
    . ' AND `new_profile_id` = ' . (int) $readerProfile->id
    . ' ORDER BY `id_event` DESC LIMIT 1'
);
adminAuditFixtureRequire(
    is_array($profileEvent) && (int) $profileEvent['id_event'] > 0,
    'The real Employee update did not persist its selected-shop profile audit event.'
);

$threadId = 1000000000 + (hexdec(substr(hash('sha256', $runId . ':' . $attempt), 0, 7)) % 1000000000);
$changedAt = gmdate('Y-m-d H:i:s');
$supportInsert = 'INSERT INTO `' . _DB_PREFIX_ . 'kuraneabackoffice_support_assignment_history`'
    . ' (`id_shop`, `id_customer_thread`, `from_employee_id`, `to_employee_id`, `actor_employee_id`, `changed_at_utc`) VALUES ('
    . $shopId . ', ' . $threadId . ', NULL, ' . (int) $reader->id . ', ' . (int) $admin->id
    . ", '" . pSQL($changedAt) . "')";
adminAuditFixtureRequire(
    $database->execute($supportInsert),
    'Could not seed the run-scoped support assignment history event.'
);
$supportEventId = (int) $database->Insert_ID();
adminAuditFixtureRequire($supportEventId > 0, 'The support assignment fixture did not persist its event identity.');

fwrite(STDOUT, 'ORDENOWA_ADMIN_AUDIT_FIXTURE=' . json_encode([
    'reader_email' => $readerEmail,
    'limited_reader_email' => $limitedEmail,
    'target_employee_id' => (int) $reader->id,
    'limited_employee_id' => (int) $limitedReader->id,
    'support_thread_id' => $threadId,
    'order_id' => $orderId,
], JSON_THROW_ON_ERROR) . PHP_EOL);
fwrite(STDOUT, "PASS: run-scoped audit readers and selected-shop event fixtures persisted in the isolated database.\n");
