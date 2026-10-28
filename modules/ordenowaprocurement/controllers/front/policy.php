<?php

declare(strict_types=1);
require_once dirname(__DIR__, 2) . '/autoload.php';
use Ordenowa\Procurement\Integration\Runtime;

class OrdenowaprocurementPolicyModuleFrontController extends ModuleFrontController
{
    public $ssl = true;

    public function getTemplateVarPage()
    {
        $page = parent::getTemplateVarPage();
        $locale = (string) ($this->context->language->iso_code ?? 'ja');
        $locale = in_array($locale, ['ja', 'en', 'ko'], true) ? $locale : 'ja';
        $section = Tools::getValue('section', 'operator');
        $descriptions = [
            'ja' => [
                'operator' => 'ORDENOWAのサービス運営者とお問い合わせ窓口をご案内します。',
                'terms' => 'ORDENOWAの商品発注依頼と運営者による確認に関する利用規約をご案内します。',
                'privacy' => 'ORDENOWAの会員情報と商品発注依頼に関する個人情報の取扱いをご案内します。',
                'points' => 'ORDENOWAの手当ポイントの付与、訂正、残高と履歴の確認に関する規約をご案内します。',
            ],
            'en' => [
                'operator' => 'Find service operator and customer support information for ORDENOWA.',
                'terms' => 'Read the terms for product procurement requests and operator review on ORDENOWA.',
                'privacy' => 'Read how ORDENOWA handles personal information for member accounts and product procurement requests.',
                'points' => 'Read the policy for allowance point credits, corrections, balance and history on ORDENOWA.',
            ],
            'ko' => [
                'operator' => 'ORDENOWA의 서비스 운영자와 고객 지원 창구를 안내합니다.',
                'terms' => 'ORDENOWA의 상품 발주 요청과 운영자 검토에 관한 이용약관을 안내합니다.',
                'privacy' => 'ORDENOWA의 회원 정보와 상품 발주 요청에 관한 개인정보 처리방침을 안내합니다.',
                'points' => 'ORDENOWA의 수당 포인트 지급·정정과 잔액·내역 확인에 관한 정책을 안내합니다.',
            ],
        ];
        if (is_string($section) && isset($descriptions[$locale][$section])) {
            $page['meta']['description'] = $descriptions[$locale][$section];
        }
        return $page;
    }

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
