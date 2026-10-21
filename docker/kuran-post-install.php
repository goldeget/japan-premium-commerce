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
if ($shop->name !== 'KURANEA') {
    $shop->name = 'KURANEA';
    if (!$shop->update()) {
        throw new RuntimeException('Could not rename the default shop to KURANEA.');
    }
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

$adminFolder = trim((string) (getenv('PS_FOLDER_ADMIN') ?: 'admin-kuranea'), '/');
if (!is_dir('/var/www/html/' . $adminFolder)) {
    throw new RuntimeException('The configured Back Office directory is missing.');
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

$container->get(AssetsInstaller::class)->installAssets($adminFolder . '/');
$filesystem = new Filesystem();
foreach (['/var/www/html/install', '/var/www/html/install.lock', PS_INSTALLATION_LOCK_FILE] as $path) {
    if (file_exists($path)) {
        $filesystem->remove($path);
    }
}

if (false === file_put_contents($bootstrapMarker, "v2\n", LOCK_EX)) {
    throw new RuntimeException('Could not persist the KURANEA bootstrap marker.');
}

echo "KURANEA bootstrap: storefront=ja, en/ko=enabled, admin=ko, theme=kuranea\n";
