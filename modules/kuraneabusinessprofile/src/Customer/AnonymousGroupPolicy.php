<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

final class AnonymousGroupPolicy
{
    /** @return array{0: bool, 1: int}|null */
    public static function resolve(
        bool $groupFeatureActive,
        int $configuredGuestGroupId,
        int $loadedGroupId,
        bool $associatedToCurrentShop
    ): ?array {
        if (!$groupFeatureActive) {
            return [false, 0];
        }

        if ($configuredGuestGroupId < 1
            || $loadedGroupId !== $configuredGuestGroupId
            || !$associatedToCurrentShop
        ) {
            return null;
        }

        return [true, $configuredGuestGroupId];
    }
}
