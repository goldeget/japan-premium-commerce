<?php

declare(strict_types=1);

require_once __DIR__ . '/run.php';

$draftOnlyRepository = new InMemoryBusinessProfileRepository();
$draftOnlyRepository->insertVersion(1, $initial, 20, null);
$providerForDraftOnlyRepository = new \Kuranea\BusinessProfile\Customer\PublishedProfileProvider($draftOnlyRepository);
assertBusinessProfileSame(null, $providerForDraftOnlyRepository->forShop(1, 'ja'), 'A draft profile must never be returned by the public customer provider.');

$provider = new \Kuranea\BusinessProfile\Customer\PublishedProfileProvider($versions);
$publishedCandidate = $initial;
$publishedCandidate['brand']['name']['ja-JP'] = '公開テストブランド';
$versions->seedPublished(1, $firstVersionId);
assertBusinessProfileSame('オーデノワ', $provider->forShop(1, 'ja')['brand']['name']['ja-JP'] ?? null, 'A different draft must not replace the already published profile.');

$publishedVersionId = $service->saveDraft(1, $publishedCandidate, 21);
$versions->seedPublished(1, $publishedVersionId);
$published = $provider->forShop(1, 'ja');
assertBusinessProfileSame('公開テストブランド', $published['brand']['name']['ja-JP'] ?? null, 'Public output must read the published version.');
assertBusinessProfileSame('ja-JP', $published['_resolved_locale'] ?? null, 'The Japanese locale must resolve to the Japanese profile content.');
assertBusinessProfileSame('en-US', \Kuranea\BusinessProfile\Customer\PublishedProfileProvider::localeForIso('en'), 'English must map to its supported profile locale.');
assertBusinessProfileSame('ko-KR', \Kuranea\BusinessProfile\Customer\PublishedProfileProvider::localeForIso('ko'), 'Korean must map to its supported profile locale.');
assertBusinessProfileSame('ja-JP', \Kuranea\BusinessProfile\Customer\PublishedProfileProvider::localeForIso('fr'), 'Unsupported locales must fall back to the configured Japanese default.');

$businessProfileModuleSource = file_get_contents(__DIR__ . '/../../modules/kuraneabusinessprofile/kuraneabusinessprofile.php');
$adminLoginTemplateSource = file_get_contents(__DIR__ . '/../../modules/kuraneabackoffice/views/templates/hook/admin-login.tpl');
assertBusinessProfileTrue(is_string($businessProfileModuleSource), 'The business profile module source must be readable for customer markup checks.');
assertBusinessProfileTrue(is_string($adminLoginTemplateSource), 'The administrator login template must be readable for markup checks.');
assertBusinessProfileTrue(
    !str_contains($businessProfileModuleSource, '\\"'),
    'Customer HTML attributes must not contain PHP-literal backslash quote sequences.'
);
assertBusinessProfileTrue(
    !str_contains($adminLoginTemplateSource, '\\"'),
    'Smarty HTML attributes must not contain literal backslashes before quotes.'
);

$manifest = \Kuranea\BusinessProfile\Customer\PwaManifestBuilder::build($published, 'https://shop.example/');
assertBusinessProfileSame('オーデノワ', $manifest['name'], 'The manifest must read the localized published app name.');
assertBusinessProfileSame('/', $manifest['id'], 'A root-installed shop should use the root path as its manifest identity.');
assertBusinessProfileSame('/', $manifest['start_url'], 'A root-installed shop should launch from the root path.');
assertBusinessProfileSame('/', $manifest['scope'], 'A root-installed shop should use the root service worker scope.');
assertBusinessProfileSame(3, count($manifest['icons']), 'The public manifest should expose the three approved official PWA images.');
assertBusinessProfileTrue(
    str_contains($manifest['icons'][2]['src'] ?? '', 'official-pwa-maskable-512.png')
        && ($manifest['icons'][2]['purpose'] ?? '') === 'maskable',
    'The published PWA manifest must include the approved maskable icon.'
);
$withIcons = $published;
$withIcons['brand']['assets']['pwa_192'] = 'img/ordenowa/versions/' . str_repeat('a', 64) . '/pwa-192.png';
$withIcons['brand']['assets']['pwa_512'] = 'https://malicious.example/fake.png';
$withIcons['brand']['assets']['pwa_maskable_512'] = 'https://malicious.example/fake-maskable.png';
$manifestWithIcons = \Kuranea\BusinessProfile\Customer\PwaManifestBuilder::build($withIcons, 'https://shop.example/');
assertBusinessProfileSame('https://shop.example/img/ordenowa/versions/' . str_repeat('a', 64) . '/pwa-192.png', $manifestWithIcons['icons'][0]['src'] ?? null, 'Manifest icons must use only versioned local ORDENOWA assets.');
assertBusinessProfileSame(1, count($manifestWithIcons['icons']), 'External or unversioned image URLs must not enter the app manifest.');
$subdirectoryManifest = \Kuranea\BusinessProfile\Customer\PwaManifestBuilder::build($published, 'https://shop.example/store/');
assertBusinessProfileSame('/store/', $subdirectoryManifest['id'], 'A subdirectory shop should keep its manifest identity within its installation path.');
assertBusinessProfileSame('/store/', $subdirectoryManifest['start_url'], 'A subdirectory shop should launch inside its installation path.');
assertBusinessProfileSame('/store/', $subdirectoryManifest['scope'], 'A subdirectory shop should scope its service worker within its installation path.');
assertBusinessProfileTrue(str_starts_with($subdirectoryManifest['icons'][0]['src'] ?? '', 'https://shop.example/store/'), 'Subdirectory PWA icons should resolve within the same shop base path.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Customer\CommerceGate::isEnabled($published), 'An unapproved seller profile must not enable checkout.');
$approved = $published;
$approved['seller']['authorization_status'] = 'approved';
$approved['seller']['corporate_number'] = '1234567890123';
foreach (['ja-JP', 'en-US', 'ko-KR'] as $locale) {
    $approved['seller']['legal_name'][$locale] = 'TEST SELLER';
    $approved['seller']['address'][$locale] = 'TEST ADDRESS';
    $approved['seller']['representative'][$locale] = 'TEST REPRESENTATIVE';
    $approved['seller']['responsible_person'][$locale] = 'TEST OWNER';
    $approved['payment'][$locale] = 'TEST PAYMENT';
    $approved['shipping'][$locale] = 'TEST SHIPPING';
    $approved['refund'][$locale] = 'TEST REFUND';
    $approved['content']['terms'][$locale] = 'TEST TERMS';
    $approved['content']['privacy'][$locale] = 'TEST PRIVACY';
    $approved['content']['specified_commercial_act'][$locale] = 'TEST LEGAL INFO';
}
$approved['brand']['assets'] = array_fill_keys(
    [
        'header_desktop', 'header_mobile', 'admin_login', 'email_logo',
        'favicon', 'favicon_16', 'favicon_32', 'apple_touch',
        'pwa_192', 'pwa_512', 'pwa_maskable_512', 'og_image',
    ],
    'img/ordenowa/versions/' . str_repeat('b', 64) . '/asset.png'
);
$approved['seller']['support'] = ['phone' => 'TEST PHONE', 'email' => 'test@example.invalid'];
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Customer\CommerceGate::isEnabled($approved), 'A Back Office status change alone must not activate production commerce.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Customer\CommerceGate::isEnabled($approved, true), 'Only an externally confirmed approval flag plus complete seller settings may enable an isolated checkout.');

$checkoutGateEnvironment = [
    'CI' => getenv('CI'),
    'GITHUB_ACTIONS' => getenv('GITHUB_ACTIONS'),
    'GITHUB_RUN_ID' => getenv('GITHUB_RUN_ID'),
    'GITHUB_RUN_ATTEMPT' => getenv('GITHUB_RUN_ATTEMPT'),
    'KURANEA_ISOLATED_CI' => getenv('KURANEA_ISOLATED_CI'),
    'KURANEA_CI_PROJECT_NAME' => getenv('KURANEA_CI_PROJECT_NAME'),
];
try {
    putenv('KURANEA_ISOLATED_CI=0');
    assertBusinessProfileSame(
        false,
        \Kuranea\BusinessProfile\Customer\CommerceGate::isRegistrationEnabled($published),
        'A pending seller profile must not expose customer registration outside the exact isolated QA override.'
    );
    assertBusinessProfileSame(
        false,
        \Kuranea\BusinessProfile\Customer\CommerceGate::isRegistrationEnabled($approved),
        'A seller without externally confirmed approval must not expose customer registration.'
    );
    foreach ([
        'CI' => 'true',
        'GITHUB_ACTIONS' => 'true',
        'GITHUB_RUN_ID' => '123456789',
        'GITHUB_RUN_ATTEMPT' => '1',
        'KURANEA_ISOLATED_CI' => '1',
        'KURANEA_CI_PROJECT_NAME' => 'kuranea-ci-123456789-1',
    ] as $name => $value) {
        putenv($name . '=' . $value);
    }
    assertBusinessProfileSame(
        true,
        \Kuranea\BusinessProfile\Customer\CommerceGate::isIsolatedCiCheckoutEnabled(),
        'A uniquely named GitHub Actions disposable Compose project must be able to reach unpaid checkout QA.'
    );
    assertBusinessProfileSame(
        true,
        \Kuranea\BusinessProfile\Customer\CommerceGate::isRegistrationEnabled($published),
        'Customer registration may open inside the exact disposable Actions project used for browser QA.'
    );
    putenv('GITHUB_RUN_ATTEMPT=2');
    assertBusinessProfileSame(
        false,
        \Kuranea\BusinessProfile\Customer\CommerceGate::isIsolatedCiCheckoutEnabled(),
        'The isolated checkout route must reject a Compose project from another Actions attempt.'
    );
    assertBusinessProfileSame(
        false,
        \Kuranea\BusinessProfile\Customer\CommerceGate::isRegistrationEnabled($published),
        'Customer registration must reject a Compose project from another Actions attempt.'
    );
    putenv('GITHUB_RUN_ATTEMPT=1');
    putenv('GITHUB_ACTIONS=false');
    assertBusinessProfileSame(
        false,
        \Kuranea\BusinessProfile\Customer\CommerceGate::isIsolatedCiCheckoutEnabled(),
        'The isolated checkout route must stay closed outside GitHub Actions.'
    );
    putenv('GITHUB_ACTIONS=true');
    putenv('KURANEA_CI_PROJECT_NAME=kuranea-production');
    assertBusinessProfileSame(
        false,
        \Kuranea\BusinessProfile\Customer\CommerceGate::isIsolatedCiCheckoutEnabled(),
        'The isolated checkout route must reject a non-run-specific Compose project name.'
    );
    putenv('KURANEA_CI_PROJECT_NAME=kuranea-ci-123456789-1');
    putenv('KURANEA_ISOLATED_CI=0');
    assertBusinessProfileSame(
        false,
        \Kuranea\BusinessProfile\Customer\CommerceGate::isIsolatedCiCheckoutEnabled(),
        'The isolated checkout route must remain closed without its explicit test flag.'
    );
} finally {
    foreach ($checkoutGateEnvironment as $name => $value) {
        if ($value === false) {
            putenv($name);
            unset($_ENV[$name], $_SERVER[$name]);
        } else {
            putenv($name . '=' . $value);
            $_ENV[$name] = $value;
            $_SERVER[$name] = $value;
        }
    }
}
unset($approved['seller']['support']['email']);
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Customer\CommerceGate::isEnabled($approved), 'Incomplete seller details must fail closed even on an approved published profile.');

echo "PASS: customer output is published-only and resolves ja/en/ko safely\n";
