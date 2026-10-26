<?php

declare(strict_types=1);
namespace Kuranea\Push\Infrastructure;

use Kuranea\Push\Domain\DeliveryPayload;
use Kuranea\Push\Domain\PushDeliveryProvider;
use Kuranea\Push\Domain\PushDeliveryResult;

final class DisabledPushDeliveryProvider implements PushDeliveryProvider
{
    public function available(): bool
    {
        return false;
    }

    public function send(array $subscription, DeliveryPayload $payload): PushDeliveryResult
    {
        throw new \RuntimeException('Push delivery is disabled.');
    }
}
