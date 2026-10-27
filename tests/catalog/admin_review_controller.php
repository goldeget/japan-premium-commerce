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
    public array $tabAccess = [];
    /** @var list<string> */
    public array $accessCalls = [];
    /** @var array<string, int> */
    public array $defaultAccess = ['view' => 1, 'edit' => 1, 'add' => 1];
    /** @var list<mixed> */
    public array $mediaModes = [];
    /** @var list<string> */
    public array $scripts = [];
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

    // Match the public PrestaShop 9.2 AdminController signature so incompatible overrides fail here.
    public function setMedia($isNewTheme = false)
    {
        $this->mediaModes[] = $isNewTheme;
    }

    public function addJS($path): void
    {
        $this->scripts[] = (string) $path;
    }

    public function access(string $action): bool
    {
        $this->accessCalls[] = $action;
        if (!array_key_exists($action, $this->tabAccess)) {
            $this->tabAccess[$action] = $this->defaultAccess[$action] ?? 0;
        }

        return !empty($this->tabAccess[$action]);
    }

    public function viewAccess(): bool
    {
        return $this->access('view');
    }
}

final class Tools
{
    public static bool $submitted = false;
    public static string $submittedAction = 'submitKuraneaCatalogApprove';
    /** @var array<string, mixed> */
    public static array $values = [];

    public static function isSubmit(string $name): bool
    {
        return self::$submitted && $name === self::$submittedAction;
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

final class CatalogAdminTestCsrfTokenManager
{
    public static ?string $acceptedRequestToken = null;

    public function isTokenValid(): bool
    {
        $submittedToken = Tools::getValue('token');

        return self::$acceptedRequestToken !== null
            && is_string($submittedToken)
            && hash_equals(self::$acceptedRequestToken, $submittedToken);
    }
}

final class CatalogAdminTestContainer
{
    public function get(string $serviceId): ?object
    {
        if ($serviceId !== 'PrestaShopBundle\\Security\\Admin\\UserTokenManager') {
            return null;
        }

        return new CatalogAdminTestCsrfTokenManager();
    }
}

final class CatalogAdminTestSymfonyContainer
{
    public static bool $available = true;
    private static ?CatalogAdminTestContainer $instance = null;

    public static function getInstance(): ?CatalogAdminTestContainer
    {
        if (!self::$available) {
            return null;
        }

        return self::$instance ??= new CatalogAdminTestContainer();
    }
}

class_alias(
    CatalogAdminTestSymfonyContainer::class,
    'PrestaShop\\PrestaShop\\Adapter\\SymfonyContainer'
);

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
if (!defined('__PS_BASE_URI__')) {
    define('__PS_BASE_URI__', '/');
}
putenv('KURANEA_CATALOG_QUEUE_DIR=' . $catalogAdminStorage);
putenv('CI=true');
putenv('GITHUB_ACTIONS=true');
putenv('KURANEA_ISOLATED_CI=1');
putenv('KURANEA_CATALOG_STORAGE_ADAPTER=json');
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
    $mediaController = new AdminKuraneaCatalogReviewController();
    $mediaController->setMedia(true);
    assertCatalogAdminSame([true], $mediaController->mediaModes, 'The review controller should forward the inherited theme mode to the PrestaShop 9.2 media setup.');
    assertCatalogAdminSame(
        ['/modules/kuraneacatalog/views/js/catalog-import-image-preview.js'],
        $mediaController->scripts,
        'The review controller should add its image preview script after the native media setup.'
    );

    $catalogAdminController = new AdminKuraneaCatalogReviewController();
    $catalogAdminController->initContent();
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, 'id="product_urls"'), 'The authorized import form should render when PrestaShop lazily resolves tab access.');
    foreach (['view', 'edit', 'add'] as $permission) {
        assertCatalogAdminTrue(in_array($permission, $catalogAdminController->accessCalls, true), 'The review controller should ask PrestaShop for the ' . $permission . ' grant.');
    }
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, '[TEST FIXTURE] 合成キッチンツール A'), 'The Korean admin controller should render a pending synthetic snapshot.');
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, '아마존 일본'), 'The admin controller should localize Amazon Japan source names.');
    assertCatalogAdminTrue(str_contains($catalogAdminController->content, 'amazon_jp:B0KURANEA1'), 'The source-qualified deduplication key should retain its provider identity.');
    $imageMetadataMatches = [];
    assertCatalogAdminTrue(
        preg_match('/<p><strong>출처 이미지 메타데이터<\/strong>[^<]*<\/p><ul>(.*?)<\/ul>/s', $catalogAdminController->content, $imageMetadataMatches) === 1,
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
    Tools::$submittedAction = 'submitKuraneaCatalogImportBatch';
    $unsupportedUrl = 'https://example.invalid/not-a-supported-product';
    Tools::$values = [
        'product_urls' => $unsupportedUrl,
        'token' => Tools::getAdminTokenLite('AdminKuraneaCatalogReview'),
    ];
    CatalogAdminTestCsrfTokenManager::$acceptedRequestToken = Tools::$values['token'];
    $unsupportedUrlController = new AdminKuraneaCatalogReviewController();
    $unsupportedUrlController->initContent();
    assertCatalogAdminTrue(
        str_contains($unsupportedUrlController->content, '상품 URL을 등록할 수 없습니다. 아마존 일본 또는 라쿠텐의 지원 상품 주소를 1~10개 입력해 주세요.'),
        'An unsupported URL should display the fixed Korean validation message.'
    );
    assertCatalogAdminTrue(!str_contains($unsupportedUrlController->content, 'not a supported marketplace product URL'), 'An unsupported URL must not expose the exception message.');
    assertCatalogAdminTrue(!str_contains($unsupportedUrlController->content, $unsupportedUrl), 'An unsupported URL must not be reflected into the response.');
    assertCatalogAdminTrue(!str_contains($unsupportedUrlController->content, 'id="catalog-import-progress"'), 'An unsupported URL must not create or render a batch.');

    $urlInputError = '상품 URL을 등록할 수 없습니다. 아마존 일본 또는 라쿠텐의 지원 상품 주소를 1~10개 입력해 주세요.';
    $invalidUrlInputs = [
        ['value' => '', 'label' => 'An empty URL list should display safe Korean validation feedback.'],
        [
            'value' => implode("\n", array_fill(0, 11, 'https://www.amazon.co.jp/dp/B0KURANEA1')),
            'label' => 'More than ten URLs should display safe Korean validation feedback.',
        ],
    ];
    foreach ($invalidUrlInputs as $invalidUrlInput) {
        Tools::$values = [
            'product_urls' => $invalidUrlInput['value'],
            'token' => Tools::getAdminTokenLite('AdminKuraneaCatalogReview'),
        ];
        CatalogAdminTestCsrfTokenManager::$acceptedRequestToken = Tools::$values['token'];
        $invalidUrlController = new AdminKuraneaCatalogReviewController();
        $invalidUrlController->initContent();
        assertCatalogAdminTrue(str_contains($invalidUrlController->content, $urlInputError), $invalidUrlInput['label']);
        assertCatalogAdminTrue(
            !str_contains($invalidUrlController->content, 'A catalog import batch must contain between one and ten URLs.'),
            'A URL count exception must not be exposed to the admin screen.'
        );
        assertCatalogAdminTrue(
            !str_contains($invalidUrlController->content, 'id="catalog-import-progress"'),
            'Invalid URL input must not render an imported batch.'
        );
    }
    Tools::$submittedAction = 'submitKuraneaCatalogApprove';

    Tools::$values = [
        'idempotency_key' => $catalogAdminEntry->idempotencyKey,
        'confirm_test_demo' => '1',
        'token' => Tools::getAdminTokenLite('AdminKuraneaCatalogReview'),
    ];
    CatalogAdminTestCsrfTokenManager::$acceptedRequestToken = Tools::$values['token'];
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
    CatalogAdminTestCsrfTokenManager::$acceptedRequestToken = Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
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
    CatalogAdminTestCsrfTokenManager::$acceptedRequestToken = Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
    $forgedTokenController = new AdminKuraneaCatalogReviewController();
    $forgedTokenController->initContent();
    assertCatalogAdminTrue(str_contains($forgedTokenController->content, '관리자 보안 토큰'), 'A forged admin token should be rejected explicitly.');
    assertCatalogAdminSame([], CatalogNativeRegistrarLockTestState::$events, 'A forged admin token must not invoke native product registration.');
    assertCatalogAdminSame('pending', $catalogAdminQueue->find($forgedTokenEntry->idempotencyKey)?->status, 'A forged admin token must leave its item pending.');

    // The CSRF manager validates the issued form token against session state,
    // even though regenerating the representation on this request differs.
    $formCsrfToken = 'mask-a.valid-session-token';
    $nextRequestCsrfToken = 'mask-b.valid-session-token';
    assertCatalogAdminTrue($formCsrfToken !== $nextRequestCsrfToken, 'The request and regenerated CSRF token representations should differ.');
    assertCatalogAdminTrue(
        $formCsrfToken !== Tools::getAdminTokenLite('AdminKuraneaCatalogReview'),
        'A valid masked form token should not be compared to a newly generated token string.'
    );
    Tools::$values['confirm_test_demo'] = '1';
    Tools::$values['token'] = $formCsrfToken;
    CatalogAdminTestCsrfTokenManager::$acceptedRequestToken = $formCsrfToken;
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
    assertCatalogAdminTrue(str_contains($readOnlyController->content, '상품 수집 작업은 편집·등록 권한이 있는 직원만 수행할 수 있습니다.'), 'A view-only employee should receive the read-only catalog message.');
    assertCatalogAdminTrue(!str_contains($readOnlyController->content, 'id="product_urls"'), 'A view-only employee must not receive the batch import form.');
    assertCatalogAdminSame([], CatalogNativeRegistrarLockTestState::$events, 'A read-only employee must not invoke native product registration.');

    $noViewController = new AdminKuraneaCatalogReviewController();
    $noViewController->tabAccess = ['view' => 0, 'edit' => 1, 'add' => 1];
    $noViewController->initContent();
    assertCatalogAdminTrue(str_contains($noViewController->content, '상품 검수 대기열을 조회할 권한이 없습니다.'), 'An employee without view access must be denied the catalog queue.');
    assertCatalogAdminTrue(!str_contains($noViewController->content, 'id="product_urls"'), 'An employee without view access must not receive the batch import form.');

    Db::$lockResult = 1;
    Db::$releaseResult = 1;
    Product::$existingProductId = 0;
    Product::$addSucceeds = true;
    CatalogNativeRegistrarLockTestState::$events = [];
    Tools::$values['idempotency_key'] = $catalogAdminEntry->idempotencyKey;
    Tools::$values['token'] = Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
    CatalogAdminTestCsrfTokenManager::$acceptedRequestToken = Tools::$values['token'];
    $approvedPostController = new AdminKuraneaCatalogReviewController();
    $approvedPostController->initContent();
    $approvedEntry = $catalogAdminQueue->find($catalogAdminEntry->idempotencyKey);
    assertCatalogAdminSame('approved', $approvedEntry?->status, 'A confirmed TEST/DEMO request should use the approval service and persist the approval.');
    assertCatalogAdminSame(1234, $approvedEntry?->nativeProductId, 'The simulated PrestaShop adapter product identity should be recorded.');
    assertCatalogAdminSame('employee:42', $approvedEntry?->approvedBy, 'The reviewer identity should come from the authenticated employee context.');
    assertCatalogAdminTrue(in_array('product.add', CatalogNativeRegistrarLockTestState::$events, true), 'A confirmed request should delegate to the native registrar adapter.');
    assertCatalogAdminTrue(str_contains($approvedPostController->content, 'TEST/DEMO 상품 ID 1234'), 'The screen should show the TEST/DEMO approval result.');

    $historyBatch = \Kuranea\Catalog\Infrastructure\Persistence\CatalogImportBatchRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_)->create(
        ['https://www.amazon.co.jp/dp/B0KURANEA6?private=must-not-render'],
        new DateTimeImmutable('2026-10-24T12:00:00+00:00')
    );
    $historyRejectedSnapshot = (new \Kuranea\Catalog\Parsing\AmazonJapanHtmlParser())->parse(
        $fixtureHtml,
        'https://www.amazon.co.jp/dp/B0KURANEA7',
        new DateTimeImmutable('2026-10-24T12:01:00+00:00')
    );
    $historyRejectedEntry = $catalogAdminQueue->enqueue($historyRejectedSnapshot);
    $catalogAdminQueue->rejectIfPending(
        $historyRejectedEntry->idempotencyKey,
        $historyRejectedEntry->snapshot->contentHash,
        'employee:42',
        new DateTimeImmutable('2026-10-24T12:02:00+00:00'),
        '합성 <script>검수</script> 반려 사유'
    );

    $_SERVER['REQUEST_METHOD'] = 'GET';
    Tools::$submitted = false;
    Tools::$values = [];
    $batchFilePath = $catalogAdminStorage . '/catalog-import-batches.json';
    $reviewFilePath = $catalogAdminStorage . '/review-queue.json';
    $batchesBeforeFreshGet = file_get_contents($batchFilePath);
    $reviewsBeforeFreshGet = file_get_contents($reviewFilePath);
    $historyController = new AdminKuraneaCatalogReviewController();
    $historyController->initContent();
    assertCatalogAdminTrue(str_contains($historyController->content, 'id="catalog-import-history"'), 'A fresh GET should render bounded catalog batch and review history.');
    assertCatalogAdminTrue(str_contains($historyController->content, '최근 상품 수집'), 'Batch history should have a Korean heading.');
    assertCatalogAdminTrue(str_contains($historyController->content, '최근 검수 처리'), 'Review history should have a Korean heading.');
    assertCatalogAdminTrue(str_contains($historyController->content, '승인 완료') && str_contains($historyController->content, '반려 완료'), 'Fresh review history should rediscover both terminal decisions.');
    assertCatalogAdminTrue(str_contains($historyController->content, '합성 &lt;script&gt;검수&lt;/script&gt; 반려 사유'), 'Fresh review history should rediscover the escaped rejection reason.');
    assertCatalogAdminTrue(!str_contains($historyController->content, '<script>검수</script>'), 'History must escape staff-supplied rejection text.');
    assertCatalogAdminTrue(str_contains($historyController->content, 'catalog_batch_id=' . $historyBatch->id), 'The batch history link should reopen a batch using its validated identity.');
    assertCatalogAdminTrue(!str_contains($historyController->content, 'https://www.amazon.co.jp/dp/B0KURANEA6'), 'History must not render submitted product URLs.');
    assertCatalogAdminSame($batchesBeforeFreshGet, file_get_contents($batchFilePath), 'Reading fresh history must not mutate batch storage.');
    assertCatalogAdminSame($reviewsBeforeFreshGet, file_get_contents($reviewFilePath), 'Reading fresh history must not mutate review decisions.');

    Tools::$values = ['catalog_batch_id' => $historyBatch->id];
    $reopenedBatchController = new AdminKuraneaCatalogReviewController();
    $reopenedBatchController->initContent();
    assertCatalogAdminTrue(str_contains($reopenedBatchController->content, 'data-batch-id="' . $historyBatch->id . '"'), 'A batch history link should reopen its persisted progress.');
    assertCatalogAdminTrue(str_contains($reopenedBatchController->content, 'id="catalog-import-next"'), 'An authorized employee should be able to continue a reopened batch with an explicit action.');
    assertCatalogAdminTrue(!str_contains($reopenedBatchController->content, 'f.requestSubmit(button)'), 'Reopening batch history on GET must not auto-submit queued work.');
    assertCatalogAdminSame($batchesBeforeFreshGet, file_get_contents($batchFilePath), 'Reopening batch history on GET must not mutate batch state.');

    $historyReadOnlyController = new AdminKuraneaCatalogReviewController();
    $historyReadOnlyController->tabAccess = ['view' => 1, 'edit' => 0, 'add' => 0];
    $historyReadOnlyController->initContent();
    assertCatalogAdminTrue(str_contains($historyReadOnlyController->content, 'id="catalog-import-history"'), 'A view-only employee should be able to inspect read-only history.');
    assertCatalogAdminTrue(!str_contains($historyReadOnlyController->content, 'id="product_urls"'), 'Read-only history must not grant catalog mutation controls.');
    assertCatalogAdminTrue(!str_contains($historyReadOnlyController->content, 'id="catalog-import-next"'), 'Read-only history must not expose progress mutation controls.');

    $historyNoViewController = new AdminKuraneaCatalogReviewController();
    $historyNoViewController->tabAccess = ['view' => 0, 'edit' => 1, 'add' => 1];
    $historyNoViewController->initContent();
    assertCatalogAdminTrue(!str_contains($historyNoViewController->content, 'id="catalog-import-history"'), 'An employee without view permission must not receive import or decision history.');

    CatalogAdminTestCsrfTokenManager::$acceptedRequestToken = $formCsrfToken;
    CatalogAdminTestSymfonyContainer::$available = false;
    $_SERVER['REQUEST_METHOD'] = 'POST';
    Tools::$submitted = true;
    Tools::$submittedAction = 'submitKuraneaCatalogApprove';
    Tools::$values = [
        'idempotency_key' => $missingTokenEntry->idempotencyKey,
        'confirm_test_demo' => '1',
        'token' => $formCsrfToken,
    ];
    CatalogNativeRegistrarLockTestState::$events = [];
    $missingCsrfServiceController = new AdminKuraneaCatalogReviewController();
    $missingCsrfServiceController->initContent();
    assertCatalogAdminTrue(str_contains($missingCsrfServiceController->content, '관리자 보안 토큰'), 'A missing PrestaShop CSRF service must fail closed.');
    assertCatalogAdminSame([], CatalogNativeRegistrarLockTestState::$events, 'A missing CSRF service must not invoke native product registration.');
    assertCatalogAdminSame('pending', $catalogAdminQueue->find($missingTokenEntry->idempotencyKey)?->status, 'A missing CSRF service must leave the review item pending.');
    CatalogAdminTestSymfonyContainer::$available = true;
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
