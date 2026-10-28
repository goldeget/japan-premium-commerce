<?php

declare(strict_types=1);
require_once dirname(__DIR__, 2) . '/autoload.php';

use Ordenowa\Procurement\Integration\Runtime;
use Ordenowa\Procurement\Security\Actor;

class AdminOrdenowaProcurementPointsController extends \Ordenowa\Procurement\Integration\AdminController
{
    protected string $procurementTab = 'AdminOrdenowaProcurementPoints';
    protected string $procurementTitle = '수당 포인트 수동 지급·정정';

    protected function renderPage(Actor $actor): string
    {
        $points = Runtime::points();
        $awardFilters = ['limit' => 51, 'before_id' => max(0, (int) \Tools::getValue('award_before', 0))];
        if ($awardFilters['before_id'] === 0) unset($awardFilters['before_id']);
        $awards = $points->awards($actor, $awardFilters);
        $pendingFilters = $this->listingFilters();
        $pendingFilters['status'] = 'APPROVED';
        $pendingFilters['unawarded'] = true;
        $requests = Runtime::requests()->adminRequests($actor, $pendingFilters);
        $pending = [];
        foreach (array_slice($requests, 0, 50) as $request) {
            $action = '';
            if (Runtime::nativePermission($this->procurementTab, 'ADD')) {
                $action = $this->formStart('award', ['id_request' => $request['id_request'], 'idempotency_key' => bin2hex(random_bytes(24))])
                    . $this->field('amount', '지급할 정수 포인트 (P)', 'number') . $this->reasonField()
                    . $this->submitButton('award', '승인 요청에 포인트 수동 지급');
            }
            $pending[] = [(string) (int) $request['id_request'], (string) (int) $request['id_customer'], $this->productLabel($request), (string) (int) $request['quantity'], $action];
        }
        $rows = [];
        foreach (array_slice($awards, 0, 50) as $award) {
            $action = '';
            if (Runtime::nativePermission($this->procurementTab, 'EDIT')) {
                $action = $this->formStart('correct', ['id_award' => $award['id_award'], 'idempotency_key' => bin2hex(random_bytes(24))])
                    . $this->field('delta', '연결 정정 포인트 (차감은 음수, 예: -20)', 'number') . $this->reasonField()
                    . $this->submitButton('correct', '원본 지급에 연결하여 정정');
            }
            $account = $points->account($actor, (int) $award['id_customer']);
            $rows[] = ['<span data-award-id="' . (int) $award['id_award'] . '">' . (int) $award['id_award'] . '</span>',
                (string) (int) $award['id_request'], '<a href="' . self::escape($this->url(['customer_id' => (int) $award['id_customer']])) . '">' . (int) $award['id_customer'] . ' 원장 조회</a>', (int) $award['amount'] . ' P',
                (int) ($account['balance'] ?? 0) . ' P', self::escape((string) $award['created_at']), $action];
        }
        $html = '<p>승인 요청마다 기본 지급은 한 번입니다. 포인트는 수당 기록이며 현금·출금 가능액이 아닙니다. 정정은 원본과 연결되어 이력을 보존합니다.</p>'
            . '<h3>승인 · 포인트 지급 대기</h3>' . $this->filterForm(['APPROVED']) . $this->table(['요청 번호', '회원 번호', '상품·옵션', '수량', '별도 수동 지급'], $pending) . $this->nextPage($requests, 'id_request')
            . '<h3>지급 내역 · 연결 정정</h3>' . $this->table(['지급 번호', '요청 번호', '회원 번호', '원본 지급', '회원 현재 잔액', '지급 일시 (UTC)', '정정'], $rows)
            . $this->nextPage($awards, 'id_award', ['before_id' => $pendingFilters['before_id'], 'award_before' => (int) ($awards[49]['id_award'] ?? 0)]);
        $customer = max(0, (int) \Tools::getValue('customer_id', 0));
        $ledgerRows = [];
        $ledger = [];
        if ($customer > 0) {
            $ledgerFilters = ['limit' => 51];
            $ledgerBefore = max(0, (int) \Tools::getValue('ledger_before', 0));
            if ($ledgerBefore > 0) $ledgerFilters['before_id'] = $ledgerBefore;
            $ledger = $points->ledger($actor, $customer, $ledgerFilters);
            $account = $points->account($actor, $customer);
            $consistent = $points->reconcile($actor, $customer);
            $html .= '<p>회원 ' . $customer . ' · 현재 잔액 ' . (int) $account['balance'] . ' P · 원장 대조: '
                . ($consistent['consistent'] ? '일치' : '불일치 — 지급을 중단하고 확인해 주세요.') . '</p>';
            foreach (array_slice($ledger, 0, 50) as $entry) {
                $ledgerRows[] = [(string) (int) $entry['id_ledger'], (string) $customer, (string) (int) $entry['id_award'],
                    (int) $entry['delta'] . ' P', self::escape((string) $entry['reason']), self::escape((string) $entry['created_at'])];
            }
        }
        return $html . '<h3>적립·정정 원장</h3>'
            . ($customer > 0 ? '' : '<p>지급 내역의 회원 번호를 선택하면 해당 회원의 원장과 잔액 대조를 표시합니다.</p>')
            . $this->table(['원장 번호', '회원 번호', '연결 지급', '증감', '사유', '기록 일시 (UTC)'], $ledgerRows)
            . $this->nextPage($ledger, 'id_ledger', ['before_id' => $pendingFilters['before_id'], 'customer_id' => $customer, 'ledger_before' => (int) ($ledger[49]['id_ledger'] ?? 0)]);
    }
}
