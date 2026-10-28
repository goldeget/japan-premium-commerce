<?php

declare(strict_types=1);
require __DIR__ . '/native_post_token_fixture.php';
use Kuranea\Backoffice\Admin\AdminPostTokenValidator;
$container=nativePostTokenFixtureContainer(static fn(string $value):bool=>in_array($value,['previous-valid-mask','current-valid-mask'],true));
$controller=new class($container){public function __construct(private object $container){}public function getContainer():object{return $this->container;}};
function postTokenAssert(bool $ok,string $message):void{if(!$ok)throw new RuntimeException($message);}
postTokenAssert(AdminPostTokenValidator::forController($controller,'previous-valid-mask'),'Valid prior masked token must use native stored seed validation.');
postTokenAssert(AdminPostTokenValidator::forController($controller,'current-valid-mask'),'Another native mask of the same authenticated seed remains valid.');
$_GET=['token'=>'previous-valid-mask','_token'=>'current-valid-mask'];
postTokenAssert(!AdminPostTokenValidator::forController($controller,'forged'),'Valid query tokens cannot authorize a forged submitted body value.');
foreach(['',null,[],1]as$invalid)postTokenAssert(!AdminPostTokenValidator::forController($controller,$invalid),'Nonempty string body token is mandatory.');
$anonymous=nativePostTokenFixtureContainer(static fn(string $value):bool=>true,false);
postTokenAssert(!$anonymous->get(AdminPostTokenValidator::class)->valid('previous-valid-mask'),'Missing authenticated native user fails closed.');
postTokenAssert(!AdminPostTokenValidator::forController(new class{public function getContainer():object{throw new RuntimeException('Missing service');}},'previous-valid-mask'),'Missing native validator service fails closed.');
echo "admin_post_token: PASS native prior-mask validation, exact body binding, authenticated user and missing-service boundaries\n";
