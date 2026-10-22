<?php

declare(strict_types=1);

$shopDomain = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['HTTP_HOST'] = $shopDomain;
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';

require_once '/var/www/html/config/config.inc.php';
require_once '/var/www/html/modules/kuraneabusinessprofile/autoload.php';

function verifyBusinessProfile(bool $condition, string $message): void
{
    if (!$condition) {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $message);
        fwrite(STDERR, 'ORDENOWA_BUSINESS_PROFILE_ASSERTION=' . $message . PHP_EOL);
        fwrite(STDOUT, '::error title=ORDENOWA business profile verifier::' . $annotation . PHP_EOL);
        throw new RuntimeException($message);
    }
}

verifyBusinessProfile(Module::isInstalled('kuraneabusinessprofile'), 'The business profile module must be installed by the official module bootstrap.');
$module = Module::getInstanceByName('kuraneabusinessprofile');
verifyBusinessProfile($module !== false && (bool) $module->active, 'The business profile module must be active after a fresh install.');

$shopId = (int) Shop::getContextShopID();
if ($shopId < 1) {
    $shopId = 1;
}
$repository = new \Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository();
$draft = $repository->loadDraft($shopId);
verifyBusinessProfile($draft !== null, 'A default ORDENOWA draft profile must be stored in the module tables.');
verifyBusinessProfile(($draft->profile['brand']['name']['ja-JP'] ?? '') === 'オーデノワ', 'The Japanese brand name must be stored in the profile.');
verifyBusinessProfile(($draft->profile['brand']['name']['en-US'] ?? '') === 'ORDENOWA', 'The English brand name must be stored in the profile.');
verifyBusinessProfile(($draft->profile['brand']['name']['ko-KR'] ?? '') === '오데노와', 'The Korean brand name must be stored in the profile.');
verifyBusinessProfile(($draft->profile['seller']['authorization_status'] ?? '') === 'pending', 'Seller authorization must remain pending after a fresh install.');
verifyBusinessProfile(($draft->profile['bank_accounts'] ?? []) === [], 'No production bank account may be seeded into CI.');
$assets = $draft->profile['brand']['assets'] ?? [];
verifyBusinessProfile(is_array($assets) && count($assets) === 12, 'The full official brand image set must be available in the current profile.');
foreach ([
    'header_desktop', 'header_mobile', 'admin_login', 'email_logo', 'og_image',
    'favicon', 'favicon_16', 'favicon_32', 'apple_touch', 'pwa_192', 'pwa_512', 'pwa_maskable_512',
] as $assetKey) {
    $path = $assets[$assetKey] ?? '';
    verifyBusinessProfile(
        is_string($path)
            && preg_match('~\Aimg/ordenowa/versions/[a-fA-F0-9]{64}/[A-Za-z0-9._-]+\.(?:png|ico)\z~D', $path) === 1
            && is_file(_PS_ROOT_DIR_ . '/' . $path),
        'The ' . $assetKey . ' brand image must resolve to an installed versioned asset.'
    );
}
verifyBusinessProfile(
    is_file(_PS_ROOT_DIR_ . '/img/ordenowa/versions/1ce6b0a015ed6748ef904cdff095ff0f38ab72c9c51fe189c33d19dc797f23fd/official-header-desktop.png'),
    'The exact approved desktop logo derivative must be installed under its immutable official path.'
);
verifyBusinessProfile(
    ($draft->profile['brand']['sources']['primary_logo']['sha256'] ?? '') === '1ce6b0a015ed6748ef904cdff095ff0f38ab72c9c51fe189c33d19dc797f23fd',
    'The approved logo source hash must be retained in the initial profile.'
);
verifyBusinessProfile(
    is_file(_PS_ROOT_DIR_ . '/var/ordenowa-private/' . ($draft->profile['brand']['sources']['primary_logo']['path'] ?? '')),
    'The exact approved source original must be retained in private runtime storage.'
);
verifyBusinessProfile(
    is_file(_PS_ROOT_DIR_ . '/var/ordenowa-private/.htaccess'),
    'The private official source directory must deny direct web access.'
);
$emailLogo = (string) ($draft->profile['brand']['assets']['email_logo'] ?? '');
verifyBusinessProfile(
    $emailLogo !== '' && (string) Configuration::get('PS_LOGO_MAIL', null, null, $shopId) === substr($emailLogo, 4),
    'The PrestaShop email logo configuration must use the approved ORDENOWA image.'
);
verifyBusinessProfile(($draft->profile['company_reference']['corporate_number'] ?? '') === '4010001226242', 'The provided LOGISTEED company reference should be present.');
verifyBusinessProfile(($draft->profile['company_reference']['phone'] ?? '') === '03-6263-2800', 'The company phone should remain in the company reference section.');
verifyBusinessProfile(($draft->profile['customer_support']['phone'] ?? '') === '', 'The company phone must not be copied into shop support.');
verifyBusinessProfile(($draft->profile['localization']['default_locale'] ?? '') === 'ja-JP', 'Japanese must remain the default customer locale.');
verifyBusinessProfile(!\Kuranea\BusinessProfile\Customer\CommerceGate::isEnabled($draft->profile, getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1'), 'A fresh install must not enable real checkout.');
verifyBusinessProfile((string) Configuration::get('PS_SHOP_NAME') === 'ORDENOWA', 'The PrestaShop compatibility shop name must use the confirmed brand.');

$shopParametersParentId = (int) Tab::getIdFromClassName('ShopParameters');
verifyBusinessProfile($shopParametersParentId > 0, 'The PrestaShop ShopParameters parent tab must exist.');
$shopParametersParent = new Tab($shopParametersParentId);
verifyBusinessProfile(
    (string) $shopParametersParent->class_name === 'ShopParameters',
    'The Korean admin tabs must attach to the exact ShopParameters class.'
);
verifyBusinessProfile((bool) $shopParametersParent->active, 'The ShopParameters parent tab must be active.');
if (isset($shopParametersParent->enabled)) {
    verifyBusinessProfile((bool) $shopParametersParent->enabled, 'The ShopParameters parent tab must be enabled.');
}

foreach (['AdminBusinessProfile' => '쇼핑몰 운영 설정', 'AdminBusinessProfileBanks' => '은행 계좌'] as $className => $expectedLabel) {
    $tabId = (int) Tab::getIdFromClassName($className);
    verifyBusinessProfile($tabId > 0, 'The Korean Back Office tab must exist: ' . $className);
    $tab = new Tab($tabId);
    verifyBusinessProfile((bool) $tab->active, 'The Korean Back Office tab must be active: ' . $className);
    if (isset($tab->enabled)) {
        verifyBusinessProfile((bool) $tab->enabled, 'The Korean Back Office tab must be enabled: ' . $className);
    }
    verifyBusinessProfile((int) $tab->id_parent === $shopParametersParentId, 'The Korean settings and bank tabs must be siblings under ShopParameters: ' . $className);
    verifyBusinessProfile(in_array($expectedLabel, (array) $tab->name, true), 'The Back Office tab must have its Korean title: ' . $expectedLabel);
    if (in_array($className, ['AdminBusinessProfile', 'AdminBusinessProfileBanks'], true)) {
        $canView = Access::isGranted(\PrestaShop\PrestaShop\Core\Security\Permission::PREFIX_TAB . strtoupper($className) . '_READ', 1);
        verifyBusinessProfile((bool) $canView, 'SuperAdmin profile 1 must be able to view the Korean admin tab: ' . $className);
    }
}

echo "PASS: fresh PrestaShop install keeps seller authorization pending and creates active Korean admin tabs with profile 1 view access\n";
