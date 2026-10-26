<?php

declare(strict_types=1);

require_once __DIR__ . '/run.php';

$profile = \Kuranea\BusinessProfile\Domain\ProfileDefaults::initial();
$profile['_resolved_locale'] = 'ja-JP';
$profile['brand']['name']['ja-JP'] = 'テストブランド';
$profile['seller']['legal_name']['ja-JP'] = 'TEST SELLER LEGAL';
$profile['seller']['corporate_number'] = '1234567890123';
$profile['seller']['address']['ja-JP'] = 'TEST SELLER ADDRESS';
$profile['seller']['representative']['ja-JP'] = 'TEST REPRESENTATIVE';
$profile['seller']['responsible_person']['ja-JP'] = 'TEST RESPONSIBLE PERSON';
$profile['seller']['support'] = ['phone' => 'TEST SELLER PHONE', 'email' => 'seller@example.invalid'];
$profile['customer_support'] = [
    'phone' => 'TEST CUSTOMER PHONE',
    'email' => 'support@example.invalid',
    'hours' => ['ja-JP' => 'TEST HOURS'],
];
$profile['company_reference']['name']['ja-JP'] = 'DO NOT PUBLISH COMPANY REFERENCE';
$profile['content']['company_profile']['ja-JP'] = 'TEST COMPANY PROFILE';
$profile['payment']['ja-JP'] = 'TEST PAYMENT';
$profile['shipping']['ja-JP'] = 'TEST SHIPPING';
$profile['refund']['ja-JP'] = 'TEST REFUND';
$profile['content']['terms']['ja-JP'] = 'TEST TERMS';
$profile['content']['privacy']['ja-JP'] = 'TEST PRIVACY';
$profile['content']['specified_commercial_act']['ja-JP'] = 'TEST SPECIFIED ACT';
$profile['bank_accounts'] = [
    [
        'id' => str_repeat('a', 32),
        'bank_name' => 'TEST BANK', 'branch_name' => 'TOKYO', 'account_type' => 'ordinary',
        'account_number' => '12345678', 'account_holder' => 'TEST HOLDER', 'active' => true,
    ],
    [
        'bank_name' => 'INACTIVE BANK', 'branch_name' => 'TOKYO', 'account_type' => 'ordinary',
        'account_number' => '87654321', 'account_holder' => 'INACTIVE HOLDER', 'active' => false,
    ],
];
$profile['payment_methods']['bank_transfer'] = ['enabled' => true, 'bank_account_id' => str_repeat('a', 32)];

$closed = \Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder::build($profile, false);
$footerLink = \Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder::footerLink($profile, 'https://shop.example/module/kuraneabusinessprofile/legal');
assertBusinessProfileTrue(str_contains($footerLink, '会社情報・お取引に関する表示'), 'The footer should expose a localized link to the public information page.');
assertBusinessProfileTrue(str_contains($footerLink, 'https://shop.example/module/kuraneabusinessprofile/legal'), 'The footer link should point at the module legal page route.');
assertBusinessProfileTrue(str_contains($closed, '<h1>会社情報・お取引に関する表示</h1>'), 'The Japanese legal page should render its localized title as the page heading.');
assertBusinessProfileTrue(str_contains($closed, '販売とお取引は受け付けていません'), 'Unapproved visitors must see a localized closed-sales notice.');
foreach ([
    'TEST SELLER LEGAL', 'TEST SELLER ADDRESS', 'TEST CUSTOMER PHONE',
    'TEST COMPANY PROFILE', 'TEST PAYMENT', '12345678', 'DO NOT PUBLISH COMPANY REFERENCE',
] as $mustRemainPrivate) {
    assertBusinessProfileTrue(!str_contains($closed, $mustRemainPrivate), 'Closed commerce must not expose seller or operating details: ' . $mustRemainPrivate);
}

$open = \Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder::build($profile, true);
foreach ([
    'TEST COMPANY PROFILE', 'TEST SELLER LEGAL', 'TEST SELLER ADDRESS', 'TEST RESPONSIBLE PERSON',
    'TEST CUSTOMER PHONE', 'TEST HOURS', 'TEST PAYMENT', 'TEST SHIPPING', 'TEST REFUND',
    'TEST TERMS', 'TEST PRIVACY', 'TEST SPECIFIED ACT',
] as $expected) {
    assertBusinessProfileTrue(str_contains($open, $expected), 'Authorized Japanese legal output must include ' . $expected . '.');
}
assertBusinessProfileTrue(!str_contains($open, 'TEST BANK') && !str_contains($open, '12345678'), 'Public legal pages must not reveal bank details before order-specific staff issuance.');
assertBusinessProfileTrue(!str_contains($open, 'INACTIVE BANK') && !str_contains($open, '87654321'), 'Inactive bank accounts must not be published.');
assertBusinessProfileTrue(!str_contains($open, 'DO NOT PUBLISH COMPANY REFERENCE'), 'Company reference data must not be presented as the selling entity.');

$profile['content']['terms']['ja-JP'] = '<script>alert(1)</script>';
$escaped = \Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder::build($profile, true);
assertBusinessProfileTrue(!str_contains($escaped, '<script>alert(1)</script>'), 'Published customer legal copy must be escaped.');
assertBusinessProfileTrue(str_contains($escaped, '&lt;script&gt;'), 'Escaping must preserve the customer-supplied text safely.');

$profile['_resolved_locale'] = 'en-US';
$profile['brand']['name']['en-US'] = 'TEST ENGLISH BRAND';
$profile['content']['specified_commercial_act']['en-US'] = 'TEST ENGLISH DISCLOSURE';
$english = \Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder::build($profile, true);
assertBusinessProfileTrue(str_contains($english, 'Company and transaction information'), 'The legal page title should be localized in English.');
assertBusinessProfileTrue(str_contains($english, 'TEST ENGLISH BRAND') && str_contains($english, 'TEST ENGLISH DISCLOSURE'), 'Published English values should use the English locale.');

$profile['_resolved_locale'] = 'ko-KR';
$profile['brand']['name']['ko-KR'] = '테스트 한국어 브랜드';
$profile['company_reference']['name']['ko-KR'] = 'DO NOT PUBLISH COMPANY REFERENCE KO';
$profile['content']['company_profile']['ko-KR'] = 'TEST KOREAN COMPANY PROFILE';
$profile['seller']['legal_name']['ko-KR'] = 'TEST KOREAN SELLER LEGAL';
$profile['seller']['address']['ko-KR'] = 'TEST KOREAN SELLER ADDRESS';
$profile['seller']['representative']['ko-KR'] = 'TEST KOREAN REPRESENTATIVE';
$profile['seller']['responsible_person']['ko-KR'] = 'TEST KOREAN RESPONSIBLE PERSON';
$profile['customer_support']['hours']['ko-KR'] = 'TEST KOREAN HOURS';
$profile['payment']['ko-KR'] = 'TEST KOREAN PAYMENT';
$profile['shipping']['ko-KR'] = 'TEST KOREAN SHIPPING';
$profile['refund']['ko-KR'] = 'TEST KOREAN REFUND';
$profile['content']['terms']['ko-KR'] = 'TEST KOREAN TERMS';
$profile['content']['privacy']['ko-KR'] = 'TEST KOREAN PRIVACY';
$profile['content']['specified_commercial_act']['ko-KR'] = 'TEST KOREAN DISCLOSURE';
$korean = \Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder::build($profile, true);
assertBusinessProfileTrue(str_contains($korean, '회사 정보 및 거래 안내'), 'The legal page title should be localized in Korean.');
assertBusinessProfileTrue(str_contains($korean, '테스트 한국어 브랜드') && str_contains($korean, 'TEST KOREAN DISCLOSURE'), 'Published Korean values should use the Korean locale.');
foreach ([
    'TEST KOREAN COMPANY PROFILE', 'TEST KOREAN SELLER LEGAL', 'TEST KOREAN SELLER ADDRESS',
    'TEST KOREAN REPRESENTATIVE', 'TEST KOREAN RESPONSIBLE PERSON', 'TEST CUSTOMER PHONE',
    'support@example.invalid', 'TEST KOREAN HOURS', 'TEST KOREAN PAYMENT', 'TEST KOREAN SHIPPING',
    'TEST KOREAN REFUND', 'TEST KOREAN TERMS', 'TEST KOREAN PRIVACY',
] as $expectedKoreanDisclosure) {
    assertBusinessProfileTrue(
        str_contains($korean, $expectedKoreanDisclosure),
        'The Korean legal page should publish localized operating setting ' . $expectedKoreanDisclosure . '.'
    );
}
assertBusinessProfileTrue(
    !str_contains($korean, 'DO NOT PUBLISH COMPANY REFERENCE KO'),
    'Korean company reference data must never be presented as the verified selling entity.'
);

echo "PASS: legal page output is localized, escaped, and seller-gated\n";
