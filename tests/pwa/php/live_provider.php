<?php

declare(strict_types=1);
require_once __DIR__ . '/../../../modules/kuraneapush/autoload.php';
$vendor = __DIR__ . '/../../../modules/kuraneapush/vendor/autoload.php';
if (is_file($vendor)) require_once $vendor;

use Kuranea\Push\Domain\DeliveryPayload;
use Kuranea\Push\Domain\PushDeliveryResult;
use Kuranea\Push\Infrastructure\WebPushDeliveryProvider;
use Kuranea\Push\Infrastructure\LivePushFactory;
use Minishlink\WebPush\VAPID;
use GuzzleHttp\Handler\MockHandler;
use GuzzleHttp\HandlerStack;
use GuzzleHttp\Psr7\Response;

function liveSame(mixed $expected, mixed $actual): void {
    if ($expected !== $actual) throw new RuntimeException('Unexpected Web Push transport behavior.');
}
class Configuration {
    public static array $values = [];
    public static function get(string $key, mixed $lang = null, mixed $group = null, mixed $shop = null): mixed {
        return self::$values[(int) $shop][$key] ?? false;
    }
}
liveSame(false, LivePushFactory::available(1));
liveSame('{"event":"points","locale":"ja"}', (new DeliveryPayload('points', 'ja'))->toJson());
liveSame('{"event":"procurement","locale":"ko"}', (new DeliveryPayload('procurement', 'ko'))->toJson());
if (!class_exists(VAPID::class)) throw new RuntimeException('Locked Web Push dependency must be installed for offline transport tests.');
$keys = VAPID::createVapidKeys();
$auth = ['subject' => 'mailto:push@example.test', 'publicKey' => $keys['publicKey'], 'privateKey' => $keys['privateKey']];
$recipientKeys = VAPID::createVapidKeys();
$subscription = ['endpoint' => 'https://fcm.googleapis.com/fcm/send/SYNTHETIC-NOT-A-SUBSCRIPTION',
    'keys' => ['p256dh' => $recipientKeys['publicKey'], 'auth' => rtrim(strtr(base64_encode(random_bytes(16)), '+/', '-_'), '=')]];
$payload = new DeliveryPayload('procurement', 'ja');
foreach ([201 => PushDeliveryResult::DELIVERED, 302 => PushDeliveryResult::RETRYABLE_FAILURE, 403 => PushDeliveryResult::RETRYABLE_FAILURE, 404 => PushDeliveryResult::GONE, 410 => PushDeliveryResult::GONE, 429 => PushDeliveryResult::RETRYABLE_FAILURE, 503 => PushDeliveryResult::RETRYABLE_FAILURE] as $status => $expected) {
    $mock = new MockHandler([new Response($status)]);
    $observed = [];
    $stack = HandlerStack::create($mock);
    $stack->push(\GuzzleHttp\Middleware::history($observed));
    $provider = new WebPushDeliveryProvider($auth, $stack);
    liveSame(true, $provider->available());
    liveSame($expected, $provider->send($subscription, $payload)->status);
    liveSame(1, count($observed));
    $options = $observed[0]['options'];
    liveSame(true, $options['verify']);
    liveSame(false, $options['allow_redirects']);
    liveSame(10.0, (float) $options['timeout']);
    liveSame(3.0, (float) $options['connect_timeout']);
    liveSame('POST', $observed[0]['request']->getMethod());
    liveSame('300', $observed[0]['request']->getHeaderLine('TTL'));
    liveSame('aes128gcm', $observed[0]['request']->getHeaderLine('Content-Encoding'));
    if ($observed[0]['request']->getHeaderLine('Authorization') === '') throw new RuntimeException('Maintained library did not sign VAPID authorization.');
    if ((string) $observed[0]['request']->getBody() === $payload->toJson()) throw new RuntimeException('Web Push payload was not encrypted by the maintained library.');
    liveSame(0, count($mock));
}
$failedRequest = new \GuzzleHttp\Psr7\Request('POST', $subscription['endpoint']);
$failedHandler = new MockHandler([new \GuzzleHttp\Exception\ConnectException('synthetic transport failure SECRET', $failedRequest)]);
$failedProvider = new WebPushDeliveryProvider($auth, HandlerStack::create($failedHandler));
liveSame(PushDeliveryResult::RETRYABLE_FAILURE, $failedProvider->send($subscription, $payload)->status);
$mock = new MockHandler([new Response(201)]);
$provider = new WebPushDeliveryProvider($auth, HandlerStack::create($mock));
foreach (['http://fcm.googleapis.com/fcm/send/not-https', 'https://127.0.0.1/push', 'https://evil.example.test/push', 'https://fcm.googleapis.com:444/push', 'https://user:secret@fcm.googleapis.com/push'] as $endpoint) {
    try { $provider->send(array_replace($subscription, ['endpoint' => $endpoint]), $payload); throw new LogicException('Disallowed endpoint was sent.'); }
    catch (InvalidArgumentException) {}
}
liveSame(1, count($mock));
$provider = new WebPushDeliveryProvider([], HandlerStack::create($mock));
liveSame(false, $provider->available());
liveSame(PushDeliveryResult::RETRYABLE_FAILURE, $provider->send($subscription, $payload)->status);
liveSame(1, count($mock));
Configuration::$values[1] = ['ORDENOWA_PUSH_LIVE_ENABLED' => 1, 'ORDENOWA_PUSH_HTTPS_VALIDATED' => 1];
putenv('ORDENOWA_PUSH_VAPID_PUBLIC_KEY=' . $keys['publicKey']);
putenv('ORDENOWA_PUSH_VAPID_PRIVATE_KEY=' . $keys['privateKey']);
putenv('ORDENOWA_PUSH_VAPID_SUBJECT=mailto:push@example.test');
liveSame(true, LivePushFactory::available(1));
liveSame(false, LivePushFactory::available(2));
putenv('ORDENOWA_PUSH_VAPID_PRIVATE_KEY=invalid');
liveSame(false, LivePushFactory::available(1));
putenv('ORDENOWA_PUSH_VAPID_PRIVATE_KEY=' . $keys['privateKey']);
Configuration::$values[1]['ORDENOWA_PUSH_HTTPS_VALIDATED'] = 0;
liveSame(false, LivePushFactory::available(1));
foreach (['ORDENOWA_PUSH_VAPID_PUBLIC_KEY', 'ORDENOWA_PUSH_VAPID_PRIVATE_KEY', 'ORDENOWA_PUSH_VAPID_SUBJECT'] as $name) putenv($name);
echo "PASS: maintained Web Push library encrypts mocked delivery; success/gone/retry, endpoint guards, TLS/timeouts and configuration boundaries\n";
