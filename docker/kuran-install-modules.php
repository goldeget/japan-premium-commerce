<?php

declare(strict_types=1);

$shopDomain = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
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

use PrestaShop\PrestaShop\Core\Context\ContextBuilderPreparer;

$db = Db::getInstance();
$japaneseLanguageId = (int) Language::getIdByIso('ja', true);
$japanCountryId = (int) Country::getByIso('JP');
$shop = new Shop(1);
$admin = new Employee(1);
if ($japaneseLanguageId < 1 || $japanCountryId < 1
    || !Validate::isLoadedObject($shop) || !Validate::isLoadedObject($admin)) {
    throw new RuntimeException('The KURANEA shop, Japanese language, country, or administrator is missing.');
}

$context = Context::getContext();
$context->shop = $shop;
Shop::setContext(Shop::CONTEXT_SHOP, 1);
$context->language = new Language($japaneseLanguageId);
$context->country = new Country($japanCountryId, $japaneseLanguageId);
$context->employee = $admin;
$context->cart = new Cart();
$context->currency = kuraneaConfigureJapaneseCurrency($context);
$kernel->getContainer()->get(ContextBuilderPreparer::class)->prepareFromLegacyContext($context);

// The database contains a valid UTF-8 Japanese order slug ("注文"), but the
// runtime canonical redirect double-encodes it into a mojibake path. Keep
// friendly URLs enabled and use a stable ASCII alias for this controller.
// This installer runs on every container start, so the narrow repair also
// applies to shops whose post-install marker already exists.
$checkoutMetaId = (int) $db->getValue(
    'SELECT id_meta FROM `' . _DB_PREFIX_ . 'meta` WHERE page = \'order\' LIMIT 1',
    false
);
if ($checkoutMetaId < 1) {
    throw new RuntimeException('The PrestaShop order page metadata is missing.');
}

$checkoutRouteWhere = sprintf(
    'id_meta = %d AND id_shop = 1 AND id_lang = %d',
    $checkoutMetaId,
    $japaneseLanguageId
);
$checkoutRouteQuery = 'SELECT url_rewrite FROM `' . _DB_PREFIX_ . 'meta_lang` WHERE ' . $checkoutRouteWhere;
$checkoutRouteSlug = $db->getValue($checkoutRouteQuery, false);
if (!is_string($checkoutRouteSlug)) {
    throw new RuntimeException('The Japanese PrestaShop order route is missing.');
}

if ($checkoutRouteSlug !== 'checkout'
    && !$db->update('meta_lang', ['url_rewrite' => 'checkout'], $checkoutRouteWhere, 1, false, false)
) {
    throw new RuntimeException('Could not normalize the Japanese PrestaShop order route.');
}

if ($db->getValue($checkoutRouteQuery, false) !== 'checkout') {
    throw new RuntimeException('The Japanese PrestaShop order route did not persist as /checkout.');
}

foreach (['kuraneapostcode', 'kuraneabackoffice', 'kuraneabusinessprofile', 'kuraneacatalog'] as $moduleName) {
    $module = Module::getInstanceByName($moduleName);
    if (!$module) {
        throw new RuntimeException(sprintf('The bundled %s module could not be loaded.', $moduleName));
    }

    if (!Module::isInstalled($moduleName)) {
        if (!$module->install()) {
            throw new RuntimeException(sprintf('Could not install the %s module.', $moduleName));
        }
    } elseif (!(bool) $module->active && !$module->enable()) {
        throw new RuntimeException(sprintf('Could not enable the %s module.', $moduleName));
    }
}

echo "Project modules: postcode=enabled, backoffice-ko=enabled, business-profile-ko=enabled, catalog-review=enabled\n";
