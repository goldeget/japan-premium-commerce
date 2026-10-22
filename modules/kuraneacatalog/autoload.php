<?php

declare(strict_types=1);

spl_autoload_register(static function (string $class): void {
    $prefix = 'Kuranea\\Catalog\\';
    if (!str_starts_with($class, $prefix)) {
        return;
    }

    $relativePath = str_replace('\\', DIRECTORY_SEPARATOR, substr($class, strlen($prefix)));
    $file = __DIR__ . '/src/' . $relativePath . '.php';
    if (is_file($file)) {
        require_once $file;
    }
});
