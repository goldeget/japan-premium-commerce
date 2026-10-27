<?php

declare(strict_types=1);

use Kuranea\BusinessProfile\Customer\CommerceGate;
use Kuranea\BusinessProfile\Customer\PublishedProfileProvider;
use Kuranea\BusinessProfile\Infrastructure\ConfiguredShopUrlProvider;
use Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository;

$stage = 'isolated CI guard';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    fwrite(STDERR, 'ORDENOWA_SITEMAP_FIXTURE stage=' . $stage
        . '; exception_class=' . get_class($exception) . PHP_EOL);
    exit(1);
});

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$attempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$project = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$productId = trim((string) getenv('CI_TEST_PRODUCT_ID'));
if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $attempt) !== 1
    || $project !== 'kuranea-ci-' . $runId . '-' . $attempt
    || preg_match('/\A[1-9][0-9]{0,9}\z/D', $productId) !== 1
    || getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1') {
    fwrite(STDERR, "BLOCKED: sitemap acceptance requires its isolated synthetic shop and no seller approval signal.\n");
    exit(77);
}

$stage = 'PrestaShop read-only bootstrap';
require '/var/www/html/config/config.inc.php';
require '/var/www/html/modules/kuraneabusinessprofile/autoload.php';

$shopId = (int) (Context::getContext()->shop->id ?? 0);
$shopCount = (int) Shop::getTotalShops(false);
$languageRows = Language::getLanguages(true, $shopId);
$localeCodes = [];
$japaneseLanguageId = 0;
foreach ($languageRows as $row) {
    $iso = strtolower((string) ($row['iso_code'] ?? ''));
    if (in_array($iso, ['ja', 'en', 'ko'], true) && (int) ($row['id_lang'] ?? 0) > 0) {
        $localeCodes[] = $iso;
        if ($iso === 'ja') {
            $japaneseLanguageId = (int) $row['id_lang'];
        }
    }
}
$localeCodes = array_values(array_unique($localeCodes));
sort($localeCodes);

$stage = 'configured shop and rewrite readback';
$shopBaseUrl = (new ConfiguredShopUrlProvider())->baseUrl($shopId);
$rewriteEnabled = (bool) Configuration::get('PS_REWRITING_SETTINGS', null, null, $shopId);
if ($shopId < 1 || $shopCount !== 1 || $shopBaseUrl === null || !$rewriteEnabled
    || $localeCodes !== ['en', 'ja', 'ko'] || $japaneseLanguageId < 1
) {
    throw new RuntimeException('The isolated shop lacks its configured URL, rewritten routes, or enabled locale fixtures.');
}

$stage = 'synthetic active guest-visible product readback';
$groupFeatureActive = (bool) Group::isFeatureActive();
$guestGroupId = (int) Configuration::get('PS_UNIDENTIFIED_GROUP');
$guestGroupAssociated = $guestGroupId > 0
    && (new Group($guestGroupId))->isAssociatedToShop($shopId);
$productAccess = $groupFeatureActive
    ? ' AND EXISTS (
        SELECT 1
        FROM ' . _DB_PREFIX_ . 'category_product cp
        INNER JOIN ' . _DB_PREFIX_ . 'category_group cg
            ON cg.id_category = cp.id_category AND cg.id_group = ' . max(0, $guestGroupId) . '
        INNER JOIN ' . _DB_PREFIX_ . 'category c
            ON c.id_category = cp.id_category AND c.active = 1
        INNER JOIN ' . _DB_PREFIX_ . 'category_shop cs
            ON cs.id_category = cp.id_category AND cs.id_shop = ' . $shopId . '
        WHERE cp.id_product = ps.id_product
    )'
    : '';
$productReadback = \Db::getInstance()->getValue(
    'SELECT COUNT(*)
    FROM ' . _DB_PREFIX_ . 'product p
    INNER JOIN ' . _DB_PREFIX_ . 'product_shop ps
        ON ps.id_product = p.id_product AND ps.id_shop = ' . $shopId . '
    INNER JOIN ' . _DB_PREFIX_ . 'product_lang pl
        ON pl.id_product = ps.id_product AND pl.id_shop = ' . $shopId . ' AND pl.id_lang = ' . $japaneseLanguageId . '
    WHERE p.id_product = ' . (int) $productId . '
        AND p.active = 1 AND ps.active = 1 AND ps.indexed = 1
        AND ps.visibility IN (\'both\', \'catalog\') AND ps.show_price = 1
        AND TRIM(pl.name) <> \'\' AND TRIM(pl.link_rewrite) <> \'\'' . $productAccess
);
if (!is_numeric($productReadback) || (int) $productReadback !== 1
    || ($groupFeatureActive
        && ($guestGroupId < 1 || !$guestGroupAssociated))
) {
    throw new RuntimeException('The synthetic active product is not visible to the configured anonymous shop group.');
}

$stage = 'CommerceGate pending-state readback';
$profileProvider = new PublishedProfileProvider(new VersionedProfileRepository());
$enabledProfileLocales = [];
$japaneseProfile = null;
foreach (['ja', 'en', 'ko'] as $iso) {
    $publishedProfile = $profileProvider->forShop($shopId, $iso);
    $locale = PublishedProfileProvider::localeForIso($iso);
    if ($publishedProfile !== null
        && in_array($locale, (array) ($publishedProfile['localization']['enabled_locales'] ?? []), true)
    ) {
        $enabledProfileLocales[] = $iso;
    }
    if ($iso === 'ja') {
        $japaneseProfile = $publishedProfile;
    }
}
$commerceEnabled = CommerceGate::isEnabled(
    $japaneseProfile,
    getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1'
);
if ($commerceEnabled) {
    throw new RuntimeException('The CI-only sitemap check must not simulate seller authorization.');
}
if ($enabledProfileLocales !== ['ja', 'en', 'ko']) {
    throw new RuntimeException('The published profile is missing a populated enabled storefront locale.');
}

$stage = 'robots core-directive baseline';
$robotsContent = Tools::getRobotsContent();
if (!is_array($robotsContent)
    || !isset($robotsContent['Allow'], $robotsContent['Directories'], $robotsContent['Files'], $robotsContent['GB'])
    || !is_array($robotsContent['Allow'])
    || !is_array($robotsContent['Directories'])
    || !is_array($robotsContent['Files'])
    || !is_array($robotsContent['GB'])
    || !is_file(_PS_ROOT_DIR_ . '/robots.txt')
) {
    throw new RuntimeException('PrestaShop did not provide its baseline robots rules.');
}

// PrestaShop 9.2 returns rule data here, not the generated robots.txt string.
// Reconstruct its core Allow/Disallow directives so the HTTP readback can prove
// they survived the module-owned sitemap rewrite.
$expectedCoreDirectives = [];
foreach ($robotsContent['Allow'] as $allowRule) {
    if (!is_string($allowRule) || $allowRule === '') {
        throw new RuntimeException('PrestaShop returned an invalid core Allow rule.');
    }
    $expectedCoreDirectives[] = 'Allow: ' . $allowRule;
}
foreach ($robotsContent['GB'] as $blockedQuery) {
    if (!is_string($blockedQuery) || $blockedQuery === '') {
        throw new RuntimeException('PrestaShop returned an invalid core query rule.');
    }
    $expectedCoreDirectives[] = 'Disallow: /*' . $blockedQuery;
}

$prefixesForGeneration = [];
foreach (Language::getIsoIds() as $language) {
    if (!is_array($language) || !is_string($language['iso_code'] ?? null) || $language['iso_code'] === '') {
        throw new RuntimeException('PrestaShop returned an invalid core language rule.');
    }
    $prefixesForGeneration[] = $language['iso_code'] . '/';
}
$prefixesForGeneration[] = '';
$defaultLanguageIso = Language::getIsoById((int) Configuration::get('PS_LANG_DEFAULT'));
foreach (Tools::getDomains() as $uriList) {
    foreach ($uriList as $uri) {
        if (!is_array($uri) || !is_string($uri['physical'] ?? null)) {
            throw new RuntimeException('PrestaShop returned an invalid core shop path.');
        }
        foreach ($prefixesForGeneration as $prefix) {
            foreach ($robotsContent['Directories'] as $directory) {
                if (!is_string($directory) || $directory === '') {
                    throw new RuntimeException('PrestaShop returned an invalid core directory rule.');
                }
                $expectedCoreDirectives[] = 'Disallow: ' . $uri['physical'] . $prefix . $directory;
            }
        }
        foreach ($robotsContent['Files'] as $iso => $files) {
            if (!is_string($iso) || !is_array($files)) {
                throw new RuntimeException('PrestaShop returned invalid core rewritten-file rules.');
            }
            foreach ($files as $file) {
                if (!is_string($file) || $file === '') {
                    throw new RuntimeException('PrestaShop returned an invalid core rewritten-file rule.');
                }
                $expectedCoreDirectives[] = 'Disallow: ' . $uri['physical'] . $iso . '/' . $file;
                if ($iso === $defaultLanguageIso) {
                    $expectedCoreDirectives[] = 'Disallow: ' . $uri['physical'] . $file;
                }
            }
        }
    }
}

$directiveHashes = [];
foreach ($expectedCoreDirectives as $directive) {
    $directiveHashes[] = hash('sha256', $directive);
}
$robotsFileContent = @file_get_contents(_PS_ROOT_DIR_ . '/robots.txt');
if (!is_string($robotsFileContent)) {
    throw new RuntimeException('The generated robots file could not be read back.');
}
preg_match_all('/^[ \t]*Sitemap[ \t]*:[ \t]*(\S+)[ \t]*$/im', $robotsFileContent, $sitemapMatches);
$sitemapHashes = [];
foreach (($sitemapMatches[0] ?? []) as $index => $directive) {
    $target = (string) ($sitemapMatches[1][$index] ?? '');
    if ($target !== $shopBaseUrl . 'sitemap.xml') {
        $sitemapHashes[] = hash('sha256', trim((string) $directive));
    }
}
sort($directiveHashes);
sort($sitemapHashes);

$stage = 'safe fixture encoding';
echo json_encode([
    'shop_base_url_sha256' => hash('sha256', $shopBaseUrl),
    'sitemap_url_sha256' => hash('sha256', $shopBaseUrl . 'sitemap.xml'),
    'robots_core_directive_sha256' => $directiveHashes,
    'robots_core_sitemap_sha256' => $sitemapHashes,
    'enabled_locales' => $localeCodes,
    'enabled_profile_locales' => $enabledProfileLocales,
    'rewriting_enabled' => $rewriteEnabled,
    'active_guest_visible_product' => true,
    'commerce_gate_enabled' => $commerceEnabled,
    'fixture_scope' => 'isolated disposable GitHub Actions shop',
], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
