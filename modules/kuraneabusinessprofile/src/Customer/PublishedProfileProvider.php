<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

use Kuranea\BusinessProfile\Domain\ProfileDefaults;
use Kuranea\BusinessProfile\Domain\ProfileVersionRepositoryInterface;

final class PublishedProfileProvider
{
    public function __construct(private readonly ProfileVersionRepositoryInterface $repository)
    {
    }

    /** @return array<string, mixed>|null */
    public function forShop(int $shopId, ?string $isoCode = null): ?array
    {
        if ($shopId < 1) {
            return null;
        }

        $published = $this->repository->loadPublished($shopId);
        if ($published === null) {
            return null;
        }

        $profile = $published->profile;
        $defaultLocale = $profile['localization']['default_locale'] ?? 'ja-JP';
        if (!in_array($defaultLocale, ProfileDefaults::LOCALES, true)) {
            $defaultLocale = 'ja-JP';
        }
        $requestedLocale = self::localeForIso((string) ($isoCode ?? ''));
        $enabledLocales = $profile['localization']['enabled_locales'] ?? ProfileDefaults::LOCALES;
        $resolvedLocale = in_array($requestedLocale, $enabledLocales, true) ? $requestedLocale : $defaultLocale;
        $profile['_resolved_locale'] = $resolvedLocale;

        return $profile;
    }

    public static function localeForIso(string $isoCode): string
    {
        return match (strtolower(trim($isoCode))) {
            'en' => 'en-US',
            'ko' => 'ko-KR',
            'ja' => 'ja-JP',
            default => 'ja-JP',
        };
    }
}
