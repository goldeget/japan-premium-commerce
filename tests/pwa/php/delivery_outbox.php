<?php
// Standalone: php tests/pwa/php/delivery_outbox.php. No provider/network/PrestaShop bootstrap.
declare(strict_types=1);
require dirname(__DIR__, 3) . '/modules/kuraneapush/autoload.php';
use Kuranea\Push\Domain\{DeliveryPayload, PushDeliveryProvider, PushDeliveryResult, PushDeliveryStore, PushOutboxStore, PushOutboxService};
use Kuranea\Push\Infrastructure\SubscriptionCipher;
function assertOutbox(bool $ok, string $label): void { if (!$ok) { throw new RuntimeException($label); } }
final class FixtureOutbox implements PushOutboxStore {
    public array $events=[];
    public array $history=[];
    public bool $locked=false;
    private function key(int $s,int $c,string $e): string { return "$s:$c:$e"; }
    public function acquire(int $s,int $c,string $e): bool { if($this->locked)return false; return $this->locked=true; }
    public function release(int $s,int $c,string $e): void { $this->locked=false; }
    public function event(int $s,int $c,string $e): ?array { return $this->events[$this->key($s,$c,$e)]??null; }
    public function create(int $s,int $c,string $e,DeliveryPayload $p,array $snapshot): void {
        $k=$this->key($s,$c,$e); if(isset($this->events[$k]))throw new RuntimeException('duplicate');
        $recipients=[];foreach($snapshot as $target)$recipients[]=$target+['outcome'=>'pending','attempts'=>0];
        $this->events[$k]=['event'=>$p->event,'locale'=>$p->locale,'recipients'=>$recipients];
    }
    public function startAttempt(int $s,int $c,string $e,string $d): int {
        $k=$this->key($s,$c,$e);foreach($this->events[$k]['recipients'] as &$r) { if($r['endpoint_digest']===$d) {
            $r['outcome']='sending';$attempt=++$r['attempts'];$this->history[]=[$k,$d,$attempt,'sending'];return $attempt;
        }}throw new RuntimeException('missing recipient');
    }
    public function finishAttempt(int $s,int $c,string $e,string $d,int $attempt,string $outcome): void {
        $k=$this->key($s,$c,$e);foreach($this->events[$k]['recipients'] as &$r) { if($r['endpoint_digest']===$d) {
            $r['outcome']=$outcome;$this->history[]=[$k,$d,$attempt,$outcome];return;
        }}throw new RuntimeException('missing recipient');
    }
}
final class FixtureTargets implements PushDeliveryStore {
    public array $rows=[];
    public array $removed=[];
    public int $readCount=0;
    public ?int $failOnRead=null;
    public function deliveryTargetsForOwner(int $s,int $c): array {
        if (++$this->readCount === $this->failOnRead) { throw new RuntimeException('Synthetic consent read failure.'); }
        return $this->rows; // Deliberately inject foreign rows.
    }
    public function removeDeliveryTargetForOwner(int $s,int $c,string $d): void {
        $this->removed[]=[$s,$c,$d];$this->rows=array_values(array_filter($this->rows,fn($r)=>!($r['id_shop']===$s&&$r['id_customer']===$c&&$r['endpoint_digest']===$d)));
    }
}
final class FixtureProvider implements PushDeliveryProvider {
    public array $calls=[];
    public array $outcomes=[];
    public bool $enabled=true;
    public function available(): bool { return $this->enabled; }
    public function send(array $subscription,DeliveryPayload $payload): PushDeliveryResult {
        $payload->toJson();$endpoint=$subscription['endpoint'];$this->calls[]=$endpoint;
        $result=$this->outcomes[$endpoint]??PushDeliveryResult::DELIVERED;
        if($result==='throw')throw new RuntimeException('synthetic failure');
        return new PushDeliveryResult($result);
    }
}
$cipher=new SubscriptionCipher(base64_encode(str_repeat('k',32)));
$subscription=fn($name)=>['endpoint'=>'https://fcm.googleapis.com/fcm/send/'.$name,'keys'=>[
    'p256dh'=>rtrim(strtr(base64_encode("\x04".str_repeat('p',64)),'+/','-_'),'='),
    'auth'=>rtrim(strtr(base64_encode(str_repeat('a',16)),'+/','-_'),'=')]];
$row=function(int $s,int $c,string $name)use($cipher,$subscription):array {
    $sub=$subscription($name);$digest=$cipher->digest($sub['endpoint']);
    return ['id_shop'=>$s,'id_customer'=>$c,'endpoint_digest'=>$digest,'encrypted_subscription'=>$cipher->encrypt($sub,$s,$c,$digest),
        'consent_notice_version'=>str_repeat('a',64),'consent_locale'=>'en','consent_accepted_at'=>'2026-10-26 00:00:00'];
};
$targets=new FixtureTargets();$outbox=new FixtureOutbox();$provider=new FixtureProvider();
$targets->rows=[$row(1,10,'ok'),$row(1,10,'retry'),$row(1,10,'gone'),$row(2,10,'other-shop'),$row(1,11,'other-customer')];
$provider->outcomes[$subscription('retry')['endpoint']]='throw';
$provider->outcomes[$subscription('gone')['endpoint']]=PushDeliveryResult::GONE;
$service=new PushOutboxService($outbox,$targets,$cipher,$provider);$payload=new DeliveryPayload('order','en');
$result=$service->receive(1,10,'event-1',$payload);
assertOutbox($result['delivered']===1&&$result['retryable_failure']===1&&$result['gone']===1,'initial outcomes persisted');
assertOutbox(count($provider->calls)===3,'foreign owner/shop never sent');
assertOutbox(count($outbox->events)===1&&count($outbox->events['1:10:event-1']['recipients'])===3,'receipt snapshots only owner recipients');
assertOutbox(count($outbox->history)===6,'every recipient has durable start/result history');
$service->receive(1,10,'event-1',$payload);
assertOutbox(count($provider->calls)===3,'duplicate receipt never triggers a resend');
try { $service->receive(1,10,'event-1',new DeliveryPayload('support','en')); throw new LogicException('conflict accepted'); }
catch(InvalidArgumentException $expected) {}
$provider->outcomes[$subscription('retry')['endpoint']]=PushDeliveryResult::DELIVERED;
// A new service uses the same persisted store, not process-local delivery state.
$service=new PushOutboxService($outbox,$targets,$cipher,$provider);
$result=$service->retry(1,10,'event-1');
assertOutbox($result['delivered']===1&&count($provider->calls)===4,'retry sends only failed recipient');
$service->retry(1,10,'event-1');assertOutbox(count($provider->calls)===4,'successful recipients never resent');
assertOutbox($service->retry(2,10,'event-1')['status']==='not_found','shop scoped event read');
assertOutbox($service->retry(1,11,'event-1')['status']==='not_found','customer scoped event read');
$targets->rows=[$row(1,10,'revoked')];$provider->outcomes[$subscription('revoked')['endpoint']]=PushDeliveryResult::RETRYABLE_FAILURE;
$service->receive(1,10,'event-revoked',$payload);$before=count($provider->calls);$targets->rows=[];
$result=$service->retry(1,10,'event-revoked');
assertOutbox($result['skipped']===1&&count($provider->calls)===$before,'withdrawn consent target stays unsent with saved outcome');
$targets->rows=[$row(1,10,'legacy')];$provider->outcomes[$subscription('legacy')['endpoint']]=PushDeliveryResult::RETRYABLE_FAILURE;
$service->receive(1,10,'event-legacy',$payload);$before=count($provider->calls);
$targets->rows[0]['consent_accepted_at']=null;
$result=$service->retry(1,10,'event-legacy');
assertOutbox($result['skipped']===1&&count($provider->calls)===$before,'missing consent evidence blocks retries even if row remains');
$targets->rows=[$row(1,10,'renewed')];$provider->outcomes[$subscription('renewed')['endpoint']]=PushDeliveryResult::RETRYABLE_FAILURE;
$service->receive(1,10,'event-renewed',$payload);$before=count($provider->calls);
// Same digest, notice and acceptance second; a fresh subscribe refreshes encryption material.
$targets->rows=[$row(1,10,'renewed')];$provider->outcomes[$subscription('renewed')['endpoint']]=PushDeliveryResult::DELIVERED;
$result=$service->retry(1,10,'event-renewed');
assertOutbox($result['skipped']===1&&count($provider->calls)===$before,'re-consent never revives an event from an earlier consent generation');
$targets->rows=[$row(1,10,'disabled')];$disabled=new PushOutboxService($outbox,$targets,$cipher);
assertOutbox($disabled->receive(1,10,'event-disabled',$payload)['status']==='provider_unavailable','default live gate closed');
assertOutbox(isset($outbox->events['1:10:event-disabled']),'disabled provider still records incoming event');
$provider->enabled=false;assertOutbox($service->retry(1,10,'event-disabled')['status']==='provider_unavailable','unavailable retry preserves receipt');
$provider->enabled=true;$outbox->locked=true;
assertOutbox($service->retry(1,10,'event-disabled')['status']==='busy','concurrent retry cannot deliver');$outbox->locked=false;
$k='1:10:event-disabled';$outbox->events[$k]['recipients'][0]['outcome']='sending';$outbox->events[$k]['recipients'][0]['attempts']=1;
$before=count($provider->calls);$result=$service->retry(1,10,'event-disabled');
assertOutbox($result['interrupted']===1&&count($provider->calls)===$before,'uncertain interrupted send is not blindly resent');
$preflightTargets=new FixtureTargets();$preflightTargets->rows=[$row(1,10,'preflight-recovery')];
$preflightTargets->failOnRead=2; // Snapshot succeeds; the current-consent recheck fails before provider I/O.
$preflightOutbox=new FixtureOutbox();$preflightProvider=new FixtureProvider();
$preflightService=new PushOutboxService($preflightOutbox,$preflightTargets,$cipher,$preflightProvider);
$preflightResult=$preflightService->receive(1,10,'delivery-history:preflight',new DeliveryPayload('delivery','en'));
$pendingRecipient=$preflightOutbox->events['1:10:delivery-history:preflight']['recipients'][0]??null;
assertOutbox($preflightResult['status']==='storage_unavailable'&&$preflightProvider->calls===[]
    &&$preflightOutbox->history===[]&&$pendingRecipient['outcome']==='pending'&&$pendingRecipient['attempts']===0,
    'consent-read failure before sending preserves a pending receipt without an interrupted attempt');
$preflightTargets->failOnRead=null;
$preflightResult=$preflightService->retry(1,10,'delivery-history:preflight');
assertOutbox($preflightResult['delivered']===1&&count($preflightProvider->calls)===1,
    'explicit retry recovers a consent-read outage and performs one synthetic provider attempt');
$preflightService->retry(1,10,'delivery-history:preflight');
assertOutbox(count($preflightProvider->calls)===1,'recovered successful recipient is not resent');
$retryTargets=new FixtureTargets();$retryTargets->rows=[$row(1,10,'retry-preflight-recovery')];
$retryOutbox=new FixtureOutbox();$retryProvider=new FixtureProvider();
$retryEndpoint=$subscription('retry-preflight-recovery')['endpoint'];
$retryProvider->outcomes[$retryEndpoint]=PushDeliveryResult::RETRYABLE_FAILURE;
$retryService=new PushOutboxService($retryOutbox,$retryTargets,$cipher,$retryProvider);
$retryService->receive(1,10,'delivery-history:retry-preflight',new DeliveryPayload('delivery','en'));
$retryTargets->failOnRead=$retryTargets->readCount+2;
$retryResult=$retryService->retry(1,10,'delivery-history:retry-preflight');
$failedRecipient=$retryOutbox->events['1:10:delivery-history:retry-preflight']['recipients'][0];
assertOutbox($retryResult['status']==='storage_unavailable'&&count($retryProvider->calls)===1
    &&$failedRecipient['outcome']==='retryable_failure'&&$failedRecipient['attempts']===1
    &&count($retryOutbox->history)===2,'consent preflight outage during retry preserves the prior failure and attempt history');
$retryTargets->failOnRead=null;$retryProvider->outcomes[$retryEndpoint]=PushDeliveryResult::DELIVERED;
$retryResult=$retryService->retry(1,10,'delivery-history:retry-preflight');
assertOutbox($retryResult['delivered']===1&&count($retryProvider->calls)===2,'retry resumes after consent storage recovers');
$overflowTargets=new FixtureTargets();
$overflowTargets->rows=array_fill(0, PushDeliveryStore::MAX_DELIVERY_TARGETS + 1, []);
$overflowOutbox=new FixtureOutbox();
$overflowProvider=new FixtureProvider();
$overflowService=new PushOutboxService($overflowOutbox,$overflowTargets,$cipher,$overflowProvider);
$overflowResult=$overflowService->receive(1,10,'event-overflow',$payload);
assertOutbox($overflowResult['status']==='storage_unavailable' && $overflowOutbox->events===[] && $overflowProvider->calls===[],
    'recipient overflow is detected before receipt creation or a provider attempt');
require __DIR__ . '/outbox_repository.php';
echo "PASS: push outbox receipts, outcomes, explicit retry, success dedupe, consent withdrawal and owner isolation\n";
