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

// PrestaShop can emit non-ASCII static slugs as raw Location header bytes.
// Convert those defaults once; later administrator SEO edits must persist.
$routeMigrationKey = 'ORDENOWA_ASCII_ROUTE_MIGRATION_V1';
try {
    if ((string) Configuration::get($routeMigrationKey) !== '1') {
        $routeMigrationSucceeded = true;
        foreach (['order' => 'checkout', 'identity' => 'identity', 'password' => 'password-reset', 'history' => 'history'] as $page => $routeSlug) {
            error_log('ORDENOWA_ROUTE_MIGRATION stage=lookup page=' . $page);
            try {
                $metaId = (int) $db->getValue(
                    "SELECT id_meta FROM `" . _DB_PREFIX_ . "meta` WHERE page = '" . pSQL($page) . "' LIMIT 1",
                    false
                );
                if ($metaId < 1 && $page === 'history') {
                    continue;
                }
                if ($metaId < 1) {
                    error_log('ORDENOWA_ROUTE_MIGRATION status=deferred page=' . $page . ' reason=meta_missing');
                    $routeMigrationSucceeded = false;
                    continue;
                }

                $routeWhere = sprintf('id_meta = %d AND id_shop = 1 AND id_lang = %d', $metaId, $japaneseLanguageId);
                $routeQuery = 'SELECT url_rewrite FROM `' . _DB_PREFIX_ . 'meta_lang` WHERE ' . $routeWhere;
                $storedRouteSlug = $db->getValue($routeQuery, false);
                if (!is_string($storedRouteSlug)) {
                    error_log('ORDENOWA_ROUTE_MIGRATION status=deferred page=' . $page . ' reason=route_missing');
                    $routeMigrationSucceeded = false;
                    continue;
                }

                $hasNonAsciiRoute = preg_match('/[^\x00-\x7F]/', $storedRouteSlug) === 1;
                if ($hasNonAsciiRoute) {
                    if (!$db->update('meta_lang', ['url_rewrite' => pSQL($routeSlug)], $routeWhere, 1, false, false)) {
                        error_log('ORDENOWA_ROUTE_MIGRATION status=deferred page=' . $page . ' reason=update_failed');
                        $routeMigrationSucceeded = false;
                        continue;
                    }
                    if ($db->getValue($routeQuery, false) !== $routeSlug) {
                        error_log('ORDENOWA_ROUTE_MIGRATION status=deferred page=' . $page . ' reason=readback_mismatch');
                        $routeMigrationSucceeded = false;
                    }
                }
            } catch (Throwable $routeMigrationError) {
                error_log('ORDENOWA_ROUTE_MIGRATION status=deferred page=' . $page . ' reason=exception');
                $routeMigrationSucceeded = false;
            }
        }

        if ($routeMigrationSucceeded) {
            error_log('ORDENOWA_ROUTE_MIGRATION stage=marker');
            if (Configuration::updateValue($routeMigrationKey, '1')) {
                error_log('ORDENOWA_ROUTE_MIGRATION status=complete');
            } else {
                error_log('ORDENOWA_ROUTE_MIGRATION status=deferred reason=marker_write');
            }
        } else {
            error_log('ORDENOWA_ROUTE_MIGRATION status=deferred reason=retry_next_start');
        }
    }
} catch (Throwable $routeMigrationError) {
    error_log('ORDENOWA_ROUTE_MIGRATION status=deferred reason=configuration_exception');
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
