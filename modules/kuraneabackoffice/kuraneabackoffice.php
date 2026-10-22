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
        $this->version = '1.0.0';
        $this->author = 'KURANEA';
        $this->need_instance = 0;
        $this->bootstrap = true;
        $this->ps_versions_compliancy = ['min' => '9.2.0', 'max' => '9.99.99'];

        parent::__construct();

        $this->displayName = 'KURANEA Back Office support';
        $this->description = 'Korean Back Office login language, branding, and translation overlays.';
    }

    public function install(): bool
    {
        return parent::install() && $this->registerHook(['displayAdminLogin', 'actionAdminControllerSetMedia']);
    }

    public function hookActionAdminControllerSetMedia(): void
    {
        $languageIsoCode = strtolower((string) ($this->context->language->iso_code ?? ''));
        if (!str_starts_with($languageIsoCode, 'ko') || get_class($this->context->controller) !== 'AdminDashboardController') {
            return;
        }

        $this->context->controller->addJs($this->_path . 'views/js/dashboard-korean.js');
    }

    public function hookDisplayAdminLogin(array $params = []): string
    {
        $this->context->smarty->assign([
            'kuranea_backoffice_logo' => $this->_path . 'views/img/kuranea-logo.png',
        ]);

        return $this->fetch('module:' . $this->name . '/views/templates/hook/admin-login.tpl');
    }
}
