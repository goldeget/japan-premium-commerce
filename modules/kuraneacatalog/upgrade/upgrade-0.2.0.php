<?php

declare(strict_types=1);

function upgrade_module_0_2_0($module): bool
{
    try {
        require_once __DIR__ . '/../autoload.php';
        \Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseBootstrap::installAndMigrate(_PS_ROOT_DIR_);
        $context = \Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseContext::fromPrestaShop(_PS_ROOT_DIR_);
        \Kuranea\Catalog\Infrastructure\Persistence\CatalogDatabaseBootstrap::assertReady($context);

        return true;
    } catch (\Throwable) {
        return false;
    }
}
