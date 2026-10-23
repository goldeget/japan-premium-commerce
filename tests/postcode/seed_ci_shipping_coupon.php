<?php

declare(strict_types=1);

$runId = trim((string) getenv('GITHUB_RUN_ID'));
$runAttempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
$projectName = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));
$expectedProjectName = 'kuranea-ci-' . $runId . '-' . $runAttempt;

if (getenv('CI') !== 'true'
    || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('KURANEA_ISOLATED_CI') !== '1'
    || preg_match('/\A[0-9]+\z/D', $runId) !== 1
    || preg_match('/\A[0-9]+\z/D', $runAttempt) !== 1
    || $projectName !== $expectedProjectName
) {
    fwrite(STDERR, "BLOCKED: shipping coupon seeding requires its matching isolated GitHub Actions Compose project.\n");
    exit(77);
}

$stage = 'PrestaShop bootstrap';
set_exception_handler(static function (Throwable $exception) use (&$stage): void {
    $message = preg_replace('/[\r\n]+/', ' ', $exception->getMessage()) ?? 'Unknown error';
    $diagnostic = sprintf(
        'KURANEA_SHIPPING_COUPON_STAGE=%s; exception=%s; message=%s',
        $stage,
        get_class($exception),
        substr($message, 0, 1000)
    );
    fwrite(STDERR, $diagnostic . PHP_EOL);
    if (getenv('GITHUB_ACTIONS') === 'true') {
        $annotation = str_replace(['%', "\r", "\n"], ['%25', '%0D', '%0A'], $diagnostic);
        fwrite(STDERR, '::error title=ORDENOWA CI coupon fixture::' . $annotation . PHP_EOL);
    }
    exit(1);
});

$shopRoot = '/var/www/html';
if (!is_file($shopRoot . '/config/config.inc.php')) {
    throw new RuntimeException('The installed PrestaShop configuration is missing.');
}
$_SERVER['HTTP_HOST'] = trim((string) getenv('PS_DOMAIN')) ?: 'localhost:8080';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_PORT'] = (string) (parse_url('http://' . $_SERVER['HTTP_HOST'], PHP_URL_PORT) ?: 80);
require_once $shopRoot . '/config/config.inc.php';

if (!defined('_DB_SERVER_') || (string) _DB_SERVER_ !== 'mariadb'
    || !defined('_DB_NAME_') || (string) _DB_NAME_ !== 'prestashop'
    || (string) Db::getInstance()->getValue('SELECT DATABASE()') !== 'prestashop') {
    throw new RuntimeException('The connected shop database is not the isolated MariaDB prestashop database.');
}

$stage = 'isolated Japanese JPY shop context';
$shopId = 1;
$currencyId = (int) Currency::getIdByIsoCode('JPY', $shopId);
if ($currencyId < 1) {
    throw new RuntimeException('The isolated shop has no JPY currency for its CI coupon.');
}
$context = Context::getContext();
$context->shop = new Shop($shopId);
$context->currency = new Currency($currencyId, null, $shopId);
Shop::setContext(Shop::CONTEXT_SHOP, $shopId);

$stage = 'run-scoped coupon creation';
$code = 'ORDENOWACI' . $runId . $runAttempt;
if (Db::getInstance()->getValue(
    'SELECT `id_cart_rule` FROM `' . _DB_PREFIX_ . 'cart_rule` WHERE `code` = "' . pSQL($code) . '"'
) !== false) {
    throw new RuntimeException('The run-scoped CI coupon code already exists; refusing to reuse a stale fixture.');
}

$rule = new CartRule();
$rule->name = [];
foreach (Language::getLanguages(false) as $language) {
    $rule->name[(int) $language['id_lang']] = 'ORDENOWA CI 50 percent test coupon';
}
$rule->description = 'Disposable isolated CI checkout fixture; no real order payment.';
$rule->code = $code;
$rule->quantity = 2;
$rule->quantity_per_user = 1;
$rule->priority = 1;
$rule->partial_use = 0;
$rule->active = 1;
$rule->highlight = 1;
$rule->cart_rule_restriction = 0;
$rule->product_restriction = 0;
$rule->shop_restriction = 0;
$rule->carrier_restriction = 0;
$rule->group_restriction = 0;
$rule->country_restriction = 0;
$rule->customer_restriction = 0;
$rule->minimum_amount = 1.0;
$rule->minimum_amount_tax = 0;
$rule->minimum_amount_currency = $currencyId;
$rule->minimum_amount_shipping = 0;
$rule->country_restriction = 0;
$rule->carrier_restriction = 0;
$rule->reduction_percent = 50.0;
$rule->reduction_amount = 0.0;
$rule->reduction_tax = 1;
$rule->reduction_currency = $currencyId;
$rule->reduction_product = 0;
$rule->free_shipping = 0;
$rule->date_from = date('Y-m-d H:i:s', time() - 600);
$rule->date_to = date('Y-m-d H:i:s', time() + 7200);

if (!$rule->add() || (int) $rule->id < 1) {
    throw new RuntimeException('Could not create the isolated 50 percent JPY cart rule.');
}
$savedRule = new CartRule((int) $rule->id);
if (!Validate::isLoadedObject($savedRule)
    || (string) $savedRule->code !== $code
    || !(bool) $savedRule->active
    || (float) $savedRule->reduction_percent !== 50.0
    || (bool) $savedRule->free_shipping
) {
    throw new RuntimeException('The run-scoped CI coupon did not persist as a non-shipping 50 percent discount.');
}

echo json_encode([
    'cart_rule_id' => (int) $savedRule->id,
    'code' => (string) $savedRule->code,
    'reduction_percent' => (float) $savedRule->reduction_percent,
    'free_shipping' => (bool) $savedRule->free_shipping,
    'currency' => 'JPY',
    'quantity' => (int) $savedRule->quantity,
    'fixture_scope' => 'run-scoped GitHub Actions disposable checkout database',
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . PHP_EOL;
fwrite(STDERR, "PASS: run-scoped 50 percent JPY coupon fixture saved without a free-shipping override.\n");
