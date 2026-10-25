<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use RuntimeException;

/** Builds importer state in the existing private catalog queue volume. */
final class CatalogImportBatchRepositoryFactory
{
    public static function fromEnvironment(string $shopRoot): JsonFileCatalogImportBatchRepository
    {
        $directory = trim((string) getenv('KURANEA_CATALOG_QUEUE_DIR'));
        $realDirectory = $directory === '' ? false : realpath($directory);
        $realShopRoot = realpath($shopRoot);
        if ($directory === '' || is_link($directory) || $realDirectory === false
            || !is_dir($realDirectory) || !is_writable($realDirectory) || $realShopRoot === false) {
            throw new RuntimeException('Catalog import storage is not provisioned as a writable private directory.');
        }

        $shopRootPrefix = rtrim($realShopRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
        if ($realDirectory === $realShopRoot || str_starts_with($realDirectory, $shopRootPrefix)) {
            throw new RuntimeException('Catalog import storage must be outside the public PrestaShop webroot.');
        }

        return new JsonFileCatalogImportBatchRepository($realDirectory, $realShopRoot);
    }
}
