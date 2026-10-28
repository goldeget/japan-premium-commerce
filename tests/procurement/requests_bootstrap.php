<?php
declare(strict_types=1);

spl_autoload_register(static function (string $class): void {
    $prefix = 'Ordenowa\\Procurement\\';
    if (str_starts_with($class, $prefix)) {
        $file = dirname(__DIR__, 2) . '/modules/ordenowaprocurement/src/'
            . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';
        if (is_file($file)) { require_once $file; }
    }
});

function requestsAssert(bool $condition, string $message): void
{
    if (!$condition) { throw new RuntimeException($message); }
}

function requestsReject(callable $operation, int $code, string $message): void
{
    try { $operation(); } catch (Throwable $error) {
        requestsAssert($error->getCode() === $code, $message . ': wrong error ' . $error->getCode());
        return;
    }
    throw new RuntimeException($message . ': operation unexpectedly succeeded');
}
