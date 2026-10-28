<?php

declare(strict_types=1);
namespace Kuranea\Backoffice\Admin;

use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\Security\Csrf\{CsrfToken,CsrfTokenManagerInterface};
use PrestaShopBundle\Security\Admin\SessionEmployeeInterface;

/** Validates the submitted value using the native session's CSRF seed, including PS9 masked tokens. */
final class AdminPostTokenValidator
{
    public function __construct(private readonly CsrfTokenManagerInterface $tokens, private readonly Security $security) {}

    public function valid(mixed $submitted): bool
    {
        if (!is_string($submitted) || $submitted === '') return false;
        try {
            $user = $this->security->getUser();
            if (!$user instanceof SessionEmployeeInterface) return false;
            $identifier = $user->getUserIdentifier();
            return is_string($identifier) && $identifier !== '' && $this->tokens->isTokenValid(new CsrfToken($identifier,$submitted));
        } catch (\Throwable) {
            return false;
        }
    }

    /** Missing native services fail closed; query tokens never stand in for the POST body. */
    public static function forController(object $controller, mixed $submitted): bool
    {
        if (!is_string($submitted) || $submitted === '') return false;
        try {
            $container = $controller->getContainer();
            if (!is_object($container)) return false;
            $service = $container->get(self::class);
            return $service instanceof self && $service->valid($submitted);
        } catch (\Throwable) {
            return false;
        }
    }
}
