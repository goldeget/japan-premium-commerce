<?php

declare(strict_types=1);

require_once __DIR__ . '/run.php';

$publicBrandProfile = $initial;
$publicBrandProfile['_resolved_locale'] = 'ja-JP';
$publicBrandProfile['seller']['legal_name']['ja-JP'] = 'TEST SELLER LEGAL NAME';
$publicBrandProfile['seller']['corporate_number'] = '9998888777766';
$publicBrandProfile['seller']['address']['ja-JP'] = 'TEST SELLER ADDRESS';
$publicBrandProfile['seller']['representative']['ja-JP'] = 'TEST SELLER REPRESENTATIVE';
$publicBrandProfile['seller']['responsible_person']['ja-JP'] = 'TEST RESPONSIBLE PERSON';
$publicBrandProfile['seller']['support'] = ['phone' => 'TEST SELLER PHONE', 'email' => 'seller@example.invalid'];
$publicBrandProfile['customer_support'] = ['phone' => 'TEST SHOP PHONE', 'email' => 'shop@example.invalid', 'hours' => ['ja-JP' => '平日 9:00-17:00']];
$publicBrandProfile['company_reference']['corporate_number'] = '4010001226242';
$publicBrandProfile['content']['company_profile']['ja-JP'] = 'TEST COMPANY PROFILE';
$publicBrandProfile['content']['specified_commercial_act']['ja-JP'] = 'TEST SPECIFIED COMMERCIAL ACT';
$publicBrandProfile['payment']['ja-JP'] = 'TEST PAYMENT INSTRUCTIONS';
$publicBrandProfile['shipping']['ja-JP'] = 'TEST SHIPPING POLICY';
$publicBrandProfile['refund']['ja-JP'] = 'TEST REFUND POLICY';
$publicBrandProfile['content']['terms']['ja-JP'] = 'TEST TERMS';
$publicBrandProfile['content']['privacy']['ja-JP'] = 'TEST PRIVACY';
$publicBrandProfile['bank_accounts'] = [[
    'id' => str_repeat('a', 32),
    'bank_name' => 'TEST BANK',
    'branch_name' => 'TOKYO',
    'account_type' => 'ordinary',
    'account_number' => '12345678',
    'account_holder' => 'TEST HOLDER',
    'active' => true,
]];
$publicBrandProfile['payment_methods']['bank_transfer'] = ['enabled' => true, 'bank_account_id' => str_repeat('a', 32)];

$brandOnlyHtml = \Kuranea\BusinessProfile\Customer\PublicFooterBuilder::build($publicBrandProfile, false);
assertBusinessProfileTrue(str_contains($brandOnlyHtml, 'オーデノワ'), 'Brand identity should be publishable before seller authorization.');
assertBusinessProfileTrue(str_contains($brandOnlyHtml, '法人向け商品調達・受発注サービス'), 'Published brand descriptions should appear in the public brand section.');
foreach ([
    'TEST SELLER LEGAL NAME', '9998888777766', 'TEST SELLER ADDRESS',
    'TEST SELLER REPRESENTATIVE', 'TEST RESPONSIBLE PERSON', '4010001226242',
    'TEST SHOP PHONE', 'TEST PAYMENT INSTRUCTIONS', '12345678', 'TEST TERMS',
] as $privateOrTransactionalValue) {
    assertBusinessProfileTrue(!str_contains($brandOnlyHtml, $privateOrTransactionalValue), 'Unapproved seller and transactional values must remain private: ' . $privateOrTransactionalValue);
}

$authorizedHtml = \Kuranea\BusinessProfile\Customer\PublicFooterBuilder::build($publicBrandProfile, true);
foreach ([
    'TEST SELLER LEGAL NAME', '9998888777766', 'TEST SELLER ADDRESS',
    'TEST SELLER REPRESENTATIVE', 'TEST RESPONSIBLE PERSON', 'TEST SELLER PHONE',
    'TEST SHOP PHONE', 'TEST PAYMENT INSTRUCTIONS', 'TEST SHIPPING POLICY',
    'TEST REFUND POLICY', 'TEST TERMS', 'TEST PRIVACY', 'TEST SPECIFIED COMMERCIAL ACT',
] as $authorizedValue) {
    assertBusinessProfileTrue(str_contains($authorizedHtml, $authorizedValue), 'Approved public seller disclosures must include ' . $authorizedValue . '.');
}
assertBusinessProfileTrue(!str_contains($authorizedHtml, '12345678') && !str_contains($authorizedHtml, 'TEST HOLDER'), 'Bank details must remain hidden until a staff-issued order instruction exists.');
assertBusinessProfileTrue(!str_contains($authorizedHtml, '4010001226242'), 'Corporate reference data must not be misrepresented as the selling entity.');
assertBusinessProfileTrue(!str_contains($authorizedHtml, '<script>'), 'Customer legal disclosures must be escaped before output.');

$escapedProfile = $publicBrandProfile;
$escapedProfile['seller']['legal_name']['ja-JP'] = '<script>alert(1)</script>';
$escapedHtml = \Kuranea\BusinessProfile\Customer\PublicFooterBuilder::build($escapedProfile, true);
assertBusinessProfileTrue(!str_contains($escapedHtml, '<script>alert(1)</script>'), 'Published seller values must be escaped.');

echo "PASS: public branding and approved seller disclosures are rendered separately by locale\n";

require_once __DIR__ . '/bank_payment_linkage.php';
