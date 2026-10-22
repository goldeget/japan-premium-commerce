<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

use Kuranea\BusinessProfile\Domain\ProfileValidator;

final class CommerceGate
{
    public static function isEnabled(?array $publishedProfile, bool $externalAuthorizationConfirmed = false): bool
    {
        if (!$externalAuthorizationConfirmed
            || $publishedProfile === null
            || ($publishedProfile['seller']['authorization_status'] ?? 'pending') !== 'approved'
        ) {
            return false;
        }

        return (new ProfileValidator())->validateForPublish($publishedProfile) === [];
    }
}
