<?php

declare(strict_types=1);
require_once dirname(__DIR__, 2) . '/autoload.php';

use Ordenowa\Procurement\Integration\Runtime;
use Ordenowa\Procurement\Security\Actor;

class AdminOrdenowaProcurementController extends \Ordenowa\Procurement\Integration\AdminController
{
    protected string $procurementTab = 'AdminOrdenowaProcurement';
    protected string $procurementTitle = '회원별 상품 발주 안내';

    private function nativeChoices(): string
    {
        $choices = Runtime::assignmentChoices();
        $html = '<details><summary>최근 회원·상품·옵션 번호 확인</summary><p>목록에 없는 이전 상품과 회원도 번호로 선택할 수 있습니다. 수집 상품은 상품 검수 대기열에서 검토·등록을 완료해 주세요.</p><h4>최근 활성 회원</h4><ul>';
        foreach ($choices['customers'] as $customer) {
            $html .= '<li>' . (int) $customer['id_customer'] . ' · ' . self::escape(trim((string) $customer['firstname'] . ' ' . (string) $customer['lastname'])) . '</li>';
        }
        $html .= '</ul><h4>최근 등록 상품 (비활성 상품 포함)</h4><ul>';
        foreach ($choices['products'] as $product) {
            $html .= '<li>상품 ' . (int) $product['id_product'] . ' · ' . self::escape((string) ($product['name'] ?? $product['reference'])) . '</li>';
        }
        $html .= '</ul><h4>상품별 정확한 옵션</h4><ul>';
        foreach ($choices['variants'] as $variant) {
            $html .= '<li>상품 ' . (int) $variant['id_product'] . ' → 옵션 ' . (int) $variant['id_product_attribute'] . ' · ' . self::escape((string) $variant['reference']) . '</li>';
        }
        $html .= '</ul><h4>기존 상품 이미지 번호 (사용 권리 확인 후 선택)</h4><ul>';
        foreach ($choices['images'] as $image) $html .= '<li>상품 ' . (int) $image['id_product'] . ' → 이미지 ' . (int) $image['id_image'] . '</li>';
        return $html . '</ul></details>';
    }

    protected function renderPage(Actor $actor): string
    {
        $html = '<p>이 쇼핑몰에 등록된 활성 회원에게 상품과 정확한 옵션을 지정합니다. 상품의 판매 활성화나 배송지 입력은 필요하지 않습니다.</p>';
        if (Runtime::nativePermission($this->procurementTab, 'ADD')) {
            $html .= '<h3>발주 안내 등록</h3>' . $this->formStart('assign')
                . $this->field('id_customer', '회원 번호', 'number')
                . $this->field('id_product', '등록 상품 번호', 'number')
                . $this->field('id_product_attribute', '정확한 상품 옵션 번호 (옵션 없는 상품은 0)', 'number', '0')
                . $this->field('default_quantity', '기본 수량', 'number', '1')
                . $this->field('max_quantity', '최대 수량', 'number', '1')
                . $this->field('instructions', '회원에게 보낼 발주 안내', 'text', '', false)
                . $this->field('deadline', '마감 일시 (UTC, 예: 2026-12-31 12:00:00)', 'text', '', false)
                . '<details><summary>직접 등록 상품의 공개 이미지 권리 확인 (선택)</summary><p>직접 소유하거나 공개 사용 허가를 받은 기존 상품 이미지만 선택하세요. 미입력 시 사진을 노출하지 않습니다. 수집 상품 이미지는 원본 검토 절차에서만 승인합니다.</p>'
                . $this->field('manual_image_ids', '공개할 기존 상품 이미지 번호 (쉼표 구분, 최대 20개)', 'text', '', false)
                . $this->field('manual_image_rights', '이미지 소유·공개 사용 허가 근거를 확인했습니다 (근거 기재)', 'text', '', false) . '</details>'
                . $this->submitButton('assign', '상품 발주 안내 보내기') . $this->nativeChoices();
        }
        $rows = [];
        $assignments = Runtime::requests()->adminAssignments($actor, $this->listingFilters());
        foreach (array_slice($assignments, 0, 50) as $assignment) {
            $action = '';
            if ($assignment['status'] === 'ACTIVE' && Runtime::nativePermission($this->procurementTab, 'EDIT')) {
                $action = $this->formStart('revoke', ['id_assignment' => $assignment['id_assignment'], 'version' => $assignment['version']])
                    . $this->reasonField() . $this->submitButton('revoke', '제출 전 안내 회수');
            }
            $rows[] = [
                '<span data-assignment-id="' . (int) $assignment['id_assignment'] . '">' . (int) $assignment['id_assignment'] . '</span>',
                (string) (int) $assignment['id_customer'], $this->productLabel($assignment),
                (int) $assignment['default_quantity'] . ' / ' . (int) $assignment['max_quantity'],
                self::escape((string) ($assignment['instructions'] ?? '')), self::escape((string) ($assignment['deadline'] ?? '')),
                $this->status($assignment['status']), $action,
            ];
        }
        return $html . '<h3>발주 안내 내역</h3>' . $this->filterForm(['ACTIVE','REQUESTED','CANCELLED','EXPIRED'])
            . $this->table(['안내 번호', '회원 번호', '상품·옵션', '기본 / 최대 수량', '안내', '마감 (UTC)', '상태', '회수'], $rows)
            . $this->nextPage($assignments, 'id_assignment');
    }
}
