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

foreach (['kuraneapostcode', 'kuraneabackoffice', 'kuraneabusinessprofile', 'kuraneacatalog', 'kuraneapush', 'ordenowaprocurement'] as $moduleName) {
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

$procurementModule = Module::getInstanceByName('ordenowaprocurement');
if (!$procurementModule || !$procurementModule->ensureInfrastructure()) {
    throw new RuntimeException('Could not ensure procurement schema, native permissions and tabs.');
}

// The core installer can mark bundled modules installed before the project
// bootstrap runs. Reapply only idempotent CREATE IF NOT EXISTS schema, hooks,
// and the module-owned tab required by the order-bound bank transfer flow.
$businessProfileModule = Module::getInstanceByName('kuraneabusinessprofile');
if (!$businessProfileModule || !$businessProfileModule->ensureBankTransferInfrastructure()) {
    throw new RuntimeException('Could not ensure the order-bound bank transfer infrastructure.');
}

// The official installer may pre-register a bundled module before project hooks are added.
$backofficeModule = Module::getInstanceByName('kuraneabackoffice');
if (!$backofficeModule || !$backofficeModule->installSupportContactPrivacy()) {
    throw new RuntimeException('Could not ensure the account-owned contact privacy hook.');
}

$pushModule = Module::getInstanceByName('kuraneapush');
if (!$pushModule
    || !$pushModule->ensureOrderHistoryPushHook()
    || !$pushModule->ensureSupportMessagePushHook()) {
    throw new RuntimeException('Could not ensure native order and support notification receipt hooks.');
}

// Repair the Korean address/address-list default route collision.
// The upstream Korean Shop.Navigation translations use "주소" for both route
// keys. Dispatcher selects the first matching route, so a saved customer's
// Addresses link opens the new-address form. Keep custom SEO routes intact.
try {
    $koreanLanguageId = (int) Language::getIdByIso('ko', true);
    if ($koreanLanguageId > 0) {
        $accountAddressRoutes = $db->executeS(
            'SELECT m.page, ml.id_meta, ml.url_rewrite'
            . ' FROM `' . _DB_PREFIX_ . 'meta_lang` ml'
            . ' INNER JOIN `' . _DB_PREFIX_ . 'meta` m ON m.id_meta = ml.id_meta'
            . " WHERE m.page IN ('address', 'addresses') AND ml.id_shop = 1 AND ml.id_lang = " . $koreanLanguageId,
            true,
            false
        );
        if (!is_array($accountAddressRoutes)) {
            throw new RuntimeException('Could not read the Korean account address routes.');
        }
        $accountAddressRouteByPage = [];
        foreach ($accountAddressRoutes as $accountAddressRoute) {
            $accountAddressRouteByPage[$accountAddressRoute['page']] = $accountAddressRoute;
        }
        $singleAddressSlug = rawurldecode((string) ($accountAddressRouteByPage['address']['url_rewrite'] ?? ''));
        $addressListSlug = rawurldecode((string) ($accountAddressRouteByPage['addresses']['url_rewrite'] ?? ''));
        if ($singleAddressSlug === '주소' && $addressListSlug === '주소') {
            $addressListMetaId = (int) $accountAddressRouteByPage['addresses']['id_meta'];
            $addressListWhere = sprintf('id_meta = %d AND id_shop = 1 AND id_lang = %d', $addressListMetaId, $koreanLanguageId);
            if ($addressListMetaId < 1
                || !$db->update('meta_lang', ['url_rewrite' => 'addresses'], $addressListWhere, 1, false, false)
                || $db->getValue('SELECT url_rewrite FROM `' . _DB_PREFIX_ . 'meta_lang` WHERE ' . $addressListWhere, false) !== 'addresses') {
                throw new RuntimeException('Could not persist the Korean account address list route.');
            }
            error_log('ORDENOWA_ACCOUNT_ADDRESS_ROUTES status=repaired');
        }
    }
} catch (Throwable $accountAddressRouteError) {
    // No completion marker: a failed read/write is retried on the next startup.
    error_log('ORDENOWA_ACCOUNT_ADDRESS_ROUTES status=deferred reason=retry_next_start');
}

// Run after bundled modules have installed so the final localized Meta rows
// are present. V1 installations get a targeted repair for the confirmed late
// Japanese identity default, while fresh installs migrate non-ASCII defaults
// once and preserve subsequent SEO edits.
$legacyRouteMigrationKey = 'ORDENOWA_ASCII_ROUTE_MIGRATION_V1';
$routeMigrationKey = 'ORDENOWA_ASCII_ROUTE_MIGRATION_V2';
$legacyRouteMigrationComplete = (string) Configuration::get($legacyRouteMigrationKey) === '1';
$optionalMetaPages = ['history'];
try {
    if ((string) Configuration::get($routeMigrationKey) !== '2') {
        $routeMigrationSucceeded = true;
        $lateInstallerRouteDefaults = ['identity' => '識別子'];
        foreach (['order' => 'checkout', 'identity' => 'identity', 'password' => 'password-reset', 'history' => 'history'] as $page => $routeSlug) {
            error_log('ORDENOWA_ROUTE_MIGRATION stage=lookup page=' . $page);
            try {
                $routeQuery = 'SELECT ml.id_meta, ml.url_rewrite'
                    . ' FROM `' . _DB_PREFIX_ . 'meta_lang` ml'
                    . ' INNER JOIN `' . _DB_PREFIX_ . 'meta` m ON m.id_meta = ml.id_meta'
                    . " WHERE m.page = '" . pSQL($page) . "' AND ml.id_shop = 1 AND ml.id_lang = " . $japaneseLanguageId
                    . ' ORDER BY ml.id_meta ASC';
                $routeRows = $db->executeS($routeQuery, true, false);

                if (!is_array($routeRows)) {
                    error_log('ORDENOWA_ROUTE_MIGRATION status=deferred page=' . $page . ' reason=query_failed');
                    $routeMigrationSucceeded = false;
                    continue;
                }

                if (!$routeRows) {
                    $metaExists = (int) $db->getValue(
                        "SELECT COUNT(*) FROM `" . _DB_PREFIX_ . "meta` WHERE page = '" . pSQL($page) . "'",
                        false
                    ) > 0;
                    if (!$metaExists && in_array($page, $optionalMetaPages, true)) {
                        continue;
                    }

                    $missingReason = $metaExists ? 'route_missing' : 'meta_missing';
                    error_log('ORDENOWA_ROUTE_MIGRATION status=deferred page=' . $page . ' reason=' . $missingReason);
                    $routeMigrationSucceeded = false;
                    continue;
                }

                foreach ($routeRows as $routeRow) {
                    $metaId = (int) ($routeRow['id_meta'] ?? 0);
                    $storedRouteSlug = $routeRow['url_rewrite'] ?? null;
                    if ($metaId < 1 || !is_string($storedRouteSlug)) {
                        error_log('ORDENOWA_ROUTE_MIGRATION status=deferred page=' . $page . ' reason=route_missing');
                        $routeMigrationSucceeded = false;
                        continue;
                    }

                    $decodedRouteSlug = rawurldecode($storedRouteSlug);
                    $hasNonAsciiRoute = preg_match('/[^\x00-\x7F]/', $decodedRouteSlug) === 1;
                    if (!$hasNonAsciiRoute) {
                        continue;
                    }

                    $isKnownLateInstallerDefault = isset($lateInstallerRouteDefaults[$page])
                        && $decodedRouteSlug === $lateInstallerRouteDefaults[$page];
                    if ($legacyRouteMigrationComplete && !$isKnownLateInstallerDefault) {
                        continue;
                    }

                    $routeWhere = sprintf('id_meta = %d AND id_shop = 1 AND id_lang = %d', $metaId, $japaneseLanguageId);
                    $routeReadbackQuery = 'SELECT url_rewrite FROM `' . _DB_PREFIX_ . 'meta_lang` WHERE ' . $routeWhere;
                    if (!$db->update('meta_lang', ['url_rewrite' => pSQL($routeSlug)], $routeWhere, 1, false, false)) {
                        error_log('ORDENOWA_ROUTE_MIGRATION status=deferred page=' . $page . ' reason=update_failed');
                        $routeMigrationSucceeded = false;
                        continue;
                    }
                    if ($db->getValue($routeReadbackQuery, false) !== $routeSlug) {
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
            if (Configuration::updateValue($routeMigrationKey, '2')) {
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

echo "Project modules: postcode=enabled, backoffice-ko=enabled, business-profile-ko=enabled, catalog-review=enabled, push-foundation=enabled\n";
