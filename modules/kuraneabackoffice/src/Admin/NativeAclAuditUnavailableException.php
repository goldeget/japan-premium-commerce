<?php

declare(strict_types=1);
namespace Kuranea\Backoffice\Admin;

/** Native Hook dispatch propagates this interface rather than swallowing observer failures. */
final class NativeAclAuditUnavailableException extends \PrestaShopException implements \PrestaShop\PrestaShop\Core\Module\Exception\ModuleErrorInterface
{
}
