<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Security;

/** Construct only from verified native identities in Integration\Runtime. */
final class Actor
{
    private function __construct(
        public readonly int $shopId,
        public readonly int $id,
        public readonly string $type,
        private readonly array $permissions
    ) {
        if ($shopId < 1 || $id < 1) {
            throw new \InvalidArgumentException('A verified identity is required.', 403);
        }
    }

    public static function customer(int $shop, int $customer): self
    {
        return new self($shop, $customer, 'customer', []);
    }

    public static function employee(int $shop, int $employee, array $permissions): self
    {
        return new self($shop, $employee, 'employee', array_values(array_filter($permissions, 'is_string')));
    }

    public function require(string $permission): void
    {
        if ($this->type !== 'employee' || !in_array($permission, $this->permissions, true)) {
            throw new \RuntimeException('Permission denied.', 403);
        }
    }
}
