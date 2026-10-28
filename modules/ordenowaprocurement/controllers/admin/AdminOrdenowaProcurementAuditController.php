<?php

declare(strict_types=1);
require_once dirname(__DIR__, 2) . '/autoload.php';

use Ordenowa\Procurement\Integration\Runtime;
use Ordenowa\Procurement\Security\Actor;

class AdminOrdenowaProcurementAuditController extends \Ordenowa\Procurement\Integration\AdminController
{
    protected string $procurementTab = 'AdminOrdenowaProcurementAudit';
    protected string $procurementTitle = '발주·포인트 감사 기록';

    protected function renderPage(Actor $actor): string
    {
        $actor->require('audit.read');
        $db = Runtime::database();
        $page = min(100000, max(1, (int) \Tools::getValue('page', 1)));
        $rows = $db->all('SELECT id_activity,actor_type,actor_id,action,target_type,target_id,created_at FROM ' . $db->table('activity')
            . ' WHERE id_shop=' . $actor->shopId . ' ORDER BY id_activity DESC LIMIT 51 OFFSET ' . (($page - 1) * 50));
        $more = count($rows) > 50;
        $display = [];
        $actions = ['assignment.created' => '발주 안내 등록', 'assignment.revoked' => '발주 안내 회수', 'request.submitted' => '발주 요청 제출',
            'request.reviewed' => '발주 요청 검토', 'points.awarded' => '수당 포인트 지급', 'points.corrected' => '수당 포인트 정정', 'points.reconciliation_failed' => '포인트 원장 대조 불일치', 'policy.updated' => '서비스 운영 정책 변경', 'support.message_created' => '발주 요청 문의 등록'];
        $targets = ['assignment' => '발주 안내', 'request' => '발주 요청', 'review' => '검토', 'policy' => '서비스 운영 정책', 'point_account' => '포인트 계정', 'point_award' => '포인트 지급', 'point_ledger' => '포인트 원장', 'ledger' => '포인트 원장', 'award' => '포인트 지급'];
        foreach (array_slice($rows, 0, 50) as $row) {
            $display[] = [(string) (int) $row['id_activity'], $row['actor_type'] === 'employee' ? '운영자' : '회원',
                (string) (int) $row['actor_id'], self::escape($actions[$row['action']] ?? $row['action']),
                self::escape($targets[$row['target_type']] ?? $row['target_type']), (string) (int) $row['target_id'], self::escape((string) $row['created_at'])];
        }
        $html = '<p>현재 쇼핑몰의 실제 처리 대상과 처리자를 조회합니다. 감사 기록은 이 화면에서 변경하거나 삭제할 수 없습니다.</p>'
            . $this->table(['기록 번호', '처리자 유형', '처리자 번호', '처리 내용', '처리 대상', '대상 번호', '기록 일시 (UTC)'], $display);
        if ($page > 1) {
            $html .= '<a class="btn btn-default" href="' . self::escape($this->url(['page' => $page - 1])) . '">이전</a> ';
        }
        if ($more) {
            $html .= '<a class="btn btn-default" href="' . self::escape($this->url(['page' => $page + 1])) . '">다음</a>';
        }
        return $html . $this->deliveries($actor);
    }
    private function deliveries(Actor $actor): string
    {
        $db = Runtime::database();
        $page = min(100000, max(1, (int) \Tools::getValue('delivery_page', 1)));
        $rows = $db->all('SELECT id_delivery,id_notification,channel,status,attempts,last_error_code,claimed_at,sent_at FROM '
            . $db->table('notification_delivery') . ' WHERE id_shop=' . $actor->shopId . ' ORDER BY id_delivery DESC LIMIT 51 OFFSET ' . (($page - 1) * 50));
        $labels = ['PENDING' => '발송 대기', 'SENDING' => '발송 중', 'SENT' => '발송 완료', 'RETRY' => '재시도 대기', 'SKIPPED' => '발송 대상 아님', 'FAILED' => '발송 실패', 'UNCERTAIN' => '전송 결과 확인 필요'];
        $display = [];
        foreach (array_slice($rows, 0, 50) as $row) {
            $code = (string) ($row['last_error_code'] ?? '');
            $display[] = [(string) (int) $row['id_delivery'], (string) (int) $row['id_notification'],
                match ($row['channel']) { 'mail' => '이메일', 'push' => '브라우저 Push', default => '채널 확인 필요' }, self::escape($labels[$row['status']] ?? '확인 필요'),
                (string) (int) $row['attempts'], preg_match('/\A[a-z_]{0,32}\z/D', $code) ? self::escape($code) : '',
                self::escape((string) ($row['claimed_at'] ?? '')), self::escape((string) ($row['sent_at'] ?? ''))];
        }
        $html = '<h3>채널별 알림 발송 상태</h3><p>전송 결과 확인 필요 상태는 중복 발송 가능성을 확인한 뒤 담당 운영자가 서버 작업으로만 재시도합니다. 이 화면은 발송·재시도를 실행하지 않습니다.</p>'
            . $this->table(['발송 번호', '알림 번호', '채널', '상태', '시도 횟수', '진단 코드', '시작 일시 (UTC)', '완료 일시 (UTC)'], $display);
        if ($page > 1) $html .= '<a class="btn btn-default" href="' . self::escape($this->url(['delivery_page' => $page - 1])) . '">발송 상태 이전</a> ';
        if (count($rows) > 50) $html .= '<a class="btn btn-default" href="' . self::escape($this->url(['delivery_page' => $page + 1])) . '">발송 상태 다음</a>';
        return $html;
    }

}
