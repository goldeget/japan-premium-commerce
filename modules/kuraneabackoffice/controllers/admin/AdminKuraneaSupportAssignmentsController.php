<?php

declare(strict_types=1);

require_once dirname(__FILE__, 3) . '/vendor/autoload.php';

use Kuranea\Backoffice\Infrastructure\SupportAssignmentRepository;

class AdminKuraneaSupportAssignmentsController extends ModuleAdminController
{
    private string $feedback = '';
    private bool $feedbackIsError = false;
    private bool $assignmentPostHandled = false;
    private string $assignmentOutcome = 'not_started';

    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '고객 문의 담당자';
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
            $this->content = '<div class="alert alert-danger">고객 문의를 조회할 권한이 없습니다.</div>';
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
            $repository = new SupportAssignmentRepository();
            $this->processAssignment($shopId, $repository);
            $page = $this->requestedPage();
            $threads = $repository->threadsForShop($shopId, $page);
            $hasNextPage = count($threads) > 100;
            if ($hasNextPage) {
                array_pop($threads);
            }
            $employees = $repository->employeesForShop($shopId);
            $selectedThread = $this->selectedThread($shopId, $repository);
            $history = $selectedThread !== null
                ? $repository->historyForThread($shopId, $selectedThread['id_customer_thread'])
                : [];

            $actionUrl = (string) $this->context->link->getAdminLink('AdminKuraneaSupportAssignments');
            $paginationUrl = $actionUrl;
            $actionUrl .= '&support_page=' . $page;
            $token = (string) $this->token;
            $this->content .= $this->renderFeedback();
            $this->content .= '<div class="panel"><h3>고객 문의 담당자 지정</h3>'
                . '<p>선택한 쇼핑몰의 문의에 활성 관리자를 지정합니다. 문의 본문, 고객 연락처와 주소는 이 화면에 표시하지 않습니다.</p>'
                . $this->renderThreadTable($threads, $employees, $actionUrl, $token)
                . $this->renderPagination($paginationUrl, $page, $hasNextPage);
            if ($selectedThread !== null) {
                $this->content .= $this->renderHistory($selectedThread, $history);
            }
            $this->content .= '</div>';
        } catch (Throwable) {
            http_response_code(503);
            $this->assignmentOutcome = $this->assignmentOutcome === 'success'
                ? 'post_commit_render_failure'
                : 'controller_failure';
            $this->content .= '<div class="alert alert-danger" data-ordenowa-support-assignment-feedback="true">'
                . '고객 문의 담당자 화면을 불러오지 못했습니다. 쇼핑몰과 권한을 확인해 주세요.</div>'
                . $this->renderIsolatedCiAssignmentEvidence();
        }

        $this->context->smarty->assign('content', $this->content);
    }

    private function processAssignment(int $shopId, SupportAssignmentRepository $repository): void
    {
        if (strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? '')) !== 'POST'
            || !Tools::isSubmit('submitOrdenowaSupportAssignment')) {
            return;
        }
        $this->assignmentPostHandled = true;

        if (!$this->hasValidAdminMutationToken()) {
            $this->fail('관리자 보안 토큰이 올바르지 않습니다. 페이지를 새로고침한 후 다시 시도해 주세요.', 'csrf_rejected');

            return;
        }

        $threadId = self::positivePostId('id_customer_thread');
        $employeeId = self::positivePostId('id_employee');
        if ($threadId === null || $employeeId === null) {
            $this->fail('문의 번호와 담당자를 다시 선택해 주세요.', 'invalid_request');

            return;
        }
        if ($repository->threadForShop($shopId, $threadId) === null) {
            $this->fail('선택한 쇼핑몰의 문의를 찾을 수 없습니다.', 'thread_not_found');

            return;
        }

        $actorEmployeeId = (int) ($this->context->employee->id ?? 0);
        if ($actorEmployeeId < 1) {
            $this->fail('현재 관리자 계정을 확인할 수 없습니다.', 'employee_missing');

            return;
        }

        try {
            $result = $repository->assign(
                $shopId,
                $threadId,
                $employeeId,
                $actorEmployeeId,
                $this->canCreate(),
                $this->canUpdate()
            );
            $this->succeed($result['changed']
                ? '문의 담당자를 저장하고 변경 이력을 기록했습니다.'
                : '선택한 담당자가 이미 지정되어 있습니다.');
        } catch (InvalidArgumentException $exception) {
            $message = $exception->getMessage();
            $outcome = match ($message) {
                '선택한 쇼핑몰의 문의를 찾을 수 없습니다.' => 'thread_not_found',
                '선택한 담당자가 이 쇼핑몰의 활성 관리자 계정이 아닙니다.' => 'employee_ineligible',
                '현재 관리자 계정을 확인할 수 없습니다.' => 'employee_missing',
                '고객 문의 담당자를 지정할 권한이 없습니다.' => 'create_permission_denied',
                '고객 문의 담당자를 변경할 권한이 없습니다.' => 'update_permission_denied',
                default => 'assignment_rejected',
            };
            $this->fail(in_array($message, [
                '선택한 쇼핑몰의 문의를 찾을 수 없습니다.',
                '선택한 담당자가 이 쇼핑몰의 활성 관리자 계정이 아닙니다.',
                '현재 관리자 계정을 확인할 수 없습니다.',
                '고객 문의 담당자를 지정할 권한이 없습니다.',
                '고객 문의 담당자를 변경할 권한이 없습니다.',
            ], true) ? $message : '담당자를 지정하지 못했습니다. 입력한 값을 확인해 주세요.', $outcome);
        } catch (Throwable) {
            $this->fail('담당자를 저장하지 못했습니다. 다시 조회한 후 시도해 주세요.', 'storage_failure');
        }
    }

    /** @param list<array<string, mixed>> $threads @param list<array{id_employee:int,firstname:string,lastname:string}> $employees */
    private function renderThreadTable(array $threads, array $employees, string $actionUrl, string $token): string
    {
        if ($threads === []) {
            return '<p>표시할 고객 문의가 없습니다.</p>';
        }

        $html = '<div class="table-responsive"><table class="table">'
            . '<thead><tr><th>문의 번호</th><th>접수 시각</th><th>상태</th><th>현재 담당자</th><th>담당자 변경</th></tr></thead><tbody>';
        foreach ($threads as $thread) {
            $threadId = (int) ($thread['id_customer_thread'] ?? 0);
            if ($threadId < 1) {
                continue;
            }
            $currentEmployeeId = max(0, (int) ($thread['id_employee'] ?? 0));
            $currentName = trim((string) ($thread['assigned_firstname'] ?? '') . ' ' . (string) ($thread['assigned_lastname'] ?? ''));
            if ($currentEmployeeId > 0 && $currentName === '') {
                $currentName = '관리자 #' . $currentEmployeeId;
            }
            if ($currentEmployeeId < 1) {
                $currentName = '미지정';
            }

            $canWrite = $currentEmployeeId > 0 ? $this->canUpdate() : $this->canCreate();
            $html .= '<tr><td>' . $threadId . '</td>'
                . '<td>' . $this->escape((string) ($thread['date_add'] ?? '')) . '</td>'
                . '<td>' . $this->escape($this->statusLabel((string) ($thread['status'] ?? ''))) . '</td>'
                . '<td>' . $this->escape($currentName) . '</td><td>';
            if ($employees === []) {
                $html .= '<span>이 쇼핑몰에 지정할 수 있는 활성 담당자가 없습니다.</span>';
            } elseif (!$canWrite) {
                $html .= '<span>변경 권한이 없습니다.</span>';
            } else {
                $html .= '<form method="post" action="' . $this->escape($actionUrl) . '">'
                    . '<input type="hidden" name="token" value="' . $this->escape($token) . '">'
                    . '<input type="hidden" name="id_customer_thread" value="' . $threadId . '">'
                    . '<select class="form-control" name="id_employee" required>';
                if ($currentEmployeeId < 1) {
                    $html .= '<option value="" selected disabled>담당자를 선택해 주세요</option>';
                }
                $currentIsListed = false;
                foreach ($employees as $employee) {
                    $employeeId = (int) $employee['id_employee'];
                    $selected = $employeeId === $currentEmployeeId;
                    $currentIsListed = $currentIsListed || $selected;
                    $name = trim($employee['firstname'] . ' ' . $employee['lastname']);
                    $html .= '<option value="' . $employeeId . '"' . ($selected ? ' selected' : '') . '>'
                        . $this->escape($name !== '' ? $name : '관리자 #' . $employeeId) . '</option>';
                }
                if ($currentEmployeeId > 0 && !$currentIsListed) {
                    $html .= '<option value="' . $currentEmployeeId . '" selected disabled>'
                        . $this->escape('비활성 또는 이 쇼핑몰에 연결되지 않은 담당자 #' . $currentEmployeeId) . '</option>';
                }
                $html .= '</select><button class="btn btn-primary" type="submit"'
                    . ' name="submitOrdenowaSupportAssignment" value="1">담당자 저장</button></form>';
            }
            $html .= ' <a href="' . $this->escape($actionUrl . '&id_customer_thread=' . $threadId) . '">변경 이력 보기</a>'
                . '</td></tr>';
        }
        $html .= '</tbody></table></div>';

        return $html;
    }

    private function statusLabel(string $status): string
    {
        return match ($status) {
            'open' => '접수',
            'closed' => '종결',
            'pending1' => '보류 1',
            'pending2' => '보류 2',
            default => '상태 확인 필요',
        };
    }

    /** @param array{id_customer_thread:int,status:string,date_add:string} $thread @param list<array<string, mixed>> $history */
    private function renderHistory(array $thread, array $history): string
    {
        $html = '<h3>문의 #' . $thread['id_customer_thread'] . ' 담당자 변경 이력</h3>';
        if ($history === []) {
            return $html . '<p>저장된 담당자 변경 이력이 없습니다.</p>';
        }

        $html .= '<div class="table-responsive"><table class="table"><thead><tr>'
            . '<th>변경 시각 (UTC)</th><th>이전 담당자</th><th>새 담당자</th><th>처리 관리자</th>'
            . '</tr></thead><tbody>';
        foreach ($history as $event) {
            $fromId = (int) ($event['from_employee_id'] ?? 0);
            $fromName = $fromId > 0
                ? trim((string) ($event['from_firstname'] ?? '') . ' ' . (string) ($event['from_lastname'] ?? ''))
                : '최초 지정';
            $toId = (int) ($event['to_employee_id'] ?? 0);
            $toName = trim((string) ($event['to_firstname'] ?? '') . ' ' . (string) ($event['to_lastname'] ?? ''));
            $actorId = (int) ($event['actor_employee_id'] ?? 0);
            $actorName = trim((string) ($event['actor_firstname'] ?? '') . ' ' . (string) ($event['actor_lastname'] ?? ''));
            $html .= '<tr><td>' . $this->escape((string) ($event['changed_at_utc'] ?? '')) . '</td>'
                . '<td>' . $this->escape($fromName !== '' ? $fromName : ($fromId > 0 ? '관리자 #' . $fromId : '최초 지정')) . '</td>'
                . '<td>' . $this->escape($toName !== '' ? $toName : '관리자 #' . $toId) . '</td>'
                . '<td>' . $this->escape($actorName !== '' ? $actorName : '관리자 #' . $actorId) . '</td></tr>';
        }
        $html .= '</tbody></table></div>';

        return $html;
    }

    /** @return array{id_customer_thread:int,status:string,date_add:string}|null */
    private function selectedThread(int $shopId, SupportAssignmentRepository $repository): ?array
    {
        $threadId = self::positiveRawId($_GET['id_customer_thread'] ?? null);
        return $threadId === null ? null : $repository->threadForShop($shopId, $threadId);
    }

    private function requestedPage(): int
    {
        $page = self::positiveRawId($_GET['support_page'] ?? null);
        return $page !== null && $page <= intdiv(PHP_INT_MAX, 100) ? $page : 1;
    }

    private function renderPagination(string $actionUrl, int $page, bool $hasNextPage): string
    {
        $html = '<nav aria-label="고객 문의 목록 페이지"><p>' . $page . '페이지</p>';
        if ($page > 1) {
            $html .= '<a class="btn btn-default" rel="prev" href="'
                . $this->escape($actionUrl . '&support_page=' . ($page - 1)) . '">이전 페이지</a> ';
        }
        if ($hasNextPage) {
            $html .= '<a class="btn btn-default" rel="next" href="'
                . $this->escape($actionUrl . '&support_page=' . ($page + 1)) . '">다음 페이지</a>';
        }
        return $html . '</nav>';
    }

    private static function positivePostId(string $name): ?int
    {
        return self::positiveRawId($_POST[$name] ?? null);
    }

    private static function positiveRawId(mixed $value): ?int
    {
        if (!is_string($value) || preg_match('/\A[1-9][0-9]{0,9}\z/D', $value) !== 1) {
            return null;
        }

        $id = (int) $value;
        return $id > 0 ? $id : null;
    }

    private function canView(): bool
    {
        return $this->viewAccess() && !empty($this->tabAccess['view']);
    }

    private function canCreate(): bool
    {
        return $this->canView() && $this->access('add') && !empty($this->tabAccess['add']);
    }

    private function canUpdate(): bool
    {
        return $this->canView() && $this->access('edit') && !empty($this->tabAccess['edit']);
    }

    private function succeed(string $message): void
    {
        $this->feedback = $message;
        $this->feedbackIsError = false;
        $this->assignmentOutcome = 'success';
    }

    private function fail(string $message, string $outcome): void
    {
        $this->feedback = $message;
        $this->feedbackIsError = true;
        $this->assignmentOutcome = $outcome;
    }

    private function renderFeedback(): string
    {
        if ($this->feedback === '') {
            return '';
        }
        $class = $this->feedbackIsError ? 'danger' : 'success';
        return '<div class="alert alert-' . $class
            . '" data-ordenowa-support-assignment-feedback="true">'
            . $this->escape($this->feedback) . '</div>' . $this->renderIsolatedCiAssignmentEvidence();
    }

    private function renderIsolatedCiAssignmentEvidence(): string
    {
        $runId = (string) getenv('GITHUB_RUN_ID');
        $runAttempt = (string) getenv('GITHUB_RUN_ATTEMPT');
        $isIsolatedCiRun = getenv('CI') === 'true'
            && getenv('GITHUB_ACTIONS') === 'true'
            && preg_match('/\A[0-9]+\z/D', $runId) === 1
            && preg_match('/\A[0-9]+\z/D', $runAttempt) === 1
            && getenv('KURANEA_CI_PROJECT_NAME') === 'kuranea-ci-' . $runId . '-' . $runAttempt;
        if (!$this->assignmentPostHandled || !$isIsolatedCiRun) {
            return '';
        }

        $allowedOutcomes = [
            'success', 'csrf_rejected', 'invalid_request', 'thread_not_found', 'employee_missing',
            'employee_ineligible', 'create_permission_denied', 'update_permission_denied',
            'assignment_rejected', 'storage_failure', 'post_commit_render_failure', 'controller_failure',
        ];
        $outcome = in_array($this->assignmentOutcome, $allowedOutcomes, true)
            ? $this->assignmentOutcome
            : 'controller_failure';

        $submittedToken = isset($_POST['token']) && is_string($_POST['token']) ? $_POST['token'] : '';
        $queryToken = isset($_GET['token']) && is_string($_GET['token']) ? $_GET['token'] : '';
        $csrfEvidence = [
            'post-value-present' => $submittedToken !== '',
            'post-matches-query' => $queryToken !== '' && hash_equals($queryToken, $submittedToken),
            'post-native-csrf-valid' => $this->hasValidAdminMutationToken(),
        ];
        $attributes = '';
        foreach ($csrfEvidence as $name => $matches) {
            $attributes .= ' data-' . $name . '="' . ($matches ? 'true' : 'false') . '"';
        }

        return '<span id="ordenowa-ci-support-assignment-evidence" hidden data-outcome="'
            . $this->escape($outcome) . '"' . $attributes . '></span>';
    }

    private function hasValidAdminMutationToken(): bool
    {
        $submittedToken = isset($_POST['token']) && is_string($_POST['token']) ? $_POST['token'] : '';
        $queryToken = isset($_GET['token']) && is_string($_GET['token']) ? $_GET['token'] : '';
        if ($submittedToken === '' || $queryToken === '' || !hash_equals($queryToken, $submittedToken)) {
            return false;
        }

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

    private function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
