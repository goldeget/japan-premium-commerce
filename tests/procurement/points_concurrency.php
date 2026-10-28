<?php
declare(strict_types=1);
require_once __DIR__ . '/points_support.php';

use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Points\PointService;
use Ordenowa\Procurement\Security\Actor;

if (($argv[1] ?? '') === 'worker') {
    try {
        $service = new PointService(pointTestDatabase($argv[2]));
        $employee = pointTestEmployee((int) $argv[4]);
        if ($argv[3] === 'award') {
            $service->award($employee, (int) $argv[5], 100, 'Concurrent manual allowance', 'concurrent-' . $argv[4]);
        } else {
            $service->correct($employee, (int) $argv[5], -60, 'Concurrent correction', 'concurrent-fix-' . $argv[4]);
        }
        print 'APPLIED';
        exit(0);
    } catch (Throwable $error) {
        if ($error->getCode() === 409 || $error->getCode() === 422) {
            print 'CONFLICT';
            exit(0);
        }
        fwrite(STDERR, 'Worker failure: ' . get_class($error) . ': ' . $error->getMessage());
        exit(1);
    }
}

function pointTestRace(\Ordenowa\Procurement\Infrastructure\Database $holder, string $prefix, string $action, int $target, int $requestId): void
{
    $holder->execute('START TRANSACTION');
    $holder->one('SELECT id_request FROM ' . $holder->table('request') . ' WHERE id_request=' . $requestId . ' FOR UPDATE');
    $jobs = [];
    foreach ([1, 2] as $employee) {
        $pipes = [];
        $process = proc_open([PHP_BINARY, __FILE__, 'worker', $prefix, $action, (string) $employee, (string) $target], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
        pointTestAssert(is_resource($process), 'worker starts');
        fclose($pipes[0]);
        $jobs[] = [$process, $pipes];
    }
    try {
        $waiting = 0;
        for ($attempt = 0; $attempt < 300; ++$attempt) {
            $waiting = (int) $holder->value("SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE ID<>CONNECTION_ID() AND DB=DATABASE() AND INFO LIKE "
                . $holder->quote('%' . $prefix . 'ordenowa_procurement_request%FOR UPDATE%'));
            if ($waiting === 2) {
                break;
            }
            usleep(10000);
        }
        pointTestAssert($waiting === 2, 'both employees actually contend on the same request lock');
    } finally {
        $holder->execute('ROLLBACK');
    }
    $results = [];
    foreach ($jobs as [$process, $pipes]) {
        $result = stream_get_contents($pipes[1]);
        $error = stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);
        pointTestAssert(proc_close($process) === 0, 'worker exits normally: ' . $error);
        $results[] = $result;
    }
    sort($results);
    pointTestAssert($results === ['APPLIED', 'CONFLICT'], 'exactly one concurrent mutation applies: ' . implode(',', $results));
}

$prefix = 'pc_' . bin2hex(random_bytes(4)) . '_';
$db = pointTestDatabase($prefix);
Schema::install($db);
try {
    $points = new PointService($db);
    $request = pointTestRequest($db);
    pointTestRace($db, $prefix, 'award', (int) $request['id_request'], (int) $request['id_request']);
    pointTestAssert($points->account(Actor::customer(1, 11))['balance'] === 100, 'concurrent base balance100');
    pointTestAssert(count($points->awards(pointTestEmployee())) === 1, 'only one base award');
    $award = $points->awards(pointTestEmployee())[0];
    pointTestRace($db, $prefix, 'correct', (int) $award['id_award'], (int) $request['id_request']);
    pointTestAssert($points->account(Actor::customer(1, 11))['balance'] === 40, 'concurrent corrections cannot over-reverse');
    pointTestAssert(count($points->ledger(Actor::customer(1, 11))) === 2, 'one base and one correction');
    pointTestAssert($points->reconcile(Actor::customer(1, 11))['consistent'] === true, 'concurrent sum agrees');
    print "PASS points concurrency: two employee awards and corrections serialize\n";
} finally {
    pointTestCleanup($db);
}
