<?php
declare(strict_types=1);

require_once __DIR__ . '/ci_bootstrap.php';
require_once '/var/www/html/modules/kuraneapush/autoload.php';
require_once '/var/www/html/modules/kuraneapush/vendor/autoload.php';

use Base64Url\Base64Url;
use GuzzleHttp\Handler\MockHandler;
use GuzzleHttp\HandlerStack;
use GuzzleHttp\Middleware;
use GuzzleHttp\Psr7\Response;
use Jose\Component\Core\AlgorithmManager;
use Jose\Component\Core\JWK;
use Jose\Component\Signature\Algorithm\ES256;
use Jose\Component\Signature\JWSVerifier;
use Jose\Component\Signature\Serializer\CompactSerializer;
use Kuranea\Push\Domain\DeliveryPayload;
use Kuranea\Push\Domain\PushDeliveryResult;
use Kuranea\Push\Infrastructure\WebPushDeliveryProvider;
use Minishlink\WebPush\VAPID;
use Ordenowa\Procurement\Integration\Runtime;

// All keys and subscriptions are ephemeral test values. Nothing enters native
// Configuration, push subscription storage, environment variables or output.
$database = Runtime::database();
$before = [];
foreach (['point_account', 'point_award', 'point_ledger', 'notification', 'notification_delivery'] as $table) {
    $before[$table] = ciDomainHash($database, $table);
}
$nativeConfiguration = hash('sha256', json_encode($database->all('SELECT * FROM `' . _DB_PREFIX_ . 'configuration` ORDER BY id_configuration'), JSON_THROW_ON_ERROR));
$keys = VAPID::createVapidKeys();
$recipientKeys = VAPID::createVapidKeys();
$auth = ['subject' => 'mailto:synthetic-push@example.invalid', 'publicKey' => $keys['publicKey'], 'privateKey' => $keys['privateKey']];
$subscription = ['endpoint' => 'https://fcm.googleapis.com/fcm/send/SYNTHETIC-NATIVE-NO-NETWORK',
    'keys' => ['p256dh' => $recipientKeys['publicKey'], 'auth' => Base64Url::encode(random_bytes(16))]];
$public = Base64Url::decode($keys['publicKey']);
$verificationKey = new JWK(['kty' => 'EC', 'crv' => 'P-256', 'x' => Base64Url::encode(substr($public, 1, 32)), 'y' => Base64Url::encode(substr($public, 33, 32))]);
$verifier = new JWSVerifier(new AlgorithmManager([new ES256()]));
$serializer = new CompactSerializer();

foreach ([201 => PushDeliveryResult::DELIVERED, 410 => PushDeliveryResult::GONE, 503 => PushDeliveryResult::RETRYABLE_FAILURE] as $status => $expected) {
    $payload = new DeliveryPayload($status === 410 ? 'points' : 'procurement', $status === 503 ? 'ko' : 'ja');
    ciAssert(array_keys(json_decode($payload->toJson(), true, 8, JSON_THROW_ON_ERROR)) === ['event', 'locale'], 'Generic payload keys only');
    $mock = new MockHandler([new Response($status)]);
    $observed = [];
    $stack = HandlerStack::create($mock);
    $stack->push(Middleware::history($observed));
    $provider = new WebPushDeliveryProvider($auth, $stack);
    ob_start();
    try {
        $available = $provider->available();
        $outcome = $provider->send($subscription, $payload);
    } finally {
        $unexpectedOutput = ob_get_clean();
    }
    ciAssert($unexpectedOutput === '', 'Provider emits no key or payload output');
    ciAssert($available && $outcome->status === $expected, 'Native maintained provider status mapping');
    ciAssert(count($observed) === 1 && count($mock) === 0, 'Exactly one mocked HTTP request');
    $request = $observed[0]['request'];
    $options = $observed[0]['options'];
    ciAssert($request->getMethod() === 'POST', 'Native Web Push uses POST');
    ciAssert($options['verify'] === true && $options['allow_redirects'] === false, 'Native TLS and redirect boundaries preserved');
    ciAssert((float) $options['timeout'] === 10.0 && (float) $options['connect_timeout'] === 3.0, 'Native transport timeout bounds preserved');
    ciAssert($request->getHeaderLine('TTL') === '300' && $request->getHeaderLine('Content-Encoding') === 'aes128gcm', 'Native TTL and encrypted content encoding');
    $body = (string) $request->getBody();
    ciAssert(strlen($body) > 86 && $body !== $payload->toJson() && !str_contains($body, $payload->toJson()), 'Native library encrypts generic event payload');
    ciAssert(ord($body[20]) === 65 && ord($body[21]) === 4, 'RFC8188 encrypted record carries ephemeral P256 key');
    $authorization = $request->getHeaderLine('Authorization');
    ciAssert(preg_match('/^vapid t=([A-Za-z0-9_.-]+), k=([A-Za-z0-9_-]+)$/D', $authorization, $parts) === 1, 'Native VAPID authorization structure');
    ciAssert(hash_equals($keys['publicKey'], $parts[2]), 'VAPID signing key matches ephemeral test key');
    $signed = $serializer->unserialize($parts[1]);
    ciAssert($verifier->verifyWithKey($signed, $verificationKey, 0), 'Native ES256 signature verifies');
    $claims = json_decode((string) $signed->getPayload(), true, 8, JSON_THROW_ON_ERROR);
    ciAssert($claims['aud'] === 'https://fcm.googleapis.com' && $claims['sub'] === $auth['subject'], 'Native JWT audience and subject');
    ciAssert(is_int($claims['exp']) && $claims['exp'] > time() && $claims['exp'] <= time() + 43200, 'Native JWT bounded lifetime');
}
foreach ($before as $table => $hash) {
    ciAssert(hash_equals($hash, ciDomainHash($database, $table)), 'Native provider test preserves domain state');
}
ciAssert(hash_equals($nativeConfiguration, hash('sha256', json_encode($database->all('SELECT * FROM `' . _DB_PREFIX_ . 'configuration` ORDER BY id_configuration'), JSON_THROW_ON_ERROR))), 'Native provider test preserves Configuration');
unset($keys, $recipientKeys, $auth, $subscription, $public, $verificationKey, $authorization, $parts, $signed, $claims, $body, $observed);
fwrite(STDOUT, "PASS procurement native Web Push coexistence: signed encrypted generic payload, mocked success/gone/retry, no state changes\n");
