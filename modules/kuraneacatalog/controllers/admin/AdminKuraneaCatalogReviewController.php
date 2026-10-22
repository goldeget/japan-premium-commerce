<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/autoload.php';

use Kuranea\Catalog\Domain\ProductReviewQueueEntry;
use Kuranea\Catalog\Infrastructure\Persistence\CatalogQueueRepositoryFactory;
use Kuranea\Catalog\Integration\PrestaShopNativeProductRegistrar;
use Kuranea\Catalog\Service\ProductApprovalService;

class AdminKuraneaCatalogReviewController extends ModuleAdminController
{
    private string $feedback = '';
    private bool $feedbackIsError = false;

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '상품 검수 대기열';
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
            $this->processApproval($queue);
            $pending = $queue->pending();
            $this->content .= $this->renderFeedback();
            $this->content .= $this->renderQueue($pending);
        } catch (Throwable) {
            http_response_code(503);
            $this->content .= '<div class="alert alert-danger">검수 대기열을 불러오지 못했습니다. 저장소 설정을 확인해 주세요.</div>';
        }

        $this->context->smarty->assign('content', $this->content);
    }

    private function processApproval(\Kuranea\Catalog\Domain\ProductReviewQueueRepositoryInterface $queue): void
    {
        if (strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? '')) !== 'POST'
            || !Tools::isSubmit('submitKuraneaCatalogApprove')) {
            return;
        }

        $submittedToken = Tools::getValue('token');
        $expectedToken = (string) Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
        if (!is_string($submittedToken) || $expectedToken === '' || !hash_equals($expectedToken, $submittedToken)) {
            $this->fail('관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.');
            return;
        }

        if (!$this->canApprove()) {
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
            $this->succeed(sprintf('TEST/DEMO 상품 ID %d를 검수 기록에 연결했습니다.', (int) $approved->nativeProductId));
        } catch (Throwable) {
            $this->fail('상품 승인에 실패했습니다. 대기 항목과 서버의 PrestaShop 설정을 확인해 주세요.');
        }
    }

    /** @param list<ProductReviewQueueEntry> $pending */
    private function renderQueue(array $pending): string
    {
        $actionUrl = (string) $this->context->link->getAdminLink('AdminKuraneaCatalogReview');
        $token = (string) Tools::getAdminTokenLite('AdminKuraneaCatalogReview');
        $approvalEnabled = getenv('KURANEA_CATALOG_TEST_DEMO_APPROVAL') === '1';
        $html = '<section class="panel"><h3>검수 대기 상품</h3>';
        $html .= '<p>모든 등록 결과는 비활성·비노출·비주문 가능 상태의 <strong>TEST/DEMO</strong> 상품입니다. 실제 판매 상품으로 사용하지 마세요.</p>';
        if (!$approvalEnabled) {
            $html .= '<div class="alert alert-warning">TEST/DEMO 승인은 현재 서버 설정에서 비활성화되어 있습니다.</div>';
        }
        if ($pending === []) {
            return $html . '<p>검수 대기 항목이 없습니다.</p></section>';
        }

        foreach ($pending as $entry) {
            $snapshot = $entry->snapshot;
            $html .= '<article class="panel"><h4>' . $this->escape($snapshot->name) . '</h4>';
            $html .= '<dl><dt>출처</dt><dd>' . $this->escape($this->sourceLabel($snapshot->source)) . '</dd>';
            $html .= '<dt>출처 상품 ID</dt><dd>' . $this->escape($snapshot->sourceProductId) . '</dd>';
            $html .= '<dt>출처 URL</dt><dd><code>' . $this->escape($snapshot->sourceUrl) . '</code></dd>';
            $html .= '<dt>브랜드</dt><dd>' . $this->escape($snapshot->brand ?? '미기재') . '</dd>';
            $html .= '<dt>가격</dt><dd>' . number_format($snapshot->priceJpy) . ' ' . $this->escape($snapshot->currency) . '</dd>';
            $html .= '<dt>조회 시각</dt><dd>' . $this->escape($snapshot->fetchedAt->format(DATE_ATOM)) . '</dd>';
            $html .= '<dt>중복 식별 키</dt><dd><code>' . $this->escape($entry->idempotencyKey) . '</code></dd></dl>';
            if ($snapshot->description !== null) {
                $html .= '<p>' . nl2br($this->escape($snapshot->description), false) . '</p>';
            }
            if ($snapshot->options !== []) {
                $optionText = [];
                foreach ($snapshot->options as $option) {
                    $optionText[] = $option->name . ': ' . implode(', ', $option->values);
                }
                $html .= '<p><strong>옵션:</strong> ' . $this->escape(implode(' / ', $optionText)) . '</p>';
            }
            if ($snapshot->images !== []) {
                $html .= '<p><strong>이미지 메타데이터</strong></p><ul>';
                foreach ($snapshot->images as $image) {
                    $html .= '<li>' . $this->escape($image->altText) . ' · ' . $this->escape($this->sourceLabel($image->source))
                        . ' · <code>' . $this->escape($image->url) . '</code></li>';
                }
                $html .= '</ul>';
            }
            if ($snapshot->sourceRating !== null || $snapshot->sourceReviewCount !== null || $snapshot->reviews !== []) {
                $html .= '<p class="text-muted">출처 사이트 평점·후기 참고정보이며 ORDENOWA 고객 후기가 아닙니다. 평점 '
                    . $this->escape((string) ($snapshot->sourceRating ?? '미기재')) . ', 후기 수 '
                    . $this->escape((string) ($snapshot->sourceReviewCount ?? '미기재')) . '</p>';
            }
            if ($snapshot->reviews !== []) {
                $html .= '<ul class="list-unstyled">';
                foreach ($snapshot->reviews as $review) {
                    $reviewLabel = $review->origin === 'source_site' ? '출처 사이트 후기' : '별도 출처 검수 정보';
                    $html .= '<li class="well"><strong>' . $reviewLabel . ' · ' . $this->escape($this->sourceLabel($review->provider)) . '</strong>';
                    if ($review->author !== null) {
                        $html .= ' · ' . $this->escape($review->author);
                    }
                    if ($review->rating !== null) {
                        $html .= ' · ' . $this->escape((string) $review->rating) . '/5';
                    }
                    if ($review->body !== null) {
                        $html .= '<p>' . nl2br($this->escape($review->body), false) . '</p>';
                    }
                    $publishStatus = $review->origin === 'source_site' || !$review->publishable ? '불가' : '별도 검수 필요';
                    $html .= '<small>고객 후기 게시: ' . $publishStatus . '</small></li>';
                }
                $html .= '</ul>';
            }

            if ($this->canApprove() && $approvalEnabled) {
                $html .= '<form method="post" action="' . $this->escape($actionUrl) . '">'
                    . '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
                    . '<input type="hidden" name="idempotency_key" value="' . $this->escape($entry->idempotencyKey) . '">'
                    . '<label><input type="checkbox" name="confirm_test_demo" value="1" required> TEST/DEMO 비활성 상품으로 등록함을 확인합니다.</label> '
                    . '<button class="btn btn-primary" type="submit" name="submitKuraneaCatalogApprove" value="1">검수 승인 및 TEST/DEMO 등록</button>'
                    . '</form>';
            }
            $html .= '</article>';
        }

        return $html . '</section>';
    }

    private function canView(): bool
    {
        $access = (array) ($this->tabAccess ?? []);

        return !empty($access['view']);
    }

    private function canApprove(): bool
    {
        $access = (array) ($this->tabAccess ?? []);

        return !empty($access['view']) && !empty($access['edit']) && !empty($access['add']);
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
