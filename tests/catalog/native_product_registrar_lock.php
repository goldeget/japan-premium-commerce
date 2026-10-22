<?php

declare(strict_types=1);

use Kuranea\Catalog\Integration\NativeProductRegistration;
use Kuranea\Catalog\Integration\PrestaShopNativeProductRegistrar;

require_once __DIR__ . '/../../modules/kuraneacatalog/autoload.php';

final class CatalogNativeRegistrarLockTestState
{
    /** @var list<string> */
    public static array $events = [];
    /** @var list<string> */
    public static array $lockNames = [];
}

final class Db
{
    public static mixed $lockResult = 1;
    public static mixed $releaseResult = 1;
    private static ?self $instance = null;

    public static function getInstance(): self
    {
        return self::$instance ??= new self();
    }

    public function getValue(string $query, bool $useCache = true): mixed
    {
        if ($useCache) {
            throw new RuntimeException('Catalog advisory-lock queries must bypass the PrestaShop SQL cache.');
        }
        if (preg_match("/GET_LOCK\\('([^']+)', 10\\)/", $query, $matches) === 1) {
            CatalogNativeRegistrarLockTestState::$events[] = 'db.lock';
            CatalogNativeRegistrarLockTestState::$lockNames[] = $matches[1];

            return self::$lockResult;
        }
        if (preg_match("/RELEASE_LOCK\\('([^']+)'\\)/", $query, $matches) === 1) {
            CatalogNativeRegistrarLockTestState::$events[] = 'db.release';
            CatalogNativeRegistrarLockTestState::$lockNames[] = $matches[1];

            return self::$releaseResult;
        }

        throw new RuntimeException('Unexpected synthetic DB query: ' . $query);
    }
}

final class Configuration
{
    public static function get(string $key): int
    {
        return match ($key) {
            'PS_CURRENCY_DEFAULT' => 1,
            'PS_HOME_CATEGORY' => 2,
            default => 0,
        };
    }
}

final class Currency
{
    public string $iso_code = 'JPY';

    public function __construct(int $currencyId)
    {
    }
}

final class Context
{
    public static function getContext(): object
    {
        return (object) [
            'language' => (object) ['id' => 1],
            'shop' => (object) ['id' => 1],
        ];
    }
}

final class Language
{
    /** @return list<array{id_lang:int}> */
    public static function getLanguages(bool $activeOnly = false): array
    {
        return [['id_lang' => 1]];
    }
}

final class Product
{
    public static int $existingProductId = 0;
    public static bool $addSucceeds = true;
    public int $id = 0;
    public $reference = '';
    public $name = '';
    public $active = 0;
    public $visibility = 'none';
    public $available_for_order = 0;
    public $link_rewrite = [];
    public $description_short = [];
    public $description = [];
    public $price = 0.0;
    public $id_shop_default = 0;
    public $id_category_default = 0;
    public $id_tax_rules_group = 0;
    public $minimal_quantity = 1;
    public $show_price = 0;

    public static function getIdByReference(string $reference): int
    {
        CatalogNativeRegistrarLockTestState::$events[] = 'product.lookup';

        return self::$existingProductId;
    }

    public function add(): bool
    {
        CatalogNativeRegistrarLockTestState::$events[] = 'product.add';
        if (!self::$addSucceeds) {
            return false;
        }

        $this->id = 1234;

        return true;
    }

    /** @param list<int> $categoryIds */
    public function addToCategories(array $categoryIds): bool
    {
        CatalogNativeRegistrarLockTestState::$events[] = 'product.categories';

        return true;
    }
}

function assertCatalogNativeLockSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertCatalogNativeLockThrows(callable $callback, string $message): void
{
    try {
        $callback();
    } catch (RuntimeException) {
        return;
    }

    throw new RuntimeException($message . '; no exception was thrown');
}

$approvedAt = new DateTimeImmutable('2026-10-22T12:30:00+00:00');
$registration = new NativeProductRegistration(
    'TEST-0123456789AB-ABCDEF012345',
    '[TEST/DEMO] Synthetic concurrency fixture',
    "KURANEA TEST/DEMO catalog import; not for sale.\nApproved by: catalog-operator\nApproved at: " . $approvedAt->format(DATE_ATOM),
    1200,
    'catalog-operator',
    $approvedAt
);
$registrar = new PrestaShopNativeProductRegistrar();

CatalogNativeRegistrarLockTestState::$events = [];
CatalogNativeRegistrarLockTestState::$lockNames = [];
Db::$lockResult = 1;
Product::$existingProductId = 0;
Product::$addSucceeds = true;
assertCatalogNativeLockSame(1234, $registrar->register($registration), 'A lock-protected TEST product registration should return the native product ID.');
assertCatalogNativeLockSame(
    ['db.lock', 'product.lookup', 'product.add', 'product.categories', 'db.release'],
    CatalogNativeRegistrarLockTestState::$events,
    'The registrar must hold a named database lock across reference lookup and native product creation.'
);
assertCatalogNativeLockSame(2, count(CatalogNativeRegistrarLockTestState::$lockNames), 'The database advisory lock must be released after registration.');
assertCatalogNativeLockSame(CatalogNativeRegistrarLockTestState::$lockNames[0], CatalogNativeRegistrarLockTestState::$lockNames[1], 'The same reference must use one stable lock name for acquire and release.');
assertCatalogNativeLockSame(64, strlen(CatalogNativeRegistrarLockTestState::$lockNames[0]), 'The lock name must fit MariaDB GET_LOCK limits.');

CatalogNativeRegistrarLockTestState::$events = [];
CatalogNativeRegistrarLockTestState::$lockNames = [];
Db::$lockResult = 0;
assertCatalogNativeLockThrows(
    static fn () => $registrar->register($registration),
    'A busy or unavailable reference lock must fail closed before product lookup or creation.'
);
assertCatalogNativeLockSame(['db.lock'], CatalogNativeRegistrarLockTestState::$events, 'A failed lock acquisition must not read or create a native product.');

CatalogNativeRegistrarLockTestState::$events = [];
CatalogNativeRegistrarLockTestState::$lockNames = [];
Db::$lockResult = 1;
Product::$addSucceeds = false;
assertCatalogNativeLockThrows(
    static fn () => $registrar->register($registration),
    'A native product creation failure should remain visible.'
);
assertCatalogNativeLockSame('db.release', end(CatalogNativeRegistrarLockTestState::$events), 'The database lock must be released when product creation throws.');

echo "PASS: native product registrar advisory-lock protocol checks\n";
