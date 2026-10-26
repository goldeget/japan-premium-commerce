<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/vendor/autoload.php';

use Kuranea\Backoffice\Infrastructure\EmployeeProfileAuditRepository;

class AdminKuraneaEmployeeProfileAuditController extends ModuleAdminController
{
    private const PAGE_SIZE = 50;

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '관리자 프로필 변경 이력';
    }

    public function initHeader()
    {
        $koreanLanguageId = (int) Language::getIdByIso('ko', true);
        if ($koreanLanguageId > 0) {
            $this->context->language = new Language($koreanLanguageId);
        }

        parent::initHeader();
    }

    public function initContent(): void
    {
        if (!$this->canView()) {
            http_response_code(403);
            $this->content = '<div class="alert alert-danger">관리자 프로필 변경 이력을 조회할 권한이 없습니다.</div>';
            $this->context->smarty->assign('content', $this->content);

            return;
        }

        $shopId = (int) ($this->context->shop->id ?? 0);
        if ($shopId < 1 || Shop::getContext() !== Shop::CONTEXT_SHOP) {
            http_response_code(403);
            $this->content = '<div class="alert alert-warning">하나의 쇼핑몰을 선택한 후 이용해 주세요.</div>';
            $this->context->smarty->assign('content', $this->content);

            return;
        }

        parent::initContent();
        try {
            $page = $this->requestedPage();
            $result = (new EmployeeProfileAuditRepository())->pageForShop($shopId, $page);
            $baseUrl = (string) $this->context->link->getAdminLink('AdminKuraneaEmployeeProfileAudit');
            $this->content .= '<div class="panel"><h3>관리자 프로필 변경 이력</h3>'
                . '<p>관리자 프로필 역할 변경 기록입니다. 권한 설정 표의 접근 권한 변경은 이 화면에 포함되지 않습니다.</p>'
                . $this->renderRows($result['rows'])
                . $this->renderPagination($baseUrl, $page, $result['has_next'])
                . '</div>';
        } catch (Throwable) {
            http_response_code(503);
            $this->content .= '<div class="alert alert-danger">관리자 프로필 변경 이력을 불러오지 못했습니다.</div>';
        }

        $this->context->smarty->assign('content', $this->content);
    }

    /** @param list<array{id_event:int,actor_employee_id:?int,target_employee_id:int,old_profile_id:int,new_profile_id:int,changed_at_utc:string}> $rows */
    private function renderRows(array $rows): string
    {
        if ($rows === []) {
            return '<p>표시할 관리자 프로필 변경 이력이 없습니다.</p>';
        }

        $html = '<div class="table-responsive"><table class="table"><thead><tr>'
            . '<th>기록 번호</th><th>처리 관리자 ID</th><th>대상 관리자 ID</th>'
            . '<th>이전 프로필 ID</th><th>새 프로필 ID</th><th>변경 시각 (UTC)</th>'
            . '</tr></thead><tbody>';
        foreach ($rows as $row) {
            $actorId = $row['actor_employee_id'];
            $html .= '<tr><td>' . (int) $row['id_event'] . '</td>'
                . '<td>' . ($actorId === null ? '확인할 수 없음' : (string) $actorId) . '</td>'
                . '<td>' . (int) $row['target_employee_id'] . '</td>'
                . '<td>' . (int) $row['old_profile_id'] . '</td>'
                . '<td>' . (int) $row['new_profile_id'] . '</td>'
                . '<td>' . $this->escape((string) $row['changed_at_utc']) . '</td></tr>';
        }
        $html .= '</tbody></table></div>';

        return $html;
    }

    private function renderPagination(string $baseUrl, int $page, bool $hasNext): string
    {
        $html = '<nav aria-label="관리자 프로필 변경 이력 페이지"><p>' . $page . '페이지</p>';
        if ($page > 1) {
            $html .= '<a class="btn btn-default" rel="prev" href="'
                . $this->escape($baseUrl . '&audit_page=' . ($page - 1)) . '">이전 페이지</a> ';
        }
        if ($hasNext) {
            $html .= '<a class="btn btn-default" rel="next" href="'
                . $this->escape($baseUrl . '&audit_page=' . ($page + 1)) . '">다음 페이지</a>';
        }

        return $html . '</nav>';
    }

    private function requestedPage(): int
    {
        $rawPage = $_GET['audit_page'] ?? null;
        if (!is_string($rawPage) && !is_int($rawPage)) {
            return 1;
        }
        $value = (string) $rawPage;
        if (preg_match('/\A[1-9][0-9]{0,9}\z/D', $value) !== 1) {
            return 1;
        }
        $page = (int) $value;

        return $page > 0 && $page <= intdiv(PHP_INT_MAX, self::PAGE_SIZE) ? $page : 1;
    }

    private function canView(): bool
    {
        return $this->viewAccess() && !empty($this->tabAccess['view']);
    }

    private function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
