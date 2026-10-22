<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Domain;

final class ProfileVersion
{
    public function __construct(
        public readonly int $id,
        public readonly int $shopId,
        public readonly array $profile,
        public readonly int $employeeId,
        public readonly ?int $parentVersionId,
        public readonly string $createdAt,
    ) {
    }
}
