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
$specifiedActSection = array_values(array_filter($adminSections, static fn (array $section): bool => $section['key'] === 'specified_commercial_act'))[0];
assertBusinessProfileSame('특정상거래법 표시 · 일본어', $specifiedActSection['fields'][0]['label'], 'The Japanese specified-commercial-act label must be presented in Korean in the admin form.');
$brandSection = array_values(array_filter($adminSections, static fn (array $section): bool => $section['key'] === 'brand'))[0];
$uploadSlots = array_map(
    static fn (array $field): mixed => $field['options']['slot'] ?? null,
    array_filter($brandSection['fields'], static fn (array $field): bool => $field['type'] === 'image_upload')
);
assertBusinessProfileSame(['primary_logo', 'favicon_symbol', 'pwa_icon'], array_values($uploadSlots), 'The Korean brand editor should accept the three official source image roles.');

$editedByAdmin = \Kuranea\BusinessProfile\Admin\AdminProfileForm::apply($initial, [
    'brand' => [
        'name' => ['ko-KR' => 'ORDENOWA 테스트'],
        'assets' => ['header_desktop' => 'https://malicious.example/fake.png'],
    ],
    'seller' => ['authorization_status' => 'approved'],
    'unrecognized' => ['secret' => 'discard this'],
]);
assertBusinessProfileSame('ORDENOWA 테스트', $editedByAdmin['brand']['name']['ko-KR'], 'The admin form should map submitted editable fields into the profile.');
assertBusinessProfileSame('pending', $initial['seller']['authorization_status'], 'Applying edits must not mutate the input profile version.');
assertBusinessProfileTrue(!isset($editedByAdmin['unrecognized']), 'The admin form must ignore fields outside its allowlist.');
assertBusinessProfileSame('pending', $editedByAdmin['seller']['authorization_status'], 'Ordinary profile edits must not grant seller authorization.');
assertBusinessProfileSame($initial['brand']['assets'], $editedByAdmin['brand']['assets'], 'Submitted paths must not replace verified image paths outside the upload pipeline.');

$renderedForm = \Kuranea\BusinessProfile\Admin\AdminProfileForm::render($initial, '/admin-test', 'csrf-token');
assertBusinessProfileTrue(str_contains($renderedForm, 'name="profile[brand][name][ja-JP]"'), 'The form should expose localized brand inputs as explicit structured fields.');
assertBusinessProfileTrue(str_contains($renderedForm, 'action="/admin-test"'), 'The form should post to the authenticated admin URL.');
assertBusinessProfileTrue(!str_contains($renderedForm, 'KURANEA'), 'The customer brand form should not display KURANEA as the current official brand.');
assertBusinessProfileTrue(str_contains($renderedForm, 'submitOrdenowaPreview'), 'The settings form should provide a private preview action.');
assertBusinessProfileTrue(str_contains($renderedForm, 'enctype="multipart/form-data"'), 'The settings form must support controlled image uploads.');
assertBusinessProfileTrue(str_contains($renderedForm, 'name="brand_uploads[primary_logo]"'), 'The official logo upload slot must be addressable without a code change.');
assertBusinessProfileTrue(str_contains($renderedForm, 'name="brand_uploads[favicon_symbol]"'), 'The favicon source upload slot must be addressable.');
assertBusinessProfileTrue(str_contains($renderedForm, 'name="brand_uploads[pwa_icon]"'), 'The PWA icon source upload slot must be addressable.');

$unsafePreviewProfile = $initial;
$unsafePreviewProfile['brand']['name']['ja-JP'] = '<script>alert(1)</script>';
$unsafePreviewProfile['localization']['default_locale'] = 'ja-JP';
$previewHtml = \Kuranea\BusinessProfile\Admin\AdminProfileForm::renderPreview($unsafePreviewProfile);
assertBusinessProfileTrue(!str_contains($previewHtml, '<script>alert(1)</script>'), 'Admin previews must escape editable customer content.');
assertBusinessProfileTrue(str_contains($previewHtml, '관리자 전용'), 'Admin previews must state that they do not publish the profile.');
$imagePreviewProfile = $initial;
$imagePreviewProfile['brand']['assets']['header_desktop'] = 'img/ordenowa/versions/' . str_repeat('c', 64) . '/header-desktop.png';
$imagePreviewHtml = \Kuranea\BusinessProfile\Admin\AdminProfileForm::renderPreview($imagePreviewProfile, 'https://shop.example/');
assertBusinessProfileTrue(str_contains($imagePreviewHtml, 'https://shop.example/img/ordenowa/versions/'), 'Uploaded brand derivatives should be visible in the authenticated preview.');
assertBusinessProfileTrue(str_contains($imagePreviewHtml, '<figcaption>이메일 로고</figcaption>'), 'The authenticated brand preview should include the email logo derivative.');

$secretProfile = $initial;
$secretProfile['bank_accounts'] = [['account_number' => '9988776655', 'account_holder' => 'PRIVATE HOLDER']];
$secretVersion = new \Kuranea\BusinessProfile\Domain\ProfileVersion(99, 1, $secretProfile, 10, null, '2026-10-22 10:00:00');
$generalProfileHtml = \Kuranea\BusinessProfile\Admin\AdminProfileForm::render($secretProfile, '/admin-test', 'csrf-token');
assertBusinessProfileTrue(!str_contains($generalProfileHtml, '9988776655') && !str_contains($generalProfileHtml, 'PRIVATE HOLDER'), 'General profile settings must not render bank secrets.');
$historyHtml = \Kuranea\BusinessProfile\Admin\AdminProfileForm::renderHistory([$secretVersion], 99, 0, '/admin-test', 'csrf-token');
assertBusinessProfileTrue(str_contains($historyHtml, '현재 초안'), 'The history should identify the active draft.');
assertBusinessProfileTrue(str_contains($historyHtml, '이 버전을 초안으로 복원'), 'The history should expose restore as a new draft action.');
assertBusinessProfileTrue(!str_contains($historyHtml, '9988776655') && !str_contains($historyHtml, 'PRIVATE HOLDER'), 'Profile history must never render full bank details.');
$viewOnlyHistory = \Kuranea\BusinessProfile\Admin\AdminProfileForm::renderHistory([$secretVersion], 99, 0, '/admin-test', 'csrf-token', false);
assertBusinessProfileTrue(!str_contains($viewOnlyHistory, 'submitOrdenowaRestore'), 'View-only employees must not receive a restore control.');

$maskedBank = \Kuranea\BusinessProfile\Admin\BankAccountPresenter::mask([
    'bank_name' => 'TEST BANK',
    'account_number' => '1234567890',
    'account_holder' => 'TEST HOLDER',
]);
assertBusinessProfileSame('••••••7890', $maskedBank['account_number'], 'General settings and history should mask the bank account number.');
assertBusinessProfileSame('TEST BANK', $maskedBank['bank_name'], 'The masked general history may retain the non-secret bank name.');

assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canEdit(['view' => 1, 'edit' => 1]), 'An employee with view and edit permission may save drafts.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canEdit(['edit' => 0]), 'An employee without edit permission must not save drafts.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canEdit(['view' => 0, 'edit' => 1]), 'Edit permission without view must not permit reading or changing settings.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canView(['view' => 1]), 'Back Office settings require an explicit view permission.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canView(['view' => 0]), 'Employees without view permission must not read settings.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canPublish(['view' => 1, 'add' => 1, 'edit' => 1]), 'Publishing requires explicit view, add, and edit access.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canPublish(['add' => 0, 'edit' => 1]), 'Edit permission alone must not permit publishing.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canPublish(['view' => 0, 'add' => 1, 'edit' => 1]), 'Publish permission also requires view access.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canViewBank(['view' => 1]), 'Bank details require separate bank tab view permission.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canViewBank(['view' => 0]), 'General profile permission must not expose bank details.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canEditBank(['view' => 1, 'edit' => 1]), 'Bank edits require separate view and edit permission.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canEditBank(['view' => 1, 'edit' => 0]), 'Bank view permission alone must not allow editing.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canApproveSeller(false), 'An ordinary employee must not approve the seller relationship.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Admin\AdminAccessPolicy::canApproveSeller(true), 'Only a PrestaShop super-administrator may approve the seller relationship.');

$bankAccounts = \Kuranea\BusinessProfile\Admin\AdminBankAccountForm::apply([
    'accounts' => [[
        'bank_name' => '  TEST BANK ',
        'branch_name' => ' Tokyo ',
        'account_type' => 'ordinary',
        'account_number' => '1234-5678',
        'account_holder' => 'TEST HOLDER',
        'active' => '1',
    ]],
]);
assertBusinessProfileSame(1, count($bankAccounts), 'The bank-only form should retain one complete bank account.');
assertBusinessProfileSame('TEST BANK', $bankAccounts[0]['bank_name'], 'Bank form fields should be trimmed before saving.');
assertBusinessProfileSame('12345678', $bankAccounts[0]['account_number'], 'Bank form account numbers should be stored as digits only.');
assertBusinessProfileSame(true, $bankAccounts[0]['active'], 'Bank accounts should retain their explicit enabled state.');

$bankForm = \Kuranea\BusinessProfile\Admin\AdminBankAccountForm::render($bankAccounts, '/admin-banks', 'bank-csrf');
assertBusinessProfileTrue(str_contains($bankForm, 'name="bank_accounts[accounts][0][account_number]"'), 'The separately authorized bank screen should expose the account number field.');
assertBusinessProfileTrue(str_contains($bankForm, '12345678'), 'The authorized bank editor should allow account details to be reviewed and corrected.');
$bankHistoryVersion = new \Kuranea\BusinessProfile\Domain\ProfileVersion(100, 1, [
    'bank_accounts' => [['bank_name' => 'TEST BANK', 'branch_name' => 'TOKYO', 'account_number' => '12345678', 'account_holder' => 'TEST HOLDER']],
], 10, null, '2026-10-22 10:00:00');
$bankHistory = \Kuranea\BusinessProfile\Admin\AdminBankAccountForm::renderHistory([$bankHistoryVersion], 101, '/admin-banks', 'bank-csrf', true);
assertBusinessProfileTrue(str_contains($bankHistory, 'submitOrdenowaRestoreBanks'), 'Bank administrators should have a dedicated historical account restore action.');
assertBusinessProfileTrue(str_contains($bankHistory, '••••••5678'), 'Bank account history should show only a masked account number.');
assertBusinessProfileTrue(!str_contains($bankHistory, '12345678') && !str_contains($bankHistory, 'TEST HOLDER'), 'Bank account history must not expose full account secrets.');
assertBusinessProfileTrue(!str_contains(\Kuranea\BusinessProfile\Admin\AdminBankAccountForm::renderHistory([$bankHistoryVersion], 101, '/admin-banks', 'bank-csrf', false), 'submitOrdenowaRestoreBanks'), 'View-only bank administrators must not receive a restore action.');
assertBusinessProfileThrows(
    static fn () => \Kuranea\BusinessProfile\Admin\AdminBankAccountForm::apply(['accounts' => [[
        'bank_name' => 'TEST BANK', 'branch_name' => 'Tokyo', 'account_type' => 'ordinary',
        'account_number' => 'ABC', 'account_holder' => 'TEST HOLDER', 'active' => '1',
    ]]]),
    'Invalid bank account numbers should be rejected.'
);

echo "PASS: Korean admin settings form sections, allowlisted edits, and bank masking\n";
