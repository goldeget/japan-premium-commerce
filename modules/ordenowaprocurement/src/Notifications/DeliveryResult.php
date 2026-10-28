<?php
declare(strict_types=1);
namespace Ordenowa\Procurement\Notifications;

final class DeliveryResult
{
    public function __construct(public readonly string $status, public readonly string $code = '')
    {
        if (!in_array($status, ['sent', 'retry', 'uncertain', 'skipped'], true)
            || preg_match('/^[a-z_]{0,32}$/D', $code) !== 1) {
            throw new \InvalidArgumentException('Invalid notification delivery result.');
        }
    }
}
