<?php

declare(strict_types=1);

function ordenowaRequireIsolatedEmailBrandSeedContext(): array
{
    $runId = (string) getenv('GITHUB_RUN_ID');
    $runAttempt = (string) getenv('GITHUB_RUN_ATTEMPT');
    $composeProject = (string) getenv('KURANEA_CI_PROJECT_NAME');
    if (getenv('CI') !== 'true'
        || getenv('GITHUB_ACTIONS') !== 'true'
        || getenv('KURANEA_ISOLATED_CI') !== '1'
    ) {
        throw new RuntimeException('The email brand customer seed can only run in isolated GitHub Actions CI.');
    }
    if (preg_match('/\\A[0-9]+\\z/D', $runId) !== 1
        || preg_match('/\\A[0-9]+\\z/D', $runAttempt) !== 1
        || $composeProject !== sprintf('kuranea-ci-%s-%s', $runId, $runAttempt)
    ) {
        throw new RuntimeException('The email brand customer seed requires the exact run-scoped Compose project.');
    }
    return [$runId, $runAttempt];
}

[$runId, $runAttempt] = ordenowaRequireIsolatedEmailBrandSeedContext();

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';

require_once '/var/www/html/config/config.inc.php';
require_once '/var/www/html/modules/kuraneabusinessprofile/autoload.php';

$shopId = max(1, (int) Shop::getContextShopID());
$approvedPrimaryLogoHash = '1ce6b0a015ed6748ef904cdff095ff0f38ab72c9c51fe189c33d19dc797f23fd';
$manifestBytes = @file_get_contents('/opt/ordenowa-brand/asset-manifest.json');
$manifest = is_string($manifestBytes) ? json_decode($manifestBytes, true) : null;
$manifestPrimaryLogoHash = is_array($manifest)
    ? ($manifest['sources_sha256']['ORDENOWA-logo.png'] ?? null)
    : null;
$officialLogoPath = '/opt/ordenowa-brand/official_originals/ORDENOWA-logo.png';
$officialLogoHash = is_file($officialLogoPath) ? hash_file('sha256', $officialLogoPath) : false;
if (!is_string($manifestPrimaryLogoHash)
    || !hash_equals($approvedPrimaryLogoHash, $manifestPrimaryLogoHash)
    || !is_string($officialLogoHash)
    || !hash_equals($approvedPrimaryLogoHash, $officialLogoHash)
) {
    throw new RuntimeException('The packaged ORDENOWA original does not match the approved image manifest.');
}

$profile = (new \Kuranea\BusinessProfile\Customer\PublishedProfileProvider(
    new \Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository()
))->forShop($shopId, 'ja');
$publishedPrimaryLogoHash = is_array($profile)
    ? ($profile['brand']['sources']['primary_logo']['sha256'] ?? null)
    : null;
if (!is_string($publishedPrimaryLogoHash)
    || !hash_equals($approvedPrimaryLogoHash, $publishedPrimaryLogoHash)
) {
    throw new RuntimeException('The published primary logo is not the approved ORDENOWA original.');
}

$emailLogo = is_array($profile) ? ($profile['brand']['assets']['email_logo'] ?? null) : null;
$emailLogoMatches = [];
if (!is_string($emailLogo)
    || preg_match('~\Aimg/ordenowa/versions/([a-f0-9]{64})/(?:email-logo|official-email-logo)\.png\z~D', $emailLogo, $emailLogoMatches) !== 1
    || !hash_equals($approvedPrimaryLogoHash, $emailLogoMatches[1])
) {
    throw new RuntimeException('The published email logo is not derived from the approved ORDENOWA original.');
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
