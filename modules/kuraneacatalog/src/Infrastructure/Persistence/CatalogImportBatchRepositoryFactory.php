<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use Kuranea\Catalog\Domain\CatalogImportBatchRepositoryInterface;
use RuntimeException;

/** Selects indexed SQL storage in PrestaShop and JSON only for explicit isolated repository tests. */
final class CatalogImportBatchRepositoryFactory
{
    public static function fromEnvironment(string $shopRoot): CatalogImportBatchRepositoryInterface
    {
        if (CatalogRepositoryBackend::useJsonTestBackend()) {
            $directory = self::validatedPrivateDirectory($shopRoot);

            return new JsonFileCatalogImportBatchRepository($directory, realpath($shopRoot) ?: $shopRoot);
        }

        $context = CatalogRepositoryBackend::databaseContext($shopRoot);

        return new DatabaseCatalogImportBatchRepository($context->database, $context->tables->batches(), $context->shopId);
    }

    private static function validatedPrivateDirectory(string $shopRoot): string
    {
        $directory = trim((string) getenv('KURANEA_CATALOG_QUEUE_DIR'));
        $realDirectory = $directory === '' || is_link($directory) ? false : realpath($directory);
        $realShopRoot = realpath($shopRoot);
        if ($realDirectory === false || !is_dir($realDirectory) || !is_writable($realDirectory)
            || $realShopRoot === false) {
            throw new RuntimeException('Catalog import storage is not provisioned as a writable private directory.');
        }
        $prefix = rtrim($realShopRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
        if ($realDirectory === $realShopRoot || str_starts_with($realDirectory, $prefix)) {
            throw new RuntimeException('Catalog import storage must be outside the public PrestaShop webroot.');
        }

        return $realDirectory;
    }
}
