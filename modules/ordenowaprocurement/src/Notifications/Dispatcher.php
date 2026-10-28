<?php
declare(strict_types=1);
namespace Ordenowa\Procurement\Notifications;

use Ordenowa\Procurement\Infrastructure\Database;

/** Post-commit worker. A connection advisory lock covers claims and external delivery. */
final class Dispatcher
{
    public const MAX_ATTEMPTS = 5;

    public function __construct(private readonly Database $db, private readonly array $transports)
    {
        foreach ($transports as $channel => $transport) {
            if (!in_array($channel, ['mail', 'push'], true) || !$transport instanceof Transport) {
                throw new \InvalidArgumentException('Configure explicit mail or push transports.');
            }
        }
        if ($transports === []) {
            throw new \InvalidArgumentException('At least one transport is required.');
        }
    }

    public function dispatch(int $shop, int $limit = 25): array
    {
        if ($shop < 1 || $limit < 1 || $limit > 100) {
            throw new \InvalidArgumentException('Choose one shop and a limit between 1 and 100.', 422);
        }
        if ((int) $this->db->value('SELECT @@in_transaction') !== 0) {
            throw new \RuntimeException('Notification dispatch requires a committed domain transaction.', 409);
        }
        $result = ['status' => 'completed', 'sent' => 0, 'retry' => 0, 'uncertain' => 0, 'skipped' => 0, 'failed' => 0];
        $lock = 'owa_notice_' . substr(hash('sha256', $this->db->table('notification_delivery') . ':' . $shop), 0, 48);
        if ((int) $this->db->value('SELECT GET_LOCK(' . $this->db->quote($lock) . ',0)') !== 1) {
            return array_replace($result, ['status' => 'busy']);
        }
        try {
            // Only a dead worker can leave SENDING while this advisory lock is available.
            $result['uncertain'] = (int) $this->db->value('SELECT COUNT(*) FROM ' . $this->db->table('notification_delivery') . " WHERE id_shop=" . $shop . " AND status='SENDING'");
            $this->db->execute('UPDATE ' . $this->db->table('notification_delivery')
                . " SET status='UNCERTAIN',last_error_code='process_interrupted' WHERE id_shop=" . $shop . " AND status='SENDING'");
            foreach (array_keys($this->transports) as $channel) {
                $quoted = $this->db->quote($channel);
                $this->db->execute('INSERT IGNORE INTO ' . $this->db->table('notification_delivery')
                    . ' (id_notification,id_shop,channel,status,attempts,available_at) SELECT n.id_notification,n.id_shop,' . $quoted . ",'PENDING',0,UTC_TIMESTAMP() FROM "
                    . $this->db->table('notification') . ' n WHERE n.id_shop=' . $shop . ' AND NOT EXISTS (SELECT 1 FROM '
                    . $this->db->table('notification_delivery') . ' d WHERE d.id_notification=n.id_notification AND d.channel=' . $quoted . ') ORDER BY n.id_notification LIMIT ' . $limit);
            }
            for ($processed = 0; $processed < $limit; ++$processed) {
                $event = $this->claim($shop);
                if ($event === null) {
                    break;
                }
                try {
                    $outcome = $this->transports[$event['channel']]->send($event);
                } catch (\Throwable) {
                    $outcome = new DeliveryResult('uncertain', 'transport_uncertain');
                }
                $status = strtoupper($outcome->status);
                if ($status === 'RETRY' && (int) $event['attempts'] >= self::MAX_ATTEMPTS) {
                    $status = 'FAILED';
                }
                $delay = min(3600, 60 * (2 ** ((int) $event['attempts'] - 1)));
                // A persistence failure leaves SENDING, which the next worker marks UNCERTAIN.
                $this->db->execute('UPDATE ' . $this->db->table('notification_delivery') . ' SET status=' . $this->db->quote($status)
                    . ',last_error_code=' . $this->db->quote($outcome->code)
                    . ',available_at=DATE_ADD(UTC_TIMESTAMP(),INTERVAL ' . $delay . ' SECOND)'
                    . ($status === 'SENT' ? ',sent_at=UTC_TIMESTAMP()' : '')
                    . ' WHERE id_delivery=' . (int) $event['id_delivery'] . ' AND id_shop=' . $shop
                    . " AND status='SENDING' AND attempts=" . (int) $event['attempts']);
                ++$result[strtolower($status)];
            }
            return $result;
        } finally {
            $this->db->value('SELECT RELEASE_LOCK(' . $this->db->quote($lock) . ')');
        }
    }

    public function retryUncertain(int $shop, int $deliveryId, bool $acknowledgePossibleDuplicate): void
    {
        if (!$acknowledgePossibleDuplicate || $shop < 1 || $deliveryId < 1) {
            throw new \InvalidArgumentException('Explicit acknowledgement of possible duplicate delivery is required.', 422);
        }
        $this->db->transaction(function () use ($shop, $deliveryId): void {
            $row = $this->db->one('SELECT * FROM ' . $this->db->table('notification_delivery') . ' WHERE id_shop=' . $shop . ' AND id_delivery=' . $deliveryId . ' FOR UPDATE');
            if ($row === null) {
                throw new \RuntimeException('Delivery not found.', 404);
            }
            if ($row['status'] !== 'UNCERTAIN' || (int) $row['attempts'] >= self::MAX_ATTEMPTS || !isset($this->transports[$row['channel']])) {
                throw new \RuntimeException('Only an uncertain delivery below the attempt limit can be retried.', 409);
            }
            $this->db->execute('UPDATE ' . $this->db->table('notification_delivery')
                . " SET status='PENDING',available_at=UTC_TIMESTAMP(),last_error_code='manual_retry_acknowledged' WHERE id_delivery=" . $deliveryId . ' AND id_shop=' . $shop);
        });
    }

    private function claim(int $shop): ?array
    {
        return $this->db->transaction(function () use ($shop): ?array {
            $channels = implode(',', array_map($this->db->quote(...), array_keys($this->transports)));
            $event = $this->db->one('SELECT n.*,d.id_delivery,d.channel,d.attempts FROM ' . $this->db->table('notification_delivery') . ' d INNER JOIN '
                . $this->db->table('notification') . ' n ON n.id_notification=d.id_notification AND n.id_shop=d.id_shop'
                . ' WHERE d.id_shop=' . $shop . ' AND d.channel IN (' . $channels . ") AND d.status IN ('PENDING','RETRY') AND d.attempts<" . self::MAX_ATTEMPTS
                . ' AND d.available_at<=UTC_TIMESTAMP() ORDER BY d.id_delivery LIMIT 1 FOR UPDATE');
            if ($event === null) {
                return null;
            }
            ++$event['attempts'];
            $this->db->execute('UPDATE ' . $this->db->table('notification_delivery') . " SET status='SENDING',attempts=" . (int) $event['attempts']
                . ',claimed_at=UTC_TIMESTAMP() WHERE id_delivery=' . (int) $event['id_delivery']);
            return $event;
        });
    }
}
