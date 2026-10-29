<?php

declare(strict_types=1);

$shopDomain = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$bootstrapMarker = '/var/www/html/var/.kuranea-bootstrap-v2';
if (is_file($bootstrapMarker)) {
    echo "KURANEA bootstrap already completed.\n";
    exit(0);
}

$_SERVER['HTTP_HOST'] = $shopDomain;
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $shopDomain, PHP_URL_PORT) ?: 80);

require_once '/var/www/html/config/config.inc.php';
require_once '/usr/local/bin/kuran-configure-jpy.php';
require_once '/var/www/html/app/AdminKernel.php';

global $kernel;
$kernel = new AdminKernel(_PS_ENV_, _PS_MODE_DEV_);
$kernel->boot();

use PrestaShop\PrestaShop\Core\Addon\Theme\ThemeManagerBuilder;
use PrestaShop\PrestaShop\Adapter\Bundle\AssetsInstaller;
use PrestaShop\PrestaShop\Core\Context\ContextBuilderPreparer;
use Symfony\Component\Filesystem\Filesystem;

$db = Db::getInstance();
$jaId = Language::getIdByIso('ja', true);
if (!$jaId) {
    throw new RuntimeException('The Japanese base language is missing after PrestaShop installation.');
}

$container = $kernel->getContainer();
$languageImporter = $container->get('prestashop.adapter.language.pack.importer');
foreach (['en', 'ko'] as $isoCode) {
    if (Language::getIdByIso($isoCode, true)) {
        continue;
    }

    $errors = $languageImporter->import($isoCode);
    if ($errors) {
        throw new RuntimeException(sprintf('Could not install the %s language pack: %s', $isoCode, implode('; ', $errors)));
    }
}

$enId = Language::getIdByIso('en', true);
$koId = Language::getIdByIso('ko', true);
if (!$enId || !$koId) {
    throw new RuntimeException('English and Korean language packs must both be installed.');
}

// Mail::getTemplateBasePath checks the active theme, its parent, then /mails,
// and a candidate can win when either MIME template exists. Make every existing
// candidate a complete pair; add root HTML only to text-only candidates and
// preserve every HTML template that is already present.
$koPasswordQueryHtml = '/var/www/html/mails/ko/password_query.html';
$koPasswordQueryTextSource = '/opt/kuranea/mails/ko/password_query.txt';
$koPasswordQueryTemplateDirectories = [
    '/var/www/html/themes/kuranea/mails/ko',
    '/var/www/html/themes/hummingbird/mails/ko',
    '/var/www/html/mails/ko',
];
if (!is_file($koPasswordQueryHtml) || !is_file($koPasswordQueryTextSource)) {
    throw new RuntimeException('Native Korean password reset mail templates are incomplete.');
}
$koPasswordQueryHtmlContents = file_get_contents($koPasswordQueryHtml);
if (!is_string($koPasswordQueryHtmlContents) || $koPasswordQueryHtmlContents === '') {
    throw new RuntimeException('The generated Korean password reset HTML template is empty or unreadable.');
}
$koPasswordQueryText = file_get_contents($koPasswordQueryTextSource);
if (!is_string($koPasswordQueryText)
    || !str_contains($koPasswordQueryText, '비밀번호')
    || !str_contains($koPasswordQueryText, '{url}')
) {
    throw new RuntimeException('Bundled Korean password reset text template is invalid.');
}
$koPasswordQueryInstalledTargets = 0;
foreach ($koPasswordQueryTemplateDirectories as $directory) {
    $htmlPath = $directory . '/password_query.html';
    $textPath = $directory . '/password_query.txt';
    if (!is_file($htmlPath) && !is_file($textPath)) {
        continue;
    }

    if (!is_file($htmlPath)
        && (false === copy($koPasswordQueryHtml, $htmlPath)
            || file_get_contents($htmlPath) !== $koPasswordQueryHtmlContents)
    ) {
        throw new RuntimeException('Could not pair the Korean password reset text template with native HTML.');
    }

    if (false === file_put_contents($textPath, $koPasswordQueryText, LOCK_EX)
        || file_get_contents($textPath) !== $koPasswordQueryText
        || !is_file($htmlPath)
    ) {
        throw new RuntimeException('Could not install the Korean password reset text template.');
    }
    ++$koPasswordQueryInstalledTargets;
}
if ($koPasswordQueryInstalledTargets < 1 || !is_file($koPasswordQueryHtml)) {
    throw new RuntimeException('No generated Korean password reset HTML candidate was preserved.');
}

Configuration::updateGlobalValue('PS_SHOP_DEFAULT', 1);
Configuration::updateGlobalValue('PS_LANG_DEFAULT', $jaId);
Configuration::updateGlobalValue('PS_BO_ALLOW_EMPLOYEE_FORM_LANG', 1);
Configuration::updateGlobalValue('PS_LOCALE_LANGUAGE', 'ja');
Configuration::updateGlobalValue('PS_LOCALE_COUNTRY', 'JP');
Configuration::updateGlobalValue('PS_TIMEZONE', 'Asia/Tokyo');

$countryId = (int) Country::getByIso('JP');
if (!$countryId) {
    throw new RuntimeException('The Japanese country data is missing.');
}
Configuration::updateGlobalValue('PS_COUNTRY_DEFAULT', $countryId);
Configuration::updateGlobalValue('PS_SHOP_DOMAIN', $shopDomain);
Configuration::updateGlobalValue('PS_SHOP_DOMAIN_SSL', $shopDomain);

$shop = new Shop(1);
if (!Validate::isLoadedObject($shop)) {
    throw new RuntimeException('The default PrestaShop shop is missing.');
}
if ($shop->name !== 'ORDENOWA') {
    $shop->name = 'ORDENOWA';
    if (!$shop->update()) {
        throw new RuntimeException('Could not rename the default shop to ORDENOWA.');
    }
}
if (!Configuration::updateValue('PS_SHOP_NAME', 'ORDENOWA', false, null, 1)) {
    throw new RuntimeException('Could not set the ORDENOWA compatibility shop name.');
}

$shopUrlId = (int) $db->getValue('SELECT id_shop_url FROM `' . _DB_PREFIX_ . 'shop_url` WHERE id_shop = 1 AND main = 1');
if (!$shopUrlId) {
    throw new RuntimeException('The default shop URL is missing.');
}
$shopUrl = new ShopUrl($shopUrlId);
if ($shopUrl->domain !== $shopDomain || $shopUrl->domain_ssl !== $shopDomain) {
    $shopUrl->domain = $shopDomain;
    $shopUrl->domain_ssl = $shopDomain;
    if (!$shopUrl->update()) {
        throw new RuntimeException('Could not update the default shop URL.');
    }
}

$admin = new Employee(1);
if (!Validate::isLoadedObject($admin)) {
    throw new RuntimeException('The default administrator account is missing.');
}
if ((int) $admin->id_lang !== $koId) {
    $admin->id_lang = $koId;
    if (!$admin->update()) {
        throw new RuntimeException('Could not set Korean as the administrator language.');
    }
}

$context = Context::getContext();
$context->shop = $shop;
Shop::setContext(Shop::CONTEXT_SHOP, 1);
$context->language = new Language($jaId);
$context->country = new Country($countryId, $jaId);
$context->employee = $admin;
$context->cart = new Cart();
$context->currency = kuraneaConfigureJapaneseCurrency($context);
$container->get(ContextBuilderPreparer::class)->prepareFromLegacyContext($context);

if (!is_file('/var/www/html/themes/hummingbird/assets/css/theme.css')
    || !is_file('/var/www/html/themes/kuranea/assets/css/custom.css')
) {
    throw new RuntimeException('The Hummingbird parent or KURANEA child theme files are missing.');
}

if ($shop->theme_name !== 'kuranea') {
    $themeManager = (new ThemeManagerBuilder($context, $db))->build();
    if (!$themeManager->install('kuranea') || !$themeManager->enable('kuranea')) {
        throw new RuntimeException('Could not install and activate the KURANEA child theme.');
    }
}

$activeShop = new Shop(1);
if ($activeShop->theme_name !== 'kuranea') {
    throw new RuntimeException('KURANEA child theme activation did not persist.');
}

if (!defined('PS_INSTALLATION_LOCK_FILE')) {
    define('PS_INSTALLATION_LOCK_FILE', '/var/www/html/var/.install.prestashop');
}
if (is_file(PS_INSTALLATION_LOCK_FILE)) {
    if (!is_file('/var/www/html/install/classes/exception.php')
        || !is_file('/var/www/html/install/langs/en/language.xml')
    ) {
        throw new RuntimeException('An unfinished PrestaShop post-install step has no installer files to resume safely.');
    }
    if (!defined('_PS_INSTALL_LANGS_PATH_')) {
        define('_PS_INSTALL_LANGS_PATH_', '/var/www/html/install/langs/');
    }
    require_once '/var/www/html/install/classes/exception.php';
    $install = new \PrestaShopBundle\Install\Install();
    $install->setTranslator($context->getTranslator());
    if (!$install->postInstall() || $install->getErrors()) {
        throw new RuntimeException('PrestaShop post-install module tasks did not complete.');
    }
}

// PrestaShop 9.2's optional Ask AI module can throw a TypeError from its
// actionAdminControllerSetMedia hook while native Symfony admin error pages
// render. ORDENOWA does not depend on this optional feature. Disable it once
// after the official installer has activated bundled modules; an administrator
// can re-enable it intentionally later.
if (Module::isInstalled('ps_ask_ai')) {
    $askAiModule = Module::getInstanceByName('ps_ask_ai');
    if (!$askAiModule instanceof Module
        || ((bool) $askAiModule->active && !$askAiModule->disable())
        || (bool) $askAiModule->active) {
        throw new RuntimeException('Could not disable the optional ps_ask_ai module for admin error-page compatibility.');
    }
}

$filesystem = new Filesystem();
$shopRoot = realpath('/var/www/html');
$adminFolder = trim((string) (getenv('KURANEA_ADMIN_FOLDER') ?: 'admin-kuranea'), '/');
if ($shopRoot === false
    || preg_match('/\A[a-zA-Z0-9_-]+\z/D', $adminFolder) !== 1
) {
    throw new RuntimeException('The requested KURANEA Back Office folder name is invalid.');
}

$installedAdminDir = realpath((string) $container->getParameter('prestashop.admin_dir'));
$adminDir = $shopRoot . DIRECTORY_SEPARATOR . $adminFolder;
if ($installedAdminDir === false || dirname($installedAdminDir) !== $shopRoot || !is_dir($installedAdminDir)) {
    throw new RuntimeException('PrestaShop could not detect the completed installer Back Office directory.');
}
if ($installedAdminDir !== $adminDir) {
    if (file_exists($adminDir)) {
        throw new RuntimeException('The requested KURANEA Back Office path already exists; refusing to overwrite it.');
    }
    $filesystem->rename($installedAdminDir, $adminDir);
}
if (!is_dir($adminDir) || is_dir($shopRoot . '/admin-dev')) {
    throw new RuntimeException('The final KURANEA Back Office path is incomplete or an admin-dev path remains.');
}

// PrestaShop 9.2's Install::finalize() installs assets before the post-install
// hook runs. Re-run the official installer against the final path so its
// generated links and bundle assets are valid after the directory rename.
$container->get(AssetsInstaller::class)->installAssets($adminFolder . '/');

foreach (['/var/www/html/install', '/var/www/html/install.lock', PS_INSTALLATION_LOCK_FILE] as $path) {
    if (file_exists($path)) {
        $filesystem->remove($path);
    }
}

if (false === file_put_contents($bootstrapMarker, "v2\n", LOCK_EX)) {
    throw new RuntimeException('Could not persist the KURANEA bootstrap marker.');
}

echo "ORDENOWA bootstrap: storefront=ja, en/ko=enabled, admin=ko, theme=kuranea\n";
