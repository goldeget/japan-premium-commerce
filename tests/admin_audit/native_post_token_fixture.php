<?php

declare(strict_types=1);
namespace Symfony\Component\Security\Csrf {
    if (!class_exists(CsrfToken::class)) { class CsrfToken { public function __construct(private string $id,private string $value){}public function getId():string{return $this->id;}public function getValue():string{return $this->value;} } }
    if (!interface_exists(CsrfTokenManagerInterface::class)) { interface CsrfTokenManagerInterface { public function getToken(string $tokenId):CsrfToken;public function refreshToken(string $tokenId):CsrfToken;public function removeToken(string $tokenId):?string;public function isTokenValid(CsrfToken $token):bool; } }
}
namespace Symfony\Component\EventDispatcher { if (!interface_exists(EventSubscriberInterface::class)) { interface EventSubscriberInterface { public static function getSubscribedEvents():array; } } }
namespace Symfony\Component\HttpKernel { if (!class_exists(KernelEvents::class)) { class KernelEvents { public const RESPONSE='kernel.response'; } } }
namespace Symfony\Component\HttpKernel\Event { if (!class_exists(ResponseEvent::class)) { class ResponseEvent { public function __construct(private object $request,private object $response,private bool $main=true){}public function isMainRequest():bool{return $this->main;}public function getRequest():object{return $this->request;}public function getResponse():object{return $this->response;} } } }
namespace Symfony\Bundle\SecurityBundle {
    if (!class_exists(Security::class)) { class Security { public function __construct(private ?object $user){}public function getUser():?object{return $this->user;} } }
}
namespace PrestaShopBundle\Security\Admin { if (!interface_exists(SessionEmployeeInterface::class)) { interface SessionEmployeeInterface {} } }
namespace {
    require_once dirname(__DIR__,2) . '/modules/kuraneabackoffice/vendor/autoload.php';
    function nativePostTokenFixtureContainer(callable $accept, bool $authenticated=true):object
    {
        $tokens=new class($accept) implements \Symfony\Component\Security\Csrf\CsrfTokenManagerInterface {
            public function __construct(private mixed $accept){}
            public function getToken(string $tokenId):\Symfony\Component\Security\Csrf\CsrfToken{throw new RuntimeException('Validation must not generate a fresh token.');}
            public function refreshToken(string $tokenId):\Symfony\Component\Security\Csrf\CsrfToken{throw new RuntimeException('Validation must not refresh a token.');}
            public function removeToken(string $tokenId):?string{throw new RuntimeException('Validation must not remove a token.');}
            public function isTokenValid(\Symfony\Component\Security\Csrf\CsrfToken $token):bool{return $token->getId()==='native-authenticated-fixture'&&($this->accept)($token->getValue());}
        };
        $user=$authenticated?new class implements \PrestaShopBundle\Security\Admin\SessionEmployeeInterface {public function getUserIdentifier():string{return 'native-authenticated-fixture';}}:null;
        $validator=new \Kuranea\Backoffice\Admin\AdminPostTokenValidator($tokens,new \Symfony\Bundle\SecurityBundle\Security($user));
        return new class($validator){public function __construct(private object $validator){}public function get(string $name):object{if($name!==\Kuranea\Backoffice\Admin\AdminPostTokenValidator::class)throw new RuntimeException('Unknown fixture service.');return $this->validator;}};
    }
}
