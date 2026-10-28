<?php

declare(strict_types=1);
require_once dirname(__DIR__, 2) . '/autoload.php';
use Ordenowa\Procurement\Integration\{Runtime, PolicyService};
use Ordenowa\Procurement\Security\Actor;

class AdminOrdenowaProcurementPoliciesController extends \Ordenowa\Procurement\Integration\AdminController
{
    protected string $procurementTab = 'AdminOrdenowaProcurementPolicies';
    protected string $procurementTitle = '서비스 운영자·고객 지원·운영 정책';

    protected function processAction(Actor $actor): void
    {
        if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'POST' || !isset($_POST['save_policy'])) return;
        $token = $_POST['token'] ?? null;
        require_once dirname(__DIR__, 3) . '/kuraneabackoffice/vendor/autoload.php';
        if (!Runtime::nativePermission($this->procurementTab, 'EDIT') || !is_string($token)
            || !\Kuranea\Backoffice\Admin\AdminPostTokenValidator::forController($this, $token)) throw new RuntimeException('정책 수정 권한 또는 보안 토큰을 확인해 주세요.', 403);
        $actor->require('policy.manage');
        $version = $_POST['version'] ?? '';
        if (!is_string($version) || preg_match('/\A(?:0|[1-9][0-9]*)\z/D', $version) !== 1 || filter_var($version, FILTER_VALIDATE_INT) === false) throw new InvalidArgumentException('정책 버전을 확인해 주세요.', 422);
        $payload = [];
        foreach (['operator_name', 'support_email', 'support_phone', 'support_url'] as $field) $payload[$field] = $_POST[$field] ?? '';
        foreach (PolicyService::SECTIONS as $section) foreach (PolicyService::LOCALES as $locale) $payload[$section][$locale] = $_POST[$section . '_' . $locale] ?? '';
        Runtime::policies()->save($actor, (int) $version, $payload);
        Tools::redirectAdmin($this->url(['ordenowa_saved' => '1']));
    }

    protected function renderPage(Actor $actor): string
    {
        $actor->require('policy.read');
        $service = Runtime::policies();
        $current = $service->current($actor->shopId);
        $payload = $current['payload'];
        $missing = $service->missing($payload);
        $labels = ['operator_name' => '실제 서비스 운영자 이름·법인명', 'support_email' => '고객 지원 이메일', 'support_phone' => '고객 지원 전화 (선택)', 'support_url' => '고객 지원 HTTPS URL (선택)', 'terms' => '서비스 이용약관', 'privacy' => '개인정보 처리방침', 'points' => '수당 포인트 정책'];
        $locales = ['ja' => '일본어', 'en' => '영어', 'ko' => '한국어'];
        $html = '<p>실제 운영 주체와 지원 연락처를 입력하세요. 회사 참고정보나 판매자 승인을 운영 권한으로 간주하지 않습니다. 판매·배송·상품 환불·은행 계좌 입력은 필요하지 않습니다.</p>'
            . '<p>현재 정책 버전: ' . (int) $current['version'] . ' · 공개 준비: ' . ($missing === [] ? '완료' : '입력 필요') . '</p>';
        if ($missing !== []) {
            $html .= '<div class="alert alert-warning"><p>다음 실제 정보를 입력하면 정책·운영자 공개 링크가 표시됩니다.</p><ul>';
            foreach ($missing as $field) { $parts = explode('.', $field); $html .= '<li>' . self::escape($labels[$parts[0]] . (isset($parts[1]) ? ' · ' . $locales[$parts[1]] : '')) . '</li>'; }
            $html .= '</ul></div>';
        }
        $canEdit = Runtime::nativePermission($this->procurementTab, 'EDIT');
        $html .= '<form method="post" data-testid="procurement-policy-settings" action="' . self::escape($this->url()) . '">'
            . '<input type="hidden" name="token" value="' . self::escape((string) Tools::getAdminTokenLite($this->procurementTab)) . '">'
            . '<input type="hidden" name="version" value="' . (int) $current['version'] . '"><fieldset' . ($canEdit ? '' : ' disabled') . '>';
        foreach (['operator_name', 'support_email', 'support_phone', 'support_url'] as $field) $html .= $this->field($field, $labels[$field], $field === 'support_email' ? 'email' : ($field === 'support_url' ? 'url' : 'text'), $payload[$field], false);
        foreach (PolicyService::SECTIONS as $section) foreach ($locales as $locale => $label) {
            $name = $section . '_' . $locale;
            $html .= '<div class="form-group"><label for="policy-' . $name . '">' . self::escape($labels[$section] . ' · ' . $label) . '</label><textarea class="form-control" rows="7" id="policy-' . $name . '" name="' . $name . '" maxlength="30000">' . self::escape($payload[$section][$locale]) . '</textarea></div>';
        }
        if ($canEdit) $html .= '<button type="submit" class="btn btn-primary" name="save_policy" value="1">새 정책 버전 저장</button>';
        $html .= '</fieldset></form><h3>변경 이력 (최근 20건)</h3>';
        $rows = [];
        foreach ($service->history($actor) as $row) $rows[] = [(string) (int) $row['version'], (string) (int) $row['id_employee'], self::escape((string) $row['created_at'])];
        return $html . $this->table(['정책 버전', '저장한 운영자 번호', '기록 일시 (UTC)'], $rows);
    }
}
