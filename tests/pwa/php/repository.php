<?php
// Exercise the actual SQL repository against a deterministic database boundary.
// Runtime MariaDB lifecycle/unique constraint coverage remains isolated CI work.
declare(strict_types=1);
use Kuranea\Push\Infrastructure\SubscriptionRepository;
if (!function_exists('pSQL')) {
    function pSQL(string $value): string { return addslashes($value); }
}
final class RecordingPushDb
{
    public array $queries = [];
    public array $reads = [];
    public bool $writeResult = true;
    public function execute(string $query): bool { $this->queries[]=$query; return $this->writeResult; }
    public function executeS(string $query): array|false { $this->queries[]=$query; return array_shift($this->reads) ?? []; }
}
$db = new RecordingPushDb();
$repository = new SubscriptionRepository($db, 'test_');
check($repository->install(), 'schema install');
check(str_contains($db->queries[0], 'UNIQUE KEY shop_endpoint (id_shop, endpoint_digest)'), 'shop digest database uniqueness');
check(str_contains($db->queries[0], 'consent_notice_version CHAR(64)') && str_contains($db->queries[0], 'consent_locale CHAR(2)')
    && str_contains($db->queries[0], 'consent_accepted_at DATETIME NULL'), 'new schema stores nullable explicit consent evidence');
check(!preg_grep('/UPDATE /i', $db->queries), 'schema upgrade does not fabricate consent for existing rows');
$db->queries=[];
$db->reads=[[],[['id_subscription'=>1,'encrypted_subscription'=>$envelope,'consent_notice_version'=>str_repeat('a',64),'consent_locale'=>'en','consent_accepted_at'=>'2026-10-26 00:00:00']]];
$repository->save(3, 44, $digest, $envelope, 'en', str_repeat('a',64));
check(count($db->queries)===3 && str_starts_with($db->queries[1], 'INSERT INTO'), 'new subscription inserts');
check(str_contains($db->queries[0], 'WHERE id_shop=3 AND id_customer=44'), 'insert lookup scoped to trusted owner');
check(str_contains($db->queries[1], 'consent_notice_version,consent_locale,consent_accepted_at'), 'insert stores consent snapshot');
$db->queries=[];$db->reads=[[['id_subscription'=>1]],[['id_subscription'=>1,'consent_notice_version'=>str_repeat('b',64),'consent_locale'=>'ja','consent_accepted_at'=>'2026-10-26 00:00:01','encrypted_subscription'=>$envelope]]];
$repository->save(3,44,$digest,$envelope,'ja',str_repeat('b',64));
check(count($db->queries)===2 && str_starts_with($db->queries[0], 'UPDATE'), 'explicit resubscribe refreshes consent evidence');
check(str_contains($db->queries[0], 'WHERE id_shop=3 AND id_customer=44'), 'consent update remains owner scoped');
check(str_contains($db->queries[0], "SET encrypted_subscription='" . pSQL($envelope) . "'"), 'same-owner resubscribe refreshes subscription encryption material');
$db->queries=[];$db->reads=[[['Field'=>'consent_notice_version']],[['Field'=>'consent_locale']],[['Field'=>'consent_accepted_at']]];
check($repository->install(), 'upgrade legacy schema');
check(count($db->queries)===4 && !preg_grep('/ALTER TABLE/i', $db->queries), 'existing columns are preserved without destructive migration');
$db->queries=[];
$db->queries=[];$db->reads=[[['id_subscription'=>1]]];
$db->reads=[[['id_subscription'=>1]],[['id_subscription'=>1,'consent_notice_version'=>str_repeat('c',64),'consent_locale'=>'ko','consent_accepted_at'=>'2026-10-26 00:00:02','encrypted_subscription'=>$envelope]]];
$repository->save(3,44,$digest,$envelope,'ko',str_repeat('c',64));
check(count($db->queries)===2, 'idempotent save refreshes consent without owner reassignment');
$db->queries=[];$db->reads=[[['id_subscription'=>1]]];
check($repository->stored(3,44), 'legacy subscription remains stored for owner revocation');
check(!str_contains($db->queries[0], 'consent_notice_version IS NOT NULL'), 'stored lookup includes legacy unconsented rows');
$db->queries=[];$db->reads=[[],[]];$db->writeResult=false;
rejected(fn() => $repository->save(3,45,$digest,$envelope,'en',str_repeat('d',64)), 'unique conflict with another owner fails closed');
check(count($db->queries)===3, 'conflict readback is scoped');
foreach ([$db->queries[0],$db->queries[2]] as $query) {
    check(str_contains($query, 'WHERE id_shop=3 AND id_customer=45'), 'conflict cannot disclose other customer owner');
}
$db->queries=[];$db->reads=[];$db->writeResult=true;
$db->reads=[[]];
check(!$repository->active(3,44), 'legacy subscription without explicit consent is not active');
check(str_contains($db->queries[0], 'consent_notice_version IS NOT NULL')
    && str_contains($db->queries[0], 'consent_accepted_at IS NOT NULL'), 'active read requires explicit consent evidence');
$db->queries=[];$db->reads=[];
$repository->revoke(3,44);
check(str_contains($db->queries[0], 'DELETE FROM') && str_contains($db->queries[0], 'WHERE id_shop=3 AND id_customer=44'), 'revoke SQL scoped to owner');
$db->queries=[];
$repository->deleteCustomer(44,[3,4]);
check(count($db->queries)===2 && str_contains($db->queries[1], 'WHERE id_shop=4 AND id_customer=44'), 'customer deletion scopes each shop');
$db->queries=[];$db->reads=[false];
rejected(fn() => $repository->active(3,44), 'database failure is not inactive success');
$db->queries=[];$db->reads=[[['id_shop'=>3,'id_customer'=>44,'endpoint_digest'=>$digest,'encrypted_subscription'=>$envelope,
    'consent_notice_version'=>str_repeat('a',64),'consent_locale'=>'ja','consent_accepted_at'=>'2026-10-26 00:00:00']]];
$targets=$repository->deliveryTargetsForOwner(3,44);
check(count($targets)===1 && $targets[0]['id_shop']===3 && $targets[0]['id_customer']===44, 'delivery target read returns owner rows');
check(str_contains($db->queries[0], 'WHERE id_shop=3 AND id_customer=44')
    && str_contains($db->queries[0], 'consent_notice_version IS NOT NULL')
    && str_contains($db->queries[0], 'consent_accepted_at IS NOT NULL')
    && str_contains($db->queries[0], 'LIMIT 100'), 'delivery target query is owner scoped, consent gated and bounded');
$db->queries=[];
$repository->removeDeliveryTargetForOwner(3,44,$digest);
check(str_contains($db->queries[0], 'DELETE FROM') && str_contains($db->queries[0], 'WHERE id_shop=3 AND id_customer=44')
    && str_contains($db->queries[0], "endpoint_digest='" . $digest . "'"), 'permanent-gone removal binds exact owner and digest');
$db->queries=[];
rejected(fn() => $repository->removeDeliveryTargetForOwner(3,44,'bad-digest'), 'delivery removal validates digest');
rejected(fn() => $repository->deliveryTargetsForOwner(3,0), 'delivery lookup rejects invalid owner');
$db->reads=[false];
rejected(fn() => $repository->deliveryTargetsForOwner(3,44), 'delivery lookup surfaces database failure');
rejected(fn() => new SubscriptionRepository($db, 'bad`;'), 'table prefix validation');
echo "PASS: SQL repository ownership, unique conflict, lifecycle and failure contracts\n";
