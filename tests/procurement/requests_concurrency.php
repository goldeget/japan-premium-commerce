<?php
declare(strict_types=1);
require __DIR__ . '/requests_bootstrap.php';

use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Requests\RequestService;
use Ordenowa\Procurement\Security\Actor;

$dsn = getenv('PROCUREMENT_TEST_DSN');
if (!$dsn || !str_contains($dsn, 'dbname=ordenowa_procurement_test')) {
    fwrite(STDERR, "Refusing concurrency tests without isolated ordenowa_procurement_test database.\n");
    exit(2);
}
$connect = static fn () => new PDO($dsn, getenv('PROCUREMENT_TEST_USER') ?: 'root', getenv('PROCUREMENT_TEST_PASSWORD') ?: '');
if (($argv[1] ?? '') === 'worker') {
    [,,$prefix,$assignmentId,$operation,$key,$gate,$worker] = $argv;
    if (!preg_match('/^rq_race_[a-f0-9]{10}_$/D', $prefix) || !ctype_digit($assignmentId)
        || !str_starts_with($gate, sys_get_temp_dir() . '/ordenowa-requests-')) { exit(2); }
    $service = new RequestService(new Database($connect(), $prefix));
    touch($gate . '.ready.' . $worker);
    $deadline = microtime(true) + 10;
    while (!is_file($gate)) {
        if (microtime(true) > $deadline) { fwrite(STDERR, "Race barrier timeout\n"); exit(2); }
        usleep(1000);
    }
    try {
        $result = $operation === 'submit'
            ? $service->submit(Actor::customer(1, 101), (int)$assignmentId, 1, 1, $key)
            : $service->revokeAssignment(Actor::employee(1, 10, ['procurement.manage']), (int)$assignmentId, 1, 'Synthetic race revoke');
        fwrite(STDOUT, json_encode(['status'=>$result['status'],'id_request'=>$result['id_request'] ?? null], JSON_THROW_ON_ERROR));
        exit(0);
    } catch (Throwable $error) {
        if ($error->getCode() === 409) { fwrite(STDOUT, '{"conflict":true}'); exit(9); }
        fwrite(STDERR, get_class($error) . ':' . $error->getMessage());
        exit(2);
    }
}

$db = new Database($connect(), 'rq_race_' . bin2hex(random_bytes(5)) . '_');
// Retain only the generated identifier, never any connection credentials.
$prefix = trim($db->table('assignment'), '`');
$prefix = substr($prefix, 0, -strlen('ordenowa_procurement_assignment'));
$tables = ['policy','notification_delivery','notification','activity','point_ledger','point_award','point_account','review','request','assignment'];
$gates = [];
try {
    Schema::install($db);
    $service = new RequestService($db);
    $manager = Actor::employee(1, 10, ['procurement.read','procurement.manage']);
    $product = ['shop_id'=>1,'id_product'=>7,'id_product_attribute'=>0,'names'=>['en'=>'Synthetic race product'],
        'descriptions'=>[],'image_url'=>'','reference'=>'SYNTHETIC','source_url'=>''];
    foreach (['same-key','different-key','revoke'] as $mode) {
        for ($round = 0; $round < 3; ++$round) {
            $assignment = $service->createAssignment($manager, 101, $product, []);
            $gate = sys_get_temp_dir() . '/ordenowa-requests-' . bin2hex(random_bytes(8));
            $gates[] = $gate;
            $processes = [];
            foreach ([0,1] as $worker) {
                $key = $mode . '-' . $round . ($mode === 'same-key' ? '' : '-' . $worker);
                $command = [PHP_BINARY,__FILE__,'worker',$prefix,(string)$assignment['id_assignment'],
                    $mode === 'revoke' && $worker === 1 ? 'revoke' : 'submit',$key,$gate,(string)$worker];
                $process = proc_open($command, [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']], $pipes);
                requestsAssert(is_resource($process), 'Race worker starts');
                fclose($pipes[0]);
                $processes[] = [$process,$pipes];
            }
            $deadline = microtime(true) + 10;
            while (!is_file($gate . '.ready.0') || !is_file($gate . '.ready.1')) {
                requestsAssert(microtime(true) < $deadline, 'Both race workers reach barrier');
                usleep(1000);
            }
            touch($gate);
            $results = [];
            foreach ($processes as [$process,$pipes]) {
                $output = stream_get_contents($pipes[1]);
                $error = stream_get_contents($pipes[2]);
                fclose($pipes[1]); fclose($pipes[2]);
                $exit = proc_close($process);
                requestsAssert(in_array($exit, [0,9], true), 'Worker completes without database error: ' . $error);
                $results[] = ['exit'=>$exit,'data'=>json_decode($output, true, 16, JSON_THROW_ON_ERROR)];
            }
            $requests = (int)$db->value('SELECT COUNT(*) FROM ' . $db->table('request') . ' WHERE id_assignment=' . $assignment['id_assignment']);
            if ($mode === 'same-key') {
                requestsAssert($results[0]['exit'] === 0 && $results[1]['exit'] === 0, 'Same-key retry succeeds for both clients');
                requestsAssert($results[0]['data']['id_request'] === $results[1]['data']['id_request'] && $requests === 1, 'Concurrent retry resolves same request');
            } else {
                $exits = array_column($results, 'exit'); sort($exits);
                requestsAssert($exits === [0,9], 'Exactly one mutation wins race');
                $status = $service->assignment($manager, $assignment['id_assignment'])['status'];
                requestsAssert(($status === 'REQUESTED' && $requests === 1) || ($status === 'CANCELLED' && $requests === 0), 'Race commits one consistent final assignment state');
            }
        }
    }
    fwrite(STDOUT, "PASS requests concurrency: same-key, different-key and revoke races (nine barriers)\n");
} finally {
    foreach ($gates as $gate) { foreach ([$gate,$gate.'.ready.0',$gate.'.ready.1'] as $file) { if (is_file($file)) { unlink($file); } } }
    foreach ($tables as $table) { $db->execute('DROP TABLE IF EXISTS ' . $db->table($table)); }
}
