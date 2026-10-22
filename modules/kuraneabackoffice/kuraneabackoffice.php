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
        $this->author = 'ORDENOWA';
        $this->need_instance = 0;
        $this->bootstrap = true;
        $this->ps_versions_compliancy = ['min' => '9.2.0', 'max' => '9.99.99'];

        parent::__construct();

        $this->displayName = 'ORDENOWA Back Office support';
        $this->description = 'Korean Back Office language, published brand display, and translation overlays.';
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
        $brandName = 'ORDENOWA';
        $logo = '';
        $autoload = _PS_MODULE_DIR_ . 'kuraneabusinessprofile/autoload.php';
        if (is_file($autoload)) {
            require_once $autoload;
            $shopId = max(1, (int) ($this->context->shop->id ?? 1));
            $isoCode = (string) ($this->context->language->iso_code ?? 'ja');
            $repository = new \Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository();
            $profile = (new \Kuranea\BusinessProfile\Customer\PublishedProfileProvider($repository))->forShop($shopId, $isoCode);
            if ($profile !== null) {
                $locale = (string) $profile['_resolved_locale'];
                $brandName = (string) ($profile['brand']['name'][$locale] ?? $brandName);
                $assetPath = $profile['brand']['assets']['admin_login'] ?? null;
                if (is_string($assetPath)
                    && preg_match('~\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/[A-Za-z0-9._-]+\.(?:png|webp)\z~D', $assetPath) === 1) {
                    $logo = rtrim((string) $this->context->link->getBaseLink(), '/') . '/' . $assetPath;
                }
            }
        }

        $this->context->smarty->assign([
            'ordenowa_backoffice_brand_name' => $brandName,
            'ordenowa_backoffice_logo' => $logo,
        ]);

        return $this->fetch('module:' . $this->name . '/views/templates/hook/admin-login.tpl');
    }
}
