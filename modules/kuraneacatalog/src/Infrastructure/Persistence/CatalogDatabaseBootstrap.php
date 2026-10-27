<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use RuntimeException;

final class CatalogDatabaseBootstrap
{
    public static function installAndMigrate(string $shopRoot): void
    {
        $context = CatalogDatabaseContext::fromPrestaShop($shopRoot);
        $context->tables->install();
        (new CatalogDatabaseLegacyImporter($context))->import();
    }

    public static function assertReady(CatalogDatabaseContext $context): void
    {
        if (!$context->tables->isInstalled()) {
            throw new RuntimeException('Catalog database storage is not installed.');
        }

        $rows = $context->database->executeS(
            'SELECT store_name FROM ' . $context->tables->migrations()
            . ' WHERE id_shop = ' . $context->shopId . ' AND state = ' . CatalogDatabaseSql::quote('verified')
        );
        if (!is_array($rows)) {
            throw new RuntimeException('Catalog database migration status is unavailable.');
        }
        $stores = array_column($rows, 'store_name');
        if (!in_array('batches', $stores, true) || !in_array('reviews', $stores, true)) {
            throw new RuntimeException('Catalog JSON migration has not been verified.');
        }
    }
}
