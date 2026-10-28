<?php

declare(strict_types=1);
require dirname(__DIR__, 2) . '/modules/kuraneapush/autoload.php';
$vendor = dirname(__DIR__, 2) . '/modules/kuraneapush/vendor/autoload.php';
if (is_file($vendor)) require_once $vendor;
use Kuranea\Push\Infrastructure\{LiveSubscriptionReadiness, LivePushFactory};
use Minishlink\WebPush\VAPID;

class Configuration
{
    public static array $values = [];
    public static array $writes = [];
    public static function get(string $key, mixed $lang = null, mixed $group = null, mixed $shop = null): mixed { return self::$values[(int) $shop][$key] ?? false; }
    public static function updateValue(string $key, mixed $value, bool $html = false, mixed $group = null, mixed $shop = null): bool { self::$writes[] = [$shop,$key]; self::$values[(int) $shop][$key] = $value; return true; }
}
class PushTestLink
{
    public static string $base = 'https://shop.example.test/';
    public function getBaseLink(int $shop): string { return self::$base; }
    public function getAdminLink(string $tab): string { return 'https://shop.example.test/admin/index.php?controller=' . $tab; }
}
class Context { public static object $context; public static function getContext(): object { return self::$context; } }
class Shop { public const CONTEXT_SHOP = 1; public static function getContext(): int { return self::CONTEXT_SHOP; } }
class Tools { public static function getAdminTokenLite(string $tab): string { return 'native-push-session-token'; } }
#[AllowDynamicProperties]
class ModuleAdminController
{
    public object $context;
    public string $content = '';
    public array $tabAccess = ['view' => 1, 'edit' => 1];
    public function __construct() { $this->context = Context::getContext(); }
    public function viewAccess(): bool { return (bool) $this->tabAccess['view']; }
    public function access(string $action): bool { return (bool) ($this->tabAccess[$action] ?? false); }
    public function initContent(): void {}
}
require dirname(__DIR__, 2) . '/modules/kuraneapush/controllers/admin/AdminKuraneaPushController.php';

function pushNativeAssert(bool $value, string $message): void { if (!$value) throw new RuntimeException($message); }
$server = ['HTTPS' => 'on', 'SERVER_PORT' => '443', 'HTTP_HOST' => 'shop.example.test'];
pushNativeAssert(LiveSubscriptionReadiness::isHttpsOrigin('https://shop.example.test/', $server), 'Actual TLS plus native matching HTTPS origin is required.');
pushNativeAssert(!LiveSubscriptionReadiness::isHttpsOrigin('https://shop.example.test/', ['HTTPS' => 'off','SERVER_PORT' => '443','HTTP_HOST' => 'shop.example.test']), 'A port number alone does not attest actual TLS.');
pushNativeAssert(!LiveSubscriptionReadiness::isHttpsOrigin('http://shop.example.test/', $server), 'HTTP native base cannot be acknowledged as HTTPS.');
pushNativeAssert(!LiveSubscriptionReadiness::isHttpsOrigin('https://other.example.test/', $server), 'Host mismatch must fail closed.');
pushNativeAssert(!LiveSubscriptionReadiness::isHttpsOrigin('https://shop.example.test/', ['HTTPS' => 'off','SERVER_PORT' => '80','HTTP_HOST' => 'shop.example.test','HTTP_X_FORWARDED_PROTO' => 'https']), 'Client forwarded-proto cannot activate subscriptions.');
pushNativeAssert(!LiveSubscriptionReadiness::isHttpsOrigin('https://shop.example.test/', ['HTTPS' => 'on','HTTP_HOST' => 'shop.example.test@attacker.test']), 'Host userinfo cannot masquerade as canonical origin.');
Context::$context = (object) ['shop' => (object) ['id' => 1], 'link' => new PushTestLink(), 'smarty' => new class { public function assign(mixed $key, mixed $value = null): void {} }];
$_SERVER = $server + ['REQUEST_METHOD' => 'POST'];
Configuration::$values[1]['PS_SSL_ENABLED'] = 1;
putenv('ORDENOWA_APP_MODE=procurement');
foreach (['CI','GITHUB_ACTIONS','KURANEA_ISOLATED_CI','ORDENOWA_PUSH_TEST_MODE','ORDENOWA_PUSH_VAPID_PUBLIC_KEY','ORDENOWA_PUSH_VAPID_PRIVATE_KEY','ORDENOWA_PUSH_VAPID_SUBJECT'] as $name) putenv($name);
pushNativeAssert(!LiveSubscriptionReadiness::canSubscribe(1, 'SYNTHETIC notice', true), 'Procurement app mode does not enable live Push.');
if (!class_exists(VAPID::class)) throw new RuntimeException('Locked offline Web Push library is required.');
$keys = VAPID::createVapidKeys();
putenv('ORDENOWA_PUSH_VAPID_PUBLIC_KEY=' . $keys['publicKey']);
putenv('ORDENOWA_PUSH_VAPID_PRIVATE_KEY=' . $keys['privateKey']);
putenv('ORDENOWA_PUSH_VAPID_SUBJECT=mailto:synthetic-push@example.test');
Configuration::$values[1]['ORDENOWA_PUSH_LIVE_ENABLED'] = 1;
Configuration::$values[1]['ORDENOWA_PUSH_HTTPS_VALIDATED'] = 1;
pushNativeAssert(LiveSubscriptionReadiness::canSubscribe(1, 'SYNTHETIC notice', true), 'Explicit enabled/acknowledged verified native TLS and offline valid provider keys permit subscription.');
pushNativeAssert(LivePushFactory::applicationServerKey(1) === $keys['publicKey'], 'The actual public application key reaches ready subscriptions.');
pushNativeAssert(!LiveSubscriptionReadiness::canSubscribe(1, '', true) && !LiveSubscriptionReadiness::canSubscribe(1, 'SYNTHETIC notice', false), 'Notice and encrypted storage remain required.');
pushNativeAssert(!LiveSubscriptionReadiness::canSubscribe(2, 'SYNTHETIC notice', true), 'Shop flags do not cross native shop boundaries.');
$_SERVER['HTTPS'] = 'off'; $_SERVER['SERVER_PORT'] = '80';
pushNativeAssert(!LiveSubscriptionReadiness::canSubscribe(1, 'SYNTHETIC notice', true), 'Acknowledgement flags never override actual HTTP transport.');
$_POST = ['submitOrdenowaPush' => '1', 'token' => Tools::getAdminTokenLite('AdminKuraneaPush'), 'ORDENOWA_PUSH_LIVE_ENABLED' => '1', 'ORDENOWA_PUSH_HTTPS_VALIDATED' => '1'];
foreach (['JA','EN','KO'] as $locale) $_POST['ORDENOWA_PUSH_CONSENT_NOTICE_' . $locale] = 'SYNTHETIC TEST consent ' . $locale;
$admin = new AdminKuraneaPushController();
$admin->initContent();
pushNativeAssert(Configuration::$writes === [], 'HTTP requests cannot save HTTPS acknowledgement or enable flags.');
$_SERVER = $server + ['REQUEST_METHOD' => 'POST'];
$_POST['token'] = 'forged';
(new AdminKuraneaPushController())->initContent();
pushNativeAssert(Configuration::$writes === [], 'Forged native CSRF token cannot update settings.');
$_POST['token'] = Tools::getAdminTokenLite('AdminKuraneaPush');
$reader = new AdminKuraneaPushController(); $reader->tabAccess['edit'] = 0; $reader->initContent();
pushNativeAssert(Configuration::$writes === [], 'READ-only admin cannot change live flags.');
$_POST['ORDENOWA_PUSH_CONSENT_NOTICE_JA'] = '';
(new AdminKuraneaPushController())->initContent();
pushNativeAssert(Configuration::$writes === [], 'Blank real consent copy cannot enable live Push.');
$_POST['ORDENOWA_PUSH_CONSENT_NOTICE_JA'] = 'SYNTHETIC TEST consent JA';
$editor = new AdminKuraneaPushController(); $editor->initContent();
pushNativeAssert(count(Configuration::$writes) === 10, 'Authorized native secure form persists all supported settings.');
pushNativeAssert(!str_contains($editor->content, $keys['privateKey']) && !str_contains($editor->content, $keys['publicKey']), 'Admin UI exposes only environment references, never key values.');
foreach (['CI'=>'true','GITHUB_ACTIONS'=>'true','KURANEA_ISOLATED_CI'=>'1','ORDENOWA_PUSH_TEST_MODE'=>'1','GITHUB_RUN_ID'=>'7','GITHUB_RUN_ATTEMPT'=>'1','KURANEA_CI_PROJECT_NAME'=>'kuranea-ci-7-1'] as $name => $value) putenv($name . '=' . $value);
$_SERVER = ['HTTPS'=>'off','SERVER_PORT'=>'80','HTTP_HOST'=>'shop.example.test'];
pushNativeAssert(LiveSubscriptionReadiness::canSubscribe(1, 'SYNTHETIC isolated notice', true), 'Exact disposable provider-free QA gate remains supported.');
echo "native_push_settings: PASS actual TLS/origin, live readiness, public key, shop, notice, storage, native CSRF/ACL and isolated QA\n";
