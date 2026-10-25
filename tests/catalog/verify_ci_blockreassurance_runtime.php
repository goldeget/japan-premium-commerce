<?php

declare(strict_types=1);

// Read-only provenance probe for the disposable fresh-install shop.
$runId = trim((string) getenv('KURANEA_CI_RUN_ID'));
$attempt = trim((string) getenv('KURANEA_CI_RUN_ATTEMPT'));
$project = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $attempt) !== 1
    || $project !== 'kuranea-ci-' . $runId . '-' . $attempt) {
    fwrite(STDERR, "BLOCKED: module provenance requires the matching isolated GitHub Actions shop.\n");
    exit(77);
}

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php')) {
    fwrite(STDERR, "The isolated PrestaShop installation is missing.\n");
    exit(1);
}
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
require_once $shopRoot . '/config/config.inc.php';

$dbServerMatches = defined('_DB_SERVER_')
    && in_array((string) _DB_SERVER_, ['mariadb', 'mariadb:3306'], true)
    && getenv('DB_SERVER') === 'mariadb'
    && getenv('DB_PORT') === '3306';
$activeDatabaseMatches = defined('_DB_NAME_')
    && (string) _DB_NAME_ === 'prestashop'
    && (string) Db::getInstance()->getValue('SELECT DATABASE()') === (string) _DB_NAME_;
if (!$dbServerMatches || !$activeDatabaseMatches) {
    fwrite(STDERR, "BLOCKED: connected database did not match the isolated PrestaShop fixture.\n");
    exit(77);
}

$moduleName = 'blockreassurance';
$installed = Module::isInstalled($moduleName);
$moduleId = (int) Module::getModuleIdByName($moduleName);
$module = $installed ? Module::getInstanceByName($moduleName) : false;
$registeredHooks = [];
$hookRows = $moduleId > 0 ? Db::getInstance()->executeS(
    'SELECT h.`name`'
    . ' FROM `' . _DB_PREFIX_ . 'hook_module` hm'
    . ' INNER JOIN `' . _DB_PREFIX_ . 'hook` h ON h.`id_hook` = hm.`id_hook`'
    . ' WHERE hm.`id_module` = ' . $moduleId
    . ' ORDER BY h.`name`'
) : false;
if (is_array($hookRows)) {
    $registeredHooks = array_values(array_filter(
        array_map(static fn (array $row): string => (string) ($row['name'] ?? ''), $hookRows),
        static fn (string $name): bool => preg_match('/\A[A-Za-z][A-Za-z0-9]{0,79}\z/D', $name) === 1
    ));
}

$selectedTemplate = null;
$themeOverridePresent = false;
if ($module instanceof Module && method_exists($module, 'hookdisplayReassurance')) {
    $method = new ReflectionMethod($module, 'hookdisplayReassurance');
    $sourcePath = $method->getFileName();
    if (is_string($sourcePath) && is_file($sourcePath)) {
        $lines = file($sourcePath, FILE_IGNORE_NEW_LINES);
        $methodSource = is_array($lines)
            ? implode("\n", array_slice($lines, max(0, $method->getStartLine() - 1), $method->getEndLine() - $method->getStartLine() + 1))
            : '';
        if (preg_match("/renderTemplateInHook\\s*\\(\\s*['\"](displayBlockProduct\\.tpl|displayBlock\\.tpl|displayBlockWhite\\.tpl)['\"]\\s*\\)/", $methodSource, $matches) === 1) {
            $selectedTemplate = $matches[1];
            $themeOverridePath = rtrim((string) _PS_THEME_DIR_, '/')
                . '/modules/blockreassurance/views/templates/hook/' . $selectedTemplate;
            $themeOverridePresent = is_file($themeOverridePath);
        }
    }
}

$languageIds = [];
foreach (['ja', 'en', 'ko'] as $isoCode) {
    $idLanguage = (int) Language::getIdByIso($isoCode, true);
    if ($idLanguage < 1) {
        fwrite(STDERR, "The isolated shop is missing a required storefront language.\n");
        exit(1);
    }
    $languageIds[$isoCode] = $idLanguage;
}
$languageRows = Db::getInstance()->executeS(
    'SELECT r.`id_psreassurance`, l.`iso_code`, rl.`title`, rl.`description`'
    . ' FROM `' . _DB_PREFIX_ . 'psreassurance` r'
    . ' INNER JOIN `' . _DB_PREFIX_ . 'psreassurance_lang` rl ON rl.`id_psreassurance` = r.`id_psreassurance`'
    . ' INNER JOIN `' . _DB_PREFIX_ . 'lang` l ON l.`id_lang` = rl.`id_lang`'
    . ' WHERE r.`id_psreassurance` IN (1, 2, 3)'
    . ' AND l.`iso_code` IN (\'ja\', \'en\', \'ko\')'
    . ' ORDER BY r.`id_psreassurance`, l.`iso_code`'
);
if (!is_array($languageRows)) {
    fwrite(STDERR, "Could not read the isolated reassurance language rows.\n");
    exit(1);
}
$seedRows = array_map(static function (array $row): array {
    return [
        'id' => (int) ($row['id_psreassurance'] ?? 0),
        'locale' => (string) ($row['iso_code'] ?? ''),
        'title' => substr((string) ($row['title'] ?? ''), 0, 255),
        'description' => substr((string) ($row['description'] ?? ''), 0, 255),
    ];
}, $languageRows);

$checkoutPosition = $module instanceof Module
    ? (int) Configuration::get('PSR_HOOK_CHECKOUT')
    : null;
$report = [
    'database_isolated' => true,
    'module' => [
        'name' => $moduleName,
        'installed' => $installed,
        'active' => $module instanceof Module && (bool) $module->active,
        'version' => $module instanceof Module ? (string) $module->version : null,
    ],
    'hooks' => [
        'registered' => $registeredHooks,
        'displayReassurance_registered' => in_array('displayReassurance', $registeredHooks, true),
        'checkout_position' => $checkoutPosition,
        'selected_template' => $selectedTemplate,
        'child_theme_override_present' => $themeOverridePresent,
    ],
    'stored_language_rows' => $seedRows,
];
echo json_encode($report, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT) . PHP_EOL;

if (!$installed
    || !($module instanceof Module)
    || !(bool) $module->active
    || !in_array('displayReassurance', $registeredHooks, true)
    || $selectedTemplate !== 'displayBlockProduct.tpl'
    || !$themeOverridePresent
    || count($seedRows) !== 9) {
    exit(1);
}
