<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

interface PushDeliveryProvider
{
    public function available(): bool;

    /** Receives a decrypted subscription for one attempt; transports send $payload->toJson() verbatim. */
    public function send(array $subscription, DeliveryPayload $payload): PushDeliveryResult;
}
