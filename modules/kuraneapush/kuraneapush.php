<?php

declare(strict_types=1);
if (!defined('_PS_VERSION_')) {
    exit;
}
require_once __DIR__ . '/autoload.php';
use Kuranea\Push\Domain\Readiness;
use Kuranea\Push\Domain\ConsentNoticeVersion;
use Kuranea\Push\Infrastructure\PushSettings;
use Kuranea\Push\Infrastructure\LivePushFactory;
use Kuranea\Push\Infrastructure\LiveSubscriptionReadiness;
use Kuranea\Push\Infrastructure\SubscriptionCipher;
use Kuranea\Push\Infrastructure\SubscriptionRepository;
use Kuranea\Push\Infrastructure\PushOutboxRepository;
use Kuranea\Push\Infrastructure\OrderHistoryPushProducer;
use Kuranea\Push\Infrastructure\SupportMessagePushProducer;

class Kuraneapush extends Module
{
    public function __construct()
    {
        $this->name = 'kuraneapush';
        $this->tab = 'administration';
        $this->version = '1.0.4';
        $this->author = 'ORDENOWA';
        $this->need_instance = 0;
        $this->bootstrap = true;
        $this->ps_versions_compliancy = ['min' => '9.2.0', 'max' => '9.99.99'];
        parent::__construct();
        $this->displayName = '고객 알림 설정';
        $this->description = '고객 알림 동의·구독과 명시적으로 활성화한 HTTPS Push 발송을 관리합니다.';
    }

    public function install(): bool
    {
        if (!parent::install() || !(new SubscriptionRepository())->install() || !(new PushOutboxRepository())->install()) {
            return false;
        }
        foreach (Shop::getShops(false, null, true) as $shop) {
            if (!PushSettings::initialize((int) $shop)) {
                return false;
            }
        }
        return $this->installTab() && $this->registerHook([
            'displayCustomerAccount', 'actionObjectCustomerDeleteAfter', 'actionOrderHistoryAddAfter',
            'actionObjectCustomerMessageAddAfter',
        ]);
    }

    public function uninstall(): bool
    {
        $tab = (int) Tab::getIdFromClassName('AdminKuraneaPush');
        if ($tab > 0 && !(new Tab($tab))->delete()) {
            return false;
        }
        // Retain encrypted subscriptions and settings across disable/uninstall/reinstall.
        return parent::uninstall();
    }

    /** Repair the additive native order event hook on already-installed stores. */
    public function ensureOrderHistoryPushHook(): bool
    {
        return $this->registerHook('actionOrderHistoryAddAfter');
    }

    /** Repair the additive native support-reply hook on already-installed stores. */
    public function ensureSupportMessagePushHook(): bool
    {
        return $this->registerHook('actionObjectCustomerMessageAddAfter');
    }

    public function getContent(): string
    {
        return '<div class="panel"><h3>고객 알림 설정</h3><a class="btn btn-primary" href="'
            . htmlspecialchars((string) $this->context->link->getAdminLink('AdminKuraneaPush'), ENT_QUOTES, 'UTF-8')
            . '">설정 열기</a></div>';
    }

    public function hookDisplayCustomerAccount(array $params = []): string
    {
        $customer = $this->context->customer;
        if (!$this->active || !$customer || !$customer->isLogged() || (bool) $customer->is_guest) {
            return '';
        }
        $shop = (int) ($this->context->shop->id ?? 0);
        if ($shop < 1 || (int) $customer->id < 1) {
            return '';
        }
        $locale = (string) ($this->context->language->iso_code ?? 'ja');
        $locale = in_array($locale, PushSettings::LOCALES, true) ? $locale : 'ja';
        $notice = trim(PushSettings::notice($shop, $locale));
        $keyAvailable = false;
        try {
            new SubscriptionCipher();
            $keyAvailable = true;
        } catch (\Throwable $e) {
        }
        $active = false;
        $revocable = false;
        try {
            $subscriptions = new SubscriptionRepository();
            $active = $subscriptions->active($shop, (int) $customer->id);
            $revocable = $subscriptions->stored($shop, (int) $customer->id);
        } catch (\Throwable $e) {
            $keyAvailable = false;
        }
        $url = (string) $this->context->link->getModuleLink($this->name, 'subscription');
        $this->context->smarty->assign([
            'ordenowa_push_status_url' => $url . (str_contains($url, '?') ? '&' : '?') . 'action=status',
            'ordenowa_push_subscription_url' => $url,
            'ordenowa_push_token' => (string) Tools::getToken('kuraneapush', $this->context),
            'ordenowa_push_locale' => $locale,
            'ordenowa_push_consent_notice' => $notice,
            'ordenowa_push_consent_notice_version' => ConsentNoticeVersion::forNotice($notice, $locale),
            'ordenowa_push_can_subscribe' => LiveSubscriptionReadiness::canSubscribe($shop, $notice, $keyAvailable),
            'ordenowa_push_active' => $active,
            'ordenowa_push_revocable' => $revocable,
            'ordenowa_push_application_server_key' => LiveSubscriptionReadiness::secureNativeRequest($shop) ? LivePushFactory::applicationServerKey($shop) : '',
        ]);
        $this->context->controller->registerJavascript('module-kuraneapush-account',
            'modules/' . $this->name . '/views/js/account-push.js', ['position' => 'bottom', 'priority' => 150]);
        $this->context->controller->registerStylesheet('module-kuraneapush-account',
            'modules/' . $this->name . '/views/css/account-push.css', ['media' => 'all', 'priority' => 150]);
        return $this->display(__FILE__, 'views/templates/hook/account_push.tpl');
    }

    public function hookActionOrderHistoryAddAfter(array $params): void
    {
        if ($this->active) {
            $producer = new OrderHistoryPushProducer();
            $producer->record($params['order_history'] ?? null);
            $producer->recordDelivery($params['order_history'] ?? null);
        }
    }

    public function hookActionObjectCustomerMessageAddAfter(array $params): void
    {
        if ($this->active) {
            (new SupportMessagePushProducer())->record($params['object'] ?? null);
        }
    }

    public function hookActionObjectCustomerDeleteAfter(array $params): void
    {
        $customer = $params['object'] ?? null;
        if (!is_object($customer) || !($customer instanceof Customer) || (int) $customer->id < 1) {
            return;
        }
        (new SubscriptionRepository())->deleteCustomer((int) $customer->id, Shop::getShops(false, null, true));
        (new PushOutboxRepository())->deleteCustomer((int) $customer->id, Shop::getShops(false, null, true));
    }

    private function installTab(): bool
    {
        $parent = 0;
        foreach (['ShopParameters', 'AdminParentShopParameters', 'AdminParentPreferences'] as $name) {
            $parent = (int) Tab::getIdFromClassName($name);
            if ($parent > 0) {
                break;
            }
        }
        if ($parent < 1) {
            return false;
        }
        $id = (int) Tab::getIdFromClassName('AdminKuraneaPush');
        $tab = $id > 0 ? new Tab($id) : new Tab();
        $tab->active = 1;
        $tab->class_name = 'AdminKuraneaPush';
        $tab->module = $this->name;
        $tab->id_parent = $parent;
        foreach (Language::getLanguages(false) as $language) {
            $tab->name[(int) $language['id_lang']] = '고객 알림 설정';
        }
        return $id > 0 ? (bool) $tab->update() : (bool) $tab->add();
    }
}
