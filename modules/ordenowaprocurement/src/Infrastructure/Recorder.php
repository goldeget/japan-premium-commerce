<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Infrastructure;

use Ordenowa\Procurement\Security\Actor;

final class Recorder
{
    public function __construct(private readonly Database $db) {}

    public function audit(Actor $actor, string $action, string $type, int $id, array $safe = []): void
    {
        // Only scalar domain identifiers/statuses belong here; never request bodies or secrets.
        $allowed = ['status', 'decision', 'version', 'id_assignment', 'id_request', 'id_review', 'id_award', 'id_ledger', 'id_account'];
        $safe = array_intersect_key($safe, array_flip($allowed));
        foreach ($safe as $key => $value) {
            if (!is_int($value) && !is_string($value)) {
                unset($safe[$key]);
            }
        }
        $this->db->execute('INSERT INTO ' . $this->db->table('activity')
            . ' (id_shop,actor_type,actor_id,action,target_type,target_id,safe_data,created_at) VALUES ('
            . $actor->shopId . ',' . $this->db->quote($actor->type) . ',' . $actor->id . ','
            . $this->db->quote($action) . ',' . $this->db->quote($type) . ',' . $id . ','
            . $this->db->quote(json_encode($safe, JSON_THROW_ON_ERROR)) . ',UTC_TIMESTAMP())');
    }

    public function notify(int $shop, int $customer, string $event, string $targetType, int $targetId): void
    {
        $eventKey = hash('sha256', json_encode([$shop, $customer, $event, $targetType, $targetId], JSON_THROW_ON_ERROR));
        $this->db->execute('INSERT INTO ' . $this->db->table('notification')
            . ' (id_shop,id_customer,event,target_type,target_id,event_key,status,attempts,created_at) VALUES ('
            . $shop . ',' . $customer . ',' . $this->db->quote($event) . ',' . $this->db->quote($targetType)
            . ',' . $targetId . ',' . $this->db->quote($eventKey) . ",'PENDING',0,UTC_TIMESTAMP())");
    }
}
