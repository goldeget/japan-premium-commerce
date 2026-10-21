<?php

declare(strict_types=1);

spl_autoload_register(static function (string $class): void {
    $prefix = 'Kuranea\\Backoffice\\';
    if (strncmp($class, $prefix, strlen($prefix)) !== 0) {
        return;
    }

    $relativeClass = substr($class, strlen($prefix));
    $sourceFile = dirname(__DIR__) . '/src/' . str_replace('\\', '/', $relativeClass) . '.php';
    if (is_file($sourceFile)) {
        require_once $sourceFile;
    }
});
