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
verifyBusinessProfile(($draft->profile['brand']['assets'] ?? []) === [], 'No unavailable or legacy brand asset may seed the ORDENOWA profile.');
verifyBusinessProfile(($draft->profile['brand']['sources'] ?? []) === [], 'No unavailable source image may seed the ORDENOWA profile.');
verifyBusinessProfile(($draft->profile['company_reference']['corporate_number'] ?? '') === '4010001226242', 'The provided LOGISTEED company reference should be present.');
verifyBusinessProfile(($draft->profile['company_reference']['phone'] ?? '') === '03-6263-2800', 'The company phone should remain in the company reference section.');
verifyBusinessProfile(($draft->profile['customer_support']['phone'] ?? '') === '', 'The company phone must not be copied into shop support.');
verifyBusinessProfile(($draft->profile['localization']['default_locale'] ?? '') === 'ja-JP', 'Japanese must remain the default customer locale.');
verifyBusinessProfile(!\Kuranea\BusinessProfile\Customer\CommerceGate::isEnabled($draft->profile, getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1'), 'A fresh install must not enable real checkout.');
verifyBusinessProfile((string) Configuration::get('PS_SHOP_NAME') === 'ORDENOWA', 'The PrestaShop compatibility shop name must use the confirmed brand.');

foreach (['AdminBusinessProfile' => '쇼핑몰 운영 설정', 'AdminBusinessProfileBanks' => '은행 계좌'] as $className => $expectedLabel) {
    $tabId = (int) Tab::getIdFromClassName($className);
    verifyBusinessProfile($tabId > 0, 'The Korean Back Office tab must exist: ' . $className);
    $tab = new Tab($tabId);
    verifyBusinessProfile(in_array($expectedLabel, (array) $tab->name, true), 'The Back Office tab must have its Korean title: ' . $expectedLabel);
}

echo "PASS: fresh PrestaShop install stores ORDENOWA defaults, keeps seller disabled, and creates Korean admin tabs\n";
