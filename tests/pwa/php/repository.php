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
$db->queries=[];
$repository->save(3, 44, $digest, $envelope);
check(count($db->queries)===2 && str_starts_with($db->queries[1], 'INSERT INTO'), 'new subscription inserts');
check(str_contains($db->queries[0], 'WHERE id_shop=3 AND id_customer=44'), 'insert lookup scoped to trusted owner');
$db->queries=[];$db->reads=[[['id_subscription'=>1]]];
$repository->save(3,44,$digest,$envelope);
check(count($db->queries)===1, 'idempotent save has no owner reassignment');
$db->queries=[];$db->reads=[[],[]];$db->writeResult=false;
rejected(fn() => $repository->save(3,45,$digest,$envelope), 'unique conflict with another owner fails closed');
check(count($db->queries)===3, 'conflict readback is scoped');
foreach ([$db->queries[0],$db->queries[2]] as $query) {
    check(str_contains($query, 'WHERE id_shop=3 AND id_customer=45'), 'conflict cannot disclose other customer owner');
}
$db->queries=[];$db->reads=[];$db->writeResult=true;
$repository->revoke(3,44);
check(str_contains($db->queries[0], 'DELETE FROM') && str_contains($db->queries[0], 'WHERE id_shop=3 AND id_customer=44'), 'revoke SQL scoped to owner');
$db->queries=[];
$repository->deleteCustomer(44,[3,4]);
check(count($db->queries)===2 && str_contains($db->queries[1], 'WHERE id_shop=4 AND id_customer=44'), 'customer deletion scopes each shop');
$db->queries=[];$db->reads=[false];
rejected(fn() => $repository->active(3,44), 'database failure is not inactive success');
rejected(fn() => new SubscriptionRepository($db, 'bad`;'), 'table prefix validation');
echo "PASS: SQL repository ownership, unique conflict, lifecycle and failure contracts\n";
