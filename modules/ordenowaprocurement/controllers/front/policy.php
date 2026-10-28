<?php

declare(strict_types=1);
require_once dirname(__DIR__, 2) . '/autoload.php';
use Ordenowa\Procurement\Integration\Runtime;

class OrdenowaprocurementPolicyModuleFrontController extends ModuleFrontController
{
    public $ssl = true;

    public function initContent(): void
    {
        parent::initContent();
        header('Cache-Control: no-store, max-age=0', true);
        header('X-Content-Type-Options: nosniff', true);
        $section = Tools::getValue('section', 'operator');
        if (!Runtime::procurementEnabled() || !is_string($section) || !in_array($section, ['operator', 'terms', 'privacy', 'points'], true)) {
            http_response_code(404);
            $this->context->smarty->assign(['ordenowa_policy_ready' => false, 'ordenowa_policy_title' => '', 'ordenowa_policy_text' => '', 'ordenowa_policy_operator' => []]);
        } else {
            $locale = (string) ($this->context->language->iso_code ?? 'ja');
            $locale = in_array($locale, ['ja', 'en', 'ko'], true) ? $locale : 'ja';
            $labels = [
                'ja' => ['operator' => '運営者・お問い合わせ', 'terms' => '利用規約', 'privacy' => 'プライバシーポリシー', 'points' => '手当ポイント規約', 'unavailable' => '運営情報・規約は現在準備中です。'],
                'en' => ['operator' => 'Operator & support', 'terms' => 'Terms', 'privacy' => 'Privacy policy', 'points' => 'Allowance points policy', 'unavailable' => 'Service information and policies are being prepared.'],
                'ko' => ['operator' => '서비스 운영자·고객 지원', 'terms' => '이용약관', 'privacy' => '개인정보 처리방침', 'points' => '수당 포인트 정책', 'unavailable' => '서비스 운영 정보와 정책을 준비 중입니다.'],
            ];
            try { $published = Runtime::policies()->published((int) ($this->context->shop->id ?? 0)); } catch (Throwable) { $published = null; }
            if ($published === null) http_response_code(503);
            $this->context->smarty->assign([
                'ordenowa_policy_ready' => $published !== null, 'ordenowa_policy_title' => $labels[$locale][$section],
                'ordenowa_policy_unavailable' => $labels[$locale]['unavailable'],
                'ordenowa_policy_text' => $published !== null && $section !== 'operator' ? $published['payload'][$section][$locale] : '',
                'ordenowa_policy_operator' => $published !== null && $section === 'operator' ? array_intersect_key($published['payload'], array_flip(['operator_name', 'support_email', 'support_phone', 'support_url'])) : [],
                'ordenowa_policy_version' => $published['version'] ?? 0,
            ]);
        }
        $this->setTemplate('module:ordenowaprocurement/views/templates/front/policy.tpl');
    }
}
