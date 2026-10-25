<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

use Kuranea\BusinessProfile\Domain\ProfileValidator;

final class CommerceGate
{
    /** Enable storefront commerce in the approved shop or its matching disposable Actions project. */
    public static function isIsolatedCiCheckoutEnabled(): bool
    {
        $runId = (string) getenv('GITHUB_RUN_ID');
        $runAttempt = (string) getenv('GITHUB_RUN_ATTEMPT');
        if (preg_match('/\\A[0-9]+\\z/D', $runId) !== 1
            || preg_match('/\\A[0-9]+\\z/D', $runAttempt) !== 1
        ) {
            return false;
        }

        return getenv('CI') === 'true'
            && getenv('GITHUB_ACTIONS') === 'true'
            && getenv('KURANEA_ISOLATED_CI') === '1'
            && getenv('KURANEA_CI_PROJECT_NAME') === 'kuranea-ci-' . $runId . '-' . $runAttempt;
    }

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

    public static function isRegistrationEnabled(
        ?array $publishedProfile,
        bool $externalAuthorizationConfirmed = false
    ): bool {
        return self::isEnabled($publishedProfile, $externalAuthorizationConfirmed)
            || self::isIsolatedCiCheckoutEnabled();
    }
}
