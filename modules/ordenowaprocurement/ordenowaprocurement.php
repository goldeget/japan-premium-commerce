<?php

declare(strict_types=1);

if (!defined('_PS_VERSION_')) {
    exit;
}
require_once __DIR__ . '/autoload.php';

use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Integration\Runtime;
use Ordenowa\Procurement\Integration\WorkspaceAccessPolicy;

class Ordenowaprocurement extends Module
{
    private const TABS = [
        'AdminOrdenowaProcurement' => '상품 발주 안내',
        'AdminOrdenowaProcurementReviews' => '발주 요청 검토',
        'AdminOrdenowaProcurementPoints' => '수당 포인트 지급·정정',
        'AdminOrdenowaProcurementAudit' => '발주·포인트 감사 기록',
        'AdminOrdenowaProcurementPolicies' => '서비스 운영자·지원·정책',
    ];
    private const HOOKS = ['actionFrontControllerInitBefore', 'actionFrontControllerSetVariables', 'displayHeader', 'displayCustomerAccount', 'displayMyAccountBlock', 'displayFooter'];

    public function __construct()
    {
        $this->name = 'ordenowaprocurement';
        $this->tab = 'administration';
        $this->version = '1.0.0';
        $this->author = 'ORDENOWA';
        $this->bootstrap = true;
        $this->need_instance = 0;
        $this->ps_versions_compliancy = ['min' => '9.2.0', 'max' => '9.99.99'];
        parent::__construct();
        $this->displayName = 'ORDENOWA 상품 발주·수당 포인트';
        $this->description = '회원별 상품 발주 안내, 수동 검토, 수당 포인트 지급·정정과 감사 기록을 관리합니다.';
    }

    public function install(): bool
    {
        return parent::install() && $this->ensureInfrastructure();
    }

    /** Additive and idempotent repair for native installer pre-registration. Never resets ACL. */
    public function ensureInfrastructure(): bool
    {
        try {
            Schema::install(Runtime::database());
            foreach (self::HOOKS as $hook) {
                if (!$this->isRegisteredInHook($hook) && !$this->registerHook($hook)) {
                    return false;
                }
            }
            $parentId = (int) Tab::getIdFromClassName('AdminParentCatalog');
            if ($parentId < 1) {
                $parentId = (int) Tab::getIdFromClassName('AdminCatalog');
            }
            if ($parentId < 1) {
                return false;
            }
            foreach (self::TABS as $className => $label) {
                $id = (int) Tab::getIdFromClassName($className);
                $tab = $id > 0 ? new Tab($id) : new Tab();
                $tab->class_name = $className;
                $tab->module = $this->name;
                $tab->active = 1;
                $tab->id_parent = $parentId;
                $tab->name = [];
                foreach (Language::getLanguages(false) as $language) {
                    $tab->name[(int) $language['id_lang']] = $label;
                }
                // Native Tab::add provisions the standard READ/CREATE/UPDATE/DELETE
                // authorization roles. Existing custom employee grants are preserved.
                if (!($id > 0 ? $tab->update() : $tab->add())) {
                    return false;
                }
            }
            return true;
        } catch (Throwable) {
            $this->_errors[] = '상품 발주 모듈의 테이블·권한·메뉴를 준비하지 못했습니다.';
            return false;
        }
    }

    public function uninstall(): bool
    {
        foreach (array_keys(self::TABS) as $name) {
            $id = (int) Tab::getIdFromClassName($name);
            if ($id > 0 && !(new Tab($id))->delete()) {
                return false;
            }
        }
        // Requests, immutable snapshots, point ledger and audit remain intact.
        return parent::uninstall();
    }

    public function getContent(): string
    {
        $mode = Runtime::procurementEnabled() ? '상품 발주 플랫폼 활성' : '기존 모드';
        $html = '<div class="panel"><h3>상품 발주 플랫폼 설정</h3><p>' . $mode . '</p>'
            . '<p>서비스 모드는 서버의 ORDENOWA_APP_MODE=procurement 설정으로 관리합니다. 회원 접근은 판매자 승인·배송·환불 설정과 분리됩니다.</p>'
            . '<p>메뉴별 조회 권한을 먼저 부여하세요. 안내 등록은 추가, 안내 회수와 검토는 수정, 포인트 지급은 추가, 포인트 정정은 수정 권한이 필요합니다.</p>';
        foreach (self::TABS as $tab => $label) {
            if (Runtime::nativePermission($tab, 'READ')) {
                $html .= '<p><a href="' . self::escape((string) $this->context->link->getAdminLink($tab)) . '">' . $label . '</a></p>';
            }
        }
        return $html . '</div>';
    }

    public function hookActionFrontControllerInitBefore(array $params = []): void
    {
        $this->assignNavigation();
        if (!Runtime::procurementEnabled()) {
            return;
        }
        $controller = $params['controller'] ?? $this->context->controller;
        $name = (string) ($controller->php_self ?? '');
        $module = $controller->module ?? null;
        if (WorkspaceAccessPolicy::deniesController($name)
            || (class_exists('PaymentModule') && $module instanceof PaymentModule)
            || ($name === '' && is_object($controller) && is_a($controller, 'GetFileControllerCore'))) {
            header('Cache-Control: private, no-store, max-age=0', true);
            header('X-Robots-Tag: noindex, nofollow', true);
            http_response_code(404);
            exit;
        }
        if ($name === 'index' && !array_key_exists('mylogout', $_GET)) {
            Tools::redirect($this->context->link->getModuleLink($this->name, 'workspace'));
        }
    }

    public function hookActionFrontControllerSetVariables(array $params = []): array
    {
        $this->assignNavigation();
        return [];
    }

    public function hookDisplayHeader(): string
    {
        $this->assignNavigation();
        return Runtime::procurementEnabled() ? '<meta name="ordenowa-platform" content="procurement">' : '';
    }

    public function hookDisplayCustomerAccount(): string
    {
        if (!Runtime::procurementEnabled()) {
            return '';
        }
        return '<a class="account-menu__link ordenowa-workspace-link" href="'
            . self::escape((string) $this->context->link->getModuleLink($this->name, 'workspace')) . '">'
            . self::escape($this->workspaceLabel()) . '</a>';
    }

    public function hookDisplayFooter(): string
    {
        if (!Runtime::procurementEnabled()) return '';
        try { $published = Runtime::policies()->published((int) $this->context->shop->id); } catch (Throwable) { return ''; }
        if ($published === null) return '';
        $locale = (string) ($this->context->language->iso_code ?? 'ja');
        $labels = [
            'ja' => ['operator' => '運営者・お問い合わせ', 'terms' => '利用規約', 'privacy' => 'プライバシー', 'points' => '手当ポイント規約'],
            'en' => ['operator' => 'Operator & support', 'terms' => 'Terms', 'privacy' => 'Privacy', 'points' => 'Allowance points policy'],
            'ko' => ['operator' => '운영자·고객 지원', 'terms' => '이용약관', 'privacy' => '개인정보 처리방침', 'points' => '수당 포인트 정책'],
        ];
        $html = '<nav class="ordenowa-service-policies" aria-label="ORDENOWA">';
        foreach ($labels[$locale] ?? $labels['ja'] as $section => $label) {
            $html .= '<a href="' . self::escape((string) $this->context->link->getModuleLink($this->name, 'policy', ['section' => $section])) . '">' . self::escape($label) . '</a> ';
        }
        return $html . '</nav>';
    }

    public function hookDisplayMyAccountBlock(): string
    {
        return Runtime::procurementEnabled() ? '<li>' . $this->hookDisplayCustomerAccount() . '</li>' : '';
    }

    private function assignNavigation(): void
    {
        $this->context->smarty->assign([
            'ordenowaProcurementEnabled' => Runtime::procurementEnabled(),
            'ordenowaWorkspaceUrl' => (string) $this->context->link->getModuleLink($this->name, 'workspace'),
            'ordenowaWorkspaceRequestsUrl' => (string) $this->context->link->getModuleLink($this->name, 'workspace', ['view' => 'requests']),
            'ordenowaWorkspacePointsUrl' => (string) $this->context->link->getModuleLink($this->name, 'workspace', ['view' => 'points']),
            'ordenowaWorkspaceLabel' => $this->workspaceLabel(),
        ]);
    }

    private function workspaceLabel(): string
    {
        return match ((string) ($this->context->language->iso_code ?? 'ja')) {
            'ko' => '발주 안내·내역·포인트',
            'en' => 'Assigned products, requests & points',
            default => '発注案内・履歴・ポイント',
        };
    }

    private static function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
