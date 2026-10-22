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
            parent::uninstall();

            return false;
        }

        return true;
    }

    public function uninstall(): bool
    {
        $this->removeTab('AdminKuraneaCatalogReview');

        // The review queue lives in its own persistent volume and is preserved on uninstall.
        return parent::uninstall();
    }

    public function getContent(): string
    {
        $adminUrl = $this->context->link->getAdminLink('AdminKuraneaCatalogReview');

        return '<div class="panel"><h3>상품 검수 대기열</h3><p>검수 승인 시 비활성 TEST/DEMO 상품으로만 등록됩니다.</p>'
            . '<a class="btn btn-primary" href="' . $this->escape((string) $adminUrl) . '">검수 대기열 열기</a></div>';
    }

    private function installTabs(): bool
    {
        $parentId = (int) Tab::getIdFromClassName('AdminParentCatalog');
        if ($parentId < 1) {
            $parentId = (int) Tab::getIdFromClassName('AdminCatalog');
        }
        if ($parentId < 1) {
            $parentId = (int) Tab::getIdFromClassName('AdminParentShopParameters');
        }
        if ($parentId < 1) {
            return false;
        }

        $tabId = (int) Tab::getIdFromClassName('AdminKuraneaCatalogReview');
        $tab = $tabId > 0 ? new Tab($tabId) : new Tab();
        $tab->active = 1;
        $tab->class_name = 'AdminKuraneaCatalogReview';
        $tab->module = $this->name;
        $tab->id_parent = $parentId;
        $tab->name = [];

        foreach (Language::getLanguages(false) as $language) {
            $tab->name[(int) $language['id_lang']] = '상품 검수 대기열';
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
