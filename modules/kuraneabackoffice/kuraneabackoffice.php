<?php

declare(strict_types=1);

if (!defined('_PS_VERSION_')) {
    exit;
}

class Kuraneabackoffice extends Module
{
    public function __construct()
    {
        $this->name = 'kuraneabackoffice';
        $this->tab = 'administration';
        $this->version = '1.0.8';
        $this->author = 'ORDENOWA';
        $this->need_instance = 0;
        $this->bootstrap = true;
        $this->ps_versions_compliancy = ['min' => '9.2.0', 'max' => '9.99.99'];

        parent::__construct();

        $this->displayName = 'ORDENOWA 관리자 화면 지원';
        $this->description = '한국어 관리자 로그인, 게시된 브랜드 표시 및 관리자 번역 오버레이를 지원합니다.';
    }

    public function install(): bool
    {
        return parent::install() && $this->registerHook([
            'displayAdminLogin',
            'displayAdminEndContent',
            'actionAdminControllerSetMedia',
        ]) && $this->installSupportAssignments() && $this->installEmployeeProfileAudit() && $this->installSupportContactPrivacy() && $this->installKoreanAdminTabLabels();
    }

    /** Only installer/upgrader/bootstrap calls this; administrator GETs stay read-only. */
    public function installKoreanAdminTabLabels(): bool
    {
        require_once __DIR__ . '/vendor/autoload.php';
        $koreanLanguageId = (int) Language::getIdByIso('ko', true);
        return $koreanLanguageId < 1 || \Kuranea\Backoffice\Admin\KoreanAdminTabLabels::repair(
            Db::getInstance(), $koreanLanguageId, _DB_PREFIX_
        );
    }

    public function installSupportContactPrivacy(): bool
    {
        return $this->registerHook('actionFrontControllerInitAfter');
    }

    public function hookActionFrontControllerInitAfter(array $params = []): void
    {
        $controller = $params['controller'] ?? $this->context->controller;
        if ((string) ($controller->php_self ?? '') !== 'contact') {
            return;
        }
        require_once __DIR__ . '/vendor/autoload.php';
        try {
            $allowed = \Kuranea\Backoffice\Support\SupportContactAccessGuard::allows(
                $this->context, $_GET, $_POST, Tools::isSubmit('submitMessage')
            );
        } catch (Throwable) {
            $allowed = false;
        }
        if ($allowed) {
            return;
        }
        http_response_code(403);
        header('Content-Type: text/plain; charset=utf-8');
        header('Cache-Control: private, no-store, max-age=0', true);
        $locale = (string) ($this->context->language->iso_code ?? 'ja');
        echo match ($locale) {
            'ko' => '이 문의를 이용하려면 해당 고객 계정으로 로그인해 주세요.',
            'en' => 'Please sign in with the customer account that owns this inquiry.',
            default => 'このお問い合わせの顧客アカウントでログインしてください。',
        };
        exit;
    }

    /** Additive install/upgrade entry point for the shop-scoped support assignment store. */
    public function installSupportAssignments(): bool
    {
        require_once __DIR__ . '/vendor/autoload.php';

        $database = Db::getInstance();
        if (!$database->execute(\Kuranea\Backoffice\Infrastructure\SupportAssignmentSchema::currentTableSql(_DB_PREFIX_))
            || !$database->execute(\Kuranea\Backoffice\Infrastructure\SupportAssignmentSchema::historyTableSql(_DB_PREFIX_))) {
            return false;
        }

        return $this->installSupportAssignmentsTab();
    }

    /** Adds a dedicated entry under customer service without altering native thread behavior. */
    public function installSupportAssignmentsTab(): bool
    {
        $parentId = (int) Tab::getIdFromClassName('AdminParentCustomerService');
        if ($parentId < 1) {
            $parentId = (int) Tab::getIdFromClassName('AdminParentOrders');
        }
        if ($parentId < 1) {
            return false;
        }

        $className = 'AdminKuraneaSupportAssignments';
        $tabId = (int) Tab::getIdFromClassName($className);
        $tab = $tabId > 0 ? new Tab($tabId) : new Tab();
        $tab->active = 1;
        $tab->class_name = $className;
        $tab->module = $this->name;
        $tab->id_parent = $parentId;
        $tab->name = [];

        $labels = [
            'ja' => '問い合わせ担当者',
            'en' => 'Support assignment',
            'ko' => '고객 문의 담당자',
        ];
        foreach (Language::getLanguages(false) as $language) {
            $languageId = (int) ($language['id_lang'] ?? 0);
            if ($languageId > 0) {
                $isoCode = strtolower((string) ($language['iso_code'] ?? 'ko'));
                $tab->name[$languageId] = $labels[$isoCode] ?? $labels['ko'];
            }
        }

        return $tabId > 0 ? (bool) $tab->update() : (bool) $tab->add();
    }

    /** Additive store, observer hooks, and native-view tab for Employee profile transitions. */
    public function installEmployeeProfileAudit(): bool
    {
        require_once __DIR__ . '/vendor/autoload.php';

        $database = Db::getInstance();
        if (!$database->execute(\Kuranea\Backoffice\Infrastructure\EmployeeProfileAuditSchema::tableSql(_DB_PREFIX_))) {
            return false;
        }

        return $this->registerHook([
            'actionObjectEmployeeUpdateBefore',
            'actionObjectEmployeeUpdateAfter',
        ]) && $this->installEmployeeProfileAuditTab() && $this->installNativeAclAudit();
    }

    /** Native AdminAccess has official Before hooks; its die() requires shutdown readback. */
    public function installNativeAclAudit(): bool
    {
        require_once __DIR__ . '/vendor/autoload.php';
        return Db::getInstance()->execute(\Kuranea\Backoffice\Infrastructure\NativeAclAuditSchema::tableSql(_DB_PREFIX_))
            && $this->registerHook(['actionAdminUpdateAccessBefore', 'actionAdminUpdateModuleAccessBefore']);
    }

    public function hookActionAdminUpdateAccessBefore(array $params): void
    {
        require_once __DIR__ . '/vendor/autoload.php';
        \Kuranea\Backoffice\Admin\NativeAclAuditObserver::before($params, 'TAB');
    }

    public function hookActionAdminUpdateModuleAccessBefore(array $params): void
    {
        require_once __DIR__ . '/vendor/autoload.php';
        \Kuranea\Backoffice\Admin\NativeAclAuditObserver::before($params, 'MODULE');
    }

    /** The tab grants no permissions; PrestaShop's existing profile access remains authoritative. */
    public function installEmployeeProfileAuditTab(): bool
    {
        $parentId = 0;
        foreach ([
            'AdminParentEmployees',
            'AdminParentAdvancedParameters',
            'AdminParentShopParameters',
            'AdminParentPreferences',
        ] as $parentClass) {
            $parentId = (int) Tab::getIdFromClassName($parentClass);
            if ($parentId > 0) {
                break;
            }
        }
        if ($parentId < 1) {
            return false;
        }

        $className = 'AdminKuraneaEmployeeProfileAudit';
        $tabId = (int) Tab::getIdFromClassName($className);
        $tab = $tabId > 0 ? new Tab($tabId) : new Tab();
        $tab->active = 1;
        $tab->class_name = $className;
        $tab->module = $this->name;
        $tab->id_parent = $parentId;
        $tab->name = [];

        $labels = [
            'ja' => '管理者監査記録',
            'en' => 'Administrator audit log',
            'ko' => '관리자 감사 기록',
        ];
        foreach (Language::getLanguages(false) as $language) {
            $languageId = (int) ($language['id_lang'] ?? 0);
            if ($languageId > 0) {
                $isoCode = strtolower((string) ($language['iso_code'] ?? 'ko'));
                $tab->name[$languageId] = $labels[$isoCode] ?? $labels['ko'];
            }
        }

        return $tabId > 0 ? (bool) $tab->update() : (bool) $tab->add();
    }

    public function hookActionObjectEmployeeUpdateBefore(array $params): void
    {
        require_once __DIR__ . '/vendor/autoload.php';
        \Kuranea\Backoffice\Admin\EmployeeProfileAuditObserver::beforeUpdate($params);
    }

    public function hookActionObjectEmployeeUpdateAfter(array $params): void
    {
        require_once __DIR__ . '/vendor/autoload.php';
        \Kuranea\Backoffice\Admin\EmployeeProfileAuditObserver::afterUpdate($params);
    }

    public function hookActionAdminControllerSetMedia(): void
    {
        $languageIsoCode = strtolower((string) ($this->context->language->iso_code ?? ''));
        $controller = $this->context->controller ?? null;
        if (!str_starts_with($languageIsoCode, 'ko') || !is_object($controller)
            || get_class($controller) !== 'AdminDashboardController') {
            return;
        }

        $controller->addJs($this->_path . 'views/js/dashboard-korean.js');
    }

    public function hookDisplayAdminEndContent(array $params = []): string
    {
        $languageIsoCode = strtolower((string) ($this->context->language->iso_code ?? ''));
        $controller = $this->context->controller;
        $controllerName = is_object($controller) ? (string) ($controller->controller_name ?? '') : '';
        if (!str_starts_with($languageIsoCode, 'ko') || $controllerName !== 'AdminOrders') {
            return '';
        }

        $this->context->smarty->assign([
            'kuranea_orders_empty_state_script' => $this->_path . 'views/js/orders-empty-state-korean.js',
        ]);

        return $this->fetch('module:' . $this->name . '/views/templates/hook/admin-orders-empty-state.tpl');
    }

    public function hookDisplayAdminLogin(array $params = []): string
    {
        $brandName = 'ORDENOWA';
        $logo = '';
        $autoload = _PS_MODULE_DIR_ . 'kuraneabusinessprofile/autoload.php';
        if (is_file($autoload)) {
            require_once $autoload;
            $shopId = max(1, (int) ($this->context->shop->id ?? 1));
            $isoCode = (string) ($this->context->language->iso_code ?? 'ja');
            $repository = new \Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository();
            $profile = (new \Kuranea\BusinessProfile\Customer\PublishedProfileProvider($repository))->forShop($shopId, $isoCode);
            if ($profile === null) {
                $profile = \Kuranea\BusinessProfile\Domain\ProfileDefaults::initial();
                $profile['_resolved_locale'] = \Kuranea\BusinessProfile\Customer\PublishedProfileProvider::localeForIso($isoCode);
            }
            $locale = (string) $profile['_resolved_locale'];
            $brandName = (string) ($profile['brand']['name'][$locale] ?? $brandName);
            $assetPath = $profile['brand']['assets']['admin_login'] ?? null;
            if (is_string($assetPath)
                && preg_match('~\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/[A-Za-z0-9._-]+\.(?:png|webp)\z~D', $assetPath) === 1) {
                $logo = rtrim((string) $this->context->link->getBaseLink(), '/') . '/' . $assetPath;
            }
        }

        $this->context->smarty->assign([
            'ordenowa_backoffice_brand_name' => $brandName,
            'ordenowa_backoffice_logo' => $logo,
        ]);

        return $this->fetch('module:' . $this->name . '/views/templates/hook/admin-login.tpl');
    }
}
