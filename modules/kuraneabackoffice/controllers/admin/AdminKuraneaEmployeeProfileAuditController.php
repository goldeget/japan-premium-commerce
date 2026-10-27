<?php

declare(strict_types=1);

require_once dirname(__DIR__, 2) . '/vendor/autoload.php';

use Kuranea\Backoffice\Infrastructure\AdminAuditEventRepository;
use PrestaShop\PrestaShop\Core\Security\Permission;

class AdminKuraneaEmployeeProfileAuditController extends ModuleAdminController
{
    private const PAGE_SIZE = 50;

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '관리자 감사 기록';
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
            $this->content = '<div class="alert alert-danger">관리자 감사 기록을 조회할 권한이 없습니다.</div>';
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
            $authorizedSources = ['employee_profile'];
            if ($this->canViewOrderHistory()) {
                $authorizedSources[] = 'order_history';
            }
            if ($this->canViewSourceTab('ADMINKURANEASUPPORTASSIGNMENTS')) {
                $authorizedSources[] = 'support_assignment';
            }
            if ($this->canViewSourceTab('ADMINBUSINESSPROFILETRANSFERS')) {
                $authorizedSources[] = 'bank_transfer_instruction';
                $authorizedSources[] = 'bank_transfer_receipt';
            }
            $result = (new AdminAuditEventRepository())->pageForShop($shopId, $page, $authorizedSources);
            $baseUrl = (string) $this->context->link->getAdminLink('AdminKuraneaEmployeeProfileAudit');
            $this->content .= '<div class="panel"><h3>관리자 감사 기록</h3>'
                . '<p>이 화면은 현재 계정이 조회할 수 있는 기존 기록만 출처별로 표시합니다. 권한 설정 표의 개별 접근 권한 변경이나 기록되지 않은 작업은 포함되지 않습니다.</p>'
                . $this->renderEvents($result['rows']);
            $this->content .= $this->renderPagination(
                $baseUrl,
                $page,
                $result['has_next']
            )
                . '</div>';
        } catch (Throwable) {
            http_response_code(503);
            $this->content .= '<div class="alert alert-danger">관리자 감사 기록을 불러오지 못했습니다.</div>';
        }

        $this->context->smarty->assign('content', $this->content);
    }

    /** @param list<array{source:string,event_id:int,event_at:string,time_basis:string,actor_employee_id:?int,action:string,target_type:string,target_id:int}> $rows */
    private function renderEvents(array $rows): string
    {
        if ($rows === []) {
            return '<p>현재 권한으로 조회할 수 있는 기록이 없습니다.</p>';
        }

        $html = '<div class="table-responsive"><table class="table"><thead><tr>'
            . '<th>기록 시각</th><th>출처</th><th>작업</th><th>처리 관리자</th><th>대상</th>'
            . '</tr></thead><tbody>';
        foreach ($rows as $row) {
            $actorId = $row['actor_employee_id'];
            $sourceLabel = self::sourceLabel($row['source']);
            $actionLabel = self::actionLabel($row['action']);
            $targetLabel = self::targetLabel($row['target_type']);
            $timeLabel = $row['time_basis'] === 'UTC' ? 'UTC' : '저장값';
            $actorLabel = $actorId === null ? '시스템 또는 확인할 수 없음' : '관리자 #' . $actorId;
            $html .= '<tr><td>' . $this->escape($row['event_at'] . ' (' . $timeLabel . ')') . '</td>'
                . '<td>' . $this->escape($sourceLabel) . '</td>'
                . '<td>' . $this->escape($actionLabel) . '</td>'
                . '<td>' . $this->escape($actorLabel) . '</td>'
                . '<td>' . $this->escape($targetLabel . ' #' . $row['target_id']) . '</td></tr>';
        }
        $html .= '</tbody></table></div>';

        return $html;
    }

    private static function sourceLabel(string $source): string
    {
        return match ($source) {
            'employee_profile' => '관리자 프로필',
            'order_history' => '주문 상태',
            'support_assignment' => '상담 배정',
            'bank_transfer_instruction' => '입금 안내',
            'bank_transfer_receipt' => '입금 확인',
            default => '기타',
        };
    }

    private static function actionLabel(string $action): string
    {
        return match ($action) {
            'employee_profile_changed' => '관리자 프로필 변경',
            'order_status_changed' => '주문 상태 변경',
            'support_assigned' => '담당자 지정',
            'support_reassigned' => '담당자 변경',
            'bank_transfer_instruction_issued' => '입금 안내 발급',
            'bank_transfer_receipt_confirmed' => '입금 확인 기록',
            default => '확인할 수 없는 작업',
        };
    }

    private static function targetLabel(string $targetType): string
    {
        return match ($targetType) {
            'employee' => '관리자',
            'order' => '주문',
            'support_thread' => '문의',
            default => '대상',
        };
    }

    private function renderPagination(string $baseUrl, int $page, bool $hasNext): string
    {
        $html = '<nav aria-label="관리자 감사 기록 페이지"><p>' . $page . '페이지</p>';
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

    private function canViewOrderHistory(): bool
    {
        return $this->canViewSourceTab('ADMINORDERS');
    }

    private function canViewSourceTab(string $tabClass): bool
    {
        $profileId = (int) ($this->context->employee->id_profile ?? 0);

        return $profileId > 0
            && Access::isGranted(Permission::PREFIX_TAB . strtoupper($tabClass) . '_READ', $profileId);
    }

    private function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
