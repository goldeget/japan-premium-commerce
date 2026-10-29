<?php
declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

ini_set('display_errors', '0');
ini_set('html_errors', '0');
ini_set('log_errors', '0');
error_reporting(E_ALL);
set_error_handler(static function (int $severity, string $message, string $file, int $line): bool {
    if ((error_reporting() & $severity) === 0) {
        return false;
    }
    throw new ErrorException('Health snapshot runtime failure.', 0, $severity, $file, $line);
});

$baseBufferLevel = ob_get_level();
$snapshotCompleted = false;
ob_start(static fn (string $buffer): string => '');
register_shutdown_function(static function () use (&$snapshotCompleted, $baseBufferLevel): void {
    if ($snapshotCompleted) {
        return;
    }
    while (ob_get_level() > $baseBufferLevel) {
        ob_end_clean();
    }
    fwrite(STDERR, "Health snapshot unavailable.\n");
    exit(3);
});

require_once dirname(__DIR__) . '/autoload.php';

$exitCode = \Ordenowa\Procurement\Notifications\HealthSnapshotCommand::run(
    array_slice($argv, 1),
    static function (int $shop, \Ordenowa\Procurement\Notifications\HealthSnapshotThresholds $thresholds): array {
        $_GET['id_shop'] = $shop;
        $_SERVER['HTTP_HOST'] ??= 'localhost';
        $_SERVER['SERVER_NAME'] ??= 'localhost';
        $_SERVER['REQUEST_URI'] ??= '/index.php';
        $_SERVER['SCRIPT_NAME'] = '/index.php';
        require dirname(__DIR__, 3) . '/config/config.inc.php';

        if (!\Ordenowa\Procurement\Integration\Runtime::procurementEnabled()) {
            throw new RuntimeException('Health snapshot unavailable.');
        }
        $nativeShop = new Shop($shop);
        if (!Validate::isLoadedObject($nativeShop) || !$nativeShop->active) {
            throw new RuntimeException('Health snapshot unavailable.');
        }
        $database = \Ordenowa\Procurement\Integration\Runtime::database();
        return (new \Ordenowa\Procurement\Notifications\NotificationHealthSnapshot(
            $database,
            _PS_ROOT_DIR_
        ))->collect($shop, $thresholds);
    },
    STDOUT,
    STDERR
);
while (ob_get_level() > $baseBufferLevel) {
    ob_end_clean();
}
$snapshotCompleted = true;
exit($exitCode);
