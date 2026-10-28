<?php

declare(strict_types=1);

namespace Ordenowa\Procurement\Integration;

use Ordenowa\Procurement\Security\Actor;

/** Shared native BO shell. Data and mutation access are rechecked per action. */
abstract class AdminController extends \ModuleAdminController
{
    protected string $procurementTab = '';
    protected string $procurementTitle = '';

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = $this->procurementTitle;
    }

    public function initHeader()
    {
        $languageId = (int) \Language::getIdByIso('ko', true);
        if ($languageId > 0) {
            $this->context->language = new \Language($languageId);
        }
        parent::initHeader();
    }

    public function initContent(): void
    {
        header('Cache-Control: private, no-store, max-age=0', true);
        header('X-Robots-Tag: noindex, nofollow', true);
        try {
            $actor = Runtime::employeeActor();
            if (!Runtime::nativePermission($this->procurementTab, 'READ')) {
                throw new \RuntimeException('조회 권한이 없습니다.', 403);
            }
            $this->processAction($actor);
            parent::initContent();
            $this->content .= '<div class="panel ordenowa-procurement-admin"><h2>' . self::escape($this->procurementTitle) . '</h2>';
            if (\Tools::getValue('ordenowa_saved') === '1') {
                $this->content .= '<p class="alert alert-success" role="status">처리 결과를 저장했습니다.</p>';
            }
            $this->content .= $this->renderPage($actor) . '</div>';
        } catch (\Throwable $error) {
            $code = (int) $error->getCode();
            http_response_code(in_array($code, [403, 404, 409, 422, 503], true) ? $code : 422);
            parent::initContent();
            $this->content .= '<div class="alert alert-danger" role="alert">'
                . self::escape($this->safeError($error)) . '</div>';
        }
        $this->context->smarty->assign('content', $this->content);
    }

    abstract protected function renderPage(Actor $actor): string;

    protected function processAction(Actor $actor): void
    {
        if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'POST') {
            return;
        }
        $action = $this->input('procurement_action');
        if ($action === '') {
            return;
        }
        $token = $this->input('token');
        if ($token === '' || !hash_equals((string) \Tools::getAdminTokenLite($this->procurementTab), $token)) {
            throw new \RuntimeException('보안 토큰이 유효하지 않습니다. 화면을 새로 열어 주세요.', 403);
        }
        $actions = [
            'assign' => ['AdminOrdenowaProcurement', 'ADD', 'procurement.manage'],
            'revoke' => ['AdminOrdenowaProcurement', 'EDIT', 'procurement.manage'],
            'review' => ['AdminOrdenowaProcurementReviews', 'EDIT', 'procurement.review'],
            'award' => ['AdminOrdenowaProcurementPoints', 'ADD', 'points.award'],
            'correct' => ['AdminOrdenowaProcurementPoints', 'EDIT', 'points.correct'],
        ];
        if (!isset($actions[$action]) || $actions[$action][0] !== $this->procurementTab
            || !Runtime::nativePermission($this->procurementTab, $actions[$action][1])) {
            throw new \RuntimeException('이 작업을 처리할 권한이 없습니다.', 403);
        }
        $actor->require($actions[$action][2]);
        switch ($action) {
            case 'assign':
                $customer = $this->integer('id_customer', 1);
                Runtime::validateCustomer($customer);
                $manualImages = $this->input('manual_image_ids');
                $manualAttestation = $this->input('manual_image_rights');
                $rights = [];
                if ($manualImages !== '' || $manualAttestation !== '') {
                    if (preg_match('/\A[1-9][0-9]*(?:[ ,]+[1-9][0-9]*)*\z/D', $manualImages) !== 1) throw new \InvalidArgumentException('이미지 번호는 양의 정수를 쉼표로 구분해 주세요.', 422);
                    $ids = preg_split('/[ ,]+/', $manualImages);
                    foreach ($ids as $id) if (filter_var($id, FILTER_VALIDATE_INT) === false) throw new \InvalidArgumentException('이미지 번호 범위를 확인해 주세요.', 422);
                    $rights = ['image_ids' => array_map('intval', $ids), 'attestation' => $manualAttestation];
                }
                $product = Runtime::productReference($this->integer('id_product', 1), $this->integer('id_product_attribute', 0), $rights);
                Runtime::requests()->createAssignment($actor, $customer, $product, [
                    'default_quantity' => $this->integer('default_quantity', 1),
                    'max_quantity' => $this->integer('max_quantity', 1),
                    'instructions' => $this->input('instructions'),
                    'deadline' => ($deadline = $this->input('deadline')) === '' ? null : $deadline,
                ]);
                break;
            case 'revoke':
                Runtime::requests()->revokeAssignment($actor, $this->integer('id_assignment', 1), $this->integer('version', 1), $this->input('reason'));
                break;
            case 'review':
                Runtime::requests()->review($actor, $this->integer('id_request', 1), $this->integer('version', 1), $this->input('decision'), $this->input('reason'));
                break;
            case 'award':
                Runtime::points()->award($actor, $this->integer('id_request', 1), $this->integer('amount', 1), $this->input('reason'), $this->input('idempotency_key'));
                break;
            case 'correct':
                Runtime::points()->correct($actor, $this->integer('id_award', 1), $this->integer('delta', PHP_INT_MIN), $this->input('reason'), $this->input('idempotency_key'));
                break;
        }
        \Tools::redirectAdmin($this->url(['ordenowa_saved' => '1']));
    }

    protected function listingFilters(): array
    {
        $query = \Tools::getValue('q', '');
        $status = \Tools::getValue('status', '');
        if (!is_string($query) || !is_string($status)) {
            throw new \InvalidArgumentException('검색 조건을 확인해 주세요.', 422);
        }
        return ['limit' => 51, 'before_id' => max(0, (int) \Tools::getValue('before_id', 0)), 'q' => trim($query), 'status' => $status];
    }

    protected function filterForm(array $statuses): string
    {
        $filters = $this->listingFilters();
        $html = '<form method="get" action="' . self::escape($this->url()) . '" class="form-inline">'
            . '<input type="hidden" name="controller" value="' . self::escape($this->procurementTab) . '">'
            . '<input type="hidden" name="token" value="' . self::escape((string) \Tools::getAdminTokenLite($this->procurementTab)) . '">'
            . '<label>상품명·참조 검색 <input class="form-control" type="search" name="q" maxlength="100" value="' . self::escape($filters['q']) . '"></label> '
            . '<label>상태 <select class="form-control" name="status"><option value="">전체</option>';
        foreach ($statuses as $status) {
            $html .= '<option value="' . self::escape($status) . '"' . ($filters['status'] === $status ? ' selected' : '') . '>' . $this->status($status) . '</option>';
        }
        return $html . '</select></label> <button class="btn btn-default" type="submit">검색</button></form>';
    }

    protected function nextPage(array $rows, string $idField, array $params = []): string
    {
        if (count($rows) < 51) {
            return '';
        }
        $last = $rows[49];
        $filters = $this->listingFilters();
        unset($filters['limit']);
        $filters['before_id'] = (int) $last[$idField];
        return '<p><a class="btn btn-default" rel="next" href="' . self::escape($this->url(array_merge($filters, $params))) . '">다음 50건</a></p>';
    }

    protected function formStart(string $action, array $hidden = []): string
    {
        $html = '<form method="post" action="' . self::escape($this->url()) . '" data-testid="procurement-' . $action . '" class="ordenowa-procurement-form">'
            . '<input type="hidden" name="token" value="' . self::escape((string) \Tools::getAdminTokenLite($this->procurementTab)) . '">';
        foreach ($hidden as $name => $value) {
            $html .= '<input type="hidden" name="' . self::escape($name) . '" value="' . self::escape((string) $value) . '">';
        }
        return $html;
    }

    protected function submitButton(string $action, string $label): string
    {
        return '<button type="submit" class="btn btn-primary" name="procurement_action" value="' . self::escape($action) . '">' . self::escape($label) . '</button></form>';
    }

    protected function field(string $name, string $label, string $type = 'text', string $value = '', bool $required = true): string
    {
        $id = 'procurement-' . $name . '-' . bin2hex(random_bytes(3));
        return '<div class="form-group"><label for="' . $id . '">' . self::escape($label) . '</label>'
            . '<input class="form-control" id="' . $id . '" name="' . self::escape($name) . '" type="' . self::escape($type) . '" value="' . self::escape($value) . '"'
            . ($required ? ' required' : '') . ($type === 'number' ? ' step="1"' : '') . '></div>';
    }

    protected function reasonField(): string
    {
        return $this->field('reason', '처리 사유 (회원에게 표시됩니다)');
    }

    protected function table(array $headers, array $rows): string
    {
        $html = '<div class="table-responsive"><table class="table"><thead><tr>';
        foreach ($headers as $header) {
            $html .= '<th scope="col">' . self::escape($header) . '</th>';
        }
        $html .= '</tr></thead><tbody>';
        foreach ($rows as $row) {
            $html .= '<tr>';
            foreach ($row as $cell) {
                $html .= '<td>' . $cell . '</td>';
            }
            $html .= '</tr>';
        }
        return $html . '</tbody></table></div>' . ($rows === [] ? '<p>표시할 내역이 없습니다.</p>' : '');
    }

    protected function productLabel(array $row): string
    {
        $product = $row['product_snapshot'] ?? $row['product'] ?? [];
        if (!is_array($product)) {
            $product = json_decode((string) $product, true) ?: [];
        }
        $label = self::escape((string) ($product['names']['ko'] ?? $product['names']['ja'] ?? $product['names']['en'] ?? '상품'))
            . ' <small>(상품 ' . (int) ($product['id_product'] ?? 0) . ' / 옵션 ' . (int) ($product['id_product_attribute'] ?? 0) . ')</small>';
        $description = (string) ($product['descriptions']['ko'] ?? $product['descriptions']['ja'] ?? $product['descriptions']['en'] ?? '');
        $label .= '<details><summary>저장된 상품·안내 상세</summary><p>' . nl2br(self::escape($description)) . '</p>'
            . '<p>' . nl2br(self::escape((string) ($row['instructions'] ?? ''))) . '</p>';
        if (($product['reference_price'] ?? '') !== '') {
            $label .= '<p>수집 시점 참고 가격: ' . self::escape((string) $product['reference_price']) . ' ' . self::escape((string) ($product['currency'] ?? '')) . '</p>';
        }
        foreach ($product['categories'] ?? [] as $category) {
            $label .= '<span class="label label-default">' . self::escape((string) ($category['names']['ko'] ?? $category['names']['ja'] ?? $category['names']['en'] ?? '')) . '</span> ';
        }
        if (isset($product['image_rights']['attestation'])) {
            $label .= '<p>이미지 공개 사용 권리 근거: ' . self::escape((string) $product['image_rights']['attestation']) . ' · 확인 운영자 ' . (int) ($product['image_rights']['id_employee'] ?? 0) . '</p>';
        }
        $source = (string) ($product['source_url'] ?? '');
        if (filter_var($source, FILTER_VALIDATE_URL) && in_array(strtolower((string) parse_url($source, PHP_URL_SCHEME)), ['https', 'http'], true)) {
            $label .= '<p><a rel="noopener noreferrer" target="_blank" href="' . self::escape($source) . '">검토된 상품 출처</a></p>';
        }
        return $label . '</details>';
    }

    protected function status(string $status): string
    {
        return self::escape(match ($status) {
            'ACTIVE' => '안내 중', 'REQUESTED' => '요청 제출', 'EXPIRED' => '기한 만료', 'CANCELLED' => '취소',
            'SUBMITTED' => '검토 대기', 'APPROVED' => '승인', 'REJECTED' => '반려', default => $status,
        });
    }

    protected function url(array $params = []): string
    {
        $url = (string) $this->context->link->getAdminLink($this->procurementTab);
        return $url . ($params === [] ? '' : '&' . http_build_query($params));
    }

    protected static function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    private function input(string $name): string
    {
        $value = $_POST[$name] ?? '';
        if (!is_string($value)) {
            throw new \InvalidArgumentException('입력 형식을 확인해 주세요.', 422);
        }
        return trim($value);
    }

    private function integer(string $name, int $minimum): int
    {
        $value = $this->input($name);
        if (preg_match('/\A-?(?:0|[1-9][0-9]*)\z/D', $value) !== 1
            || filter_var($value, FILTER_VALIDATE_INT) === false || (int) $value < $minimum) {
            throw new \InvalidArgumentException('정수 입력값을 확인해 주세요.', 422);
        }
        return (int) $value;
    }

    private function safeError(\Throwable $error): string
    {
        // Domain failures are deliberately brief; SQL/driver paths never reach BO output.
        $message = $error->getMessage();
        if ($error instanceof \InvalidArgumentException || in_array((int) $error->getCode(), [403, 404, 409, 422, 503], true)) {
            return preg_match('/[가-힣]/u', $message) === 1 ? $message : match ((int) $error->getCode()) {
                403 => '처리 권한을 확인해 주세요.', 404 => '현재 쇼핑몰에서 내역을 찾을 수 없습니다.',
                409 => '이미 처리되었거나 화면 정보가 변경되었습니다. 내역을 새로 확인해 주세요.',
                503 => '상품 발주 서비스를 준비 중입니다.', default => '입력값과 요청 상태를 확인해 주세요.',
            };
        }
        return '처리를 완료하지 못했습니다. 저장된 내역을 확인한 뒤 다시 시도해 주세요.';
    }
}
