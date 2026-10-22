<?php

declare(strict_types=1);

require_once __DIR__ . '/run.php';

assertBusinessProfileSame(['ja-JP', 'en-US', 'ko-KR'], $initial['localization']['enabled_locales'] ?? null, 'All three supported customer locales should be independently listed in profile settings.');
assertBusinessProfileSame('ja-JP', $initial['localization']['default_locale'] ?? null, 'Japanese should remain the default customer locale.');

$adminSections = \Kuranea\BusinessProfile\Admin\AdminProfileForm::sections();
$adminSectionTitles = array_column($adminSections, 'title');
foreach (['기본 정보', '브랜드·로고', '사업자 정보', '고객센터', '은행 계좌', '결제 설정', '배송 설정', '반품·환불', '이용약관', '특정상거래법 표시', '다국어', 'SEO·PWA'] as $requiredSection) {
    assertBusinessProfileTrue(in_array($requiredSection, $adminSectionTitles, true), 'The Korean admin form should include the ' . $requiredSection . ' section.');
}

$editedByAdmin = \Kuranea\BusinessProfile\Admin\AdminProfileForm::apply($initial, [
    'brand' => ['name' => ['ko-KR' => 'ORDENOWA 테스트']],
    'seller' => ['authorization_status' => 'approved'],
    'unrecognized' => ['secret' => 'discard this'],
]);
assertBusinessProfileSame('ORDENOWA 테스트', $editedByAdmin['brand']['name']['ko-KR'], 'The admin form should map submitted editable fields into the profile.');
assertBusinessProfileSame('pending', $initial['seller']['authorization_status'], 'Applying edits must not mutate the input profile version.');
assertBusinessProfileTrue(!isset($editedByAdmin['unrecognized']), 'The admin form must ignore fields outside its allowlist.');
assertBusinessProfileSame('pending', $editedByAdmin['seller']['authorization_status'], 'Ordinary profile edits must not grant seller authorization.');

$renderedForm = \Kuranea\BusinessProfile\Admin\AdminProfileForm::render($initial, '/admin-test', 'csrf-token');
assertBusinessProfileTrue(str_contains($renderedForm, 'name="profile[brand][name][ja-JP]"'), 'The form should expose localized brand inputs as explicit structured fields.');
assertBusinessProfileTrue(str_contains($renderedForm, 'action="/admin-test"'), 'The form should post to the authenticated admin URL.');
assertBusinessProfileTrue(!str_contains($renderedForm, 'KURANEA'), 'The customer brand form should not display KURANEA as the current official brand.');

$maskedBank = \Kuranea\BusinessProfile\Admin\BankAccountPresenter::mask([
    'bank_name' => 'TEST BANK',
    'account_number' => '1234567890',
    'account_holder' => 'TEST HOLDER',
]);
assertBusinessProfileSame('••••••7890', $maskedBank['account_number'], 'General settings and history should mask the bank account number.');
assertBusinessProfileSame('TEST BANK', $maskedBank['bank_name'], 'The masked general history may retain the non-secret bank name.');

assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canEdit(['edit' => 1]), 'An employee with edit permission may save drafts.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canEdit(['edit' => 0]), 'An employee without edit permission must not save drafts.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canPublish(['add' => 1, 'edit' => 1]), 'Publishing requires explicit add and edit access.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canPublish(['add' => 0, 'edit' => 1]), 'Edit permission alone must not permit publishing.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canEditBank(['edit' => 1]), 'Bank edits require the separate bank tab edit permission.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canEditBank(['edit' => 0]), 'General profile permission must not imply bank edit permission.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canApproveSeller(false), 'An ordinary employee must not approve the seller relationship.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canApproveSeller(true), 'Only a PrestaShop super-administrator may approve the seller relationship.');

echo "PASS: Korean admin settings form sections, allowlisted edits, and bank masking\n";
