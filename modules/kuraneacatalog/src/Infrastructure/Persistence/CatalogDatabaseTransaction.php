<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Infrastructure\Persistence;

use RuntimeException;
use Throwable;

/** Request-local transaction nesting shared by both repositories on PrestaShop's connection. */
final class CatalogDatabaseTransaction
{
    private static int $depth = 0;
    private static ?int $connectionId = null;

    public static function run(object $database, callable $operation): mixed
    {
        $connectionId = spl_object_id($database);
        if (self::$depth > 0) {
            if (self::$connectionId !== $connectionId) {
                throw new RuntimeException('Catalog transaction connection changed unexpectedly.');
            }
            self::$depth++;
            try {
                return $operation();
            } finally {
                self::$depth--;
            }
        }

        if (!$database->execute('START TRANSACTION')) {
            throw new RuntimeException('Catalog storage transaction could not start.');
        }
        self::$depth = 1;
        self::$connectionId = $connectionId;
        try {
            $result = $operation();
            if (!$database->execute('COMMIT')) {
                throw new RuntimeException('Catalog storage transaction could not commit.');
            }

            return $result;
        } catch (Throwable $exception) {
            $database->execute('ROLLBACK');
            throw $exception;
        } finally {
            self::$depth = 0;
            self::$connectionId = null;
        }
    }
}
