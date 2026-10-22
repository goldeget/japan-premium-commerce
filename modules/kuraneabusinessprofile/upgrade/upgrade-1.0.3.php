<?php

declare(strict_types=1);

require_once dirname(__DIR__) . '/autoload.php';

use Kuranea\BusinessProfile\Domain\ProfileDefaults;
use Kuranea\BusinessProfile\Infrastructure\VersionedProfileRepository;

/** Add approved image paths as new immutable versions while preserving all operational fields. */
function upgrade_module_1_0_3($module): bool
{
    $repository = new VersionedProfileRepository();
    $defaults = ProfileDefaults::initial();
    $shopIds = \Shop::getShops(true, null, true);
    if (!is_array($shopIds) || $shopIds === []) {
        $shopIds = [1];
    }

    foreach ($shopIds as $shopIdValue) {
        $shopId = max(1, (int) $shopIdValue);
        $draft = $repository->loadDraft($shopId);
        if ($draft !== null) {
            $profile = ordenowa_add_verified_brand_defaults($draft->profile, $defaults);
            if ($profile !== $draft->profile) {
                $version = $repository->insertVersion($shopId, $profile, 0, $draft->id);
                $repository->setDraftPointer($shopId, $version->id);
            }
        }

        $published = $repository->loadPublished($shopId);
        if ($published !== null) {
            $profile = ordenowa_add_verified_brand_defaults($published->profile, $defaults);
            if ($profile !== $published->profile) {
                $version = $repository->insertVersion($shopId, $profile, 0, $published->id);
                $repository->publishVersion($shopId, $version->id, 0);
            }
            if (is_object($module) && method_exists($module, 'configureOfficialMailLogo')) {
                $module->configureOfficialMailLogo($profile, $shopId);
            }
        } elseif ($draft !== null && is_object($module) && method_exists($module, 'configureOfficialMailLogo')) {
            $module->configureOfficialMailLogo($defaults, $shopId);
        }
    }

    return true;
}

/** @param array<string, mixed> $profile
 *  @param array<string, mixed> $defaults
 *  @return array<string, mixed>
 */
function ordenowa_add_verified_brand_defaults(array $profile, array $defaults): array
{
    $defaultBrand = $defaults['brand'];
    $brand = is_array($profile['brand'] ?? null) ? $profile['brand'] : [];
    $assets = is_array($brand['assets'] ?? null) ? $brand['assets'] : [];
    foreach ($defaultBrand['assets'] as $key => $defaultPath) {
        $candidate = $assets[$key] ?? null;
        if (!is_string($candidate)
            || preg_match('~\Aimg/ordenowa/versions/[A-Fa-f0-9]{64}/[A-Za-z0-9._-]+\.(?:png|ico)\z~D', $candidate) !== 1
            || !is_file(_PS_ROOT_DIR_ . '/' . $candidate)
        ) {
            $assets[$key] = $defaultPath;
        }
    }

    $sources = is_array($brand['sources'] ?? null) ? $brand['sources'] : [];
    foreach ($defaultBrand['sources'] as $slot => $defaultSource) {
        $candidate = $sources[$slot] ?? null;
        $relativePath = is_array($candidate) ? (string) ($candidate['path'] ?? '') : '';
        $expectedHash = is_array($candidate) ? (string) ($candidate['sha256'] ?? '') : '';
        $sourcePath = _PS_ROOT_DIR_ . '/var/ordenowa-private/' . $relativePath;
        if (preg_match('~\Asource/[a-z_]+/[A-Fa-f0-9]{64}\.(?:png|jpg|webp)\z~D', $relativePath) !== 1
            || preg_match('/\A[a-fA-F0-9]{64}\z/D', $expectedHash) !== 1
            || !is_file($sourcePath)
            || !hash_equals($expectedHash, (string) hash_file('sha256', $sourcePath))
        ) {
            $sources[$slot] = $defaultSource;
        }
    }

    $brand['assets'] = $assets;
    $brand['sources'] = $sources;
    $profile['brand'] = $brand;

    return $profile;
}
