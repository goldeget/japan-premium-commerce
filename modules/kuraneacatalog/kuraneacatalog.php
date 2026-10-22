<?php

declare(strict_types=1);

if (!defined('_PS_VERSION_')) {
    exit;
}

require_once __DIR__ . '/autoload.php';

use Kuranea\Catalog\Infrastructure\Persistence\CatalogQueueRepositoryFactory;

class Kuraneacatalog extends Module
{
    public function __construct()
    {
        $this->name = 'kuraneacatalog';
        $this->tab = 'administration';
        $this->version = '0.1.0';
        $this->author = 'KURANEA';
        $this->need_instance = 0;
        $this->bootstrap = true;
        $this->ps_versions_compliancy = ['min' => '9.2.0', 'max' => '9.99.99'];

        parent::__construct();

        $this->displayName = '상품 검수 대기열';
        $this->description = '오프라인 상품 스냅샷을 검수하고 TEST/DEMO 상품으로 등록합니다.';
    }

    public function install(): bool
    {
        if (!parent::install()) {
            return false;
        }

        try {
            CatalogQueueRepositoryFactory::fromEnvironment(_PS_ROOT_DIR_);
        } catch (Throwable) {
            parent::uninstall();

            return false;
        }

        if (!$this->installTabs()) {
            $this->removeTab('AdminKuraneaCatalogReview');
            $this->removeTab('AdminOrdenowaProductManager');
            parent::uninstall();

            return false;
        }

        return true;
    }

    public function uninstall(): bool
    {
        $this->removeTab('AdminKuraneaCatalogReview');
        $this->removeTab('AdminOrdenowaProductManager');

        // The review queue lives in its own persistent volume and is preserved on uninstall.
        return parent::uninstall();
    }

    public function getContent(): string
    {
        $adminUrl = $this->context->link->getAdminLink('AdminKuraneaCatalogReview');
        $productUrl = $this->context->link->getAdminLink('AdminOrdenowaProductManager');

        return '<div class="panel"><h3>ORDENOWA 상품 관리</h3>'
            . '<p>새 상품은 비활성·비노출·주문 불가 상태로 등록되며, 관리자 판매 승인 절차를 통과하기 전에는 구매할 수 없습니다.</p>'
            . '<a class="btn btn-primary" href="' . $this->escape((string) $productUrl) . '">상품 등록·관리</a> '
            . '<a class="btn btn-default" href="' . $this->escape((string) $adminUrl) . '">상품 검수 대기열</a></div>';
    }

    private function installTabs(): bool
    {
        $catalogParentId = (int) Tab::getIdFromClassName('AdminParentCatalog');
        if ($catalogParentId < 1) {
            $catalogParentId = (int) Tab::getIdFromClassName('AdminCatalog');
        }
        if ($catalogParentId < 1) {
            $catalogParentId = (int) Tab::getIdFromClassName('ShopParameters');
        }
        $settingsParentId = (int) Tab::getIdFromClassName('ShopParameters');
        if ($settingsParentId < 1) {
            $settingsParentId = (int) Tab::getIdFromClassName('AdminParentShopParameters');
        }
        if ($settingsParentId < 1) {
            $settingsParentId = (int) Tab::getIdFromClassName('AdminParentPreferences');
        }
        if ($settingsParentId < 1) {
            $settingsParentId = $catalogParentId;
        }
        if ($catalogParentId < 1 || $settingsParentId < 1) {
            return false;
        }

        return $this->installTab('AdminKuraneaCatalogReview', '상품 검수 대기열', $catalogParentId)
            && $this->installTab('AdminOrdenowaProductManager', '상품 등록·관리', $settingsParentId);
    }

    private function installTab(string $className, string $label, int $parentId): bool
    {
        $tabId = (int) Tab::getIdFromClassName($className);
        $tab = $tabId > 0 ? new Tab($tabId) : new Tab();
        $tab->active = 1;
        $tab->class_name = $className;
        $tab->module = $this->name;
        $tab->id_parent = $parentId;
        $tab->name = [];
        foreach (Language::getLanguages(false) as $language) {
            $tab->name[(int) $language['id_lang']] = $label;
        }

        return $tabId > 0 ? (bool) $tab->update() : (bool) $tab->add();
    }

    private function removeTab(string $className): void
    {
        $tabId = (int) Tab::getIdFromClassName($className);
        if ($tabId > 0) {
            (new Tab($tabId))->delete();
        }
    }

    private function escape(string $value): string
    {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
