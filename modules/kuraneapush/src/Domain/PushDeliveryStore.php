<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

interface PushDeliveryStore
{
    public const MAX_DELIVERY_TARGETS = 100;

    /** Returns only rows owned by the requested shop/customer with explicit consent. */
    public function deliveryTargetsForOwner(int $shop, int $customer): array;

    /** Removes one permanently invalid endpoint under the exact owner scope. */
    public function removeDeliveryTargetForOwner(int $shop, int $customer, string $digest): void;
}
