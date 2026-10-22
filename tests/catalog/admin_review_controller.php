<?php

declare(strict_types=1);

final class CatalogAdminTestSmarty
{
    public array $assigned = [];

    public function assign(string $name, mixed $value): void
    {
        $this->assigned[$name] = $value;
    }
}

final class CatalogAdminTestLink
{
    public function getAdminLink(string $controller): string
    {
        return '/admin?controller=' . rawurlencode($controller);
    }
}

class ModuleAdminController
{
    public bool $bootstrap = false;
    public string $meta_title = '';
    public string $content = '';
    public array $tabAccess = ['view' => 1, 'edit' => 1, 'add' => 1];
    public object $context;

    public function __construct()
    {
        $this->context = (object) [
            'smarty' => new CatalogAdminTestSmarty(),
            'link' => new CatalogAdminTestLink(),
            'employee' => (object) ['id' => 42],
        ];
    }

    public function initContent(): void
    {
    }
}

final class Tools
{
    public static bool $submitted = false;
    /** @var array<string, mixed> */
    public static array $values = [];

    public static function isSubmit(string $name): bool
    {
        return self::$submitted && $name === 'submitKuraneaCatalogApprove';
    }

    public static function getValue(string $name, mixed $default = null): mixed
    {
        return self::$values[$name] ?? $default;
    }

    public static function getAdminTokenLite(string $controller): string
    {
        return 'synthetic-admin-token-' . $controller;
    }
}

function assertCatalogAdminSame(mixed $expected, mixed $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . '; expected ' . var_export($expected, true) . ', got ' . var_export($actual, true));
    }
}

function assertCatalogAdminTrue(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$catalogAdminRoot = sys_get_temp_dir() . '/kuranea-admin-contract-' . bin2hex(random_bytes(8));
$catalogAdminShopRoot = $catalogAdminRoot . '/public';
$catalogAdminStorage = $catalogAdminRoot . '/private';
if (!mkdir($catalogAdminShopRoot, 0700, true) || !mkdir($catalogAdminStorage, 0700)) {
    throw new RuntimeException('Could not create isolated catalog admin contract directories.');
}
if (!defined('_PS_ROOT_DIR_')) {
    define('_PS_ROOT_DIR_', $catalogAdminShopRoot);
}
putenv('KURANEA_CATALOG_QUEUE_DIR=' . $catalogAdminStorage);
putenv('KURANEA_CATALOG_TEST_DEMO_APPROVAL=0');

require_once __DIR__ . '/../../modules/kuraneacatalog/controllers/admin/AdminKuraneaCatalogReviewController.php';

$fixtureHtml = file_get_contents(__DIR__ . '/fixtures/amazon-jp-product.synthetic.html');
if ($fixtureHtml === false) {
    throw new RuntimeException('Could not read the synthetic catalog fixture for admin review tests.');
}
$catalogAdminSnapshot = (new \Kuranea\Catalog\Parsing\AmazonJapanHtmlParser())->parse(
    $fixtureHtml,
    'https://www.amazon.co.jp/dp/B0KURANEA1',
    new DateTimeImmutable('2026-10-22T12:30:00+00:00')
);
$catalogAdminQueue = \Kuranea\Catalog\Infrastructure\Persistence\CatalogQueueRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_);
$catalogAdminEntry = $catalogAdminQueue->enqueue($catalogAdminSnapshot);
$missingTokenEntry = $catalogAdminQueue->enqueue((new \Kuranea\Catalog\Parsing\AmazonJapanHtmlParser())->parse(
    $fixtureHtml,
    'https://www.amazon.co.jp/dp/B0KURANEA2',
    new DateTimeImmutable('2026-10-22T12:31:00+00:00')
));
$forgedTokenEntry = $catalogAdminQueue->enqueue((new \Kuranea\Catalog\Parsing\AmazonJapanHtmlParser())->parse(
    $fixtureHtml,
    'https://www.amazon.co.jp/dp/B0KURANEA3',
    new DateTimeImmutable('2026-10-22T12:32:00+00:00')
));

try {
    $_SERVER['REQUEST_METHOD'] = 'GET';
    Tools::$submitted = false;
    Tools::$values = [];
    $catalogAdminController = new AdminKuraneaCatalogReviewController();
    $catalogAdminController->initContent();
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, '[TEST FIXTURE] 合成キッチンツール A'), 'The Korean admin controller should render a pending synthetic snapshot.');
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, '아마존 일본'), 'The admin controller should localize Amazon Japan source names.');
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, 'amazon_jp:B0KURANEA1'), 'The source-qualified deduplication key should retain its provider identity.');
    $imageMetadataMatches = [];
    assertCatalogAdminTrue(
        preg_match('/<p><strong>이미지 메타데이터<\/strong><\/p><ul>(.*?)<\/ul>/s', $catalogAdminController->content, $imageMetadataMatches) === 1,
        'The review screen should render image metadata for the synthetic source fixture.'
    );
    $imageMetadataHtml = $imageMetadataMatches[1];
    assertCatalogAdminTrue(str_contains($imageMetadataHtml, '아마존 일본'), 'Image metadata should localize its source provider.');
    assertCatalogAdminTrue(!str_contains($imageMetadataHtml, 'amazon_jp'), 'Image metadata should use the Korean marketplace label instead of a provider slug.');
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, '중복 식별 키'), 'The admin review screen should expose the deduplication key.');
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, '출처 사이트 후기'), 'Source-site reviews should be distinguished from KURANEA customer reviews.');
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, 'ORDENOWA 고객 후기'), 'Imported source reviews should not be presented as ORDENOWA customer reviews.');
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, 'KURANEA_CATALOG_TEST_DEMO_APPROVAL') || str_contains($catalogAdminController->content, '비활성화'), 'The default-disabled TEST/DEMO guard should be visible.');

    $_SERVER['REQUEST_METHOD'] = 'POST';
    Tools::$submitted = true;
    Tools::$values = [
        'idempotency_key' => $catalogAdminEntry->idempotencyKey,
        'confirm_test_demo' => '1',
        'token' => Tools::getAdminTokenLite('AdminKuraneaCatalogReview'),
    ];
    CatalogNativeRegistrarLockTestState::$events = [];
    $disabledPostController = new AdminKuraneaCatalogReviewController();
    $disabledPostController->initContent();
    assertCatalogAdminTrue(str_contains($disabledPostController->content, '서버 설정에서 비활성화'), 'A POST must not register when the deployment approval gate is disabled.');
    assertCatalogAdminSame([], CatalogNativeRegistrarLockTestState::$events, 'A disabled approval gate must not touch native product or database registration.');
    assertCatalogAdminSame('pending', $catalogAdminQueue->find($catalogAdminEntry->idempotencyKey)?->status, 'A disabled approval gate must leave the queue item pending.');

    putenv('KURANEA_CATALOG_TEST_DEMO_APPROVAL=1');
    Tools::$values['confirm_test_demo'] = '0';
    $unconfirmedPostController = new AdminKuraneaCatalogReviewController();
    $unconfirmedPostController->initContent();
    assertCatalogAdminTrue(str_contains($unconfirmedPostController->content, '명시 확인이 필요합니다'), 'An enabled deployment gate still requires explicit TEST/DEMO confirmation.');
    assertCatalogAdminTrue(str_contains($unconfirmedPostController->content, 'name="token"') && str_contains($unconfirmedPostController->content, 'name="confirm_test_demo"'), 'The approval form should include the PrestaShop admin token and explicit TEST/DEMO checkbox.');
    assertCatalogAdminSame([], CatalogNativeRegistrarLockTestState::$events, 'An unconfirmed request must not invoke native product registration.');

    CatalogNativeRegistrarLockTestState::$events = [];
    Tools::$values = [
        'idempotency_key' => $missingTokenEntry->idempotencyKey,
        'confirm_test_demo' => '1',
    ];
    $missingTokenController = new AdminKuraneaCatalogReviewController();
    $missingTokenController->initContent();
    assertCatalogAdminTrue(str_contains($missingTokenController->content, '관리자 보안 토큰'), 'A missing admin token should be rejected explicitly.');
    assertCatalogAdminSame([], CatalogNativeRegistrarLockTestState::$events, 'A missing admin token must not invoke native product registration.');
    assertCatalogAdminSame('pending', $catalogAdminQueue->find($missingTokenEntry->idempotencyKey)?->status, 'A missing admin token must leave its item pending.');

    Tools::$values = [
        'idempotency_key' => $forgedTokenEntry->idempotencyKey,
        'confirm_test_demo' => '1',
        'token' => 'forged-token',
    ];
    $forgedTokenController = new AdminKuraneaCatalogReviewController();
    $forgedTokenController->initContent();
    assertCatalogAdminTrue(str_contains($forgedTokenController->content, '관리자 보안 토큰'), 'A forged admin token should be rejected explicitly.');
    assertCatalogAdminSame([], CatalogNativeRegistrarLockTestState::$events, 'A forged admin token must not invoke native product registration.');
    assertCatalogAdminSame('pending', $catalogAdminQueue->find($forgedTokenEntry->idempotencyKey)?->status, 'A forged admin token must leave its item pending.');

    Tools::$values['confirm_test_demo'] = '1';
    Tools::$values['token'] = Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
    $noAddController = new AdminKuraneaCatalogReviewController();
    $noAddController->tabAccess = ['view' => 1, 'edit' => 1, 'add' => 0];
    $noAddController->initContent();
    assertCatalogAdminTrue(str_contains($noAddController->content, '승인할 권한이 없습니다'), 'An employee without add permission must not approve a catalog item.');
    assertCatalogAdminSame([], CatalogNativeRegistrarLockTestState::$events, 'Missing add permission must not invoke native product registration.');
    assertCatalogAdminSame('pending', $catalogAdminQueue->find($forgedTokenEntry->idempotencyKey)?->status, 'Missing add permission must leave the item pending.');

    $readOnlyController = new AdminKuraneaCatalogReviewController();
    $readOnlyController->tabAccess = ['view' => 1, 'edit' => 0, 'add' => 1];
    $readOnlyController->initContent();
    assertCatalogAdminTrue(str_contains($readOnlyController->content, '승인할 권한이 없습니다'), 'An employee without edit access must not approve a catalog item.');
    assertCatalogAdminSame([], CatalogNativeRegistrarLockTestState::$events, 'A read-only employee must not invoke native product registration.');

    Db::$lockResult = 1;
    Db::$releaseResult = 1;
    Product::$existingProductId = 0;
    Product::$addSucceeds = true;
    CatalogNativeRegistrarLockTestState::$events = [];
    Tools::$values['idempotency_key'] = $catalogAdminEntry->idempotencyKey;
    Tools::$values['token'] = Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
    $approvedPostController = new AdminKuraneaCatalogReviewController();
    $approvedPostController->initContent();
    $approvedEntry = $catalogAdminQueue->find($catalogAdminEntry->idempotencyKey);
    assertCatalogAdminSame('approved', $approvedEntry?->status, 'A confirmed TEST/DEMO request should use the approval service and persist the approval.');
    assertCatalogAdminSame(1234, $approvedEntry?->nativeProductId, 'The simulated PrestaShop adapter product identity should be recorded.');
    assertCatalogAdminSame('employee:42', $approvedEntry?->approvedBy, 'The reviewer identity should come from the authenticated employee context.');
    assertCatalogAdminTrue(in_array('product.add', CatalogNativeRegistrarLockTestState::$events, true), 'A confirmed request should delegate to the native registrar adapter.');
    assertCatalogAdminTrue(str_contains($approvedPostController->content, 'TEST/DEMO 상품 ID 1234'), 'The screen should show the TEST/DEMO approval result.');
} finally {
    foreach (glob($catalogAdminStorage . '/*') ?: [] as $catalogAdminFile) {
        unlink($catalogAdminFile);
    }
    rmdir($catalogAdminStorage);
    rmdir($catalogAdminShopRoot);
    rmdir($catalogAdminRoot);
    putenv('KURANEA_CATALOG_QUEUE_DIR');
    putenv('KURANEA_CATALOG_TEST_DEMO_APPROVAL');
}

echo "PASS: offline Korean catalog admin review and guarded TEST/DEMO approval checks\n";
