<?php

declare(strict_types=1);

require_once __DIR__ . '/run.php';

function makeBankPaymentAccount(string $id, string $bankName, string $accountNumber, bool $active = true): array
{
    return [
        'id' => $id,
        'bank_name' => $bankName,
        'branch_name' => 'TOKYO',
        'account_type' => 'ordinary',
        'account_number' => $accountNumber,
        'account_holder' => 'TEST HOLDER',
        'active' => $active,
    ];
}

function makePublishableBankPaymentProfile(): array
{
    $profile = \Kuranea\BusinessProfile\Domain\ProfileDefaults::initial();
    $profile['seller']['authorization_status'] = 'approved';
    foreach (\Kuranea\BusinessProfile\Domain\ProfileDefaults::LOCALES as $locale) {
        $profile['seller']['legal_name'][$locale] = 'TEST SELLER';
        $profile['seller']['address'][$locale] = 'TEST ADDRESS';
        $profile['seller']['representative'][$locale] = 'TEST REPRESENTATIVE';
        $profile['seller']['responsible_person'][$locale] = 'TEST RESPONSIBLE PERSON';
        $profile['payment'][$locale] = 'TEST PAYMENT';
        $profile['shipping'][$locale] = 'TEST SHIPPING';
        $profile['refund'][$locale] = 'TEST REFUND';
        $profile['content']['terms'][$locale] = 'TEST TERMS';
        $profile['content']['privacy'][$locale] = 'TEST PRIVACY';
        $profile['content']['specified_commercial_act'][$locale] = 'TEST DISCLOSURE';
    }
    $profile['brand']['assets'] = array_fill_keys([
        'header_desktop', 'header_mobile', 'admin_login', 'email_logo', 'favicon',
        'favicon_16', 'favicon_32', 'apple_touch', 'pwa_192', 'pwa_512',
        'pwa_maskable_512', 'og_image',
    ], 'validated-asset.png');
    $profile['seller']['support'] = ['phone' => '03-0000-0000', 'email' => 'seller@example.invalid'];

    return $profile;
}

$accountAId = str_repeat('a', 32);
$accountBId = str_repeat('b', 32);
$inactiveId = str_repeat('c', 32);
$profile = makePublishableBankPaymentProfile();
assertBusinessProfileSame(
    ['enabled' => false, 'bank_account_id' => ''],
    \Kuranea\BusinessProfile\Domain\ProfileDefaults::initial()['payment_methods']['bank_transfer'],
    'Bank transfer should be explicitly disabled until an operator selects and links an account.'
);
$profile['bank_accounts'] = [
    makeBankPaymentAccount($accountAId, 'SELECTED TEST BANK', '11112222'),
    makeBankPaymentAccount($accountBId, 'OTHER ACTIVE TEST BANK', '33334444'),
    makeBankPaymentAccount($inactiveId, 'INACTIVE TEST BANK', '55556666', false),
];
$profile['payment_methods']['bank_transfer'] = ['enabled' => true, 'bank_account_id' => $accountAId];
$profile['_resolved_locale'] = 'ja-JP';

$footer = \Kuranea\BusinessProfile\Customer\PublicFooterBuilder::build($profile, true);
assertBusinessProfileTrue(!str_contains($footer, 'SELECTED TEST BANK') && !str_contains($footer, '11112222'), 'Generic storefront output must not reveal bank details before staff issues an order-bound instruction.');
assertBusinessProfileTrue(!str_contains($footer, 'OTHER ACTIVE TEST BANK') && !str_contains($footer, '33334444'), 'Generic storefront output must never reveal another account.');
assertBusinessProfileTrue(!str_contains($footer, 'INACTIVE TEST BANK') && !str_contains($footer, '55556666'), 'Generic storefront output must never reveal inactive account details.');

$legal = \Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder::build($profile, true);
assertBusinessProfileTrue(!str_contains($legal, 'SELECTED TEST BANK') && !str_contains($legal, '11112222'), 'The generic legal page must not reveal bank details before staff issues an order-bound instruction.');
assertBusinessProfileTrue(!str_contains($legal, 'OTHER ACTIVE TEST BANK') && !str_contains($legal, '33334444'), 'The legal page must not show any bank account.');

$disabled = $profile;
$disabled['payment_methods']['bank_transfer'] = ['enabled' => false, 'bank_account_id' => $accountAId];
$disabledFooter = \Kuranea\BusinessProfile\Customer\PublicFooterBuilder::build($disabled, true);
assertBusinessProfileTrue(!str_contains($disabledFooter, '11112222'), 'Active bank details must stay private when bank transfer is disabled.');
assertBusinessProfileTrue(!str_contains(\Kuranea\BusinessProfile\Customer\PublishedLegalPageBuilder::build($disabled, true), '11112222'), 'The legal page must hide accounts when bank transfer is disabled.');
$legacyProfile = $profile;
unset($legacyProfile['payment_methods']);
assertBusinessProfileTrue(!str_contains(\Kuranea\BusinessProfile\Customer\PublicFooterBuilder::build($legacyProfile, true), '11112222'), 'Legacy profiles without payment-method settings must fail closed and hide bank details.');

$mailHtml = '<html><body>Order</body></html>';
$mailText = 'Order';
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Customer\OrderConfirmationMailContent::append('order_conf', $mailHtml, $mailText, $profile, true), 'Order confirmation mail should still include the published profile.');
assertBusinessProfileTrue(!str_contains($mailHtml, '11112222') && !str_contains($mailHtml, '33334444'), 'Generic HTML order mail must not reveal bank details before staff issues an order-bound instruction.');
assertBusinessProfileTrue(!str_contains($mailText, '11112222') && !str_contains($mailText, '33334444'), 'Generic plain-text order mail must not reveal bank details before staff issuance.');
$disabledMailHtml = '<html><body>Order</body></html>';
$disabledMailText = 'Order';
\Kuranea\BusinessProfile\Customer\OrderConfirmationMailContent::append('order_conf', $disabledMailHtml, $disabledMailText, $disabled, true);
assertBusinessProfileTrue(!str_contains($disabledMailHtml, '11112222') && !str_contains($disabledMailText, '11112222'), 'Order mail must hide active bank details when bank transfer is disabled.');

$validator = new \Kuranea\BusinessProfile\Domain\ProfileValidator();
assertBusinessProfileSame([], $validator->validateForPublish($profile), 'An enabled bank-transfer method linked to a complete active account should be publishable.');
assertBusinessProfileSame(true, \Kuranea\BusinessProfile\Customer\CommerceGate::isEnabled($profile, true), 'Commerce may pass the gate when the selected bank-transfer account is valid.');
$missingLink = $profile;
$missingLink['payment_methods']['bank_transfer']['bank_account_id'] = '';
$missingLinkErrors = $validator->validateForPublish($missingLink);
assertBusinessProfileTrue(in_array('은행 계좌이체 결제에는 게시할 활성 계좌를 연결해야 합니다.', $missingLinkErrors, true), 'Publishing enabled bank transfer without a linked active account must fail with a clear Korean error.');
assertBusinessProfileSame(false, \Kuranea\BusinessProfile\Customer\CommerceGate::isEnabled($missingLink, true), 'Commerce must fail closed when enabled bank transfer has no linked active account.');
$inactiveLink = $profile;
$inactiveLink['payment_methods']['bank_transfer']['bank_account_id'] = $inactiveId;
assertBusinessProfileTrue(in_array('은행 계좌이체 결제에는 게시할 활성 계좌를 연결해야 합니다.', $validator->validateForPublish($inactiveLink), true), 'Publishing a link to an inactive account must fail.');
$noBankTransfer = $profile;
$noBankTransfer['payment_methods']['bank_transfer'] = ['enabled' => false, 'bank_account_id' => ''];
$noBankTransfer['bank_accounts'] = [];
assertBusinessProfileSame([], $validator->validateForPublish($noBankTransfer), 'A complete seller profile may publish without bank transfer when that method is explicitly disabled.');

$adminAccounts = \Kuranea\BusinessProfile\Admin\AdminBankAccountForm::apply(['accounts' => [[
    'id' => $accountAId,
    'bank_name' => 'SELECTED TEST BANK',
    'branch_name' => 'TOKYO',
    'account_type' => 'ordinary',
    'account_number' => '11112222',
    'account_holder' => 'TEST HOLDER',
    'active' => '1',
]]]);
assertBusinessProfileSame($accountAId, $adminAccounts[0]['id'] ?? null, 'The bank form should preserve stable account IDs across edits.');
$paymentMethod = \Kuranea\BusinessProfile\Admin\AdminBankAccountForm::applyPaymentMethod([
    'enabled' => '1',
    'bank_account_id' => $accountAId,
], $adminAccounts);
assertBusinessProfileSame(['enabled' => true, 'bank_account_id' => $accountAId], $paymentMethod, 'The restricted bank settings form should save the explicit method and account link.');
$inactiveAdminAccounts = [...$adminAccounts, makeBankPaymentAccount($inactiveId, 'INACTIVE TEST BANK', '55556666', false)];
assertBusinessProfileSame(
    ['enabled' => true, 'bank_account_id' => ''],
    \Kuranea\BusinessProfile\Admin\AdminBankAccountForm::applyPaymentMethod(['enabled' => '1', 'bank_account_id' => $inactiveId], $inactiveAdminAccounts),
    'The admin settings parser must refuse to link an inactive account.'
);
$bankForm = \Kuranea\BusinessProfile\Admin\AdminBankAccountForm::render($adminAccounts, '/admin-banks', 'bank-csrf', $paymentMethod);
assertBusinessProfileTrue(str_contains($bankForm, 'name="bank_accounts[payment_method][enabled]"'), 'The bank settings page should expose an explicit bank-transfer switch.');
assertBusinessProfileTrue(str_contains($bankForm, 'name="bank_accounts[payment_method][bank_account_id]"'), 'The bank settings page should let an operator select the linked account.');

$repository = new InMemoryBusinessProfileRepository();
$service = new \Kuranea\BusinessProfile\Domain\ProfileVersionService($repository, $validator);
$first = $profile;
$firstId = $service->saveDraft(1, $first, 31);
$second = $first;
$second['payment_methods']['bank_transfer'] = ['enabled' => true, 'bank_account_id' => $accountBId];
$service->saveDraft(1, $second, 32);
assertBusinessProfileThrows(
    static fn () => $service->restoreAsDraft(1, $firstId, 33),
    'General settings restore must not change the bank account link without bank-management authorization.'
);
$restoredId = $service->restoreBankAccountsAsDraft(1, $firstId, 34);
assertBusinessProfileSame($accountAId, $repository->loadDraft(1)?->profile['payment_methods']['bank_transfer']['bank_account_id'] ?? null, 'Bank-only restore should restore the linked bank-transfer account together with bank accounts.');
assertBusinessProfileSame($restoredId, $repository->loadDraft(1)?->id, 'Bank linkage restore should create a new draft version.');

echo "PASS: bank transfer publication, public disclosure, email, and account linkage are fail-closed\n";
