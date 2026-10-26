<?php
// SQL-boundary contracts, not a substitute for an actual MariaDB concurrency/crash test.
declare(strict_types=1);
use Kuranea\Push\Domain\DeliveryPayload;
use Kuranea\Push\Infrastructure\PushOutboxRepository;
if(!function_exists('pSQL')) { function pSQL(string $value): string { return addslashes($value); } }
final class OutboxRecordingDb {
    public array $queries=[];
    public array $reads=[];
    public array $cache=[];
    public ?string $fail=null;
    public function execute(string $sql): bool {
        $this->queries[]=$sql;
        return $this->fail===null || !str_contains($sql,$this->fail);
    }
    public function executeS(string $sql,bool $array=true,bool $cache=true): array|false {
        $this->queries[]=$sql;$this->cache[]=$cache;return array_shift($this->reads)??[];
    }
}
$db=new OutboxRecordingDb();$repository=new PushOutboxRepository($db,'fixture_');
assertOutbox($repository->install(),'outbox schema install');
assertOutbox(count($db->queries)===3,'separate receipt recipient and attempt tables');
foreach($db->queries as $query) {
    assertOutbox(str_contains($query,'PRIMARY KEY(id_shop,id_customer,event_id'),'all durable records have exact owner/event key');
    assertOutbox(!str_contains($query,'encrypted_subscription'),'outbox never duplicates subscription secrets');
}
try{$repository->event(1,10,'e');throw new LogicException('unlocked access');}catch(RuntimeException $expected){}
$db->reads=[[['acquired'=>1]]];assertOutbox($repository->acquire(1,10,'e'),'owner event lock');
assertOutbox(!$repository->acquire(1,10,'e'),'same repository cannot reacquire owner event');
$db->queries=[];$digest=str_repeat('a',64);$repository->create(1,10,'e',new DeliveryPayload('order','en'),[['endpoint_digest'=>$digest,'consent_generation'=>str_repeat('b',64)]]);
assertOutbox($db->queries[0]==='START TRANSACTION'&&end($db->queries)==='COMMIT','receipt and recipient snapshot atomically committed');
assertOutbox(str_contains($db->queries[1],"VALUES (1,10,'e','order','en',UTC_TIMESTAMP())"),'trusted owner and minimal event payload persisted');
assertOutbox(str_contains($db->queries[2],"'pending',0,UTC_TIMESTAMP()"),'new recipient starts pending without fabricated attempts');
$db->queries=[];$db->reads=[[['event_type'=>'order','locale'=>'en']],[['endpoint_digest'=>$digest,'outcome'=>'pending','attempts'=>0]]];
$event=$repository->event(1,10,'e');assertOutbox($event['recipients'][0]['attempts']===0,'receipt readback includes durable recipient state');
foreach($db->queries as $query)assertOutbox(str_contains($query,"WHERE id_shop=1 AND id_customer=10 AND event_id='e'"),'receipt and recipients read owner scoped');
$db->queries=[];$db->reads=[[['attempts'=>0,'outcome'=>'pending']]];
assertOutbox($repository->startAttempt(1,10,'e',$digest)===1,'attempt number increments durable state');
assertOutbox(str_contains(implode('\n',$db->queries),"'sending',UTC_TIMESTAMP()"),'attempt begins before external send');
assertOutbox(end($db->queries)==='COMMIT','sending is committed before returning to provider');
$db->queries=[];$db->reads=[[['attempts'=>1,'outcome'=>'sending']]];
$repository->finishAttempt(1,10,'e',$digest,1,'retryable_failure');
assertOutbox(str_contains(implode('\n',$db->queries),"completed_at=UTC_TIMESTAMP()"),'attempt completion persists timestamp');
assertOutbox(end($db->queries)==='COMMIT','recipient result and attempt completion commit together');
$db->queries=[];$db->reads=[[['attempts'=>1,'outcome'=>'delivered']]];
try{$repository->startAttempt(1,10,'e',$digest);throw new LogicException('resent delivered');}catch(RuntimeException $expected){}
assertOutbox(end($db->queries)==='ROLLBACK','successful recipient cannot start another attempt');
$db->queries=[];$db->fail='INSERT INTO';
try{$repository->create(1,10,'e',new DeliveryPayload('order','en'),[['endpoint_digest'=>$digest,'consent_generation'=>str_repeat('b',64)]]);throw new LogicException('write failure ignored');}catch(RuntimeException $expected){}
assertOutbox(end($db->queries)==='ROLLBACK','failed persistence rolls back receipt snapshot');$db->fail=null;
$db->reads=[[['released'=>1]]];$repository->release(1,10,'e');
assertOutbox(count(array_filter($db->cache))===0,'lock and state queries bypass PrestaShop query cache');
$db->reads=[[['acquired'=>1]]];assertOutbox($repository->acquire(2,10,'e'),'same event ID isolated in different shop');
$db->reads=[[['released'=>1]]];$repository->release(2,10,'e');
$db->queries=[];$repository->deleteCustomer(10,[1,2]);
$deletes=array_values(array_filter($db->queries,fn($query)=>str_starts_with($query,'DELETE')));
assertOutbox(count($deletes)===6,'customer erasure includes all outbox records across enumerated shops');
foreach($deletes as $query) {
    assertOutbox(str_contains($query,'WHERE id_shop=')&&str_contains($query,'AND id_customer=10'),'outbox erasure is owner scoped');
}
