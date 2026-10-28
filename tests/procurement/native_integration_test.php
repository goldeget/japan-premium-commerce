<?php

declare(strict_types=1);

// A hermetic native-boundary test: fake native sessions/ACL/reads, real Runtime,
// Actor, module installation, AdminController input authorization and schema.
// No existing shop database or volume is opened.
define('_DB_PREFIX_', 'native_test_');
define('_PS_VERSION_', '9.2.0');
require_once dirname(__DIR__) . '/admin_audit/native_post_token_fixture.php';
$nativeImageDirectory = sys_get_temp_dir() . '/ordenowa-native-images-' . bin2hex(random_bytes(6));
mkdir($nativeImageDirectory, 0700, true);
define('_PS_PRODUCT_IMG_DIR_', $nativeImageDirectory . '/');
foreach ([501,502,701,702,703,704,705] as $imageId) {
    $imageFolder = $nativeImageDirectory . '/' . implode('/', str_split((string) $imageId));
    mkdir($imageFolder, 0700, true);
    file_put_contents($imageFolder . '/' . $imageId . '-home_default.jpg', 'SYNTHETIC local existing image path fixture');
}
register_shutdown_function(static function () use ($nativeImageDirectory): void {
    $iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($nativeImageDirectory, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST);
    foreach ($iterator as $file) { if ($file->isDir()) rmdir($file->getPathname()); else unlink($file->getPathname()); }
    rmdir($nativeImageDirectory);
});

#[AllowDynamicProperties]
class Module
{
    public array $hooks = [];
    public array $_errors = [];
    public function __construct() { $this->context = Context::getContext(); }
    public function install(): bool { return true; }
    public function uninstall(): bool { return true; }
    public function isRegisteredInHook(string $hook): bool { return in_array($hook, $this->hooks, true); }
    public function registerHook(string $hook): bool { $this->hooks[] = $hook; return true; }
}
class ModuleAdminController { public function __construct() {} public function getContainer(): object { $tab=$this->procurementTab; return nativePostTokenFixtureContainer(static fn(string $value):bool=>in_array($value,[Tools::getAdminTokenLite($tab),'native-valid-previous-mask'],true)); } }
#[AllowDynamicProperties]
class Tab
{
    public static array $ids = ['AdminParentCatalog' => 1];
    public static array $saved = [];
    public function __construct(public int $id = 0) {}
    public static function getIdFromClassName(string $name): int { return self::$ids[$name] ?? 0; }
    public function add(): bool { $this->id = count(self::$ids) + 1; self::$ids[$this->class_name] = $this->id; self::$saved[$this->class_name] = $this->name; return true; }
    public function update(): bool { self::$saved[$this->class_name] = $this->name; return true; }
    public function delete(): bool { return true; }
}
class Language { public static function getLanguages(bool $active): array { return [['id_lang' => 1], ['id_lang' => 2], ['id_lang' => 3]]; } }
class Shop { public const CONTEXT_SHOP = 1; public static int $context = 1; public static function getContext(): int { return self::$context; } }
class Access
{
    public static array $roles = [];
    public static function sluggifyTab(array $tab, string $action): string { if (!in_array($action, ['READ','CREATE','UPDATE','DELETE'], true)) throw new RuntimeException('Invalid native action slug.'); return 'ROLE_MOD_TAB_' . strtoupper($tab['class_name']) . '_' . $action; }
    public static function isGranted(string $role, int $profile): bool { return in_array($role, self::$roles[$profile] ?? [], true); }
}
class Tools { public static function getAdminTokenLite(string $tab): string { return 'native-session-token-' . $tab; } public static function getValue(string $key, mixed $default = false): mixed { return $_GET[$key] ?? $default; } }
class NativeTestSession
{
    public int $id = 1;
    public int $id_profile = 2;
    public bool $active = true;
    public bool $logged = true;
    public function isLogged(): bool { return $this->logged; }
    public function isLoggedBack(): bool { return $this->logged; }
}
class Context
{
    public static object $context;
    public static function getContext(): object { return self::$context; }
}
class Db
{
    public static ?self $db = null;
    public bool $employeeShop = true;
    public bool $customerActive = true;
    public array $writes = [];
    public array $auditRows = [];
    public array $deliveryRows = [];
    public bool $evidenceInstalled = false;
    public array $evidenceRows = [];
    public array $imageRows = [
        ['id_image'=>501,'id_product'=>11,'id_shop'=>1], ['id_image'=>502,'id_product'=>11,'id_shop'=>1],
        ['id_image'=>701,'id_product'=>14,'id_shop'=>1], ['id_image'=>702,'id_product'=>14,'id_shop'=>1],
        ['id_image'=>703,'id_product'=>12,'id_shop'=>1], ['id_image'=>704,'id_product'=>14,'id_shop'=>1], ['id_image'=>705,'id_product'=>14,'id_shop'=>2],
    ];
    public static function getInstance(): self { return self::$db ??= new self(); }
    public function escape(string $value, bool $html): string { return addslashes($value); }
    public function execute(string $sql, bool $cache): bool { $this->writes[] = $sql; return true; }
    public function executeS(string $sql, bool $array, bool $cache): array
    {
        if ($cache !== false) throw new RuntimeException('Native reads must disable cache.');
        if (str_contains($sql, '`native_test_ordenowa_procurement_activity`')) return $this->auditRows;
        if (str_contains($sql, '`native_test_ordenowa_procurement_notification_delivery`')) return $this->deliveryRows;
        if (str_contains($sql, '`native_test_image`')) {
            if (!preg_match('/i.id_product=([0-9]+)/', $sql, $product) || !preg_match('/ims.id_shop=([0-9]+)/', $sql, $shop) || !preg_match('/IN \(([0-9,]+)\)/', $sql, $ids)) throw new RuntimeException('Native image read must constrain product, shop and approved IDs.');
            $approved = array_map('intval', explode(',', $ids[1]));
            return array_values(array_map(static fn(array $row): array => ['id_image'=>$row['id_image']], array_filter($this->imageRows, static fn(array $row): bool => $row['id_product']===(int)$product[1] && $row['id_shop']===(int)$shop[1] && in_array($row['id_image'],$approved,true))));
        }
        if (str_contains($sql, 'information_schema.TABLES')) return $this->evidenceInstalled ? [['present'=>1]] : [];
        if (str_contains($sql, '`native_test_kuraneacatalog_review`')) return str_contains($sql, 'id_shop = 1') && str_contains($sql, 'native_product_id = 14') ? $this->evidenceRows : [];
        if (str_contains($sql, '`native_test_employee_shop`')) return $this->employeeShop ? [['id_employee' => 1]] : [];
        if (str_contains($sql, '`native_test_employee`')) return [['id_employee' => 1, 'id_profile' => 2]];
        if (str_contains($sql, '`native_test_customer`')) return $this->customerActive && str_contains($sql, 'id_customer=1 AND id_shop=1') ? [['id_customer' => 1]] : [];
        if (str_contains($sql, '`native_test_product_attribute_combination`')) return [['iso_code' => 'ja', 'group_name' => '色', 'attribute_name' => '赤']];
        if (str_contains($sql, '`native_test_product_attribute`')) return str_contains($sql, 'pa.id_product=12 ') ? [['id_product_attribute' => 121, 'reference' => 'NATIVE-OPTION']] : [];
        if (str_contains($sql, '`native_test_product_lang`')) return [['iso_code' => 'ja', 'name' => '<b>Trusted native product</b>', 'description' => '<p>Native description</p>', 'description_short' => '', 'link_rewrite' => 'native']];
        if (str_contains($sql, '`native_test_category_product`')) return [['id_category' => 3, 'id_parent' => 2, 'iso_code' => 'ja', 'name' => '<b>Reviewed native category</b>']];
        if (str_contains($sql, '`native_test_product`')) {
            if (!str_contains($sql, 'ps.id_shop=1')) return [];
            if (str_contains($sql, 'p.id_product=11 ')) return [['id_product' => 11, 'reference' => 'NATIVE-PRIVATE']];
            if (str_contains($sql, 'p.id_product=12 ')) return [['id_product' => 12, 'reference' => 'NATIVE-VARIANTS']];
            if (str_contains($sql, 'p.id_product=14 ')) return [['id_product' => 14, 'reference' => 'OWA-IMPORT-reviewed']];
            if (str_contains($sql, 'p.id_product=13 ')) return [['id_product' => 13, 'reference' => 'OWA-IMPORT-unreviewed']];
            return [];
        }
        throw new RuntimeException('Unexpected native boundary query.');
    }
}

class NativeTestLink { public function getImageLink(string $slug, string $id, string $type): string { return 'https://native.example/img/' . $id . '.jpg'; } }
Context::$context = (object) ['link' => new NativeTestLink(), 'shop' => (object) ['id' => 1], 'customer' => new NativeTestSession(), 'employee' => new NativeTestSession()];
require dirname(__DIR__, 2) . '/modules/ordenowaprocurement/ordenowaprocurement.php';
require dirname(__DIR__, 2) . '/modules/kuraneabusinessprofile/autoload.php';

use Ordenowa\Procurement\Integration\Runtime;
use Ordenowa\Procurement\Integration\WorkspaceAccessPolicy;
use Ordenowa\Procurement\Security\Actor;
use Kuranea\BusinessProfile\Customer\CommerceGate;

function nativeAssert(bool $ok, string $message): void { if (!$ok) throw new RuntimeException($message); }
function nativeDenied(callable $operation, int $code): void
{
    try { $operation(); } catch (Throwable $error) { nativeAssert($error->getCode() === $code, 'Unexpected denial code: ' . $error->getMessage()); return; }
    throw new RuntimeException('Expected a server denial.');
}
function nativeRole(string $tab, string $permission): string { return 'ROLE_MOD_TAB_' . strtoupper($tab) . '_' . (['ADD' => 'CREATE', 'EDIT' => 'UPDATE'][$permission] ?? $permission); }

putenv('ORDENOWA_APP_MODE=procurement');
$module = new Ordenowaprocurement();
nativeAssert($module->install(), 'Native module installation must succeed.');
nativeAssert(count(Db::getInstance()->writes) >= 8, 'Install must create the dedicated transactional tables.');
foreach (Db::getInstance()->writes as $sql) {
    nativeAssert(str_starts_with($sql, 'CREATE TABLE IF NOT EXISTS `native_test_ordenowa_procurement_') && str_contains($sql, 'ENGINE=InnoDB'), 'Install is additive and domain-only.');
}
nativeAssert(count(Tab::$saved) === 5, 'Five native ACL-backed tabs must be installed.');
nativeAssert($module->ensureInfrastructure() && count(Tab::$saved) === 5, 'Install repair is idempotent.');
foreach (Tab::$saved as $labels) { nativeAssert(count($labels) === 3 && preg_match('/[가-힣]/u', implode('', $labels)) === 1, 'Every native admin locale receives Korean labels.'); }
Db::getInstance()->writes = [];

$_POST = ['id_customer' => '2', 'id_shop' => '99', 'permissions' => ['points.correct'], 'product' => ['names' => ['ja' => 'Forged']]];
$customer = Runtime::customerActor();
nativeAssert($customer->id === 1 && $customer->shopId === 1, 'Customer actor must derive only from native session and shop.');
Context::$context->customer->logged = false;
nativeDenied(fn () => Runtime::customerActor(), 403);
Context::$context->customer->logged = true;
Db::getInstance()->customerActive = false;
nativeDenied(fn () => Runtime::customerActor(), 404);
Db::getInstance()->customerActive = true;
nativeDenied(fn () => Runtime::validateCustomer(2), 404);
Shop::$context = 2;
nativeDenied(fn () => Runtime::customerActor(), 403);
Shop::$context = 1;

$pointsTab = 'AdminOrdenowaProcurementPoints';
Access::$roles[2] = [nativeRole($pointsTab, 'READ'), nativeRole($pointsTab, 'ADD')];
$employee = Runtime::employeeActor();
$employee->require('points.award');
nativeDenied(fn () => $employee->require('points.correct'), 403);
Db::getInstance()->employeeShop = false;
nativeDenied(fn () => Runtime::employeeActor(), 403);
Db::getInstance()->employeeShop = true;
Context::$context->employee->logged = false;
nativeDenied(fn () => Runtime::employeeActor(), 403);
Context::$context->employee->logged = true;
Access::$roles[2] = [nativeRole($pointsTab, 'ADD')];
nativeDenied(fn () => Runtime::employeeActor()->require('points.award'), 403);

$product = Runtime::productReference(11);
nativeAssert($product['names']['ja'] === 'Trusted native product' && $product['image_url'] === '', 'Product presentation must come from native rows and require explicit public image approval.');
nativeAssert($product['categories'][0]['names']['ja'] === 'Reviewed native category', 'Category labels must be shop-scoped and stripped of markup.');
nativeDenied(fn () => Runtime::productReference(999), 404);
nativeDenied(fn () => Runtime::productReference(11, 121), 422);
nativeDenied(fn () => Runtime::productReference(12, 0), 422);
nativeDenied(fn () => Runtime::productReference(12, 999), 422);
nativeAssert(str_contains(Runtime::productReference(12, 121)['names']['ja'], '色: 赤'), 'Variant label must be derived from the verified native combination.');
nativeAssert(Runtime::productReference(12, 121)['reference'] === 'NATIVE-OPTION', 'Exact validated variant must be frozen into snapshot.');
nativeDenied(fn () => Runtime::productReference(13), 422);
Access::$roles[2] = [nativeRole('AdminOrdenowaProcurement','READ'), nativeRole('AdminOrdenowaProcurement','ADD')];
$manualImage = Runtime::productReference(11, 0, ['image_ids' => [501], 'attestation' => 'SYNTHETIC own native photograph permission']);
nativeAssert($manualImage['image_url'] === '/img/p/5/0/1/501-home_default.jpg' && $manualImage['image_rights']['id_employee'] === 1, 'Explicit native rights attestation binds validated local image and native issuing employee.');
nativeDenied(fn () => Runtime::productReference(11, 0, ['image_ids' => [999], 'attestation' => 'SYNTHETIC permission']), 422);
$manualGallery = Runtime::productReference(11, 0, ['image_ids'=>[501,502], 'attestation'=>'SYNTHETIC operator-owned local image pair']);
nativeAssert($manualGallery['image_urls'] === ['/img/p/5/0/1/501-home_default.jpg','/img/p/5/0/2/502-home_default.jpg'] && $manualGallery['image_url'] === $manualGallery['image_urls'][0], 'Every explicitly approved local photo enters the bounded native gallery.');
require_once dirname(__DIR__,2) . '/modules/kuraneacatalog/autoload.php';
$sourceSnapshot = (new \Kuranea\Catalog\Parsing\AmazonJapanHtmlParser())->parse(file_get_contents(dirname(__DIR__) . '/catalog/fixtures/amazon-jp-review-single-option.synthetic.html'), 'https://www.amazon.co.jp/dp/B0KURANEA1');
$rightsEvidence = \Kuranea\Catalog\Domain\ProductImageRightsEvidence::record('licensed', 'SYNTHETIC offline local image rights fixture only', 'employee:1', new DateTimeImmutable('2026-10-29T00:00:00Z'), [701,702,703,705]);
$entry = (new \Kuranea\Catalog\Domain\ProductReviewQueueEntry($sourceSnapshot->deduplicationKey,'pending',$sourceSnapshot,new DateTimeImmutable()))->approve(14,'employee:1',new DateTimeImmutable('2026-10-29T00:00:00Z'),$rightsEvidence);
$reviewRow = \Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseRowMapper::review($entry);
Db::getInstance()->evidenceInstalled = true;
Db::getInstance()->evidenceRows = [['status'=>$reviewRow['status'],'native_product_id'=>14,'content_hash'=>$reviewRow['content_hash'],'payload_sha256'=>$reviewRow['hash'],'payload'=>$reviewRow['payload']]];
$licensedGallery = Runtime::productReference(14);
nativeAssert($licensedGallery['image_urls'] === ['/img/p/7/0/1/701-home_default.jpg','/img/p/7/0/2/702-home_default.jpg'], 'Reviewed gallery retains all licensed own-product/shop photos and excludes unlicensed, other-product and other-shop images.');
Db::getInstance()->evidenceInstalled = false;
Db::getInstance()->evidenceRows = [];

nativeDenied(fn () => Runtime::productReference(11, 0, ['image_ids' => [501], 'attestation' => '']), 422);
Access::$roles[2] = [nativeRole('AdminOrdenowaProcurement','READ')];
nativeDenied(fn () => Runtime::productReference(11, 0, ['image_ids' => [501], 'attestation' => 'SYNTHETIC permission']), 403);
nativeAssert(Db::getInstance()->writes === [], 'Native snapshots must not activate native retail products or write orders.');

class NativeAdminActionHarness extends \Ordenowa\Procurement\Integration\AdminController
{
    protected string $procurementTab = 'AdminOrdenowaProcurementPoints';
    public function __construct() {}
    protected function renderPage(Actor $actor): string { return ''; }
    public function action(Actor $actor): void { $this->processAction($actor); }
}
$admin = new NativeAdminActionHarness();
Access::$roles[2] = [nativeRole($pointsTab, 'READ')];
$_SERVER['REQUEST_METHOD'] = 'POST';
$_POST = ['procurement_action' => 'award', 'token' => Tools::getAdminTokenLite($pointsTab), 'id_request' => '1', 'amount' => '100', 'reason' => 'manual', 'idempotency_key' => 'test'];
nativeDenied(fn () => $admin->action(Runtime::employeeActor()), 403);
Access::$roles[2][] = nativeRole($pointsTab, 'ADD');
$_POST['token'] = 'forged';
nativeDenied(fn () => $admin->action(Runtime::employeeActor()), 403);
$_POST['token'] = Tools::getAdminTokenLite($pointsTab);
$_POST['procurement_action'] = 'correct';
nativeDenied(fn () => $admin->action(Runtime::employeeActor()), 403);
$_POST['procurement_action'] = 'assign';
nativeDenied(fn () => $admin->action(Runtime::employeeActor()), 403);
$_POST['procurement_action'] = 'award';
$_POST['amount'] = '1.2';
nativeDenied(fn () => $admin->action(Runtime::employeeActor()), 422);
$_POST['token'] = 'native-valid-previous-mask';
nativeDenied(fn () => $admin->action(Runtime::employeeActor()), 422);
nativeAssert(Db::getInstance()->writes === [], 'Denied native form actions must never reach domain writes.');

require dirname(__DIR__, 2) . '/modules/ordenowaprocurement/controllers/admin/AdminOrdenowaProcurementAuditController.php';
class NativeAuditRenderHarness extends AdminOrdenowaProcurementAuditController
{
    public object $context;
    public function __construct() { $this->context = Context::getContext(); }
    public function render(Actor $actor): string { return $this->renderPage($actor); }
}
$_GET = [];
Db::getInstance()->auditRows = [['id_activity' => 1,'actor_type' => 'customer','actor_id' => 1,'action' => 'support.message_created','target_type' => 'request','target_id' => 1,'created_at' => '2026-10-29 00:00:00']];
$delivery = ['id_notification' => 1,'status' => 'SENT','attempts' => 1,'last_error_code' => '', 'claimed_at' => '2026-10-29 00:00:00','sent_at' => '2026-10-29 00:00:01'];
Db::getInstance()->deliveryRows = [array_merge($delivery,['id_delivery'=>1,'channel'=>'mail']), array_merge($delivery,['id_delivery'=>2,'channel'=>'push'])];
$auditHtml = (new NativeAuditRenderHarness())->render(Actor::employee(1,1,['audit.read']));
nativeAssert(substr_count($auditHtml,'<td>이메일</td>') === 1 && substr_count($auditHtml,'<td>브라우저 Push</td>') === 1, 'Actual audit render distinguishes native mail and push channel identifiers.');
nativeAssert(str_contains($auditHtml,'발주 요청 문의 등록') && !str_contains($auditHtml,'support.message_created'), 'Actual audit render labels support messages in Korean.');
nativeAssert(Db::getInstance()->writes === [], 'Audit rendering remains read-only.');

nativeAssert(CommerceGate::isRegistrationEnabled(null, false), 'Procurement membership must not require seller, shipping or refund policy.');
nativeAssert(!CommerceGate::isEnabled(null, true) && !CommerceGate::isIsolatedCiCheckoutEnabled(), 'Procurement mode cannot activate seller checkout.');
foreach (['product', 'cart', 'order', 'addresses', 'order-return', 'pdf-invoice', 'getfile'] as $route) nativeAssert(WorkspaceAccessPolicy::deniesController($route), 'Legacy private retail route must deny.');
foreach (['authentication', 'registration', 'password', 'identity', 'contact', 'my-account'] as $route) nativeAssert(!WorkspaceAccessPolicy::deniesController($route), 'Native member/support route must remain available.');
putenv('ORDENOWA_APP_MODE=legacy_retail');
nativeAssert(!Runtime::procurementEnabled() && !CommerceGate::isRegistrationEnabled(null, false), 'Legacy gate behavior must remain explicit.');
nativeDenied(fn () => Runtime::customerActor(), 503);
putenv('ORDENOWA_APP_MODE');
nativeAssert(!Runtime::procurementEnabled(), 'Unset deployment mode must never implicitly expose procurement.');
echo "native_integration: PASS session, shop, product, variant, ACL, CSRF, install, audit labels and mode boundaries\n";
