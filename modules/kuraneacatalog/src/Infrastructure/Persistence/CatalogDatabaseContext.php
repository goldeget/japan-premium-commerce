<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use RuntimeException;

final class CatalogDatabaseContext
{
    public function __construct(
        public readonly object $database,
        public readonly CatalogDatabaseTables $tables,
        public readonly string $privateDirectory,
        public readonly string $shopRoot,
        public readonly int $shopId
    ) {
    }

    public static function fromPrestaShop(string $shopRoot): self
    {
        $directory = trim((string) getenv('KURANEA_CATALOG_QUEUE_DIR'));
        $realDirectory = $directory === '' || is_link($directory) ? false : realpath($directory);
        $realShopRoot = $shopRoot === '' ? false : realpath($shopRoot);
        if ($realDirectory === false || !is_dir($realDirectory) || !is_writable($realDirectory)
            || $realShopRoot === false) {
            throw new RuntimeException('Catalog storage is not provisioned as a writable private directory.');
        }
        $shopPrefix = rtrim($realShopRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
        if ($realDirectory === $realShopRoot || str_starts_with($realDirectory, $shopPrefix)) {
            throw new RuntimeException('Catalog storage must be outside the public PrestaShop webroot.');
        }

        if (!class_exists('Db') || !class_exists('Context')) {
            throw new RuntimeException('Catalog database storage is unavailable.');
        }
        $context = \Context::getContext();
        $shopId = (int) ($context->shop->id ?? 0);
        if ($shopId < 1) {
            throw new RuntimeException('Catalog shop context is unavailable.');
        }

        $database = \Db::getInstance();
        $tables = new CatalogDatabaseTables($database);

        return new self($database, $tables, $realDirectory, $realShopRoot, $shopId);
    }
}
