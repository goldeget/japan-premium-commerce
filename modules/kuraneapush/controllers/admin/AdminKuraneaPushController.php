<?php

declare(strict_types=1);
require_once dirname(__FILE__, 3) . '/autoload.php';
use Kuranea\Push\Infrastructure\PushSettings;

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
        if ($language > 0) {
            $this->context->language = new Language($language);
        }
        parent::initHeader();
    }

    public function initContent(): void
    {
        $allowed = $this->viewAccess();
        if (!$allowed || empty($this->tabAccess['view'])) {
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
        if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST' && Tools::isSubmit('submitOrdenowaPush')) {
            $submitted = Tools::getValue('token');
            if (!$canEdit || !is_string($submitted) || !hash_equals($token, $submitted)) {
                http_response_code(403);
                $this->content .= '<div class="alert alert-danger">설정을 변경할 권한이 없거나 요청이 유효하지 않습니다.</div>';
            } else {
                $this->save($shop);
            }
        }
        $this->content .= '<div class="panel"><h3>고객 알림 설정</h3><p>발송 상태: 사용할 수 없음</p>'
            . '<p>실제 알림 발송 기능이 연결되지 않았습니다. 동의 안내문이 비어 있으면 새 구독을 받지 않습니다.</p>'
            . '<form method="post" action="' . $this->escape((string) $this->context->link->getAdminLink('AdminKuraneaPush')) . '">'
            . '<input type="hidden" name="token" value="' . $this->escape($token) . '">';
        foreach (['ORDER' => '주문 알림', 'DELIVERY' => '배송 알림', 'SUPPORT' => '고객 지원 알림'] as $event => $label) {
            $key = 'ORDENOWA_PUSH_EVENT_' . $event;
            $this->content .= '<div class="form-group"><label><input type="checkbox" name="' . $key . '" value="1"'
                . ((bool) Configuration::get($key, null, null, $shop) ? ' checked' : '')
                . ($canEdit ? '' : ' disabled') . '> ' . $label . '</label></div>';
        }
        foreach (['ja' => '일본어', 'en' => '영어', 'ko' => '한국어'] as $locale => $label) {
            $key = 'ORDENOWA_PUSH_CONSENT_NOTICE_' . strtoupper($locale);
            $this->content .= '<div class="form-group"><label for="' . $key . '">' . $label . ' 동의 안내문</label>'
                . '<textarea class="form-control" id="' . $key . '" name="' . $key . '" maxlength="4000"'
                . ($canEdit ? '' : ' disabled') . '>' . $this->escape(PushSettings::notice($shop, $locale)) . '</textarea></div>';
        }
        if ($canEdit) {
            $this->content .= '<button class="btn btn-primary" type="submit" name="submitOrdenowaPush" value="1">설정 저장</button>';
        }
        $this->content .= '</form></div>';
        $this->context->smarty->assign('content', $this->content);
    }

    private function save(int $shop): void
    {
        $notices = [];
        foreach (PushSettings::LOCALES as $locale) {
            $key = 'ORDENOWA_PUSH_CONSENT_NOTICE_' . strtoupper($locale);
            $value = Tools::getValue($key, '');
            if (!is_string($value) || strlen($value) > 16000 || preg_match('//u', $value) !== 1
                || mb_strlen($value, 'UTF-8') > 4000) {
                $this->content .= '<div class="alert alert-danger">동의 안내문은 4,000자 이내로 입력해 주세요.</div>';
                return;
            }
            $notices[$key] = trim($value);
        }
        $ok = true;
        foreach ($notices as $key => $value) {
            $ok = Configuration::updateValue($key, $value, false, null, $shop) && $ok;
        }
        foreach (PushSettings::EVENTS as $event) {
            $key = 'ORDENOWA_PUSH_EVENT_' . $event;
            $ok = Configuration::updateValue($key, Tools::getValue($key) === '1' ? 1 : 0, false, null, $shop) && $ok;
        }
        $this->content .= $ok ? '<div class="alert alert-success">알림 설정을 저장했습니다.</div>'
            : '<div class="alert alert-danger">알림 설정을 저장하지 못했습니다.</div>';
    }

    private function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
