<?php
declare(strict_types=1);
require_once __DIR__ . '/points_support.php';

use Ordenowa\Procurement\Infrastructure\Recorder;
use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Notifications\Dispatcher;
use Ordenowa\Procurement\Notifications\DeliveryResult;
use Ordenowa\Procurement\Notifications\Transport;

final class NotificationProbeTransport implements Transport
{
    public function __construct(private readonly \Ordenowa\Procurement\Infrastructure\Database $db, private readonly ?string $release = null) {}
    public function send(array $event): DeliveryResult
    {
        $this->db->execute('INSERT INTO ' . $this->db->table('notification_probe') . ' (id_notification) VALUES (' . (int) $event['id_notification'] . ')');
        if ($this->release !== null) {
            pointTestAssert((int) $this->db->value('SELECT GET_LOCK(' . $this->db->quote($this->release) . ',5)') === 1, 'test provider release acquired');
            $this->db->value('SELECT RELEASE_LOCK(' . $this->db->quote($this->release) . ')');
        }
        return new DeliveryResult('sent');
    }
}
if (($argv[1] ?? '') === 'worker') {
    $db = pointTestDatabase($argv[2]);
    $dispatcher = new Dispatcher($db, ['mail' => new NotificationProbeTransport($db, $argv[3])]);
    print json_encode($dispatcher->dispatch(1), JSON_THROW_ON_ERROR);
    exit;
}
$prefix = 'nc_' . bin2hex(random_bytes(4)) . '_';
$db = pointTestDatabase($prefix);
Schema::install($db);
$release = 'notification_test_release_' . bin2hex(random_bytes(8));
$process = null;
$pipes = [];
try {
    $db->execute('CREATE TABLE ' . $db->table('notification_probe') . ' (id_notification BIGINT PRIMARY KEY) ENGINE=InnoDB');
    $db->transaction(fn() => (new Recorder($db))->notify(1, 11, 'assignment.created', 'assignment', 1));
    pointTestAssert((int) $db->value('SELECT GET_LOCK(' . $db->quote($release) . ',0)') === 1, 'test transport gate acquired');
    $process = proc_open([PHP_BINARY, __FILE__, 'worker', $prefix, $release], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    pointTestAssert(is_resource($process), 'concurrent worker starts');
    fclose($pipes[0]);
    for ($attempt = 0; $attempt < 300; ++$attempt) {
        if ((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_probe')) === 1) { break; }
        usleep(10000);
    }
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_probe')) === 1, 'first worker is inside external transport');
    $second = new Dispatcher($db, ['mail' => new NotificationProbeTransport($db)]);
    pointTestAssert($second->dispatch(1)['status'] === 'busy', 'second worker cannot claim while first transmits');
    $db->value('SELECT RELEASE_LOCK(' . $db->quote($release) . ')');
    $output = stream_get_contents($pipes[1]);
    $error = stream_get_contents($pipes[2]);
    fclose($pipes[1]); fclose($pipes[2]);
    pointTestAssert(proc_close($process) === 0, 'first worker exits: ' . $error);
    $process = null;
    pointTestAssert(json_decode($output, true, 512, JSON_THROW_ON_ERROR)['sent'] === 1, 'first worker sends once');
    pointTestAssert($second->dispatch(1)['sent'] === 0, 'next worker sees completed delivery');
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_probe')) === 1, 'external send exactly once');
    $db->transaction(fn() => (new Recorder($db))->notify(1, 11, 'request.submitted', 'request', 2));
    pointTestAssert((int) $db->value('SELECT GET_LOCK(' . $db->quote($release) . ',0)') === 1, 'crash gate acquired');
    $process = proc_open([PHP_BINARY, __FILE__, 'worker', $prefix, $release], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    pointTestAssert(is_resource($process), 'crash worker starts');
    fclose($pipes[0]);
    for ($attempt = 0; $attempt < 300; ++$attempt) {
        if ((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_probe')) === 2) { break; }
        usleep(10000);
    }
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_probe')) === 2, 'crash worker entered transport after durable claim');
    proc_terminate($process, 9);
    fclose($pipes[1]); fclose($pipes[2]);
    proc_close($process);
    $process = null;
    $db->value('SELECT RELEASE_LOCK(' . $db->quote($release) . ')');
    $workerLock = 'owa_notice_' . substr(hash('sha256', $db->table('notification_delivery') . ':1'), 0, 48);
    for ($attempt = 0; $attempt < 300; ++$attempt) {
        if ((int) $db->value('SELECT IS_FREE_LOCK(' . $db->quote($workerLock) . ')') === 1) { break; }
        usleep(10000);
    }
    pointTestAssert((int) $db->value('SELECT IS_FREE_LOCK(' . $db->quote($workerLock) . ')') === 1, 'killed worker connection released claim lock');
    pointTestAssert($second->dispatch(1)['sent'] === 0, 'killed worker uncertain delivery never repeated');
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_delivery') . " WHERE status='UNCERTAIN' AND last_error_code='process_interrupted'") === 1, 'actual process crash records uncertainty');
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_probe')) === 2, 'crash recovery sends no additional request');
    print "PASS notifications concurrency: active transport blocks second claim, completed delivery never repeated, killed sender remains uncertain\n";
} finally {
    $db->value('SELECT RELEASE_LOCK(' . $db->quote($release) . ')');
    if (is_resource($process)) {
        foreach ([1, 2] as $pipe) { if (isset($pipes[$pipe]) && is_resource($pipes[$pipe])) { fclose($pipes[$pipe]); } }
        proc_close($process);
    }
    $db->execute('DROP TABLE IF EXISTS ' . $db->table('notification_probe'));
    pointTestCleanup($db);
}
