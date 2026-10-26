<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/autoload.php';

use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogQueueRepositoryFactory;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogImportBatchRepositoryFactory;
use Kuranea\Catalog\Domain\CatalogImportBatch;
use Kuranea\Catalog\Domain\CatalogImportBatchItem;
use Kuranea\Catalog\Domain\ProductAdminDraft;
use Kuranea\Catalog\Domain\ProductImageRightsEvidence;
use Kuranea\Catalog\Domain\ProductImportReviewEvidence;
use Kuranea\Catalog\Fetching\BoundedSystemResolver;
use Kuranea\Catalog\Fetching\CurlTransport;
use Kuranea\Catalog\Fetching\PublicProductFetcher;
use Kuranea\Catalog\Integration\PrestaShopNativeProductManager;
use Kuranea\Catalog\Integration\PrestaShopNativeProductRegistrar;
use Kuranea\Catalog\Service\CatalogImportService;
use Kuranea\Catalog\Service\ProductApprovalService;

class AdminKuraneaCatalogReviewController extends ModuleAdminController
{
    private string $feedback = '';
    private bool $feedbackIsError = false;
    private ?CatalogImportBatch $activeBatch = null;
    private ?ProductReviewQueueEntry $reviewedEntry = null;

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '상품 검수 대기열';
    }

    public function setMedia()
    {
        parent::setMedia();
        $this->addJS(__PS_BASE_URI__ . 'modules/kuraneacatalog/views/js/catalog-import-image-preview.js');
    }

    public function initHeader()
    {
        $koreanLanguageId = (int) Language::getIdByIso('ko', true);
        if ($koreanLanguageId > 0) {
            // PrestaShop 9's legacy Back Office header reads its document
            // language from Context::language while the header is initialized.
            $this->context->language = new Language($koreanLanguageId);
        }

        parent::initHeader();
    }

    public function initContent(): void
    {
        if (!$this->canView()) {
            http_response_code(403);
            $this->content = '<div class="alert alert-danger">상품 검수 대기열을 조회할 권한이 없습니다.</div>';
            $this->context->smarty->assign('content', $this->content);

            return;
        }

        parent::initContent();

        try {
            $queue = CatalogQueueRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_);
            $batchRepository = CatalogImportBatchRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_);
            $this->processImportRequests($queue, $batchRepository);
            $this->processApproval($queue);
            $pending = $queue->pending();
            $this->content .= $this->renderFeedback();
            $this->content .= $this->renderImportForm();
            $this->activeBatch ??= $this->loadRequestedBatch($batchRepository);
            $this->content .= $this->renderBatch($batchRepository);
            $this->content .= $this->renderQueue($pending, new PrestaShopNativeProductManager());
        } catch (Throwable) {
            http_response_code(503);
            $this->content .= '<div class="alert alert-danger">검수 대기열을 불러오지 못했습니다. 저장소 설정을 확인해 주세요.</div>';
        }

        $this->context->smarty->assign('content', $this->content);
    }

    private function processImportRequests(
        \Kuranea\Catalog\Domain\ProductReviewQueueRepositoryInterface $queue,
        \Kuranea\Catalog\Domain\CatalogImportBatchRepositoryInterface $batches
    ): void {
        if (strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? '')) !== 'POST') {
            return;
        }

        if (Tools::isSubmit('submitKuraneaCatalogImportBatch')) {
            if (!$this->validateImportMutation()) {
                return;
            }
            $raw = Tools::getValue('product_urls', '');
            if (!is_string($raw)) {
                $this->fail('상품 URL을 한 줄에 하나씩 입력해 주세요.');
                return;
            }
            $urls = array_values(array_filter(array_map('trim', preg_split('/\R/u', $raw) ?: []), static fn (string $url): bool => $url !== ''));
            try {
                $this->activeBatch = $batches->create($urls);
                $this->succeed(sprintf('%d개 고유 상품 URL을 수집 대기열에 추가했습니다.', count($this->activeBatch->items)));
            } catch (\InvalidArgumentException) {
                $this->fail('상품 URL을 등록할 수 없습니다. Amazon Japan 또는 Rakuten의 지원 상품 주소를 1~10개 입력해 주세요.');
            } catch (Throwable) {
                $this->fail('상품 URL 일괄 등록을 저장하지 못했습니다. URL과 저장 공간을 확인해 주세요.');
            }

            return;
        }

        if (Tools::isSubmit('submitKuraneaCatalogImportNext')) {
            if (!$this->validateImportMutation()) {
                return;
            }
            $batchId = trim((string) Tools::getValue('catalog_batch_id', ''));
            try {
                $this->activeBatch = $this->catalogImportService($queue, $batches)->processNext($batchId);
                $counts = $this->activeBatch->counts();
                $this->succeed(sprintf(
                    '수집 진행: 성공 %d건, 실패 %d건, 대기 %d건입니다.',
                    $counts['succeeded'],
                    $counts['failed'],
                    $counts['queued']
                ));
            } catch (Throwable) {
                $this->fail('상품 수집 단계가 완료되지 않았습니다. 배치 상태를 다시 확인해 주세요.');
                $this->activeBatch = $this->loadBatch($batches, $batchId);
            }

            return;
        }

        if (Tools::isSubmit('submitKuraneaCatalogImportRetry')) {
            if (!$this->validateImportMutation()) {
                return;
            }
            $batchId = trim((string) Tools::getValue('catalog_batch_id', ''));
            try {
                $service = $this->catalogImportService($queue, $batches);
                $currentBatch = $service->findBatch($batchId);
                if ($currentBatch === null) {
                    throw new \InvalidArgumentException('Catalog import batch was not found.');
                }
                $hasRetryableItems = false;
                foreach ($currentBatch->items as $item) {
                    if ($item->status === CatalogImportBatchItem::STATUS_FAILED
                        && $item->attempts < CatalogImportBatchItem::MAX_ATTEMPTS) {
                        $hasRetryableItems = true;
                        break;
                    }
                }
                if (!$hasRetryableItems) {
                    $this->activeBatch = $currentBatch;
                    $this->fail('재시도 가능한 실패 항목이 없습니다. 실패 사유와 시도 횟수를 확인해 주세요.');
                    return;
                }
                $this->activeBatch = $service->retryFailedItems($batchId);
                $this->succeed('실패한 상품만 재시도 대기열에 넣었습니다. 성공 항목은 유지했습니다.');
            } catch (Throwable) {
                $this->fail('실패 항목을 재시도 대기열에 넣지 못했습니다. 배치 상태를 확인해 주세요.');
                $this->activeBatch = $this->loadBatch($batches, $batchId);
            }

            return;
        }

        if (Tools::isSubmit('submitKuraneaCatalogReject')) {
            if (!$this->validateImportMutation()) {
                return;
            }
            $key = trim((string) Tools::getValue('idempotency_key', ''));
            $hash = trim((string) Tools::getValue('content_hash', ''));
            $reason = trim((string) Tools::getValue('rejection_reason', ''));
            try {
                $rejected = $queue->rejectIfPending(
                    $key,
                    $hash,
                    'employee:' . (int) ($this->context->employee->id ?? 0),
                    new \DateTimeImmutable('now', new \DateTimeZone('UTC')),
                    $reason
                );
                if ($rejected === null) {
                    $this->fail('검수 대상이 변경되었거나 이미 처리되었습니다. 최신 내용을 다시 확인해 주세요.');
                } else {
                    $this->reviewedEntry = $rejected;
                    $this->succeed('상품 수집 항목을 반려했습니다. 사유와 담당자 기록을 보존했습니다.');
                }
            } catch (Throwable) {
                $this->fail('반려 사유를 저장하지 못했습니다. 사유를 확인하고 다시 시도해 주세요.');
            }

            return;
        }

        if (Tools::isSubmit('submitKuraneaCatalogImportedDraft')) {
            $this->processImportedDraft($queue);
        }
    }

    private function processImportedDraft(\Kuranea\Catalog\Domain\ProductReviewQueueRepositoryInterface $queue): void
    {
        if (!$this->validateImportMutation()) {
            return;
        }
        $key = trim((string) Tools::getValue('idempotency_key', ''));
        $hash = trim((string) Tools::getValue('content_hash', ''));
        $entry = $queue->find($key);
        if ($entry === null || $entry->status !== ProductReviewQueueEntry::STATUS_PENDING
            || !hash_equals($entry->snapshot->contentHash, $hash)) {
            $this->fail('검수 내용이 갱신되었습니다. 새 출처 정보를 확인한 뒤 다시 등록해 주세요.');
            return;
        }

        $uploads = $this->normalizedImportUploads();
        $uploadCount = count(array_filter($uploads, static fn (array $upload): bool => ($upload['error'] ?? UPLOAD_ERR_NO_FILE) === UPLOAD_ERR_OK));
        $imageRightsBasis = (string) Tools::getValue('image_rights_basis', '');
        $imageRightsReference = trim((string) Tools::getValue('image_rights_reference', ''));
        if (!$this->validateImageRightsInputs(
            $uploads,
            $imageRightsBasis,
            $imageRightsReference,
            $entry->linkedProductId !== null
        )) {
            $this->fail('이미지 파일, 사용권 근거, 확인 참조를 먼저 검토해 주세요.');
            return;
        }

        if (count($entry->snapshot->options) > 1) {
            $this->fail('현재 수집기는 여러 옵션 그룹의 실제 조합·조합별 가격·재고를 검증할 수 없어 이 상품 초안 등록을 지원하지 않습니다. 원본에서 확인된 단일 옵션 그룹만 사용해 주세요.');
            return;
        }

        if ($entry->linkedProductId !== null) {
            if ($uploadCount > 0) {
                $this->fail('기존 초안에 이 화면에서 이미지를 추가하지 않습니다. 관리자 상품 화면에서 검토해 주세요.');
                return;
            }
            if (Tools::getValue('confirm_keep_existing_draft') !== '1') {
                $this->fail('기존 초안을 유지할지 확인해 주세요. 새로 수집한 출처 변경은 초안에 자동 반영하지 않습니다.');
                return;
            }
            if (Tools::getValue('translation_reviewed_en') !== '1' || Tools::getValue('translation_reviewed_ko') !== '1') {
                $this->fail('최신 출처 정보와 함께 기존 영어·한국어 상품 내용을 다시 검수해 주세요.');
                return;
            }
            if ($entry->snapshot->options !== [] && Tools::getValue('confirm_options_supported') !== '1') {
                $this->fail('최신 출처 옵션과 기존 상품 옵션의 연결을 다시 확인해 주세요.');
                return;
            }
            try {
                $manager = new PrestaShopNativeProductManager();
                $editorData = $manager->editorData($entry->linkedProductId);
                $imageIds = $manager->imageIds($entry->linkedProductId);
                $imageRights = $entry->imageRightsEvidence;
                if ($imageIds !== [] && Tools::getValue('confirm_existing_image_rights') === '1') {
                    $imageRights = ProductImageRightsEvidence::record(
                        $imageRightsBasis,
                        $imageRightsReference,
                        'employee:' . (int) ($this->context->employee->id ?? 0),
                        new \DateTimeImmutable('now', new \DateTimeZone('UTC')),
                        $imageIds
                    );
                }
                if (!$this->imageIdsMatchEvidence($imageIds, $imageRights)) {
                    $this->fail('기존 이미지가 사용권 검수를 받지 않았거나 검수 기록과 달라 출처 변경을 승인하지 않았습니다. 이미지를 검토하고 기록을 확인해 주세요.');
                    return;
                }
                $previousEvidence = $entry->importReviewEvidence;
                $taxRulesGroupId = (int) ($editorData['tax_rules_group_id'] ?? -1);
                $taxTreatment = $taxRulesGroupId === 0 ? 'explicitly_exempt' : 'taxable';
                $taxEvidenceReference = trim((string) Tools::getValue(
                    'tax_evidence_reference',
                    $previousEvidence?->taxEvidenceReference ?? ''
                ));
                if ($taxRulesGroupId === 0 && trim((string) $taxEvidenceReference) === '') {
                    $this->fail('기존 초안의 세금 규칙이 면세 미할당 상태지만 유효한 면세 근거가 없습니다. 근거를 확인하고 다시 검수해 주세요.');
                    return;
                }
                $combinationQuantities = $editorData['combination_quantities'] ?? null;
                if (!is_array($combinationQuantities)) {
                    $this->fail('기존 초안의 옵션별 재고를 다시 확인하지 못했습니다.');
                    return;
                }
                $stockValues = array_values(array_unique(array_map('intval', $combinationQuantities)));
                if (count($stockValues) > 1) {
                    $this->fail('기존 초안의 옵션별 재고가 서로 달라 하나의 수집 검수 기록으로 표현할 수 없습니다. 옵션별 검수를 완료한 뒤 다시 시도해 주세요.');
                    return;
                }
                $ownStock = $stockValues[0] ?? (int) ($editorData['quantity'] ?? -1);
                $categoryIds = array_values(array_unique(array_map('intval', $editorData['category_ids'] ?? [])));
                if ($taxRulesGroupId < 0 || (int) ($editorData['price_jpy'] ?? 0) < 1
                    || $ownStock < 0 || $categoryIds === []) {
                    $this->fail('기존 비활성 초안의 가격·세금·재고·카테고리 readback이 불완전합니다.');
                    return;
                }
                $importReviewEvidence = new ProductImportReviewEvidence(
                    (int) $editorData['price_jpy'],
                    $taxRulesGroupId,
                    $taxTreatment,
                    $taxEvidenceReference,
                    $ownStock,
                    $categoryIds,
                    $entry->snapshot->options === [] || Tools::getValue('confirm_options_supported') === '1',
                    ['en', 'ko'],
                    $entry->snapshot->contentHash
                );
                $linked = $queue->linkDraftIfCurrent(
                    $entry->idempotencyKey,
                    $entry->snapshot->contentHash,
                    $entry->linkedProductId,
                    $imageRights,
                    $importReviewEvidence
                );
                if ($linked === null || $linked->importReviewEvidence?->sourceContentHash !== $entry->snapshot->contentHash) {
                    throw new \RuntimeException('The current source revision was not linked to fresh product review evidence.');
                }
                $approved = $queue->approveIfPending(
                    $entry->idempotencyKey,
                    $linked->snapshot->contentHash,
                    $entry->linkedProductId,
                    'employee:' . (int) ($this->context->employee->id ?? 0),
                    new \DateTimeImmutable('now', new \DateTimeZone('UTC')),
                    $imageRights,
                    $importReviewEvidence
                );
                if ($approved === null) {
                    throw new \RuntimeException('The source changed while its existing draft was reviewed.');
                }
                $this->reviewedEntry = $approved;
                $this->succeed(sprintf('출처 변경을 검토했습니다. 기존 비활성 초안 ID %d와 관리자 편집값·판매가격·재고를 유지했습니다.', $entry->linkedProductId));
            } catch (Throwable) {
                $this->fail('기존 비활성 초안을 확인하거나 출처 변경을 검수하지 못했습니다. 상품 관리 화면에서 상태를 확인해 주세요.');
            }

            return;
        }

        if ($entry->snapshot->options !== [] && Tools::getValue('confirm_options_supported') !== '1') {
            $this->fail('표시한 옵션 값으로 생성될 모든 상품 조합이 실제 판매 옵션과 일치하는지 확인해 주세요.');
            return;
        }
        foreach (['name_ja', 'name_en', 'name_ko'] as $nameField) {
            if (trim((string) Tools::getValue($nameField, '')) === '') {
                $this->fail('일본어·영어·한국어 상품명을 모두 검수해 입력해 주세요.');
                return;
            }
        }
        if (Tools::getValue('translation_reviewed_en') !== '1' || Tools::getValue('translation_reviewed_ko') !== '1') {
            $this->fail('영어·한국어 상품명과 상세정보의 번역 검수 여부를 각각 확인해 주세요.');
            return;
        }
        if ($entry->snapshot->description !== null
            && (trim((string) Tools::getValue('description_en', '')) === ''
                || trim((string) Tools::getValue('description_ko', '')) === '')) {
            $this->fail('출처 상세 설명이 있어 영어·한국어 설명을 검수 입력해야 초안으로 저장할 수 있습니다.');
            return;
        }
        $rawTaxGroupId = Tools::getValue('tax_rules_group_id', null);
        $taxTreatment = (string) Tools::getValue('tax_treatment', '');
        $taxEvidenceReference = trim((string) Tools::getValue('tax_evidence_reference', ''));
        if ((string) $rawTaxGroupId === '0'
            && ($taxTreatment !== 'explicitly_exempt' || $taxEvidenceReference === '')) {
            $this->fail('세금 규칙 미할당을 선택하려면 상품·판매자 세무 근거와 승인 참조를 기록해야 합니다.');
            return;
        }
        if ((string) $rawTaxGroupId !== '0' && $taxTreatment !== 'taxable') {
            $this->fail('세금 규칙 그룹과 세무 분류 확인을 함께 선택해 주세요.');
            return;
        }

        try {
            $draft = ProductAdminDraft::fromArray([
                'name_ja' => Tools::getValue('name_ja', ''),
                'name_en' => Tools::getValue('name_en', ''),
                'name_ko' => Tools::getValue('name_ko', ''),
                'price_jpy' => Tools::getValue('sale_price_jpy', ''),
                'tax_rules_group_id' => Tools::getValue('tax_rules_group_id', null),
                'quantity' => Tools::getValue('own_quantity', ''),
                'category_ids' => Tools::getValue('category_ids', []),
                'description_ja' => Tools::getValue('description_ja', ''),
                'description_en' => Tools::getValue('description_en', ''),
                'description_ko' => Tools::getValue('description_ko', ''),
                'options' => Tools::getValue('options', ''),
            ]);
            if ($draft->priceJpy === $entry->snapshot->priceJpy
                && Tools::getValue('confirm_same_source_price') !== '1') {
                $this->fail('출처 참고 가격과 같은 판매가격을 사용하려면 별도 가격 확인을 선택해 주세요.');
                return;
            }
            $manager = new PrestaShopNativeProductManager();
            $result = $manager->saveImportedDraftWithResult($entry->idempotencyKey, $draft, $uploads);
            $imageRights = null;
            $imageIds = $manager->imageIds($result->productId);
            if ($result->created) {
                if ($uploadCount > 0) {
                    if (count($imageIds) !== $uploadCount) {
                        throw new \RuntimeException('Imported native image count does not match the locally reviewed upload count.');
                    }
                    $imageRights = ProductImageRightsEvidence::record(
                        $imageRightsBasis,
                        $imageRightsReference,
                        'employee:' . (int) ($this->context->employee->id ?? 0),
                        new \DateTimeImmutable('now', new \DateTimeZone('UTC')),
                        $imageIds
                    );
                } elseif ($imageIds !== []) {
                    $this->fail('새 초안에 이미지가 연결되었지만 검수 기록을 만들 입력이 없어 승인을 보류했습니다.');
                    return;
                }
            } elseif ($uploadCount > 0) {
                $this->fail('기존 초안에는 이번 업로드가 적용되지 않았습니다. 이미지를 확인하고 별도 검수 기록을 저장하기 전까지 승인을 보류했습니다.');
                return;
            } elseif (!$this->imageIdsMatchEvidence($imageIds, $entry->imageRightsEvidence)) {
                $this->fail('기존 이미지가 사용권 검수를 받지 않아 승인을 보류했습니다. 기존 초안의 이미지와 검수 기록을 확인해 주세요.');
                return;
            }
            if (!$this->imageIdsMatchEvidence($imageIds, $imageRights ?? $entry->imageRightsEvidence)) {
                $this->fail('현재 초안 이미지와 저장된 사용권 검수 기록이 일치하지 않아 승인을 보류했습니다.');
                return;
            }
            $taxRulesGroupId = (int) Tools::getValue('tax_rules_group_id', -1);
            $importReviewEvidence = new ProductImportReviewEvidence(
                $draft->priceJpy,
                $taxRulesGroupId,
                $taxTreatment,
                $taxEvidenceReference === '' ? null : $taxEvidenceReference,
                $draft->quantity,
                $draft->categoryIds,
                $entry->snapshot->options === [] || Tools::getValue('confirm_options_supported') === '1',
                ['en', 'ko'],
                $entry->snapshot->contentHash
            );
            $linked = $queue->linkDraftIfCurrent(
                $entry->idempotencyKey,
                $entry->snapshot->contentHash,
                $result->productId,
                $imageRights,
                $importReviewEvidence
            );
            if ($linked === null) {
                // Keep the inactive product and its local image evidence
                // recoverable if a newer source observation won the save race.
                $latest = $queue->find($entry->idempotencyKey);
                if ($latest !== null) {
                    $linked = $queue->linkDraftIfCurrent(
                        $entry->idempotencyKey,
                        $latest->snapshot->contentHash,
                        $result->productId,
                        $imageRights,
                        null
                    );
                }
            }
            if ($linked === null) {
                throw new \RuntimeException('The native draft could not be linked to its current review entry.');
            }
            if ($linked->snapshot->contentHash !== $entry->snapshot->contentHash
                || $linked->status !== ProductReviewQueueEntry::STATUS_PENDING) {
                $this->fail('출처 정보가 저장 중 변경됐거나 검수 상태가 달라졌습니다. 비활성 초안 연결과 이미지 검수 기록은 보존했으며 최신 항목을 다시 확인해 주세요.');
                return;
            }
            $approvedAt = new \DateTimeImmutable('now', new \DateTimeZone('UTC'));
            $approved = $queue->approveIfPending(
                $entry->idempotencyKey,
                $linked->snapshot->contentHash,
                $result->productId,
                'employee:' . (int) ($this->context->employee->id ?? 0),
                $approvedAt,
                $imageRights,
                $importReviewEvidence
            );
            if ($approved === null) {
                throw new \RuntimeException('The source snapshot changed before its native draft link was saved.');
            }
            $this->reviewedEntry = $approved;
            $this->succeed(sprintf(
                '%s 비활성 상품 초안 ID %d를 저장했습니다. 실제 판매는 별도 승인 전까지 활성화되지 않습니다.',
                $result->created ? '새' : '기존',
                $result->productId
            ));
        } catch (\InvalidArgumentException $exception) {
            $this->fail($exception->getMessage());
        } catch (Throwable) {
            $this->fail('비활성 상품 초안을 저장하지 못했습니다. 가격·세금·카테고리·옵션·이미지 입력을 확인해 주세요.');
        }
    }

    private function validateImportMutation(): bool
    {
        if (!$this->isValidImportMutationToken()) {
            $this->fail('관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.');
            return false;
        }
        if (!$this->canApprove() || (int) ($this->context->employee->id ?? 0) < 1) {
            $this->fail('상품 수집·검수·등록 권한이 없습니다.');
            return false;
        }

        return true;
    }

    private function isValidImportMutationToken(): bool
    {
        try {
            $container = \PrestaShop\PrestaShop\Adapter\SymfonyContainer::getInstance();
            if ($container === null) {
                return false;
            }

            $tokenManager = $container->get(\PrestaShopBundle\Security\Admin\UserTokenManager::class);

            return is_object($tokenManager)
                && method_exists($tokenManager, 'isTokenValid')
                && $tokenManager->isTokenValid() === true;
        } catch (Throwable) {
            return false;
        }
    }

    private function catalogImportService(
        \Kuranea\Catalog\Domain\ProductReviewQueueRepositoryInterface $queue,
        \Kuranea\Catalog\Domain\CatalogImportBatchRepositoryInterface $batches
    ): CatalogImportService {
        if ($this->isIsolatedCatalogCi() && !$this->isRunScopedCatalogFixtureMode()) {
            throw new \RuntimeException('Isolated catalog import requires the run-scoped fixture adapter.');
        }

        $fetcher = null;
        if (getenv('KURANEA_CATALOG_IMPORT_FIXTURE_MODE') === '1') {
            if (!$this->isRunScopedCatalogFixtureMode()) {
                throw new \RuntimeException('Catalog fixture mode requires the matching isolated GitHub Actions project.');
            }
            require_once '/tmp/ordenowa-ci-catalog-import-fixture-fetcher.php';
            if (!class_exists('ORDENOWACatalogImportFixtureFetcher')) {
                throw new \RuntimeException('The isolated catalog fixture adapter is missing.');
            }
            $fetcher = new \ORDENOWACatalogImportFixtureFetcher();
        } else {
            $fetcher = new PublicProductFetcher(new BoundedSystemResolver(), new CurlTransport());
        }

        return new CatalogImportService($batches, $queue, $fetcher);
    }

    /** @param list<array{name:string,tmp_name:string,size:int,error:int}> $uploads */
    private function validateImageRightsInputs(
        array $uploads,
        string $basis,
        string $reference,
        bool $allowExistingImageReview = false
    ): bool
    {
        if (count($uploads) > ProductImageRightsEvidence::MAX_IMAGE_IDS) {
            return false;
        }

        $uploadCount = 0;
        foreach ($uploads as $upload) {
            $error = $upload['error'] ?? UPLOAD_ERR_NO_FILE;
            if ($error === UPLOAD_ERR_NO_FILE) {
                continue;
            }
            if ($error !== UPLOAD_ERR_OK) {
                return false;
            }
            ++$uploadCount;
        }

        if ($uploadCount === 0) {
            if ($basis === '' && $reference === '') {
                return true;
            }
            if (!$allowExistingImageReview || Tools::getValue('confirm_existing_image_rights') !== '1') {
                return false;
            }
            $supportedBases = ['seller_owned', 'licensed', 'public_domain', 'explicit_permission'];
            $isSyntheticFixture = $basis === ProductImageRightsEvidence::BASIS_SYNTHETIC_CI_FIXTURE;
            return (($isSyntheticFixture && $this->isRunScopedCatalogFixtureMode())
                    || (!$isSyntheticFixture && in_array($basis, $supportedBases, true)))
                && trim($reference) !== ''
                && strlen($reference) <= ProductImageRightsEvidence::MAX_REFERENCE_LENGTH
                && preg_match('/[\x00-\x1f\x7f]/', $reference) !== 1;
        }

        $supportedBases = ['seller_owned', 'licensed', 'public_domain', 'explicit_permission'];
        $isSyntheticFixture = $basis === ProductImageRightsEvidence::BASIS_SYNTHETIC_CI_FIXTURE;
        if (Tools::getValue('confirm_image_rights') !== '1'
            || (!$isSyntheticFixture && !in_array($basis, $supportedBases, true))
            || ($isSyntheticFixture && !$this->isRunScopedCatalogFixtureMode())
            || trim($reference) === ''
            || strlen($reference) > ProductImageRightsEvidence::MAX_REFERENCE_LENGTH
            || preg_match('/[\x00-\x1f\x7f]/', $reference) === 1) {
            return false;
        }

        return true;
    }

    private function isIsolatedCatalogCi(): bool
    {
        return getenv('CI') === 'true'
            && getenv('GITHUB_ACTIONS') === 'true'
            && getenv('KURANEA_ISOLATED_CI') === '1';
    }

    private function isRunScopedCatalogFixtureMode(): bool
    {
        if (!$this->isIsolatedCatalogCi() || getenv('KURANEA_CATALOG_IMPORT_FIXTURE_MODE') !== '1') {
            return false;
        }

        $runId = trim((string) getenv('GITHUB_RUN_ID'));
        $attempt = trim((string) getenv('GITHUB_RUN_ATTEMPT'));
        $domainRunId = trim((string) getenv('KURANEA_CI_RUN_ID'));
        $domainAttempt = trim((string) getenv('KURANEA_CI_RUN_ATTEMPT'));
        $project = trim((string) getenv('KURANEA_CI_PROJECT_NAME'));

        return preg_match('/\A[0-9]+\z/D', $domainRunId) === 1
            && preg_match('/\A[0-9]+\z/D', $domainAttempt) === 1
            && $domainRunId === $runId
            && $domainAttempt === $attempt
            && preg_match('/\A[0-9]+\z/D', $runId) === 1
            && preg_match('/\A[0-9]+\z/D', $attempt) === 1
            && $project === 'kuranea-ci-' . $runId . '-' . $attempt
            && is_file('/tmp/ordenowa-ci-catalog-import-fixture-fetcher.php');
    }

    /** @return list<array{name:string,tmp_name:string,size:int,error:int}> */
    private function normalizedImportUploads(): array
    {
        $files = $_FILES['import_product_images'] ?? null;
        if (!is_array($files) || !is_array($files['name'] ?? null)) {
            return [];
        }

        $uploads = [];
        foreach ($files['name'] as $index => $name) {
            $uploads[] = [
                'name' => (string) $name,
                'tmp_name' => (string) ($files['tmp_name'][$index] ?? ''),
                'size' => (int) ($files['size'][$index] ?? 0),
                'error' => (int) ($files['error'][$index] ?? UPLOAD_ERR_NO_FILE),
            ];
        }

        return $uploads;
    }

    private function loadRequestedBatch(\Kuranea\Catalog\Domain\CatalogImportBatchRepositoryInterface $batches): ?CatalogImportBatch
    {
        return $this->loadBatch($batches, trim((string) Tools::getValue('catalog_batch_id', '')));
    }

    private function loadBatch(\Kuranea\Catalog\Domain\CatalogImportBatchRepositoryInterface $batches, string $batchId): ?CatalogImportBatch
    {
        return preg_match('/\A[a-f0-9]{32}\z/', $batchId) === 1 ? $batches->find($batchId) : null;
    }

    private function processApproval(\Kuranea\Catalog\Domain\ProductReviewQueueRepositoryInterface $queue): void
    {
        if (strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? '')) !== 'POST'
            || !Tools::isSubmit('submitKuraneaCatalogApprove')) {
            return;
        }

        if (!$this->isValidImportMutationToken()) {
            $this->fail('관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.');
            return;
        }

        if (!$this->canApprove() || (int) ($this->context->employee->id ?? 0) < 1) {
            $this->fail('상품을 승인할 권한이 없습니다.');
            return;
        }
        if (getenv('KURANEA_CATALOG_TEST_DEMO_APPROVAL') !== '1') {
            $this->fail('TEST/DEMO 상품 등록 기능이 서버 설정에서 비활성화되어 있습니다.');
            return;
        }

        $employeeId = (int) ($this->context->employee->id ?? 0);
        $idempotencyKey = trim((string) Tools::getValue('idempotency_key', ''));
        if ($employeeId < 1 || $idempotencyKey === '' || Tools::getValue('confirm_test_demo') !== '1') {
            $this->fail('직원 로그인, 대기 항목 및 TEST/DEMO 명시 확인이 필요합니다.');
            return;
        }

        try {
            $service = new ProductApprovalService($queue, new PrestaShopNativeProductRegistrar());
            $approved = $service->approve(
                $idempotencyKey,
                'employee:' . $employeeId,
                null,
                true
            );
            $this->reviewedEntry = $approved;
            $this->succeed(sprintf('TEST/DEMO 상품 ID %d를 검수 기록에 연결했습니다.', (int) $approved->nativeProductId));
        } catch (Throwable) {
            $this->fail('상품 승인에 실패했습니다. 대기 항목과 서버의 PrestaShop 설정을 확인해 주세요.');
        }
    }

    private function renderImportForm(): string
    {
        $action = (string) $this->context->link->getAdminLink('AdminKuraneaCatalogReview');
        $token = (string) Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
        $html = '<section class="panel"><h3>Amazon Japan·Rakuten 상품 URL 수집</h3>'
            . '<p>공개 상품 페이지 URL을 한 줄에 하나씩 입력합니다. HTTPS 상품 경로만 허용하며 최대 10개를 한 번에 처리합니다. 로그인·CAPTCHA·접근 제한은 우회하지 않습니다.</p>'
            . '<p>수집 가격은 출처 참고값이며 실제 판매가격이 아닙니다. 출처 재고는 ORDENOWA 재고와 별도입니다.</p>';
        if (!$this->canApprove()) {
            return $html . '<p class="alert alert-info">상품 수집 작업은 편집·등록 권한이 있는 직원만 수행할 수 있습니다.</p></section>';
        }
        $html .= '<form method="post" action="' . $this->escape($action) . '">'
            . '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
            . '<div class="form-group"><label for="product_urls">상품 URL 일괄 입력</label>'
            . '<textarea class="form-control" id="product_urls" name="product_urls" rows="5" maxlength="22000" required></textarea>'
            . '<p class="help-block">지원: https://www.amazon.co.jp/dp/ASIN 및 https://item.rakuten.co.jp/판매점/상품코드/</p></div>'
            . '<button class="btn btn-primary" type="submit" name="submitKuraneaCatalogImportBatch" value="1">수집 대기열 만들기</button></form></section>';

        return $html;
    }

    private function renderBatch(\Kuranea\Catalog\Domain\CatalogImportBatchRepositoryInterface $batches): string
    {
        if ($this->activeBatch === null) {
            return '';
        }
        $action = (string) $this->context->link->getAdminLink('AdminKuraneaCatalogReview');
        $token = (string) Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
        $counts = $this->activeBatch->counts();
        $completed = $counts['succeeded'] + $counts['failed'];
        $total = count($this->activeBatch->items);
        $autoAdvance = $counts['queued'] > 0 && $this->canApprove();
        $hasRetryableItems = false;
        foreach ($this->activeBatch->items as $item) {
            if ($item->status === CatalogImportBatchItem::STATUS_FAILED
                && $item->attempts < CatalogImportBatchItem::MAX_ATTEMPTS) {
                $hasRetryableItems = true;
                break;
            }
        }
        $html = '<section class="panel" id="catalog-import-progress" data-batch-id="' . $this->escape($this->activeBatch->id) . '">'
            . '<h3>상품 수집 진행</h3><p>전체 ' . $total . '건 · 완료 ' . $completed . '건 · 성공 ' . $counts['succeeded']
            . '건 · 실패 ' . $counts['failed'] . '건 · 대기 ' . $counts['queued'] . '건</p>'
            . '<progress max="' . $total . '" value="' . $completed . '">' . $completed . '/' . $total . '</progress>'
            . '<table class="table"><thead><tr><th>판매처</th><th>출처 상품 ID</th><th>상태</th><th>결과</th></tr></thead><tbody>';
        foreach ($this->activeBatch->items as $item) {
            $html .= '<tr><td>' . $this->escape($this->sourceLabel($item->provider)) . '</td><td>'
                . $this->escape($item->sourceProductId) . '</td><td>' . $this->escape($this->batchStatusLabel($item->status)) . '</td><td>';
            if ($item->failureMessage() !== null) {
                $html .= '<span class="text-danger">' . $this->escape($item->failureMessage()) . '</span>';
            } elseif ($item->status === CatalogImportBatchItem::STATUS_SUCCEEDED) {
                $html .= '검수 대기열에 저장 · 조회 ' . $this->escape($item->snapshot?->fetchedAt->format(DATE_ATOM) ?? '미기재');
            } else {
                $html .= $item->status === CatalogImportBatchItem::STATUS_PROCESSING ? '처리 중' : '대기';
            }
            $html .= '</td></tr>';
        }
        $html .= '</tbody></table>';
        if ($autoAdvance) {
            $html .= '<form id="catalog-import-next" method="post" action="' . $this->escape($action) . '">'
                . '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
                . '<input type="hidden" name="catalog_batch_id" value="' . $this->escape($this->activeBatch->id) . '">'
                . '<button class="btn btn-primary" type="submit" name="submitKuraneaCatalogImportNext" value="1">다음 상품 수집</button></form>'
                . '<script>window.setTimeout(function(){var f=document.getElementById("catalog-import-next");var button=f?f.querySelector(\'button[name="submitKuraneaCatalogImportNext"]\'):null;if(f&&button){f.requestSubmit(button);}},150);</script>';
        }
        if ($hasRetryableItems && $this->canApprove()) {
            $html .= '<form method="post" action="' . $this->escape($action) . '">'
                . '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
                . '<input type="hidden" name="catalog_batch_id" value="' . $this->escape($this->activeBatch->id) . '">'
                . '<button class="btn btn-default" type="submit" name="submitKuraneaCatalogImportRetry" value="1">실패 항목만 재시도</button></form>';
        }

        return $html . '</section>';
    }

    /** @param list<int> $imageIds */
    private function imageIdsMatchEvidence(array $imageIds, ?ProductImageRightsEvidence $evidence): bool
    {
        $recordedImageIds = $evidence?->imageIds ?? [];
        if (!array_is_list($imageIds) || !array_is_list($recordedImageIds)) {
            return false;
        }
        foreach ($imageIds as $imageId) {
            if (!is_int($imageId) || $imageId < 1) {
                return false;
            }
        }
        foreach ($recordedImageIds as $imageId) {
            if (!is_int($imageId) || $imageId < 1) {
                return false;
            }
        }

        sort($imageIds, SORT_NUMERIC);
        sort($recordedImageIds, SORT_NUMERIC);

        return $imageIds === $recordedImageIds;
    }

    /** @param list<ProductReviewQueueEntry> $pending */
    private function renderQueue(array $pending, PrestaShopNativeProductManager $manager): string
    {
        $actionUrl = (string) $this->context->link->getAdminLink('AdminKuraneaCatalogReview');
        $token = (string) Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
        $approvalEnabled = getenv('KURANEA_CATALOG_TEST_DEMO_APPROVAL') === '1';
        $html = '<section class="panel"><h3>검수 대기 상품</h3>'
            . '<p>출처 정보와 운영용 상품 초안은 분리됩니다. 실제 판매가격·세금 그룹·카테고리·자체 재고를 직원이 직접 검수해야 초안이 저장됩니다. 모든 신규 초안은 비활성·비노출·주문 불가입니다.</p>';
        if (!$approvalEnabled) {
            $html .= '<div class="alert alert-info">기존 TEST/DEMO 등록 경로는 별도 서버 게이트로 비활성화되어 있습니다. 운영용 초안은 아래 검수 폼을 사용합니다.</div>';
        }
        $html .= $this->renderReviewedStatus();
        if ($pending === []) {
            return $html . '<p>검수 대기 항목이 없습니다.</p></section>';
        }
        $categories = [];
        $taxRulesGroups = [];
        try { $categories = $manager->categories(); } catch (Throwable) {}
        try { $taxRulesGroups = $manager->taxRulesGroups(); } catch (Throwable) {}

        foreach ($pending as $entry) {
            $snapshot = $entry->snapshot;
            $html .= '<article class="panel" data-catalog-key="' . $this->escape($entry->idempotencyKey) . '"><h4>' . $this->escape($snapshot->name) . '</h4>';
            $html .= '<dl><dt>출처</dt><dd>' . $this->escape($this->sourceLabel($snapshot->source)) . '</dd>';
            $html .= '<dt>출처 상품 ID</dt><dd>' . $this->escape($snapshot->sourceProductId) . '</dd>';
            $html .= '<dt>출처 URL</dt><dd><code>' . $this->escape($snapshot->sourceUrl) . '</code></dd>';
            $html .= '<dt>브랜드</dt><dd>' . $this->escape($snapshot->brand ?? '미수집') . '</dd>';
            $html .= '<dt>출처 가격(참고값)</dt><dd>' . number_format($snapshot->priceJpy) . ' ' . $this->escape($snapshot->currency)
                . ' · 판매가격으로 자동 사용하지 않음</dd>';
            $html .= '<dt>출처 재고 상태</dt><dd>' . $this->escape($this->availabilityLabel($snapshot->availability)) . ' · 자체 재고와 별도</dd>';
            $html .= '<dt>출처 카테고리</dt><dd>' . $this->escape($snapshot->categories === [] ? '미수집' : implode(' / ', $snapshot->categories)) . '</dd>';
            $html .= '<dt>수집 시각</dt><dd>' . $this->escape($snapshot->fetchedAt->format(DATE_ATOM)) . '</dd>';
            $html .= '<dt>검수 언어</dt><dd>일본어 원문 · 영어/한국어 번역 검수 필요</dd>';
            $html .= '<dt>중복 식별 키</dt><dd><code>' . $this->escape($entry->idempotencyKey) . '</code></dd></dl>';
            if ($entry->previousSnapshot !== null) {
                $html .= $this->renderSourceChanges($entry->previousSnapshot, $snapshot);
            }
            if ($snapshot->description !== null) {
                $html .= '<p><strong>출처 상세 설명</strong><br>' . nl2br($this->escape($snapshot->description), false) . '</p>';
            } else {
                $html .= '<p><strong>출처 상세 설명</strong>: 미수집</p>';
            }
            if ($snapshot->options !== []) {
                $optionText = [];
                foreach ($snapshot->options as $option) {
                    $optionText[] = $option->name . ': ' . implode(', ', $option->values);
                }
                $html .= '<p><strong>출처 옵션</strong>: ' . $this->escape(implode(' / ', $optionText)) . '</p>';
            } else {
                $html .= '<p><strong>출처 옵션</strong>: 미수집</p>';
            }
            if ($snapshot->images !== []) {
                $html .= '<p><strong>출처 이미지 메타데이터</strong> · 파일 다운로드 전 · 사용권 미확인</p><ul>';
                foreach ($snapshot->images as $image) {
                    $html .= '<li>' . $this->escape($image->altText === '' ? '대체 설명 미수집' : $image->altText)
                        . ' · ' . $this->escape($this->sourceLabel($image->source)) . ' · <code>' . $this->escape($image->url) . '</code></li>';
                }
                $html .= '</ul>';
            } else {
                $html .= '<p><strong>출처 이미지</strong>: 미수집</p>';
            }
            if ($snapshot->sourceRating !== null || $snapshot->sourceReviewCount !== null || $snapshot->reviews !== []) {
                $html .= '<p class="text-muted">출처 사이트 평점·후기 참고정보이며 ORDENOWA 고객 후기가 아닙니다. 평점 '
                    . $this->escape((string) ($snapshot->sourceRating ?? '미수집')) . ', 후기 수 '
                    . $this->escape((string) ($snapshot->sourceReviewCount ?? '미수집')) . '</p>';
            }
            if ($snapshot->reviews !== []) {
                $html .= '<ul class="list-unstyled">';
                foreach ($snapshot->reviews as $review) {
                    $reviewLabel = $review->origin === 'source_site' ? '출처 사이트 후기' : '별도 출처 검수 정보';
                    $html .= '<li class="well"><strong>' . $reviewLabel . ' · ' . $this->escape($this->sourceLabel($review->provider)) . '</strong>';
                    if ($review->author !== null) $html .= ' · ' . $this->escape($review->author);
                    if ($review->rating !== null) $html .= ' · ' . $this->escape((string) $review->rating) . '/5';
                    if ($review->body !== null) $html .= '<p>' . nl2br($this->escape($review->body), false) . '</p>';
                    $html .= '<small>ORDENOWA 구매후기 등록: 불가</small></li>';
                }
                $html .= '</ul>';
            }

            if ($entry->linkedProductId !== null) {
                $productManagerUrl = $this->productManagerUrl((int) $entry->linkedProductId);
                $html .= '<p class="alert alert-warning">기존 비활성 초안 ID ' . (int) $entry->linkedProductId
                    . '가 연결되어 있습니다. 재수집 내용은 초안에 자동 적용되지 않으며 판매가격·재고·관리자 편집값은 유지됩니다. '
                    . '<a href="' . $this->escape($productManagerUrl) . '">기존 초안 열기</a></p>';
                if ($this->canApprove()) {
                    $html .= $this->renderLinkedDraftReviewForm($entry, $manager, $actionUrl, $token);
                }
            } elseif ($this->canApprove()) {
                $html .= $this->renderImportedDraftForm($entry, $categories, $taxRulesGroups, $actionUrl, $token);
            }

            if ($this->canApprove()) {
                $html .= '<form method="post" action="' . $this->escape($actionUrl) . '" class="catalog-review-reject">'
                    . $this->hiddenReviewFields($entry, $token)
                    . '<label for="reject-' . $this->escape(substr(hash('sha256', $entry->idempotencyKey), 0, 12)) . '">반려 사유</label>'
                    . '<input class="form-control" id="reject-' . $this->escape(substr(hash('sha256', $entry->idempotencyKey), 0, 12))
                    . '" name="rejection_reason" type="text" maxlength="2000" required> '
                    . '<button class="btn btn-default" type="submit" name="submitKuraneaCatalogReject" value="1">반려</button></form>';
            }

            if ($this->canApprove() && $approvalEnabled) {
                $html .= '<form method="post" action="' . $this->escape($actionUrl) . '">'
                    . '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
                    . '<input type="hidden" name="idempotency_key" value="' . $this->escape($entry->idempotencyKey) . '">'
                    . '<label><input type="checkbox" name="confirm_test_demo" value="1" required> 합성 TEST/DEMO 상품으로 등록함을 확인합니다.</label> '
                    . '<button class="btn btn-default" type="submit" name="submitKuraneaCatalogApprove" value="1">별도 TEST/DEMO 경로 사용</button>'
                    . '</form>';
            }
            $html .= '</article>';
        }

        return $html . '</section>';
    }

    private function renderLinkedDraftReviewForm(
        ProductReviewQueueEntry $entry,
        PrestaShopNativeProductManager $manager,
        string $actionUrl,
        string $token
    ): string {
        if (count($entry->snapshot->options) > 1) {
            return '<div class="alert alert-warning">이 수집 버전은 여러 옵션 그룹의 실제 조합을 검증하지 못합니다. 최신 출처의 옵션을 지원하기 전까지 이 연결된 초안은 승인할 수 없습니다.</div>';
        }
        try {
            $data = $manager->editorData((int) $entry->linkedProductId);
        } catch (Throwable) {
            return '<div class="alert alert-danger">기존 초안의 실제 저장값을 읽지 못해 재수집 검수를 차단했습니다. 비활성 초안 상태를 확인해 주세요.</div>';
        }

        $html = '<div class="alert alert-info"><strong>현재 저장된 초안 검수</strong><dl>';
        foreach ([
            'name_ja' => '일본어 상품명',
            'name_en' => '영어 상품명',
            'name_ko' => '한국어 상품명',
            'price_jpy' => '세금 포함 판매가격(JPY)',
            'tax_rules_group_id' => '세금 규칙 그룹 ID',
            'quantity' => '상품 단위 자체 재고',
            'options' => '저장된 상품 옵션',
        ] as $field => $label) {
            $value = (string) ($data[$field] ?? '');
            $html .= '<dt>' . $this->escape($label) . '</dt><dd>' . nl2br($this->escape($value), false) . '</dd>';
        }
        $html .= '<dt>카테고리 ID</dt><dd>' . $this->escape(implode(', ', array_map('strval', $data['category_ids'] ?? []))) . '</dd>'
            . '<dt>옵션별 재고 종류</dt><dd>' . count($data['combination_quantities'] ?? []) . '</dd>'
            . '<dt>이미지 수</dt><dd>' . count($data['image_ids'] ?? []) . '</dd></dl>'
            . '<p>최신 출처 변경과 위에 표시된 실제 저장값을 다시 검토합니다. 이 확인은 기존 초안을 수정하지 않습니다.</p></div>';
        $html .= '<form method="post" action="' . $this->escape($actionUrl) . '">'
            . $this->hiddenReviewFields($entry, $token)
            . '<label><input type="checkbox" name="confirm_keep_existing_draft" value="1" required> 최신 출처 변경과 현재 상품 내용·판매가격·세금·재고·카테고리를 검토했고 기존 초안을 유지합니다.</label><br>'
            . '<label><input type="checkbox" name="translation_reviewed_en" value="1" required> 기존 영어 상품 내용을 다시 검수했습니다.</label><br>'
            . '<label><input type="checkbox" name="translation_reviewed_ko" value="1" required> 기존 한국어 상품 내용을 다시 검수했습니다.</label>';
        if ($entry->snapshot->options !== []) {
            $html .= '<br><label><input type="checkbox" name="confirm_options_supported" value="1" required> 최신 출처 옵션이 기존 저장 옵션과 호환됨을 확인했습니다.</label>';
        }
        if ((int) ($data['tax_rules_group_id'] ?? -1) === 0) {
            $priorReference = $this->escape((string) ($entry->importReviewEvidence?->taxEvidenceReference ?? ''));
            $html .= '<div class="form-group"><label for="existing-tax-evidence-' . $this->escape(substr(hash('sha256', $entry->idempotencyKey), 0, 12)) . '">기존 면세 근거·승인 참조</label>'
                . '<input class="form-control" id="existing-tax-evidence-' . $this->escape(substr(hash('sha256', $entry->idempotencyKey), 0, 12))
                . '" name="tax_evidence_reference" type="text" maxlength="512" required value="' . $priorReference . '"></div>';
        }
        if (($data['image_ids'] ?? []) !== []) {
            $existingImageBasis = (string) ($entry->imageRightsEvidence?->basis ?? '');
            $imageRightsOptions = '';
            foreach ([
                'seller_owned' => '판매자 소유',
                'licensed' => '사용 허가',
                'public_domain' => '공개 저작물 근거 확인',
                'explicit_permission' => '권리자 명시 허가',
            ] as $basis => $label) {
                $selected = $existingImageBasis === $basis ? ' selected' : '';
                $imageRightsOptions .= '<option value="' . $basis . '"' . $selected . '>' . $label . '</option>';
            }
            if ($this->isRunScopedCatalogFixtureMode()) {
                $selected = $existingImageBasis === ProductImageRightsEvidence::BASIS_SYNTHETIC_CI_FIXTURE ? ' selected' : '';
                $imageRightsOptions .= '<option value="' . ProductImageRightsEvidence::BASIS_SYNTHETIC_CI_FIXTURE . '"' . $selected
                    . '>격리 CI 합성 이미지 검증 기록 · 실제 사용권 없음</option>';
            }
            $html .= '<div class="form-group"><label for="existing-image-rights-' . $this->escape(substr(hash('sha256', $entry->idempotencyKey), 0, 12)) . '">기존 이미지 사용권 근거 참조</label>'
                . '<select class="form-control" name="image_rights_basis" required><option value="">사용권 근거 선택</option>' . $imageRightsOptions . '</select>'
                . '<input class="form-control" id="existing-image-rights-' . $this->escape(substr(hash('sha256', $entry->idempotencyKey), 0, 12))
                . '" name="image_rights_reference" type="text" maxlength="512" value="' . $this->escape((string) ($entry->imageRightsEvidence?->reference ?? '')) . '">'
                . '<label><input type="checkbox" name="confirm_existing_image_rights" value="1" required> 현재 연결된 이미지와 사용권 근거를 다시 확인했습니다.</label></div>';
        }
        $html .= '<button class="btn btn-primary" type="submit" name="submitKuraneaCatalogImportedDraft" value="1">최신 출처 검수 · 기존 초안 유지</button></form>';

        return $html;
    }

    private function renderReviewedStatus(): string
    {
        $entry = $this->reviewedEntry;
        if ($entry === null || !in_array($entry->status, [ProductReviewQueueEntry::STATUS_APPROVED, ProductReviewQueueEntry::STATUS_REJECTED], true)) {
            return '';
        }

        $html = '<section class="panel" data-catalog-review-status="' . $this->escape($entry->status) . '">'
            . '<h4>검수 처리 상태</h4><p>상품명: ' . $this->escape($entry->snapshot->name) . '</p>';
        if ($entry->status === ProductReviewQueueEntry::STATUS_APPROVED) {
            $productId = (int) ($entry->nativeProductId ?? 0);
            $html .= '<p>승인 완료 · 상품 ID ' . $productId . ' · 검수자 ' . $this->escape((string) $entry->approvedBy)
                . ' · 처리 시각 ' . $this->escape($entry->approvedAt?->format(DATE_ATOM) ?? '미기재') . '</p>';
            if ($productId > 0) {
                $html .= '<a href="' . $this->escape($this->productManagerUrl($productId)) . '">비활성 상품 관리자에서 열기</a>';
            }
        } else {
            $html .= '<p>반려 완료 · 검수자 ' . $this->escape((string) $entry->rejectedBy)
                . ' · 처리 시각 ' . $this->escape($entry->rejectedAt?->format(DATE_ATOM) ?? '미기재') . '</p>'
                . '<p>반려 사유: ' . nl2br($this->escape((string) $entry->rejectionReason), false) . '</p>';
        }

        return $html . '</section>';
    }

    private function productManagerUrl(int $productId): string
    {
        $url = (string) $this->context->link->getAdminLink('AdminOrdenowaProductManager');
        $separator = str_contains($url, '?') ? '&' : '?';

        return $url . $separator . 'id_product=' . max(0, $productId);
    }

    /** @param list<array{id_category:int,name:string}> $categories
     *  @param list<array{id_tax_rules_group:int,name:string}> $taxRulesGroups
     */
    private function renderImportedDraftForm(
        ProductReviewQueueEntry $entry,
        array $categories,
        array $taxRulesGroups,
        string $actionUrl,
        string $token
    ): string {
        $snapshot = $entry->snapshot;
        $options = [];
        foreach ($snapshot->options as $option) {
            if ($option->name === '' || $option->values === []) continue;
            $options[] = $option->name . ':' . implode('|', $option->values);
        }
        $hash = $this->escape($snapshot->contentHash);
        $suffix = substr($hash, 0, 12);
        $optionReviewConfirmation = '';
        if ($snapshot->options !== []) {
            if (count($snapshot->options) > 1) {
                $optionReviewConfirmation = '<div class="alert alert-warning">현재 수집기는 여러 옵션 그룹 사이의 실제 판매 조합·조합별 가격·재고를 확인하지 못합니다. 이 상품은 옵션 연결을 지원하지 않아 초안 등록이 차단됩니다.</div>';
            } else {
                $optionReviewConfirmation = '<div class="form-group"><label><input type="checkbox" name="confirm_options_supported" value="1" required> '
                    . '원본에서 표시된 모든 단일 옵션 값이 실제 판매 가능한 조합임을 확인했습니다.</label>'
                    . '<p class="help-block">조합별 가격이나 출처 재고는 가져오지 않습니다. ORDENOWA 판매가격과 자체 재고를 별도로 입력하세요.</p></div>';
            }
        }
        $imageRightsOptions = '<option value="seller_owned">판매자 소유</option><option value="licensed">사용 허가</option>'
            . '<option value="public_domain">공개 저작물 근거 확인</option><option value="explicit_permission">권리자 명시 허가</option>';
        if ($this->isRunScopedCatalogFixtureMode()) {
            $imageRightsOptions .= '<option value="synthetic_ci_fixture">격리 CI 합성 이미지 검증 기록 · 실제 사용권 없음</option>';
        }
        $html = '<form method="post" enctype="multipart/form-data" class="catalog-import-review-form" action="' . $this->escape($actionUrl) . '">'
            . $this->hiddenReviewFields($entry, $token)
            . '<h5>운영용 비활성 상품 초안 입력</h5>'
            . '<p>출처 가격·재고는 복사되지 않습니다. 일본어 원문 외 영어·한국어는 직접 입력하거나 번역 검수해 주세요.</p>'
            . $this->reviewTextField('name_ja', '일본어 상품명', $snapshot->name, true)
            . $this->reviewTextField('name_en', '영어 상품명', '', false)
            . $this->reviewTextField('name_ko', '한국어 상품명', '', false)
            . $this->reviewTextArea('description_ja', '일본어 상세 설명', $snapshot->description ?? '')
            . $this->reviewTextArea('description_en', '영어 상세 설명', '')
            . $this->reviewTextArea('description_ko', '한국어 상세 설명', '')
            . '<div class="form-group"><label><input type="checkbox" name="translation_reviewed_en" value="1" required> 영어 상품명·상세 설명 번역을 검수했습니다.</label>'
            . '<p class="help-block">영어 상품명과 상세 설명을 일본어 원문과 대조해 의미·수치·주의사항을 확인합니다.</p></div>'
            . '<div class="form-group"><label><input type="checkbox" name="translation_reviewed_ko" value="1" required> 한국어 상품명·상세 설명 번역을 검수했습니다.</label>'
            . '<p class="help-block">한국어 상품명과 상세 설명을 일본어 원문과 대조해 의미·수치·주의사항을 확인합니다.</p></div>'
            . '<div class="form-group"><label for="sale-price-' . substr($hash, 0, 12) . '">세금 포함 판매가격 (JPY)</label>'
            . '<input class="form-control" id="sale-price-' . substr($hash, 0, 12) . '" name="sale_price_jpy" type="number" min="1" step="1" required value="">'
            . '<p class="help-block">출처 가격 ' . number_format($snapshot->priceJpy) . ' JPY는 참고값입니다. 검수한 최종 표시 판매가격을 직접 입력하세요.</p>'
            . '<label><input type="checkbox" name="confirm_same_source_price" value="1"> 출처 참고 가격과 같은 판매가격을 선택했다면, 이 일치를 검토하고 승인합니다.</label></div>'
            . $this->reviewTaxRules($taxRulesGroups, $suffix)
            . '<div class="form-group"><label for="own-quantity-' . substr($hash, 0, 12) . '">ORDENOWA 자체 재고</label>'
            . '<input class="form-control" id="own-quantity-' . substr($hash, 0, 12) . '" name="own_quantity" type="number" min="0" step="1" required value="">'
            . '<p class="help-block">출처 판매처의 재고 상태와 별도입니다. 확인한 수량을 입력하세요.</p></div>'
            . $this->reviewCategories($categories, $suffix)
            . $this->reviewTextArea('options', '검수할 상품 옵션', implode("\n", $options))
            . $optionReviewConfirmation
            . '<div class="form-group"><label for="import-images-' . substr($hash, 0, 12) . '">사용권 확인된 상품 이미지 업로드</label>'
            . '<input class="form-control" id="import-images-' . substr($hash, 0, 12) . '" name="import_product_images[]" type="file" accept="image/jpeg,image/png,image/webp" multiple>'
            . '<p class="help-block">출처 이미지 URL을 읽은 것만으로 파일을 내려받거나 사용할 권리가 생기지 않습니다. 권리가 확인된 파일만 올리세요.</p>'
            . '<div class="catalog-import-image-preview" data-catalog-image-preview data-preview-count="0" role="status" aria-live="polite">'
            . '<p data-preview-status>파일 선택 시 업로드 예정 이미지의 미리보기가 표시됩니다.</p>'
            . '<p class="help-block">미리보기는 업로드 예정 파일만 표시하며 사용권 승인을 대신하지 않습니다.</p>'
            . '<div data-preview-items></div></div></div>'
            . '<div class="form-group"><label for="image-rights-basis-' . substr($hash, 0, 12) . '">이미지 사용권 근거</label><select class="form-control" id="image-rights-basis-'
            . substr($hash, 0, 12) . '" name="image_rights_basis"><option value="">이미지 미사용 또는 권리 미확인</option>'
            . $imageRightsOptions . '</select>'
            . '<label for="image-rights-reference-' . substr($hash, 0, 12) . '">권리 문서·승인 참조</label>'
            . '<input class="form-control" id="image-rights-reference-' . substr($hash, 0, 12) . '" name="image_rights_reference" type="text" maxlength="512"></div>'
            . '<label><input type="checkbox" name="confirm_image_rights" value="1"> 업로드한 이미지의 사용권 근거를 확인했습니다.</label><br>'
            . '<button class="btn btn-primary" type="submit" name="submitKuraneaCatalogImportedDraft" value="1">검수 승인 · 비활성 초안 등록</button></form>';

        return $html;
    }

    private function hiddenReviewFields(ProductReviewQueueEntry $entry, string $token): string
    {
        return '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
            . '<input type="hidden" name="idempotency_key" value="' . $this->escape($entry->idempotencyKey) . '">'
            . '<input type="hidden" name="content_hash" value="' . $this->escape($entry->snapshot->contentHash) . '">';
    }

    private function renderSourceChanges(\Kuranea\Catalog\Domain\NormalizedProductSnapshot $before, \Kuranea\Catalog\Domain\NormalizedProductSnapshot $after): string
    {
        $changes = [];
        foreach ([
            '상품명' => [$before->name, $after->name],
            '상세 설명' => [$before->description ?? '미수집', $after->description ?? '미수집'],
            '출처 가격' => [$before->priceJpy . ' ' . $before->currency, $after->priceJpy . ' ' . $after->currency],
            '출처 재고' => [$before->availability ?? '미수집', $after->availability ?? '미수집'],
            '카테고리' => [implode(' / ', $before->categories) ?: '미수집', implode(' / ', $after->categories) ?: '미수집'],
            '옵션' => [$this->snapshotOptionText($before), $this->snapshotOptionText($after)],
            '이미지 수' => [(string) count($before->images), (string) count($after->images)],
        ] as $label => [$old, $new]) {
            if ($old !== $new) $changes[] = '<li><strong>' . $this->escape($label) . '</strong>: '
                . $this->escape($old) . ' → ' . $this->escape($new) . '</li>';
        }
        if ($changes === []) $changes[] = '<li>변경된 표시 필드를 찾지 못했습니다. 수집 시각과 원본 지문은 달라졌습니다.</li>';

        return '<div class="alert alert-warning"><strong>이전 수집과 비교</strong><ul>' . implode('', $changes)
            . '</ul><p>기존 관리자 초안·판매가격·자체 재고는 이 비교로 갱신되지 않습니다.</p></div>';
    }

    private function snapshotOptionText(\Kuranea\Catalog\Domain\NormalizedProductSnapshot $snapshot): string
    {
        $values = [];
        foreach ($snapshot->options as $option) $values[] = $option->name . ':' . implode('|', $option->values);
        return $values === [] ? '미수집' : implode(' / ', $values);
    }

    private function reviewTextField(string $name, string $label, string $value, bool $required): string
    {
        return '<div class="form-group"><label for="' . $this->escape($name) . '">' . $this->escape($label)
            . '</label><input class="form-control" id="' . $this->escape($name) . '" name="' . $this->escape($name)
            . '" type="text" maxlength="128"' . ($required ? ' required' : '') . ' value="' . $this->escape($value) . '"></div>';
    }

    private function reviewTextArea(string $name, string $label, string $value): string
    {
        return '<div class="form-group"><label for="' . $this->escape($name) . '">' . $this->escape($label)
            . '</label><textarea class="form-control" id="' . $this->escape($name) . '" name="' . $this->escape($name)
            . '" rows="4" maxlength="20000">' . $this->escape($value) . '</textarea></div>';
    }

    /** @param list<array{id_tax_rules_group:int,name:string}> $groups */
    private function reviewTaxRules(array $groups, string $suffix): string
    {
        $html = '<div class="form-group"><label for="tax-group-' . $suffix . '">PrestaShop 세금 규칙 그룹</label><select class="form-control" id="tax-group-' . $suffix . '" name="tax_rules_group_id" required>'
            . '<option value="" selected disabled>상품별 일본 세금 규칙을 검토하고 선택하세요</option>';
        foreach ($groups as $group) {
            $html .= '<option value="' . (int) $group['id_tax_rules_group'] . '">' . $this->escape((string) $group['name']) . '</option>';
        }
        return $html . '</select><p class="help-block">출처 가격을 세금이나 판매가격으로 간주하지 않습니다. 실제 상품 세무 분류를 승인받아 설정하세요.</p>'
            . '<label for="tax-treatment-' . $suffix . '">상품 세무 분류</label><select class="form-control" id="tax-treatment-' . $suffix . '" name="tax_treatment" required>'
            . '<option value="" selected disabled>과세 여부를 검토하고 선택하세요</option>'
            . '<option value="taxable">선택한 세금 규칙 그룹에 따른 과세</option>'
            . '<option value="explicitly_exempt">승인된 근거가 있는 면세</option></select>'
            . '<label for="tax-evidence-' . $suffix . '">면세 근거·승인 참조</label>'
            . '<input class="form-control" id="tax-evidence-' . $suffix . '" name="tax_evidence_reference" type="text" maxlength="512">'
            . '<p class="help-block">면세 분류는 그룹 미할당과 승인 근거 참조가 모두 있어야 저장됩니다.</p></div>';
    }

    /** @param list<array{id_category:int,name:string}> $categories */
    private function reviewCategories(array $categories, string $suffix): string
    {
        $html = '<fieldset class="form-group"><legend>ORDENOWA 카테고리 선택</legend>';
        foreach ($categories as $category) {
            $id = (int) $category['id_category'];
            $html .= '<label class="checkbox-inline"><input type="checkbox" name="category_ids[]" value="' . $id . '"> '
                . $this->escape((string) $category['name']) . '</label> ';
        }
        if ($categories === []) $html .= '<p>사용 가능한 카테고리를 확인할 수 없습니다.</p>';
        return $html . '</fieldset>';
    }

    private function batchStatusLabel(string $status): string
    {
        return match ($status) {
            CatalogImportBatchItem::STATUS_QUEUED => '대기',
            CatalogImportBatchItem::STATUS_PROCESSING => '수집 중',
            CatalogImportBatchItem::STATUS_SUCCEEDED => '성공',
            CatalogImportBatchItem::STATUS_FAILED => '실패',
            default => '확인 필요',
        };
    }

    private function availabilityLabel(?string $availability): string
    {
        return match (strtolower((string) $availability)) {
            'https://schema.org/instock', 'instock' => '출처 판매처 판매 중 표기',
            'https://schema.org/outofstock', 'outofstock' => '출처 판매처 품절 표기',
            default => '미수집 또는 판정 불가',
        };
    }

    private function canView(): bool
    {
        return $this->viewAccess();
    }

    private function canApprove(): bool
    {
        return $this->canView() && $this->access('edit') && $this->access('add');
    }

    private function sourceLabel(string $source): string
    {
        return match ($source) {
            'amazon_jp' => '아마존 일본',
            'rakuten_ichiba' => '라쿠텐 이치바',
            default => $source,
        };
    }

    private function fail(string $message): void
    {
        $this->feedback = $message;
        $this->feedbackIsError = true;
    }

    private function succeed(string $message): void
    {
        $this->feedback = $message;
        $this->feedbackIsError = false;
    }

    private function renderFeedback(): string
    {
        if ($this->feedback === '') {
            return '';
        }
        $class = $this->feedbackIsError ? 'alert-danger' : 'alert-success';

        return '<div class="alert ' . $class . '">' . $this->escape($this->feedback) . '</div>';
    }

    private function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
