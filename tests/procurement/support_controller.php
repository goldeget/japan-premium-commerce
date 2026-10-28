<?php

declare(strict_types=1);
require_once __DIR__ . '/requests_bootstrap.php';
use Ordenowa\Procurement\Infrastructure\Database;
use Ordenowa\Procurement\Security\Actor;

class SupportControllerRuntime {
    public static bool $enabled = true;
    public static int $actorCalls = 0;
    public static object $connection;
    public static function procurementEnabled(): bool { return self::$enabled; }
    public static function customerActor(): Actor { ++self::$actorCalls; return Actor::customer(1,11); }
    public static function database(): Database { return new Database(self::$connection,'test_'); }
}
class_alias(SupportControllerRuntime::class,'Ordenowa\\Procurement\\Integration\\Runtime');
class Tools {
    public static array $input = [];
    public static function getValue(string $key,mixed $default=false): mixed { return self::$input[$key] ?? $default; }
    public static function getToken(mixed $unused): string { return 'native-session-token'; }
    public static function redirect(string $url): void { throw new LogicException('Denied request redirected.'); }
}
class ModuleFrontController {
    public object $context;
    public function initContent(): void {}
    public function setTemplate(string $template): void {}
}
require_once __DIR__ . '/../../modules/ordenowaprocurement/controllers/front/support.php';
$connection = new class {
    public int $reads = 0;
    public function executeS(string $sql,bool $array=true,bool $cache=true): array { ++$this->reads; return []; }
};
SupportControllerRuntime::$connection = $connection;
$smarty = new class { public array $data=[]; public function assign(array $values): void { $this->data=$values; } };
$context = (object)['language'=>(object)['iso_code'=>'en'],'smarty'=>$smarty];
$controller = new OrdenowaprocurementSupportModuleFrontController();
$controller->context = $context;
$_FILES = [];
$_SERVER['REQUEST_METHOD'] = 'GET';
Tools::$input = ['id_request'=>'1'];
SupportControllerRuntime::$enabled = false;
$controller->initContent();
requestsAssert(http_response_code()===503 && SupportControllerRuntime::$actorCalls===0 && $connection->reads===0,'legacy mode refuses support before session/database work');
SupportControllerRuntime::$enabled = true;
$_SERVER['REQUEST_METHOD']='POST';
Tools::$input = ['id_request'=>'1','action'=>'message','token'=>'wrong','message'=>'hello','idempotency_key'=>str_repeat('a',64)];
$controller->initContent();
requestsAssert(http_response_code()===403 && $connection->reads===0,'bad native CSRF cannot access or mutate a thread');
Tools::$input['token']='native-session-token';
Tools::$input['id_customer_thread']='42';
$controller->initContent();
requestsAssert(http_response_code()===404 && $connection->reads===0,'client thread identity cannot select a conversation');
unset(Tools::$input['id_customer_thread']);
$_FILES=['attachment'=>['error'=>0]];
$controller->initContent();
requestsAssert(http_response_code()===422 && $connection->reads===0,'attachment input denied before native message mutation');
requestsAssert($smarty->data['ordenowa_support']['allowed']===false,'denied response contains no support form or history');
echo "PASS request support controller: explicit mode gate, CSRF, client thread rejection and no attachments before database access\n";
