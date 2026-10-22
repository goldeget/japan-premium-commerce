<?php

declare(strict_types=1);

require_once __DIR__ . '/run.php';

$adminSections = \Kuranea\BusinessProfile\Admin\AdminProfileForm::sections();
$adminSectionTitles = array_column($adminSections, 'title');
foreach (['기본 정보', '브랜드·로고', '사업자 정보', '고객센터', '결제 설정', '배송 설정', '반품·환불', '이용약관', '특정상거래법 표시', 'SEO·PWA'] as $requiredSection) {
    assertBusinessProfileTrue(in_array($requiredSection, $adminSectionTitles, true), 'The Korean admin form should include the ' . $requiredSection . ' section.');
}
assertBusinessProfileTrue(!in_array('은행 계좌', $adminSectionTitles, true), 'Bank information must be managed through its separately permissioned admin tab.');

$editedByAdmin = \Kuranea\BusinessProfile\Admin\AdminProfileForm::apply($initial, [
    'brand' => ['name' => ['ko-KR' => 'ORDENOWA 테스트']],
    'seller' => ['authorization_status' => 'approved'],
    'unrecognized' => ['secret' => 'discard this'],
]);
assertBusinessProfileSame('ORDENOWA 테스트', $editedByAdmin['brand']['name']['ko-KR'], 'The admin form should map submitted editable fields into the profile.');
assertBusinessProfileSame('pending', $initial['seller']['authorization_status'], 'Applying edits must not mutate the input profile version.');
assertBusinessProfileTrue(!isset($editedByAdmin['unrecognized']), 'The admin form must ignore fields outside its allowlist.');

$maskedBank = \Kuranea\BusinessProfile\Admin\BankAccountPresenter::mask([
    'bank_name' => 'TEST BANK',
    'account_number' => '1234567890',
    'account_holder' => 'TEST HOLDER',
]);
assertBusinessProfileSame('••••••7890', $maskedBank['account_number'], 'General settings and history should mask the bank account number.');

echo "PASS: Korean admin settings form sections, allowlisted edits, and bank masking\n";
