<?php
declare(strict_types=1);
require_once __DIR__ . '/points_support.php';

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Notifications\HealthSnapshotCommand;
use Ordenowa\Procurement\Notifications\HealthSnapshotThresholds;
use Ordenowa\Procurement\Notifications\NotificationHealthSnapshot;

final class HealthSnapshotFailingConnection
{
    public function __construct(private readonly string $privateFailure) {}

    public function executeS(string $sql, bool $array = true, bool $useCache = true): array
    {
        throw new RuntimeException($this->privateFailure);
    }
}

function healthSnapshotAssert(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException('Health snapshot assertion failed: ' . $message);
    }
}

function healthSnapshotSeed(Database $db, int $shop, string $status, int $target, int $ageSeconds = 0, bool $futureRetry = false): void
{
    $eventKey = hash('sha256', 'health-synthetic-' . $shop . '-' . $target);
    $db->execute('INSERT INTO ' . $db->table('notification')
        . ' (id_shop,id_customer,event,target_type,target_id,event_key,status,attempts,created_at) VALUES ('
        . $shop . ',11,\'health.synthetic\',\'assignment\',' . $target . ',' . $db->quote($eventKey)
        . ',\'PENDING\',0,DATE_SUB(UTC_TIMESTAMP(),INTERVAL ' . $ageSeconds . ' SECOND))');
    $notification = $db->insertId();
    $availableAt = $futureRetry
        ? 'DATE_ADD(UTC_TIMESTAMP(),INTERVAL 3600 SECOND)'
        : 'DATE_SUB(UTC_TIMESTAMP(),INTERVAL ' . $ageSeconds . ' SECOND)';
    $claimedAt = $status === 'SENDING'
        ? 'DATE_SUB(UTC_TIMESTAMP(),INTERVAL ' . $ageSeconds . ' SECOND)'
        : 'NULL';
    $db->execute('INSERT INTO ' . $db->table('notification_delivery')
        . ' (id_notification,id_shop,channel,status,attempts,available_at,claimed_at) VALUES ('
        . $notification . ',' . $shop . ',\'mail\',' . $db->quote($status) . ',0,' . $availableAt . ',' . $claimedAt . ')');
}

function healthSnapshotSeedUndeliveredEvent(Database $db, int $shop, int $target, int $ageSeconds): void
{
    $eventKey = hash('sha256', 'health-undelivered-' . $shop . '-' . $target);
    $db->execute('INSERT INTO ' . $db->table('notification')
        . ' (id_shop,id_customer,event,target_type,target_id,event_key,status,attempts,created_at) VALUES ('
        . $shop . ',11,\'health.synthetic\',\'assignment\',' . $target . ',' . $db->quote($eventKey)
        . ',\'PENDING\',0,DATE_SUB(UTC_TIMESTAMP(),INTERVAL ' . $ageSeconds . ' SECOND))');
}

function healthSnapshotDataHash(Database $db): string
{
    $data = [];
    foreach (['notification', 'notification_delivery'] as $table) {
        $rows = $db->all('SELECT * FROM ' . $db->table($table) . ' ORDER BY 1');
        foreach ($rows as &$row) {
            foreach ($row as &$value) {
                $value = $value === null ? null : (string) $value;
            }
            unset($value);
        }
        unset($row);
        $data[$table] = $rows;
    }
    return hash('sha256', json_encode($data, JSON_THROW_ON_ERROR));
}

function healthSnapshotRunCommand(array $arguments, callable $collect): array
{
    $stdout = fopen('php://temp', 'r+');
    $stderr = fopen('php://temp', 'r+');
    healthSnapshotAssert(is_resource($stdout) && is_resource($stderr), 'temporary output streams open');
    $exit = HealthSnapshotCommand::run($arguments, $collect, $stdout, $stderr);
    rewind($stdout);
    rewind($stderr);
    $result = [$exit, stream_get_contents($stdout), stream_get_contents($stderr)];
    fclose($stdout);
    fclose($stderr);
    return $result;
}

function healthSnapshotRemoveTree(string $path): void
{
    if (!is_dir($path)) {
        if (file_exists($path)) {
            unlink($path);
        }
        return;
    }
    $items = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($path, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST
    );
    foreach ($items as $item) {
        if ($item->isDir() && !$item->isLink()) {
            rmdir($item->getPathname());
        } else {
            unlink($item->getPathname());
        }
    }
    rmdir($path);
}

function healthSnapshotAssertPrematureBootstrapExitIsUnavailable(): void
{
    $repoRoot = dirname(__DIR__, 2);
    $moduleRoot = $repoRoot . '/modules/ordenowaprocurement';
    $sandbox = sys_get_temp_dir() . '/ordenowa-health-bootstrap-' . bin2hex(random_bytes(8));
    $binDir = $sandbox . '/modules/ordenowaprocurement/bin';
    $sourceDir = $sandbox . '/modules/ordenowaprocurement/src/Notifications';
    if (!mkdir($binDir, 0700, true) || !mkdir($sourceDir, 0700, true) || !mkdir($sandbox . '/config', 0700, true)) {
        throw new RuntimeException('Cannot prepare isolated CLI bootstrap fixture.');
    }
    try {
        foreach ([
            [$moduleRoot . '/autoload.php', $sandbox . '/modules/ordenowaprocurement/autoload.php'],
            [$moduleRoot . '/bin/health-snapshot.php', $binDir . '/health-snapshot.php'],
            [$moduleRoot . '/src/Notifications/HealthSnapshotCommand.php', $sourceDir . '/HealthSnapshotCommand.php'],
            [$moduleRoot . '/src/Notifications/HealthSnapshotThresholds.php', $sourceDir . '/HealthSnapshotThresholds.php'],
        ] as [$source, $destination]) {
            if (!copy($source, $destination)) {
                throw new RuntimeException('Cannot stage isolated CLI bootstrap fixture.');
            }
        }
        file_put_contents($sandbox . '/config/config.inc.php', "<?php echo 'private-bootstrap-marker'; exit(0);\n");
        $process = proc_open(
            [PHP_BINARY, $binDir . '/health-snapshot.php', '--shop=1'],
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes
        );
        healthSnapshotAssert(is_resource($process), 'isolated CLI child process starts');
        fclose($pipes[0]);
        $stdout = stream_get_contents($pipes[1]);
        $stderr = stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);
        $exit = proc_close($process);
        healthSnapshotAssert($exit === 3, 'premature native bootstrap exit cannot produce success');
        healthSnapshotAssert($stdout === '', 'native bootstrap stdout is discarded');
        healthSnapshotAssert($stderr === "Health snapshot unavailable.\n", 'premature exit has fixed redacted stderr');
        healthSnapshotAssert(!str_contains($stderr, 'private-bootstrap-marker'), 'bootstrap diagnostics do not escape the buffer');
    } finally {
        healthSnapshotRemoveTree($sandbox);
    }
}

$db = pointTestDatabase('nh_' . bin2hex(random_bytes(4)) . '_');
Schema::install($db);
$diskStats = static fn (string $path): array => [800, 1000];
$collector = new NotificationHealthSnapshot($db, sys_get_temp_dir(), $diskStats);
$defaults = HealthSnapshotThresholds::defaults();
$thresholds = new HealthSnapshotThresholds(0.10, 0.05, 2, 3, 2, 3, 1, 2);

try {
    $before = healthSnapshotDataHash($db);
    $empty = $collector->collect(1, $defaults);
    healthSnapshotAssert($empty['database_select_1'] === true, 'SELECT 1 reports database health');
    healthSnapshotAssert($empty['disk_free_ratio'] === 0.8, 'disk ratio is bounded numeric output');
    healthSnapshotAssert($empty['notification_counts'] === [
        'backlog' => 0,
        'future_retry' => 0,
        'undelivered_events' => 0,
        'failed' => 0,
        'uncertain' => 0,
        'oldest_stale_age_seconds' => 0,
    ], 'empty shop counts are zero');
    healthSnapshotAssert($empty['status'] === 'ok', 'empty shop remains healthy above thresholds');
    healthSnapshotAssert(hash_equals($before, healthSnapshotDataHash($db)), 'empty health check does not mutate rows');

    foreach ([[8, 100, 'warning'], [4, 100, 'critical']] as [$freeBytes, $totalBytes, $expectedStatus]) {
        $diskCollector = new NotificationHealthSnapshot($db, sys_get_temp_dir(), static fn (string $path): array => [$freeBytes, $totalBytes]);
        healthSnapshotAssert($diskCollector->collect(1, $defaults)['status'] === $expectedStatus, 'low disk free ratio produces the expected attention state');
    }
    $unavailableDisk = new NotificationHealthSnapshot($db, sys_get_temp_dir(), static fn (string $path): array => [false, 100]);
    [$diskExit, $diskJson, $diskError] = healthSnapshotRunCommand(
        ['--shop=1'],
        static fn (int $shop, HealthSnapshotThresholds $settings): array => $unavailableDisk->collect($shop, $settings)
    );
    healthSnapshotAssert($diskExit === 3 && $diskJson === '' && $diskError === "Health snapshot unavailable.\n", 'disk statistics failure is unavailable without diagnostic output');

    [$exit, $json, $error] = healthSnapshotRunCommand(
        ['--shop=1'],
        static fn (int $shop, HealthSnapshotThresholds $settings): array => $collector->collect($shop, $settings)
    );
    healthSnapshotAssert($exit === 0 && $error === '' && json_decode(trim($json), true)['status'] === 'ok', 'healthy output uses exit 0');

    foreach (['PENDING', 'RETRY', 'SENDING', 'FAILED', 'FAILED', 'UNCERTAIN', 'SENT'] as $index => $status) {
        $age = $status === 'SENDING' ? 2000 : (in_array($status, ['PENDING', 'RETRY'], true) ? 1200 : 0);
        healthSnapshotSeed($db, 1, $status, $index + 1, $age);
    }
    healthSnapshotSeed($db, 2, 'RETRY', 100, 0, true);
    healthSnapshotSeedUndeliveredEvent($db, 1, 200, 1800);
    healthSnapshotSeedUndeliveredEvent($db, 2, 201, 10);
    healthSnapshotSeedUndeliveredEvent($db, 3, 301, 1800);
    $seededDataHash = healthSnapshotDataHash($db);

    $shopOne = $collector->collect(1, $thresholds);
    healthSnapshotAssert($shopOne['notification_counts']['backlog'] === 4
        && $shopOne['notification_counts']['future_retry'] === 0
        && $shopOne['notification_counts']['undelivered_events'] === 1
        && $shopOne['notification_counts']['failed'] === 2
        && $shopOne['notification_counts']['uncertain'] === 1,
        'shop one aggregates active, undelivered, failed and uncertain rows');
    healthSnapshotAssert($shopOne['notification_counts']['oldest_stale_age_seconds'] >= 2000, 'claimed SENDING age contributes to stale age');
    healthSnapshotAssert($shopOne['status'] === 'critical', 'critical backlog threshold affects aggregate health');
    [$exit, $json, $error] = healthSnapshotRunCommand(
        ['--shop=1', '--backlog-warning=2', '--backlog-critical=3', '--failed-warning=2', '--failed-critical=3', '--uncertain-warning=1', '--uncertain-critical=2'],
        static fn (int $shop, HealthSnapshotThresholds $settings): array => $collector->collect($shop, $settings)
    );
    healthSnapshotAssert($exit === 2 && $error === '' && json_decode(trim($json), true)['status'] === 'critical', 'critical output uses exit 2');
    $shopTwo = $collector->collect(2, $thresholds);
    healthSnapshotAssert($shopTwo['notification_counts']['backlog'] === 1
        && $shopTwo['notification_counts']['future_retry'] === 1
        && $shopTwo['notification_counts']['undelivered_events'] === 1
        && $shopTwo['notification_counts']['failed'] === 0
        && $shopTwo['notification_counts']['uncertain'] === 0,
        'shop two counts are isolated and future retries are not due backlog');
    healthSnapshotAssert($shopTwo['notification_counts']['oldest_stale_age_seconds'] < 900, 'future retry age does not become stale age');
    healthSnapshotAssert($shopTwo['status'] === 'ok', 'a future retry below count thresholds is not falsely stale');
    $shopThree = $collector->collect(3, $thresholds);
    healthSnapshotAssert($shopThree['notification_counts']['backlog'] === 1
        && $shopThree['notification_counts']['future_retry'] === 0
        && $shopThree['notification_counts']['undelivered_events'] === 1
        && $shopThree['notification_counts']['failed'] === 0
        && $shopThree['notification_counts']['uncertain'] === 0
        && $shopThree['notification_counts']['oldest_stale_age_seconds'] >= 1800,
        'low-volume event with no delivery row is visible only for its shop');
    healthSnapshotAssert($shopThree['status'] === 'warning', 'stale age threshold catches a single stuck event below backlog count thresholds');
    [$exit, $json, $error] = healthSnapshotRunCommand(
        ['--shop=3'],
        static fn (int $shop, HealthSnapshotThresholds $settings): array => $collector->collect($shop, $settings)
    );
    healthSnapshotAssert($exit === 1 && $error === '' && json_decode(trim($json), true)['status'] === 'warning', 'warning output uses exit 1');

    $collector->collect(1, $thresholds);
    healthSnapshotAssert(hash_equals($seededDataHash, healthSnapshotDataHash($db)), 'collector reads do not mutate notification rows');

    [$exit, $json, $error] = healthSnapshotRunCommand(
        ['--shop=1'],
        static fn (int $shop, HealthSnapshotThresholds $settings): array => $collector->collect($shop, $settings)
    );
    healthSnapshotAssert($exit === 1 && $error === '' && json_decode(trim($json), true)['status'] === 'warning', 'seeded warning snapshot uses warning exit 1');
    $decoded = json_decode(trim($json), true, 16, JSON_THROW_ON_ERROR);
    healthSnapshotAssert(array_keys($decoded) === ['status', 'shop_id', 'database_select_1', 'disk_free_ratio', 'notification_counts'], 'output contains only snapshot metrics');
    healthSnapshotAssert(hash_equals($seededDataHash, healthSnapshotDataHash($db)), 'CLI snapshot does not mutate notification rows');

    foreach ([
        [],
        ['--shop=0'],
        ['--shop=1', '--shop=2'],
        ['--shop=1;echo-secret'],
        ['--shop=1', '--disk-warning-ratio=0.01', '--disk-critical-ratio=0.05'],
        ['--shop=1', '--backlog-warning=0'],
        ['--shop=1', '--stale-after-seconds=0'],
        ['--shop=1', '--unexpected=private-secret'],
    ] as $invalidArguments) {
        [$exit, $json, $error] = healthSnapshotRunCommand($invalidArguments, static fn (): array => []);
        healthSnapshotAssert($exit === 64 && $json === '', 'invalid CLI argument shape uses usage exit 64 without output');
        healthSnapshotAssert(str_contains($error, 'Usage:') && !str_contains($error, 'private-secret'), 'usage error does not echo input values');
    }

    $privateError = 'synthetic-private-db-password-0123456789';
    $brokenDb = new Database(new HealthSnapshotFailingConnection($privateError), 'nhf_');
    $brokenCollector = new NotificationHealthSnapshot($brokenDb, sys_get_temp_dir(), $diskStats);
    [$exit, $json, $error] = healthSnapshotRunCommand(
        ['--shop=1'],
        static fn (int $shop, HealthSnapshotThresholds $settings): array => $brokenCollector->collect($shop, $settings)
    );
    healthSnapshotAssert($exit === 3 && $json === '', 'runtime collection failure uses unavailable exit 3');
    healthSnapshotAssert($error === "Health snapshot unavailable.\n", 'runtime failure message is fixed');
    healthSnapshotAssert(!str_contains($error, $privateError), 'runtime exception secrets are redacted');
    healthSnapshotAssertPrematureBootstrapExitIsUnavailable();

    print "PASS notification health: database/disk metrics, empty/backlog/failure/uncertain states, stale and future retries, shop isolation, read-only data, exit codes, CLI validation, and redaction\n";
} finally {
    pointTestCleanup($db);
}
