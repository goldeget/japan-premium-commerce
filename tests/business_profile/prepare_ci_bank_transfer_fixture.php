<?php

declare(strict_types=1);

use Kuranea\BusinessProfile\Customer\CommerceGate;
use Kuranea\BusinessProfile\Domain\ProfileValidator;
use Kuranea\BusinessProfile\Domain\ProfileVersionService;
use Kuranea\BusinessProfile\Infrastructure\DatabaseSchema;
use Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository;

function ordenowaBankFixtureRequire(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$runId = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
$project = (string) getenv('CI_COMPOSE_PROJECT_NAME');
$orderIdText = (string) getenv('KURANEA_CI_ORDER_ID');
$viewport = (string) getenv('KURANEA_CI_VIEWPORT');
$expectedProject = sprintf('kuranea-ci-%s-%s', $runId, $attempt);
ordenowaBankFixtureRequire(
    getenv('CI') === 'true'
        && getenv('GITHUB_ACTIONS') === 'true'
        && getenv('KURANEA_ISOLATED_CI') === '1'
        && preg_match('/\A[0-9]+\z/D', $runId) === 1
        && preg_match('/\A[0-9]+\z/D', $attempt) === 1
        && $project === $expectedProject
        && getenv('KURANEA_CI_PROJECT_NAME') === $expectedProject
        && $viewport === 'bank'
        && preg_match('/\A[1-9][0-9]{0,9}\z/D', $orderIdText) === 1,
    'Synthetic bank-transfer fixture requires its exact disposable Actions project and order.'
);

$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';
require_once '/var/www/html/modules/kuraneabusinessprofile/autoload.php';

ordenowaBankFixtureRequire(
    CommerceGate::isIsolatedCiCheckoutEnabled(),
    'Synthetic bank-transfer fixture was not running behind the isolated commerce gate.'
);

$shopId = (int) Shop::getContextShopID();
$shop = new Shop($shopId);
$order = new Order((int) $orderIdText);
$customer = Validate::isLoadedObject($order) ? new Customer((int) $order->id_customer) : false;
$currency = Validate::isLoadedObject($order) ? new Currency((int) $order->id_currency) : false;
$state = Validate::isLoadedObject($order) ? new OrderState((int) $order->current_state, (int) $order->id_lang) : false;
$expectedEmail = sprintf(
    'qa-ordenowa-checkout-%s-%s-bank@example.invalid',
    $runId,
    $attempt
);
ordenowaBankFixtureRequire(
    $shopId > 0
        && Validate::isLoadedObject($shop)
        && Shop::getTotalShops() === 1
        && Validate::isLoadedObject($order)
        && (int) $order->id_shop === $shopId
        && (int) $order->id_customer > 0
        && Validate::isLoadedObject($customer)
        && strtolower((string) $customer->email) === $expectedEmail
        && !(bool) $customer->is_guest
        && (string) $order->module === 'ps_checkpayment'
        && Validate::isLoadedObject($currency)
        && strtoupper((string) $currency->iso_code) === 'JPY'
        && Validate::isLoadedObject($state)
        && !(bool) $state->paid
        && (float) $order->total_paid_real === 0.0,
    'The supplied run-scoped order is not a same-shop, unpaid JPY offline fixture.'
);

$database = Db::getInstance();
ordenowaBankFixtureRequire(
    $database->execute(DatabaseSchema::createBankTransferInstructionTableSql(_DB_PREFIX_))
        && $database->execute(DatabaseSchema::createBankTransferReceiptLedgerTableSql(_DB_PREFIX_)),
    'Could not ensure the additive synthetic transfer tables in the isolated shop.'
);

$repository = new VersionedProfileRepository();
$baseVersion = $repository->loadDraft($shopId) ?? $repository->loadPublished($shopId);
ordenowaBankFixtureRequire($baseVersion !== null, 'The existing isolated shop profile is unavailable.');
$profile = $baseVersion->profile;
$accountId = substr(hash('sha256', 'ordenowa-ci-bank-account:' . $runId . ':' . $attempt), 0, 32);
$accountNumber = '00001234';
$account = [
    'id' => $accountId,
    'bank_name' => 'ORDENOWA CI synthetic bank',
    'branch_name' => 'QA branch',
    'account_type' => 'ordinary',
    'account_number' => $accountNumber,
    'account_holder' => 'ORDENOWA CI ONLY',
    'active' => true,
];
$accounts = $profile['bank_accounts'] ?? [];
ordenowaBankFixtureRequire(is_array($accounts), 'The isolated bank-account profile section is invalid.');
$accounts[] = $account;
$profile['bank_accounts'] = $accounts;
$profile['payment_methods']['bank_transfer'] = [
    'enabled' => true,
    'bank_account_id' => $accountId,
];
$profile['seller']['legal_name']['ja-JP'] = 'ORDENOWA CI ONLY seller';

$employeeId = 1;
$service = new ProfileVersionService($repository, new ProfileValidator());
$draftVersionId = $service->saveDraft($shopId, $profile, $employeeId);
$publish = $service->publish($shopId, $draftVersionId, $employeeId);
ordenowaBankFixtureRequire($publish['published'] === true, 'The synthetic account could not be published for this disposable acceptance.');

fwrite(STDOUT, "PASS: isolated transfer UI has one run-scoped synthetic account; native order remains unpaid.\n");
