<?php

declare(strict_types=1);
require_once dirname(__DIR__, 2) . '/autoload.php';

use Ordenowa\Procurement\Integration\Runtime;
use Ordenowa\Procurement\Security\Actor;

class AdminOrdenowaProcurementReviewsController extends \Ordenowa\Procurement\Integration\AdminController
{
    protected string $procurementTab = 'AdminOrdenowaProcurementReviews';
    protected string $procurementTitle = '상품 발주 요청 검토';

    protected function renderPage(Actor $actor): string
    {
        $rows = [];
        $requests = Runtime::requests()->adminRequests($actor, $this->listingFilters());
        foreach (array_slice($requests, 0, 50) as $request) {
            $action = '';
            if ($request['status'] === 'SUBMITTED' && Runtime::nativePermission($this->procurementTab, 'EDIT')) {
                $action = $this->formStart('review', ['id_request' => $request['id_request'], 'version' => $request['version']])
                    . '<label>검토 결과 <select class="form-control" name="decision" required><option value="">선택해 주세요</option><option value="APPROVED">승인</option><option value="REJECTED">반려</option><option value="CANCELLED">취소</option></select></label>'
                    . $this->reasonField() . $this->submitButton('review', '검토 결과 저장');
            }
            $support = '';
            $supportClass = '\\Ordenowa\\Procurement\\Support\\SupportService';
            if (class_exists($supportClass) && method_exists($supportClass, 'adminThreadId') && Runtime::nativePermission('AdminCustomerThreads', 'READ')) {
                $thread = (new $supportClass(Runtime::database()))->adminThreadId($actor, (int) $request['id_request']);
                if ($thread !== null) $support = '<a data-testid="procurement-admin-support" href="' . self::escape((string) $this->context->link->getAdminLink('AdminCustomerThreads') . '&id_customer_thread=' . (int) $thread . '&viewcustomer_thread=1') . '">이 발주 요청의 고객 문의</a>';
            }
            $rows[] = [
                '<span data-request-id="' . (int) $request['id_request'] . '">' . (int) $request['id_request'] . '</span>',
                (string) (int) $request['id_customer'], $this->productLabel($request), (string) (int) $request['quantity'],
                $this->status($request['status']), self::escape((string) ($request['review_reason'] ?? '')), $action . $support,
            ];
        }
        return '<p>상품·옵션·수량·회원과 안내 내역을 확인해 주세요. 검토 승인은 포인트를 지급하지 않습니다. 최종 결과는 변경할 수 없습니다.</p>'
            . $this->filterForm(['SUBMITTED','APPROVED','REJECTED','CANCELLED']) . $this->table(['요청 번호', '회원 번호', '상품·옵션', '수량', '검토 상태', '검토 사유', '수동 검토'], $rows) . $this->nextPage($requests, 'id_request');
    }
}
