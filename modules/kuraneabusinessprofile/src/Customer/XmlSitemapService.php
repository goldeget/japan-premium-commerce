<?php

declare(strict_types=1);

namespace Kuranea\BusinessProfile\Customer;

use Kuranea\BusinessProfile\Domain\ProfileDefaults;
use Kuranea\BusinessProfile\Infrastructure\ConfiguredShopUrlProvider;
use Kuranea\BusinessProfile\Infrastructure\PublicSitemapRepository;
use Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository;

final class XmlSitemapService
{
    private const LOCALE_ISO = [
        'ja-JP' => 'ja',
        'en-US' => 'en',
        'ko-KR' => 'ko',
    ];

    public function index(int $shopId): array
    {
        $baseUrl = (new ConfiguredShopUrlProvider())->baseUrl($shopId);
        if ($baseUrl === null) {
            return self::response(503, SitemapXmlRenderer::index([]) ?? '');
        }

        $urls = [];
        $anonymousAccess = $this->anonymousGroupAccess($shopId);
        if ($anonymousAccess === null) {
            return self::response(200, SitemapXmlRenderer::index([]) ?? '');
        }
        [$groupFeatureActive, $guestGroupId] = $anonymousAccess;
        foreach ($this->enabledLanguages($shopId) as $language) {
            $iso = (string) $language['iso_code'];
            $langId = (int) $language['id_lang'];
            $profile = (new PublishedProfileProvider(new VersionedProfileRepository()))->forShop($shopId, $iso);
            if (!CommerceGate::isEnabled($profile, getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1')) {
                continue;
            }

            $locale = PublishedProfileProvider::localeForIso($iso);
            if (!in_array($locale, (array) ($profile['localization']['enabled_locales'] ?? []), true)) {
                continue;
            }

            $pageCount = $this->pageCount($shopId, $langId, $groupFeatureActive, $guestGroupId);
            if ($pageCount === null || $pageCount > SitemapUrlPolicy::MAX_SITEMAPS_PER_INDEX) {
                return self::response(503, SitemapXmlRenderer::index([]) ?? '');
            }

            for ($page = 1; $page <= $pageCount; ++$page) {
                $nativeUrl = \Context::getContext()->link->getModuleLink(
                    'kuraneabusinessprofile',
                    'sitemappage',
                    ['iso' => $iso, 'page' => $page],
                    null,
                    $langId,
                    $shopId
                );
                $url = SitemapUrlPolicy::canonicalizeNativeUrl(
                    (string) $nativeUrl,
                    $baseUrl,
                    'module',
                    0,
                    $langId,
                    $iso,
                    $page
                );
                if ($url === null || count($urls) >= SitemapUrlPolicy::MAX_SITEMAPS_PER_INDEX) {
                    return self::response(503, SitemapXmlRenderer::index([]) ?? '');
                }
                $urls[] = $url;
            }
        }

        $xml = SitemapXmlRenderer::index($urls);

        return $xml === null ? self::response(503, SitemapXmlRenderer::index([]) ?? '') : self::response(200, $xml);
    }

    public function page(int $shopId, string $iso, int $page): array
    {
        $emptyXml = SitemapXmlRenderer::urlSet([]);
        if ($emptyXml === null) {
            return self::response(503, '');
        }

        if ($shopId < 1 || !in_array($iso, ['ja', 'en', 'ko'], true) || $page < 1) {
            return self::response(404, $emptyXml);
        }

        $baseUrl = (new ConfiguredShopUrlProvider())->baseUrl($shopId);
        if ($baseUrl === null) {
            return self::response(503, $emptyXml);
        }

        $language = null;
        foreach ($this->enabledLanguages($shopId) as $candidate) {
            if ((string) $candidate['iso_code'] === $iso) {
                $language = $candidate;
                break;
            }
        }
        if ($language === null) {
            return self::response(404, $emptyXml);
        }

        $langId = (int) $language['id_lang'];
        $profile = (new PublishedProfileProvider(new VersionedProfileRepository()))->forShop($shopId, $iso);
        $locale = PublishedProfileProvider::localeForIso($iso);
        if (!CommerceGate::isEnabled($profile, getenv('ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') === '1')
            || !in_array($locale, (array) ($profile['localization']['enabled_locales'] ?? []), true)
        ) {
            return self::response(200, $emptyXml);
        }

        $repository = new PublicSitemapRepository();
        $rootCategoryId = (int) \Configuration::get('PS_ROOT_CATEGORY');
        $homeCategoryId = (int) \Configuration::get('PS_HOME_CATEGORY');
        $anonymousAccess = $this->anonymousGroupAccess($shopId);
        if ($anonymousAccess === null) {
            return self::response(200, $emptyXml);
        }
        [$groupFeatureActive, $guestGroupId] = $anonymousAccess;
        $candidateCount = $repository->countEntries(
            $shopId,
            $langId,
            $rootCategoryId,
            $homeCategoryId,
            $groupFeatureActive,
            $guestGroupId
        );
        if ($candidateCount === null) {
            return self::response(503, $emptyXml);
        }

        $totalEntries = 1 + $candidateCount;
        $pageCount = max(1, (int) ceil($totalEntries / SitemapUrlPolicy::MAX_URLS_PER_SITEMAP));
        if ($pageCount > SitemapUrlPolicy::MAX_SITEMAPS_PER_INDEX) {
            return self::response(503, $emptyXml);
        }
        if ($page > $pageCount) {
            return self::response(404, $emptyXml);
        }

        $offset = ($page - 1) * SitemapUrlPolicy::MAX_URLS_PER_SITEMAP;
        $nativeEntries = [];
        $candidateOffset = $offset;
        $candidateLimit = SitemapUrlPolicy::MAX_URLS_PER_SITEMAP;
        if ($offset === 0) {
            $nativeEntries[] = [
                'kind' => 'home',
                'id' => 0,
                'url' => \Context::getContext()->link->getPageLink('index', null, $langId, null, false, $shopId),
            ];
            $candidateOffset = 0;
            --$candidateLimit;
        } else {
            --$candidateOffset;
        }

        $expectedCandidates = min($candidateLimit, max(0, $candidateCount - $candidateOffset));
        $entries = $repository->entries(
            $shopId,
            $langId,
            $rootCategoryId,
            $homeCategoryId,
            $candidateOffset,
            $candidateLimit,
            $groupFeatureActive,
            $guestGroupId
        );
        if ($entries === null || count($entries) !== $expectedCandidates) {
            return self::response(503, $emptyXml);
        }

        foreach ($entries as $entry) {
            if ($entry['kind'] === 'category') {
                $nativeUrl = \Context::getContext()->link->getCategoryLink(
                    $entry['id'],
                    $entry['link_rewrite'],
                    $langId,
                    null,
                    $shopId,
                    false
                );
            } else {
                $nativeUrl = \Context::getContext()->link->getProductLink(
                    $entry['id'],
                    $entry['link_rewrite'],
                    null,
                    null,
                    $langId,
                    $shopId,
                    null,
                    false,
                    false,
                    false,
                    [],
                    false
                );
            }

            $nativeEntries[] = ['kind' => $entry['kind'], 'id' => $entry['id'], 'url' => $nativeUrl];
        }

        if (count($nativeEntries) > SitemapUrlPolicy::MAX_URLS_PER_SITEMAP) {
            return self::response(503, $emptyXml);
        }

        $urls = [];
        foreach ($nativeEntries as $entry) {
            $url = SitemapUrlPolicy::canonicalizeNativeUrl(
                (string) $entry['url'],
                $baseUrl,
                (string) $entry['kind'],
                (int) $entry['id'],
                $langId
            );
            if ($url === null) {
                return self::response(503, $emptyXml);
            }
            $urls[] = $url;
        }

        $xml = SitemapXmlRenderer::urlSet($urls);

        return $xml === null ? self::response(503, $emptyXml) : self::response(200, $xml);
    }

    /** @return list<array{id_lang: int, iso_code: string}> */
    private function enabledLanguages(int $shopId): array
    {
        $languages = [];
        foreach (\Language::getLanguages(true, $shopId) as $language) {
            $iso = strtolower((string) ($language['iso_code'] ?? ''));
            $locale = array_search($iso, self::LOCALE_ISO, true);
            if ($locale === false || !in_array($locale, ProfileDefaults::LOCALES, true)) {
                continue;
            }
            $languages[] = [
                'id_lang' => (int) ($language['id_lang'] ?? 0),
                'iso_code' => $iso,
            ];
        }

        return array_values(array_filter($languages, static fn (array $item): bool => $item['id_lang'] > 0));
    }

    private function pageCount(int $shopId, int $langId, bool $groupFeatureActive, int $guestGroupId): ?int
    {
        $count = (new PublicSitemapRepository())->countEntries(
            $shopId,
            $langId,
            (int) \Configuration::get('PS_ROOT_CATEGORY'),
            (int) \Configuration::get('PS_HOME_CATEGORY'),
            $groupFeatureActive,
            $guestGroupId
        );
        if ($count === null) {
            return null;
        }

        return max(1, (int) ceil((1 + $count) / SitemapUrlPolicy::MAX_URLS_PER_SITEMAP));
    }

    /** Resolve the exact public visitor group even when the sitemap request has an authenticated session.
     *  A missing or shop-unassociated guest group must fail closed; customer membership is not equivalent.
     *  @return array{0: bool, 1: int}|null
     */
    private function anonymousGroupAccess(int $shopId): ?array
    {
        if (!\Group::isFeatureActive()) {
            return [false, 0];
        }

        $groupId = (int) \Configuration::get('PS_UNIDENTIFIED_GROUP', null, null, $shopId);
        if ($groupId < 1) {
            return null;
        }
        $group = new \Group($groupId);

        return AnonymousGroupPolicy::resolve(
            true,
            $groupId,
            (int) ($group->id ?? 0),
            $group->isAssociatedToShop($shopId)
        );
    }

    /** @return array{status: int, body: string} */
    private static function response(int $status, string $body): array
    {
        return ['status' => $status, 'body' => $body];
    }
}
