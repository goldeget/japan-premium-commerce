<?php

declare(strict_types=1);
spl_autoload_register(static function (string $class): void {
    $prefix = 'Kuranea\\Push\\';
    if (strncmp($class, $prefix, strlen($prefix)) !== 0) {
        return;
    }
    $relative = substr($class, strlen($prefix));
    if (preg_match('/\A[A-Za-z0-9_\\\\]+\z/D', $relative) !== 1) {
        return;
    }
    $file = __DIR__ . '/src/' . str_replace('\\', '/', $relative) . '.php';
    if (is_file($file)) {
        require_once $file;
    }
});
