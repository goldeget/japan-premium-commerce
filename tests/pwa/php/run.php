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
use Kuranea\Push\Infrastructure\SubscriptionCipher;

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

final class MemoryStore implements SubscriptionStore {
    public array $rows=[];
    public function active(int $shop, int $customer): bool { foreach($this->rows as $row) {if($row[0]===$shop && $row[1]===$customer) return true;} return false; }
    public function save(int $shop,int $customer,string $digest,string $envelope): void {
        $id=$shop.':'.$digest;
        if(isset($this->rows[$id]) && $this->rows[$id][1]!==$customer) throw new RuntimeException('conflict');
        $this->rows[$id]=[$shop,$customer,$envelope];
    }
    public function revoke(int $shop,int $customer): void { foreach($this->rows as $id=>$row) { if($row[0]===$shop && $row[1]===$customer) unset($this->rows[$id]); } }
}
$store = new MemoryStore();
$api = new SubscriptionApi($store, $cipher);
$body=['action'=>'subscribe','token'=>'purpose','consent'=>true,'locale'=>'ja','subscription'=>$subscription];
$call=fn($action,$payload,$shop=1,$customer=10,$ready=true,$method='POST',$origin='https://shop.example',$authenticated=true) => $api->handle($method,$action,$payload,$authenticated,$shop,$customer,$origin,'https://shop.example/','purpose',$ready,'Synthetic copy');
check($call('subscribe',$body)[0]===200,'subscribe');
check($call('subscribe',$body)[0]===200 && count($store->rows)===1,'idempotent subscribe');
check($call('subscribe',$body,1,11)[0]===400,'endpoint owner cannot transfer');
check($call('subscribe',$body,2,11)[0]===200,'other shop isolated');
check($call('status',[],1,10,true,'GET')[1]===['active'=>true,'can_subscribe'=>true],'status minimal');
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
$bad=$body;$bad['subscription']['keys']['auth']='secret';
$response=$call('subscribe',$bad);
check($response===[400,['error'=>'invalid_request']], 'errors contain no subscription or key data');
$api = new SubscriptionApi($store, null);
$result=$api->handle('POST','revoke',['action'=>'revoke','token'=>'purpose'],true,1,10,'https://shop.example','https://shop.example/','purpose',false,'');
check($result[0]===200 && !$store->active(1,10) && $store->active(2,11),'revoke without key/readiness/copy preserves other shop');
check($api->handle('POST','revoke',['token'=>'purpose'],true,1,10,'https://shop.example','https://shop.example/','purpose',false,'')[0]===200,'idempotent revoke');
echo "PASS: subscription validation, encryption, purpose token, origin, readiness, ownership, consent, API and revoke contracts\n";

require __DIR__ . '/repository.php';
