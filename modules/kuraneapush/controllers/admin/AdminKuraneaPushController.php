<?php

declare(strict_types=1);
require_once dirname(__FILE__, 3) . '/autoload.php';
use Kuranea\Push\Infrastructure\PushSettings;
use Kuranea\Push\Infrastructure\LivePushFactory;
use Kuranea\Push\Infrastructure\LiveSubscriptionReadiness;

class AdminKuraneaPushController extends ModuleAdminController
{
    public function __construct()
    {
        $this->bootstrap = true;
        parent::__construct();
        $this->meta_title = '고객 알림 설정';
    }

    public function initHeader()
    {
        $language = (int) Language::getIdByIso('ko', true);
        if ($language > 0) $this->context->language = new Language($language);
        parent::initHeader();
    }

    public function initContent(): void
    {
        header('Cache-Control: private, no-store, max-age=0', true);
        header('X-Robots-Tag: noindex, nofollow', true);
        if (!$this->viewAccess() || empty($this->tabAccess['view'])) {
            http_response_code(403);
            $this->content = '<div class="alert alert-danger">알림 설정을 조회할 권한이 없습니다.</div>';
            $this->context->smarty->assign('content', $this->content);
            return;
        }
        parent::initContent();
        $shop = (int) ($this->context->shop->id ?? 0);
        if ($shop < 1 || Shop::getContext() !== Shop::CONTEXT_SHOP) {
            $this->content .= '<div class="alert alert-warning">설정할 쇼핑몰을 하나 선택해 주세요.</div>';
            $this->context->smarty->assign('content', $this->content);
            return;
        }
        $canEdit = (bool) $this->access('edit') && !empty($this->tabAccess['edit']);
        $token = (string) Tools::getAdminTokenLite('AdminKuraneaPush');
        if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST' && isset($_POST['submitOrdenowaPush'])) {
            $submitted = $_POST['token'] ?? null;
            if (!$canEdit || !is_string($submitted) || !hash_equals($token, $submitted)) {
                http_response_code(403);
                $this->content .= '<div class="alert alert-danger">설정을 변경할 권한이 없거나 요청이 유효하지 않습니다.</div>';
            } else {
                $this->save($shop);
            }
        }
        $ready = LivePushFactory::available($shop);
        $secure = LiveSubscriptionReadiness::secureNativeRequest($shop);
        $this->content .= '<div class="panel"><h3>고객 알림 설정</h3><p>서버 발송 준비: ' . ($ready ? '연결됨' : '사용할 수 없음')
            . ' · 현재 HTTPS 원본 확인: ' . ($secure ? '확인됨' : '확인되지 않음') . '</p>'
            . '<p>실제 전송은 명시적 활성화, HTTPS 확인, 서버 키·라이브러리와 회원 동의가 모두 준비된 뒤 가능합니다. 서비스 모드만으로 활성화되지 않습니다.</p>'
            . '<p>서버에서 ORDENOWA_PUSH_VAPID_PUBLIC_KEY, ORDENOWA_PUSH_VAPID_PRIVATE_KEY, ORDENOWA_PUSH_VAPID_SUBJECT, ORDENOWA_PUSH_STORAGE_KEY를 설정하세요. 비밀 키는 이 화면에 입력하거나 표시하지 않습니다.</p>'
            . '<form method="post" data-testid="push-settings" action="' . $this->escape((string) $this->context->link->getAdminLink('AdminKuraneaPush')) . '">'
            . '<input type="hidden" name="token" value="' . $this->escape($token) . '">';
        foreach (['ORDENOWA_PUSH_LIVE_ENABLED' => '실제 고객 Push 발송 활성화', 'ORDENOWA_PUSH_HTTPS_VALIDATED' => '이 쇼핑몰의 실제 HTTPS 접근·인증서·동작을 확인했습니다'] as $key => $label) {
            $this->content .= $this->checkbox($shop, $key, $label, $canEdit);
        }
        foreach (['ORDER' => '기존 주문 알림', 'DELIVERY' => '기존 배송 알림', 'SUPPORT' => '고객 지원 알림', 'PROCUREMENT' => '상품 발주 안내·요청·검토 알림', 'POINTS' => '수당 포인트 지급·정정 알림'] as $event => $label) {
            $this->content .= $this->checkbox($shop, 'ORDENOWA_PUSH_EVENT_' . $event, $label, $canEdit);
        }
        foreach (['ja' => '일본어', 'en' => '영어', 'ko' => '한국어'] as $locale => $label) {
            $key = 'ORDENOWA_PUSH_CONSENT_NOTICE_' . strtoupper($locale);
            $this->content .= '<div class="form-group"><label for="' . $key . '">' . $label . ' 동의 안내문</label>'
                . '<textarea class="form-control" id="' . $key . '" name="' . $key . '" maxlength="4000"'
                . ($canEdit ? '' : ' disabled') . '>' . $this->escape(PushSettings::notice($shop, $locale)) . '</textarea></div>';
        }
        if ($canEdit) $this->content .= '<button class="btn btn-primary" type="submit" name="submitOrdenowaPush" value="1">설정 저장</button>';
        $this->content .= '</form></div>';
        $this->context->smarty->assign('content', $this->content);
    }

    private function save(int $shop): void
    {
        $values = [];
        foreach (PushSettings::LOCALES as $locale) {
            $key = 'ORDENOWA_PUSH_CONSENT_NOTICE_' . strtoupper($locale);
            $value = $_POST[$key] ?? '';
            if (!is_string($value) || strlen($value) > 16000 || preg_match('//u', $value) !== 1 || mb_strlen($value, 'UTF-8') > 4000) {
                $this->content .= '<div class="alert alert-danger">동의 안내문은 4,000자 이내로 입력해 주세요.</div>';
                return;
            }
            $values[$key] = trim($value);
        }
        foreach (PushSettings::EVENTS as $event) {
            $key = 'ORDENOWA_PUSH_EVENT_' . $event;
            $values[$key] = ($_POST[$key] ?? '') === '1' ? 1 : 0;
        }
        foreach (['ORDENOWA_PUSH_LIVE_ENABLED', 'ORDENOWA_PUSH_HTTPS_VALIDATED'] as $key) $values[$key] = ($_POST[$key] ?? '') === '1' ? 1 : 0;
        if ($values['ORDENOWA_PUSH_HTTPS_VALIDATED'] === 1 && !LiveSubscriptionReadiness::secureNativeRequest($shop)) {
            $this->content .= '<div class="alert alert-danger">현재 쇼핑몰의 실제 HTTPS 원본에서만 HTTPS 확인을 저장할 수 있습니다.</div>';
            return;
        }
        if ($values['ORDENOWA_PUSH_LIVE_ENABLED'] === 1) {
            foreach (PushSettings::LOCALES as $locale) {
                if ($values['ORDENOWA_PUSH_CONSENT_NOTICE_' . strtoupper($locale)] === '') {
                    $this->content .= '<div class="alert alert-danger">실제 Push 활성화 전 일본어·영어·한국어 동의 안내문을 입력해 주세요.</div>';
                    return;
                }
            }
            if ($values['ORDENOWA_PUSH_HTTPS_VALIDATED'] !== 1) {
                $this->content .= '<div class="alert alert-danger">실제 HTTPS 동작 확인 후 활성화해 주세요.</div>';
                return;
            }
        }
        $ok = true;
        foreach ($values as $key => $value) $ok = Configuration::updateValue($key, $value, false, null, $shop) && $ok;
        $this->content .= $ok ? '<div class="alert alert-success">알림 설정을 저장했습니다. 서버 준비와 실제 구독 가능 여부는 별도로 확인됩니다.</div>'
            : '<div class="alert alert-danger">알림 설정을 저장하지 못했습니다.</div>';
    }

    private function checkbox(int $shop, string $key, string $label, bool $canEdit): string
    {
        return '<div class="form-group"><label><input type="checkbox" name="' . $key . '" value="1"'
            . ((string) Configuration::get($key, null, null, $shop) === '1' ? ' checked' : '')
            . ($canEdit ? '' : ' disabled') . '> ' . $this->escape($label) . '</label></div>';
    }

    private function escape(string $value): string { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
}
