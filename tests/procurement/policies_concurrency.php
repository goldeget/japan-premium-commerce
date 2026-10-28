<?php

declare(strict_types=1);
require __DIR__ . '/requests_bootstrap.php';
use Ordenowa\Procurement\Infrastructure\{Database, Schema};
use Ordenowa\Procurement\Integration\PolicyService;
use Ordenowa\Procurement\Security\Actor;
$dsn = getenv('PROCUREMENT_TEST_DSN');
if (!$dsn || !str_contains($dsn, 'dbname=ordenowa_procurement_test')) { fwrite(STDERR,"Isolated procurement test database required.\n"); exit(2); }
$connect = static fn () => new PDO($dsn, getenv('PROCUREMENT_TEST_USER') ?: 'root', getenv('PROCUREMENT_TEST_PASSWORD') ?: '');
if (($argv[1] ?? '') === 'worker') {
    [,,$prefix,$shop,$version,$gate,$worker] = $argv;
    if (!preg_match('/\Apolrace_[a-f0-9]{10}_\z/D',$prefix) || !ctype_digit($shop) || !ctype_digit($version)
        || !str_starts_with($gate, sys_get_temp_dir() . '/ordenowa-policy-')) exit(2);
    $service = new PolicyService(new Database($connect(), $prefix));
    touch($gate . '.ready.' . $worker);
    $deadline = microtime(true)+10;
    while (!is_file($gate)) { if (microtime(true)>$deadline) exit(2); usleep(1000); }
    try {
        $result = $service->save(Actor::employee((int)$shop, 10+(int)$worker, ['policy.manage']), (int)$version,
            ['operator_name' => 'SYNTHETIC concurrent operator ' . $worker]);
        echo json_encode(['version'=>$result['version']],JSON_THROW_ON_ERROR); exit(0);
    } catch (Throwable $error) { if ($error->getCode() === 409) { echo '{"conflict":true}'; exit(9); } fwrite(STDERR,'Unexpected policy worker failure'); exit(2); }
}
$prefix = 'polrace_' . bin2hex(random_bytes(5)) . '_';
$db = new Database($connect(), $prefix);
$gates = [];
$tables = ['support_post','support_link','policy','notification_delivery','notification','activity','point_ledger','point_award','point_account','review','request','assignment'];
try {
    Schema::install($db);
    for ($shop=1;$shop<=3;++$shop) foreach ([0,1] as $version) {
        $gate = sys_get_temp_dir() . '/ordenowa-policy-' . bin2hex(random_bytes(8)); $gates[]=$gate;
        $processes=[];
        foreach ([0,1] as $worker) {
            $process=proc_open([PHP_BINARY,__FILE__,'worker',$prefix,(string)$shop,(string)$version,$gate,(string)$worker], [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes);
            requestsAssert(is_resource($process),'Policy race worker starts'); fclose($pipes[0]); $processes[]=[$process,$pipes];
        }
        $deadline=microtime(true)+10;
        while (!is_file($gate.'.ready.0') || !is_file($gate.'.ready.1')) { requestsAssert(microtime(true)<$deadline,'Policy workers reach barrier'); usleep(1000); }
        touch($gate); $exits=[];
        foreach ($processes as [$process,$pipes]) { $output=stream_get_contents($pipes[1]);$error=stream_get_contents($pipes[2]);fclose($pipes[1]);fclose($pipes[2]);$exit=proc_close($process);requestsAssert(in_array($exit,[0,9],true),'Policy race returns success or version conflict:'.$error);$exits[]=$exit; }
        sort($exits); requestsAssert($exits===[0,9],'Exactly one policy revision wins simultaneous same-version edits');
        requestsAssert((int)$db->value('SELECT COUNT(*) FROM '.$db->table('policy').' WHERE id_shop='.$shop)===$version+1,'Unique immutable shop version survives concurrent initial or subsequent saves');
        requestsAssert((int)$db->value('SELECT COUNT(*) FROM '.$db->table('activity').' WHERE id_shop='.$shop)===$version+1,'Only committed policy revisions generate audit');
    }
    echo "policies_concurrency: PASS six initial/subsequent employee races, immutable versions and atomic audit\n";
} finally {
    foreach ($tables as $table) $db->execute('DROP TABLE IF EXISTS '.$db->table($table));
    foreach ($gates as $gate) foreach ([$gate,$gate.'.ready.0',$gate.'.ready.1'] as $file) if (is_file($file)) unlink($file);
}
