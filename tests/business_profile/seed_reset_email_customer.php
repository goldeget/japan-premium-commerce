<?php

declare(strict_types=1);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';

require_once '/var/www/html/config/config.inc.php';
require_once '/var/www/html/modules/kuraneabusinessprofile/autoload.php';

$runId = preg_replace('/[^0-9]/', '', (string) getenv('GITHUB_RUN_ID')) ?? '';
$runAttempt = preg_replace('/[^0-9]/', '', (string) getenv('GITHUB_RUN_ATTEMPT')) ?? '';
if ($runId === '' || $runAttempt === '') {
    throw new RuntimeException('The isolated email brand QA requires a GitHub Actions run identifier.');
}

$shopId = max(1, (int) Shop::getContextShopID());
$profile = (new \Kuranea\BusinessProfile\Customer\PublishedProfileProvider(
    new \Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository()
))->forShop($shopId, 'ja');
$emailLogo = is_array($profile) ? ($profile['brand']['assets']['email_logo'] ?? null) : null;
if (!is_string($emailLogo)
    || preg_match('~\Aimg/ordenowa/versions/([a-fA-F0-9]{64})/(?:email-logo|official-email-logo)\.png\z~D', $emailLogo) !== 1
) {
    throw new RuntimeException('The published profile does not contain a versioned ORDENOWA email logo.');
}

$emailLogoRelative = substr($emailLogo, 4);
if ((string) Configuration::get('PS_LOGO_MAIL', null, null, $shopId) !== $emailLogoRelative
    || !is_file(_PS_IMG_DIR_ . $emailLogoRelative)
) {
    throw new RuntimeException('PrestaShop mail configuration is not using the published ORDENOWA email logo.');
}

$email = sprintf(
    'ordenowa-reset-logo-%s-%s-%s@example.invalid',
    $runId,
    $runAttempt,
    bin2hex(random_bytes(3))
);
$customer = new Customer();
$customer->firstname = 'ORDENOWA';
$customer->lastname = 'CI Email Brand';
$customer->email = $email;
$customer->passwd = Tools::hash(bin2hex(random_bytes(24)));
$customer->id_lang = max(1, (int) Language::getIdByIso('ja', true));
$customer->id_default_group = (int) Configuration::get('PS_CUSTOMER_GROUP');
$customer->id_shop = $shopId;
$customer->secure_key = md5(bin2hex(random_bytes(16)));
$customer->active = 1;
if (!$customer->add()) {
    throw new RuntimeException('Could not create the disposable email-logo QA customer.');
}

$result = json_encode(
    [
        'customer_email' => $email,
        'published_email_logo_path' => $emailLogoRelative,
    ],
    JSON_HEX_TAG | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_HEX_AMP | JSON_THROW_ON_ERROR
);
echo 'ORDENOWA_RESET_EMAIL_BRAND_SEED=' . $result . PHP_EOL;
