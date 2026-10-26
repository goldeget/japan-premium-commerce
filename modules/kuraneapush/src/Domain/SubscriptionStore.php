<?php

declare(strict_types=1);
namespace Kuranea\Push\Domain;

interface SubscriptionStore
{
    public function active(int $shop, int $customer): bool;
    public function save(int $shop, int $customer, string $digest, string $envelope): void;
    public function revoke(int $shop, int $customer): void;
}
