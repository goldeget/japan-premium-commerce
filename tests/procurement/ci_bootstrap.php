<?php

declare(strict_types=1);

// Every mutating native acceptance entry point shares this guard. Never use a
// saved development database or the base Compose project's named volumes.
$run = (string) getenv('GITHUB_RUN_ID');
$attempt = (string) getenv('GITHUB_RUN_ATTEMPT');
if (getenv('CI') !== 'true' || getenv('KURANEA_ISOLATED_CI') !== '1'
    || !preg_match('/\A[0-9]+\z/D', $run) || !preg_match('/\A[0-9]+\z/D', $attempt)
    || getenv('KURANEA_CI_PROJECT_NAME') !== 'ordenowa-procurement-ci-' . $run . '-' . $attempt
    || getenv('DB_SERVER') !== 'mariadb' || getenv('ORDENOWA_APP_MODE') !== 'procurement') {
    fwrite(STDERR, "BLOCKED: exact disposable procurement run identity required.\n");
    exit(77);
}
set_exception_handler(static function (Throwable $error): void {
    // Exception bodies/stack traces can contain SQL, customer data or tokens.
    $site = $error->getTrace()[0] ?? [];
    $file = basename((string) ($site['file'] ?? $error->getFile()));
    $line = (int) ($site['line'] ?? $error->getLine());
    $source = preg_match('/\A[A-Za-z0-9_.-]+\.php\z/D', $file) ? $file . ':' . $line : 'unknown.php:0';
    fwrite(STDERR, 'FAIL procurement native acceptance: ' . get_class($error) . ' source=' . $source . "\n");
    exit(1);
});
$_SERVER['HTTP_HOST'] = (string) getenv('PS_DOMAIN') ?: 'localhost:18081';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
require_once '/var/www/html/config/config.inc.php';
require_once '/var/www/html/modules/ordenowaprocurement/autoload.php';
if ((string) Db::getInstance()->getValue('SELECT DATABASE()') !== 'prestashop'
    || !in_array((string) _DB_SERVER_, ['mariadb', 'mariadb:3306'], true)) {
    throw new RuntimeException('Database isolation guard failed');
}
Shop::setContext(Shop::CONTEXT_SHOP, 1);
$context = Context::getContext();
$context->shop = new Shop(1);
$context->language = new Language((int) Language::getIdByIso('ja', true));
$context->currency = new Currency((int) Configuration::get('PS_CURRENCY_DEFAULT'));

function ciAssert(bool $condition, string $label): void
{
    if (!$condition) {
        // Labels are fixed source literals only.
        throw new RuntimeException($label);
    }
}

function ciFixture(): array
{
    $path = '/tmp/ordenowa-procurement-ci/identity.json';
    $identity = json_decode((string) file_get_contents($path), true, 32, JSON_THROW_ON_ERROR);
    ciAssert(($identity['run'] ?? '') === getenv('GITHUB_RUN_ID') . '-' . getenv('GITHUB_RUN_ATTEMPT'), 'Fixture run mismatch');
    return $identity;
}

/** Native mysqli and restored PDO differ in integer fetch types. Hash SQL values. */
function ciDomainHash(Ordenowa\Procurement\Infrastructure\Database $database, string $suffix): string
{
    $rows = $database->all('SELECT * FROM ' . $database->table($suffix) . ' ORDER BY 1');
    foreach ($rows as &$row) {
        foreach ($row as &$value) {
            $value = $value === null ? null : (string) $value;
        }
        unset($value);
    }
    unset($row);
    return hash('sha256', json_encode($rows, JSON_THROW_ON_ERROR));
}

/**
 * Native support bodies/tokens and ACL audit identities are part of restoration.
 * Only hashes enter the private manifest; rows and schema never reach artifacts.
 */
function ciNativeCriticalManifest(Ordenowa\Procurement\Infrastructure\Database $database): array
{
    $prefix = (string) _DB_PREFIX_;
    ciAssert(preg_match('/\A[A-Za-z0-9_]*\z/D', $prefix) === 1, 'Native manifest prefix invalid');
    $manifest = [];
    foreach (['customer_thread' => 'id_customer_thread', 'customer_message' => 'id_customer_message',
        'kuraneabackoffice_native_acl_audit' => 'id_event'] as $suffix => $primary) {
        $table = '`' . $prefix . $suffix . '`';
        $schema = $database->one('SHOW CREATE TABLE ' . $table);
        ciAssert(is_array($schema) && is_string($schema['Create Table'] ?? null), 'Native critical schema missing');
        $rows = $database->all('SELECT * FROM ' . $table . ' ORDER BY `' . $primary . '`');
        foreach ($rows as &$row) {
            foreach ($row as &$value) $value = $value === null ? null : (string) $value;
            unset($value);
        }
        unset($row);
        $manifest[$suffix] = [
            'schema' => hash('sha256', $schema['Create Table']),
            'data' => hash('sha256', json_encode($rows, JSON_THROW_ON_ERROR)),
        ];
    }
    return $manifest;
}
