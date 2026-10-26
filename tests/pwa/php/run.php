<?php
// Standalone behavioral contracts: php tests/pwa/php/run.php
// No PrestaShop bootstrap, customer fixtures, DNS, provider, or network access.
declare(strict_types=1);
$root = dirname(__DIR__, 3);
if (!is_file($root . '/modules/kuraneapush/autoload.php')) {
    fwrite(STDERR, "FAIL: push module contracts are absent\n");
    exit(1);
}
require $root . '/modules/kuraneapush/autoload.php';
use Kuranea\Push\Domain\SubscriptionValidator;
use Kuranea\Push\Domain\Readiness;
use Kuranea\Push\Domain\RequestGuard;
use Kuranea\Push\Domain\SubscriptionStore;
use Kuranea\Push\Domain\SubscriptionApi;
use Kuranea\Push\Domain\ConsentNoticeVersion;
use Kuranea\Push\Infrastructure\SubscriptionCipher;
use Kuranea\Push\Domain\DeliveryPayload;
use Kuranea\Push\Domain\PushDeliveryResult;
use Kuranea\Push\Domain\PushDeliveryStore;
use Kuranea\Push\Domain\PushDeliveryService;
use Kuranea\Push\Infrastructure\DisabledPushDeliveryProvider;
use Kuranea\Push\Infrastructure\IsolatedSyntheticPushDeliveryProvider;

function check(bool $ok, string $label): void {
    if (!$ok) { throw new RuntimeException('FAIL: ' . $label); }
}
function rejected(callable $fn, string $label): void {
    try { $fn(); } catch (InvalidArgumentException | RuntimeException $e) { return; }
    throw new RuntimeException('FAIL: ' . $label);
}
function b64url(string $value): string { return rtrim(strtr(base64_encode($value), '+/', '-_'), '='); }
$subscription = ['endpoint' => 'https://fcm.googleapis.com/fcm/send/synthetic-only',
    'keys' => ['p256dh' => b64url("\x04" . str_repeat('p', 64)), 'auth' => b64url(str_repeat('a', 16))]];
check(SubscriptionValidator::validate($subscription) === $subscription, 'valid synthetic fields');
foreach (['http://fcm.googleapis.com/p', 'https://127.0.0.1/p', 'https://[::1]/p', 'https://internal/p', 'https://fcm.googleapis.com.evil.example/p', 'https://user@fcm.googleapis.com/p', 'https://fcm.googleapis.com/p#fragment', 'https://fcm.googleapis.com:444/p', 'https://fcm.googleapis.com/' . str_repeat('x', 2048)] as $endpoint) {
    $bad = $subscription; $bad['endpoint'] = $endpoint;
    rejected(fn() => SubscriptionValidator::validate($bad), 'unsafe endpoint rejected');
}
foreach (['p256dh' => b64url(str_repeat('x', 64)), 'auth' => b64url(str_repeat('x', 15))] as $name => $value) {
    $bad = $subscription; $bad['keys'][$name] = $value;
    rejected(fn() => SubscriptionValidator::validate($bad), 'invalid key length rejected');
}
$bad = $subscription; $bad['id_customer'] = 42;
rejected(fn() => SubscriptionValidator::validate($bad), 'extra subscription fields rejected');
$key = base64_encode(str_repeat('k', 32));
$cipher = new SubscriptionCipher($key);
$digest = $cipher->digest($subscription['endpoint']);
$envelope = $cipher->encrypt($subscription, 1, 10, $digest);
check($envelope !== $cipher->encrypt($subscription, 1, 10, $digest), 'random nonce');
check(strpos($envelope, $subscription['endpoint']) === false, 'encrypted endpoint');
check($cipher->decrypt($envelope, 1, 10, $digest) === $subscription, 'round trip');
rejected(fn() => $cipher->decrypt($envelope, 2, 10, $digest), 'shop bound AAD');
rejected(fn() => $cipher->decrypt($envelope, 1, 11, $digest), 'customer bound AAD');
rejected(fn() => $cipher->decrypt($envelope, 1, 10, str_repeat('0', 64)), 'digest bound AAD');
$tampered = json_decode($envelope, true, 8, JSON_THROW_ON_ERROR);
$tag = base64_decode($tampered['tag'], true); $tag[0] = chr(ord($tag[0]) ^ 1);
$tampered['tag'] = base64_encode($tag);
rejected(fn() => $cipher->decrypt(json_encode($tampered), 1, 10, $digest), 'tampered authentication tag');
rejected(fn() => $cipher->decrypt(str_repeat('x', 8193), 1, 10, $digest), 'bounded encrypted envelope');
rejected(fn() => new SubscriptionCipher(''), 'missing key fails closed');
rejected(fn() => new SubscriptionCipher(base64_encode(str_repeat('k', 31))), 'wrong key length');
check(RequestGuard::allows('POST', 'https://shop.example', 'https://shop.example/store/', 'purpose', 'purpose'), 'same origin purpose token');
check(RequestGuard::allows('POST', 'http://localhost:18080', 'http://localhost:18080/store/', 'purpose', 'purpose'), 'configured HTTP loopback origin');
check(!RequestGuard::allows('POST', 'https://localhost:18080', 'http://localhost:18080/store/', 'purpose', 'purpose'), 'wrong scheme');
check(!RequestGuard::allows('POST', 'http://evil.example:18080', 'http://localhost:18080/store/', 'purpose', 'purpose'), 'wrong configured host');
foreach ([['GET','https://shop.example','purpose'], ['POST','https://evil.example','purpose'], ['POST','https://shop.example','wrong'], ['POST','','purpose'], ['POST','https://shop.example/','purpose']] as [$method,$origin,$token]) {
    check(!RequestGuard::allows($method,$origin,'https://shop.example/store/',$token,'purpose'), 'request rejected');
}
$env = ['CI'=>'true','GITHUB_ACTIONS'=>'true','KURANEA_ISOLATED_CI'=>'1','ORDENOWA_PUSH_TEST_MODE'=>'1','GITHUB_RUN_ID'=>'123','GITHUB_RUN_ATTEMPT'=>'2','KURANEA_CI_PROJECT_NAME'=>'kuranea-ci-123-2'];
check(Readiness::isolated($env), 'exact isolated run');
foreach (array_keys($env) as $name) { $bad=$env; unset($bad[$name]); check(!Readiness::isolated($bad), 'all readiness gates required'); }
check(!Readiness::canSubscribe($env, ' ', true), 'blank consent copy');
check(!Readiness::canSubscribe($env, 'Synthetic copy', false), 'missing key');
check(!Readiness::isolated([]), 'production unavailable');
check(ConsentNoticeVersion::forNotice(' Synthetic copy ', 'en') === ConsentNoticeVersion::forNotice('Synthetic copy', 'en'), 'displayed notice boundary whitespace normalization');
check(ConsentNoticeVersion::forNotice('Synthetic copy', 'ja') !== ConsentNoticeVersion::forNotice('Synthetic copy', 'en'), 'notice locale changes version');

final class MemoryStore implements SubscriptionStore {
    public array $rows=[];
    public int $saveCount=0;
    public function active(int $shop, int $customer): bool { foreach($this->rows as $row) {if($row[0]===$shop && $row[1]===$customer && isset($row[3],$row[4],$row[5])) return true;} return false; }
    public function stored(int $shop, int $customer): bool { foreach($this->rows as $row) {if($row[0]===$shop && $row[1]===$customer) return true;} return false; }
    public function save(int $shop,int $customer,string $digest,string $envelope,string $locale,string $noticeVersion): void {
        $id=$shop.':'.$digest;
        if(isset($this->rows[$id]) && $this->rows[$id][1]!==$customer) throw new RuntimeException('conflict');
        $this->saveCount++;
        $this->rows[$id]=[$shop,$customer,$envelope,$locale,$noticeVersion,'synthetic-utc-acceptance'];
    }
    public function revoke(int $shop,int $customer): void { foreach($this->rows as $id=>$row) { if($row[0]===$shop && $row[1]===$customer) unset($this->rows[$id]); } }
}
$store = new MemoryStore();
$api = new SubscriptionApi($store, $cipher);
$notice = 'Synthetic copy';
$body=['action'=>'subscribe','token'=>'purpose','consent'=>true,'locale'=>'en','notice_version'=>ConsentNoticeVersion::forNotice($notice, 'en'),'subscription'=>$subscription];
$call=fn($action,$payload,$shop=1,$customer=10,$ready=true,$method='POST',$origin='https://shop.example',$authenticated=true,$currentNotice=$notice,$trustedLocale='en') => $api->handle($method,$action,$payload,$authenticated,$shop,$customer,$origin,'https://shop.example/','purpose',$ready,$currentNotice,$trustedLocale);
check($call('subscribe',$body)[0]===200,'subscribe');
check($call('subscribe',$body)[0]===200 && count($store->rows)===1,'idempotent subscribe');
check($store->rows['1:'.$digest][3]==='en' && $store->rows['1:'.$digest][4]===$body['notice_version'] && $store->rows['1:'.$digest][5]!==null,'explicit consent evidence stored');
check($store->saveCount===2,'re-consent refreshes acceptance evidence');
$bad=$body;$bad['notice_version']=ConsentNoticeVersion::forNotice('Old copy','en');
check($call('subscribe',$bad)[0]===400,'tampered or stale notice version rejected');
$bad=$body;$bad['locale']='ja';
check($call('subscribe',$bad)[0]===400,'notice locale is bound to version');
$forged=$body;$forged['locale']='ja';$forgedNotice='合成日本語案内';$forged['notice_version']=ConsentNoticeVersion::forNotice($forgedNotice,'ja');
check($call('subscribe',$forged,1,10,true,'POST','https://shop.example',true,$forgedNotice,'en')[0]===400,'forged locale rejected even with its matching public digest');
check($call('subscribe',$body,1,10,true,'POST','https://shop.example',true,'Changed copy')[0]===400,'copy changed after render rejects stale consent');
check($call('subscribe',$body,1,11)[0]===400,'endpoint owner cannot transfer');
check($call('subscribe',$body,2,11)[0]===200,'other shop isolated');
check($call('status',[],1,10,true,'GET')[1]===['active'=>true,'can_subscribe'=>true],'status minimal');
$legacyStore = new MemoryStore();
$legacyStore->rows['1:'.$digest]=[1,10,'legacy-envelope',null,null,null];
$legacyApi = new SubscriptionApi($legacyStore, $cipher);
check($legacyApi->handle('GET','status',[],true,1,10,'https://shop.example','https://shop.example/','purpose',true,$notice,'en')[1]['active']===false,'legacy row is not treated as explicit consent');
check($legacyStore->stored(1,10) && !$legacyStore->active(1,10),'legacy row remains revocable but ineligible');
check($legacyApi->handle('POST','subscribe',$body,true,1,10,'https://shop.example','https://shop.example/','purpose',true,$notice,'en')[0]===200
    && $legacyStore->active(1,10),'explicit re-consent upgrades legacy row');
$legacyRevoke=$legacyApi->handle('POST','revoke',['action'=>'revoke','token'=>'purpose'],true,1,10,'https://shop.example','https://shop.example/','purpose',false,'','en');
check($legacyRevoke[0]===200 && !$legacyStore->stored(1,10),'legacy subscription can be revoked without readiness or consent copy');
check($call('subscribe',$body,1,10,true,'GET')[0]===405,'GET mutation');
check($call('subscribe',$body,1,10,true,'POST','https://evil.example')[0]===403,'cross origin');
check($call('subscribe',$body,1,10,true,'POST','https://shop.example',false)[0]===401,'authentication required');
$bad=$body;$bad['token']='wrong';check($call('subscribe',$bad)[0]===403,'wrong purpose token');
$bad=$body;$bad['consent']=false;check($call('subscribe',$bad)[0]===400,'explicit consent');
$bad=$body;$bad['id_customer']=11;check($call('subscribe',$bad)[0]===400,'client owner rejected');
check($call('subscribe',$body,1,10,false)[0]===400,'readiness withdrawn');
check($call('subscribe',$body,0,10)[0]===401,'shop context required');
check($call('subscribe',$body,1,0)[0]===401,'customer context required');
$bad=$body;$bad['locale']='fr';check($call('subscribe',$bad)[0]===400,'locale allowlist');
$bad=$body;unset($bad['notice_version']);check($call('subscribe',$bad)[0]===400,'notice version required');
$bad=$body;$bad['subscription']['keys']['auth']='secret';
$response=$call('subscribe',$bad);
check($response===[400,['error'=>'invalid_request']], 'errors contain no subscription or key data');
$api = new SubscriptionApi($store, null);
$result=$api->handle('POST','revoke',['action'=>'revoke','token'=>'purpose'],true,1,10,'https://shop.example','https://shop.example/','purpose',false,'','en');
check($result[0]===200 && !$store->active(1,10) && $store->active(2,11),'revoke without key/readiness/copy preserves other shop');
check($api->handle('POST','revoke',['token'=>'purpose'],true,1,10,'https://shop.example','https://shop.example/','purpose',false,'','en')[0]===200,'idempotent revoke');
echo "PASS: subscription validation, encryption, purpose token, origin, readiness, ownership, consent, API and revoke contracts\n";

require __DIR__ . '/repository.php';

// Provider and dispatch boundary tests. The isolated provider is a no-network fixture.
final class MemoryPushDeliveryStore implements PushDeliveryStore {
    public array $rows=[];
    public array $removed=[];
    public array $requests=[];
    public function deliveryTargetsForOwner(int $shop, int $customer): array {
        $this->requests[]=[$shop,$customer];
        return $this->rows;
    }
    public function removeDeliveryTargetForOwner(int $shop, int $customer, string $digest): void {
        $this->removed[]=[$shop,$customer,$digest];
    }
}

function restorePushEnvironment(array $previous): void {
    foreach ($previous as $name=>$value) {
        if ($value === false) { putenv($name); }
        else { putenv($name . '=' . $value); }
    }
}

$pushEnvironmentNames=['CI','GITHUB_ACTIONS','KURANEA_ISOLATED_CI','ORDENOWA_PUSH_TEST_MODE',
    'GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','KURANEA_CI_PROJECT_NAME'];
$previousPushEnvironment=[];
foreach ($pushEnvironmentNames as $name) { $previousPushEnvironment[$name]=getenv($name); }
try {
    foreach ($pushEnvironmentNames as $name) { putenv($name); }
    rejected(fn() => new IsolatedSyntheticPushDeliveryProvider(), 'synthetic provider disabled without exact isolated Actions gate');
    $disabledProvider=new DisabledPushDeliveryProvider();
    check(!$disabledProvider->available(), 'live transport disabled without an approved provider');

    foreach (['CI'=>'true','GITHUB_ACTIONS'=>'true','KURANEA_ISOLATED_CI'=>'1','ORDENOWA_PUSH_TEST_MODE'=>'1',
        'GITHUB_RUN_ID'=>'123','GITHUB_RUN_ATTEMPT'=>'2','KURANEA_CI_PROJECT_NAME'=>'kuranea-ci-123-2'] as $name=>$value) {
        putenv($name . '=' . $value);
    }
    $provider=new IsolatedSyntheticPushDeliveryProvider();
    check($provider->available(), 'synthetic provider becomes available only in exact isolated Actions context');

    $deliveryStore=new MemoryPushDeliveryStore();
    $deliveryCipher=new SubscriptionCipher($key);
    $payload=new DeliveryPayload('order', 'en');
    foreach (['order','delivery','support'] as $event) {
        foreach (['ja','en','ko'] as $locale) {
            $wire=(new DeliveryPayload($event,$locale))->toJson();
            check($wire === '{"event":"' . $event . '","locale":"' . $locale . '"}',
                'serialized delivery matches exact worker event/locale wire contract');
            check($provider->send($subscription,new DeliveryPayload($event,$locale))->status===PushDeliveryResult::DELIVERED,
                'synthetic provider accepts each worker-compatible serialized event/locale');
        }
    }
    $ownerSubscription=$subscription;
    $ownerSubscription['endpoint']='https://fcm.googleapis.com/fcm/send/owner-10';
    $ownerDigest=$deliveryCipher->digest($ownerSubscription['endpoint']);
    $otherSubscription=$subscription;
    $otherSubscription['endpoint']='https://fcm.googleapis.com/fcm/send/customer-11';
    $otherDigest=$deliveryCipher->digest($otherSubscription['endpoint']);
    $goneSubscription=$subscription;
    $goneSubscription['endpoint']='https://fcm.googleapis.com/fcm/send/gone-10';
    $goneDigest=$deliveryCipher->digest($goneSubscription['endpoint']);
    $retrySubscription=$subscription;
    $retrySubscription['endpoint']='https://fcm.googleapis.com/fcm/send/retry-10';
    $retryDigest=$deliveryCipher->digest($retrySubscription['endpoint']);
    $consentVersion=ConsentNoticeVersion::forNotice('Synthetic copy','en');
    $record=static function (int $shop,int $customer,array $recordSubscription,string $digest,?string $version,?string $locale,?string $acceptedAt) use ($deliveryCipher): array {
        return ['id_shop'=>$shop,'id_customer'=>$customer,'endpoint_digest'=>$digest,
            'encrypted_subscription'=>$deliveryCipher->encrypt($recordSubscription,$shop,$customer,$digest),
            'consent_notice_version'=>$version,'consent_locale'=>$locale,'consent_accepted_at'=>$acceptedAt];
    };
    $deliveryStore->rows=[
        $record(1,10,$ownerSubscription,$ownerDigest,$consentVersion,'en','2026-10-26 00:00:00'),
        $record(1,11,$otherSubscription,$otherDigest,$consentVersion,'en','2026-10-26 00:00:00'),
        $record(1,10,$goneSubscription,$goneDigest,$consentVersion,'en','2026-10-26 00:00:00'),
        $record(1,10,$retrySubscription,$retryDigest,$consentVersion,'en','2026-10-26 00:00:00'),
        $record(1,10,$ownerSubscription,$ownerDigest,null,null,null), // Legacy/no explicit consent is never eligible.
    ];
    $provider=new IsolatedSyntheticPushDeliveryProvider([
        hash('sha256',$goneSubscription['endpoint'])=>PushDeliveryResult::GONE,
        hash('sha256',$retrySubscription['endpoint'])=>PushDeliveryResult::RETRYABLE_FAILURE,
    ]);
    $service=new PushDeliveryService($deliveryStore,$deliveryCipher,$provider);
    $summary=$service->deliverToOwner(1,10,$payload);
    check($summary->status==='completed' && $summary->delivered===1 && $summary->permanentlyGone===1
        && $summary->retryableFailure===1 && $summary->ineligible===2, 'owner delivery distinguishes success, gone, retryable and ineligible rows');
    check(count($deliveryStore->requests)===1 && $deliveryStore->requests[0]===[1,10], 'delivery query is scoped to exactly the requested shop and customer');
    check($deliveryStore->removed===[[1,10,$goneDigest]], 'permanently gone endpoint removal is owner scoped and exact');

    $invalidStore=new MemoryPushDeliveryStore();
    $invalidStore->rows=[['id_shop'=>1,'id_customer'=>10,'endpoint_digest'=>str_repeat('0',64),
        'encrypted_subscription'=>'invalid','consent_notice_version'=>$consentVersion,
        'consent_locale'=>'en','consent_accepted_at'=>'2026-10-26 00:00:00']];
    $invalidService=new PushDeliveryService($invalidStore,$deliveryCipher,$provider);
    $invalidSummary=$invalidService->deliverToOwner(1,10,$payload);
    check($invalidSummary->status==='completed' && $invalidSummary->delivered===0
        && $invalidSummary->retryableFailure===0 && $invalidSummary->ineligible===1,
        'corrupt or mismatched encrypted subscriptions are not sent and produce no endpoint detail');

    $emptyStore=new MemoryPushDeliveryStore();
    $disabledService=new PushDeliveryService($emptyStore,$deliveryCipher,$disabledProvider);
    $disabledSummary=$disabledService->deliverToOwner(1,10,$payload);
    check($disabledSummary->status==='provider_unavailable' && $disabledSummary->delivered===0
        && $emptyStore->requests===[], 'disabled live provider short-circuits before reading or decrypting subscriptions');

    $defaultDisabledStore=new MemoryPushDeliveryStore();
    $defaultDisabledService=new PushDeliveryService($defaultDisabledStore,$deliveryCipher);
    $defaultDisabledSummary=$defaultDisabledService->deliverToOwner(1,10,$payload);
    check($defaultDisabledSummary->status==='provider_unavailable' && $defaultDisabledStore->requests===[],
        'delivery service defaults to the disabled provider and never reads recipients');

    foreach (['other','ORDER','order update','private order text',''] as $event) {
        rejected(fn() => new DeliveryPayload($event,'en'), 'delivery rejects arbitrary events and private text');
    }
    foreach (['en-US','EN','https://outside.example/',''] as $locale) {
        rejected(fn() => new DeliveryPayload('order',$locale), 'delivery rejects unsupported locales and destinations');
    }
    echo "PASS: isolated synthetic delivery is owner-scoped, consent-gated, encrypted, and failure-aware; live provider remains disabled\n";
} finally {
    restorePushEnvironment($previousPushEnvironment);
}

require __DIR__ . '/delivery_outbox.php';
require __DIR__ . '/order_history_producer.php';
