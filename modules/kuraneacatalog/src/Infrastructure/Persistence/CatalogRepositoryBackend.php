<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use RuntimeException;

final class CatalogRepositoryBackend
{
    public static function useJsonTestBackend(): bool
    {
        $requested = trim((string) getenv('KURANEA_CATALOG_STORAGE_ADAPTER'));
        if ($requested === '') {
            return false;
        }
        if ($requested !== 'json' || getenv('CI') !== 'true'
            || getenv('KURANEA_ISOLATED_CI') !== '1' || getenv('GITHUB_ACTIONS') !== 'true') {
            throw new RuntimeException('Catalog test storage is unavailable outside isolated CI.');
        }

        return true;
    }

    public static function databaseContext(string $shopRoot): CatalogDatabaseContext
    {
        $context = CatalogDatabaseContext::fromPrestaShop($shopRoot);
        CatalogDatabaseBootstrap::assertReady($context);

        return $context;
    }
}
