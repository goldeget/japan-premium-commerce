<?php
declare(strict_types=1);
require_once __DIR__ . '/points_support.php';

use Ordenowa\Procurement\Infrastructure\Recorder;
use Ordenowa\Procurement\Infrastructure\Schema;
use Ordenowa\Procurement\Notifications\Dispatcher;
use Ordenowa\Procurement\Notifications\DeliveryResult;
use Ordenowa\Procurement\Notifications\Transport;

final class NotificationTestTransport implements Transport
{
    public array $sent = [];
    public string $outcome = 'sent';
    public function send(array $event): DeliveryResult
    {
        $this->sent[] = $event['id_notification'];
        if ($this->outcome === 'throw') {
            throw new RuntimeException('Potentially transmitted private content must not be logged');
        }
        return new DeliveryResult($this->outcome, $this->outcome === 'retry' ? 'provider_unavailable' : '');
    }
}

$db = pointTestDatabase('nt_' . bin2hex(random_bytes(4)) . '_');
Schema::install($db);
try {
    $mail = new NotificationTestTransport();
    $push = new NotificationTestTransport();
    $dispatcher = new Dispatcher($db, ['mail' => $mail, 'push' => $push]);
    $recorder = new Recorder($db);
    pointTestReject(function () use ($db, $recorder): void {
        $db->transaction(function () use ($recorder): void {
            $recorder->notify(1, 11, 'points.awarded', 'point_ledger', 1);
            throw new RuntimeException('Rollback');
        });
    }, 'rolled back event is invisible');
    pointTestReject(fn() => $db->transaction(fn() => $dispatcher->dispatch(1)), 'dispatcher must run after commit', 409);
    pointTestAssert($dispatcher->dispatch(1)['sent'] === 0, 'no delivery before domain commit');
    $db->transaction(fn() => $recorder->notify(1, 11, 'assignment.created', 'assignment', 1));
    $push->outcome = 'retry';
    $result = $dispatcher->dispatch(1);
    pointTestAssert($result['sent'] === 1 && $result['retry'] === 1, 'channels tracked independently');
    pointTestAssert(count($mail->sent) === 1 && count($push->sent) === 1, 'one attempt per channel');
    $dispatcher->dispatch(1);
    pointTestAssert(count($mail->sent) === 1 && count($push->sent) === 1, 'sent never repeated and failed observes backoff');
    $db->execute('UPDATE ' . $db->table('notification_delivery') . " SET available_at=DATE_SUB(UTC_TIMESTAMP(),INTERVAL 1 SECOND) WHERE channel='push'");
    $push->outcome = 'sent';
    pointTestAssert($dispatcher->dispatch(1)['sent'] === 1, 'due failure retries only push');
    pointTestAssert(count($mail->sent) === 1 && count($push->sent) === 2, 'mail success survives push failure');
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification') . " WHERE status='PENDING'") === 1, 'in-app record remains independently available');
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('point_ledger')) === 0, 'notification retries cannot award points');

    $db->transaction(fn() => $recorder->notify(1, 11, 'request.reviewed', 'request', 2));
    $mail->outcome = 'throw';
    $result = $dispatcher->dispatch(1);
    pointTestAssert($result['uncertain'] === 1, 'transport exception preserves uncertainty');
    $count = count($mail->sent);
    $dispatcher->dispatch(1);
    pointTestAssert(count($mail->sent) === $count, 'uncertain never automatically resent');
    $uncertain = $db->one('SELECT * FROM ' . $db->table('notification_delivery') . " WHERE channel='mail' AND status='UNCERTAIN'");
    pointTestAssert($uncertain['last_error_code'] === 'transport_uncertain', 'exception content never persisted');
    pointTestReject(fn() => $dispatcher->retryUncertain(1, (int) $uncertain['id_delivery'], false), 'manual duplicate acknowledgement required');
    $dispatcher->retryUncertain(1, (int) $uncertain['id_delivery'], true);
    $mail->outcome = 'sent';
    pointTestAssert($dispatcher->dispatch(1)['sent'] === 1, 'explicit acknowledged retry permitted');

    $db->transaction(fn() => $recorder->notify(1, 11, 'points.corrected', 'point_ledger', 3));
    $mail->outcome = 'retry';
    for ($attempt = 1; $attempt <= 5; ++$attempt) {
        $dispatcher->dispatch(1);
        $db->execute('UPDATE ' . $db->table('notification_delivery') . " SET available_at=UTC_TIMESTAMP() WHERE status='RETRY'");
    }
    $failed = $db->one('SELECT * FROM ' . $db->table('notification_delivery') . " WHERE channel='mail' AND status='FAILED'");
    pointTestAssert((int) $failed['attempts'] === 5, 'five attempt bound enforced');
    $count = count($mail->sent);
    $dispatcher->dispatch(1);
    pointTestAssert(count($mail->sent) === $count, 'exhausted channel stops');

    // Simulate process loss after claim: claim is durable but transmission outcome is unknown.
    $db->transaction(fn() => $recorder->notify(1, 11, 'request.submitted', 'request', 4));
    $dispatcher->dispatch(2);
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_delivery') . ' WHERE id_shop=2') === 0, 'worker exact shop boundary');
    $db->execute('INSERT INTO ' . $db->table('notification_delivery') . " (id_notification,id_shop,channel,status,attempts,available_at,claimed_at) SELECT id_notification,id_shop,'mail','SENDING',1,UTC_TIMESTAMP(),UTC_TIMESTAMP() FROM " . $db->table('notification') . ' WHERE target_id=4');
    $mail->outcome = 'sent';
    $count = count($mail->sent);
    pointTestAssert($dispatcher->dispatch(1)['uncertain'] === 1, 'recovered uncertainty included in aggregate result');
    pointTestAssert(count($mail->sent) === $count, 'crashed claim is not resent');
    pointTestAssert((int) $db->value('SELECT COUNT(*) FROM ' . $db->table('notification_delivery') . " WHERE status='UNCERTAIN' AND last_error_code='process_interrupted'") === 1, 'crash uncertainty recorded');
    print "PASS notifications: commit visibility, independent channels, backoff, bounded retry, uncertainty, shop isolation, zero point mutations\n";
} finally {
    $db->execute('DROP TABLE IF EXISTS ' . $db->table('notification_delivery'));
    pointTestCleanup($db);
}
