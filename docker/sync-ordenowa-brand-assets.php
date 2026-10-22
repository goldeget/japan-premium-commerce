<?php

declare(strict_types=1);

/** Install the verified deployment pack without replacing any existing image. */
$sourceRoot = rtrim((string) (getenv('ORDENOWA_BRAND_SOURCE_ROOT') ?: '/opt/ordenowa-brand'), DIRECTORY_SEPARATOR);
$webRoot = rtrim((string) (getenv('ORDENOWA_BRAND_WEB_ROOT') ?: '/var/www/html'), DIRECTORY_SEPARATOR);
$privateRoot = rtrim((string) (getenv('ORDENOWA_BRAND_PRIVATE_ROOT') ?: '/var/www/html/var/ordenowa-private'), DIRECTORY_SEPARATOR);
$testMode = getenv('ORDENOWA_BRAND_TEST_MODE') === '1';
$manifestPath = $sourceRoot . '/asset-manifest.json';
$manifestBytes = @file_get_contents($manifestPath);
$manifest = is_string($manifestBytes) ? json_decode($manifestBytes, true) : null;
if (!is_array($manifest) || ($manifest['brand'] ?? null) !== 'ORDENOWA'
    || !is_array($manifest['sources_sha256'] ?? null) || !is_array($manifest['derived'] ?? null)
) {
    throw new RuntimeException('The official ORDENOWA image manifest is missing or invalid.');
}

$sourceDefinitions = [
    'primary_logo' => ['ORDENOWA-logo.png', 2172, 724],
    'favicon_symbol' => ['ORDENOWA-favicon-source.png', 1254, 1254],
    'pwa_icon' => ['ORDENOWA-pwa-icon-source.png', 1254, 1254],
];
$sourceMetadata = [];
foreach ($sourceDefinitions as $slot => [$filename, $width, $height]) {
    $bytes = readVerified($sourceRoot . '/official_originals/' . $filename, $manifest['sources_sha256'][$filename] ?? null);
    $imageInfo = @getimagesizefromstring($bytes);
    if (!is_array($imageInfo) || $imageInfo[0] !== $width || $imageInfo[1] !== $height || ($imageInfo['mime'] ?? '') !== 'image/png') {
        throw new RuntimeException('The official ORDENOWA source image has unexpected image data.');
    }
    $hash = hash('sha256', $bytes);
    $extension = 'png';
    $relativePath = 'source/' . $slot . '/' . $hash . '.' . $extension;
    installImmutable($privateRoot . '/' . $relativePath, $bytes, $hash, 0600, $testMode);
    if (!$testMode) {
        setPrivatePathOwner($privateRoot, $privateRoot . '/' . $relativePath);
    }
    $sourceMetadata[$slot] = [
        'path' => $relativePath,
        'sha256' => $hash,
        'mime' => 'image/png',
        'width' => $width,
        'height' => $height,
    ];
}

$primaryHash = $sourceMetadata['primary_logo']['sha256'];
$faviconHash = $sourceMetadata['favicon_symbol']['sha256'];
$pwaHash = $sourceMetadata['pwa_icon']['sha256'];
$assetDefinitions = [
    ['logo-desktop.png', $primaryHash, 'official-header-desktop.png'],
    ['logo-mobile.png', $primaryHash, 'official-header-mobile.png'],
    ['logo-desktop.png', $primaryHash, 'official-admin-login.png'],
    ['logo-email.png', $primaryHash, 'official-email-logo.png'],
    ['og-1200x630.png', $primaryHash, 'official-og-brand.png'],
    ['favicon.ico', $faviconHash, 'official-favicon.ico'],
    ['favicon-16x16.png', $faviconHash, 'official-favicon-16.png'],
    ['favicon-32x32.png', $faviconHash, 'official-favicon-32.png'],
    ['apple-touch-icon.png', $pwaHash, 'official-apple-touch-icon.png'],
    ['pwa-192x192.png', $pwaHash, 'official-pwa-192.png'],
    ['pwa-512x512.png', $pwaHash, 'official-pwa-512.png'],
    ['pwa-maskable-512x512.png', $pwaHash, 'official-pwa-maskable-512.png'],
];

foreach ($assetDefinitions as [$sourceFilename, $sourceHash, $targetFilename]) {
    $expected = $manifest['derived'][$sourceFilename] ?? null;
    if (!is_array($expected)) {
        throw new RuntimeException('The official ORDENOWA image manifest omits a required derivative.');
    }
    $bytes = readVerified($sourceRoot . '/web_assets/' . $sourceFilename, $expected['sha256'] ?? null);
    if (strlen($bytes) !== (int) ($expected['bytes'] ?? -1)) {
        throw new RuntimeException('An official ORDENOWA derivative has an unexpected file size.');
    }
    $relativePath = 'img/ordenowa/versions/' . $sourceHash . '/' . $targetFilename;
    installImmutable($webRoot . '/' . $relativePath, $bytes, (string) $expected['sha256'], 0644, $testMode);
}

if (!$testMode) {
    $versionsRoot = $webRoot . '/img/ordenowa/versions';
    setOwner($versionsRoot);
    if (!chmod($versionsRoot, 0755)) {
        throw new RuntimeException('Could not prepare writable versioned ORDENOWA image storage.');
    }
    foreach ([$primaryHash, $faviconHash, $pwaHash] as $versionHash) {
        $versionDirectory = $versionsRoot . '/' . $versionHash;
        setOwner($versionDirectory);
        if (!chmod($versionDirectory, 0755)) {
            throw new RuntimeException('Could not prepare the official ORDENOWA image version directory.');
        }
    }
}

$accessRules = "Options -Indexes\nRequire all denied\nDeny from all\n";
ensureDirectory($privateRoot, 0700);
$accessFile = $privateRoot . '/.htaccess';
if (is_link($accessFile)) {
    throw new RuntimeException('The private ORDENOWA source access file cannot be a symbolic link.');
}
if (is_file($accessFile)) {
    $existingRules = file_get_contents($accessFile);
    if (!is_string($existingRules) || !str_contains($existingRules, 'Require all denied') || !str_contains($existingRules, 'Deny from all')) {
        throw new RuntimeException('The private ORDENOWA source directory is missing its deny rule.');
    }
} else {
    installImmutable($accessFile, $accessRules, hash('sha256', $accessRules), 0600, $testMode);
}

if (!$testMode) {
    setOwner($accessFile);
    if (!chmod($accessFile, 0600)) {
        throw new RuntimeException('Could not protect the private ORDENOWA source access file.');
    }
    setPrivatePathOwner($privateRoot, $accessFile);
    if (!chmod($privateRoot, 0700)) {
        throw new RuntimeException('Could not protect the private ORDENOWA source directory.');
    }
}

echo "PASS: verified ORDENOWA source originals and public derivatives installed without overwriting existing files.\n";

function readVerified(string $path, mixed $expectedHash): string
{
    if (!is_string($expectedHash) || preg_match('/\A[a-f0-9]{64}\z/D', $expectedHash) !== 1 || is_link($path)) {
        throw new RuntimeException('The official ORDENOWA asset manifest has an invalid hash or source path.');
    }
    $bytes = @file_get_contents($path);
    if (!is_string($bytes) || !hash_equals($expectedHash, hash('sha256', $bytes))) {
        throw new RuntimeException('An official ORDENOWA asset failed SHA-256 verification.');
    }

    return $bytes;
}

function installImmutable(string $path, string $bytes, string $expectedHash, int $mode, bool $testMode): void
{
    if (is_link($path)) {
        throw new RuntimeException('The ORDENOWA asset target cannot be a symbolic link.');
    }
    ensureDirectory(dirname($path), $mode === 0600 ? 0700 : 0755);
    if (is_file($path)) {
        $existingHash = hash_file('sha256', $path);
        if (!is_string($existingHash) || !hash_equals($expectedHash, $existingHash)) {
            throw new RuntimeException('An existing ORDENOWA asset differs; preserving it without overwrite.');
        }
    } else {
        $temporary = tempnam(dirname($path), '.ordenowa-');
        if ($temporary === false) {
            throw new RuntimeException('Could not create a temporary ORDENOWA asset file.');
        }
        try {
            if (file_put_contents($temporary, $bytes, LOCK_EX) !== strlen($bytes)) {
                throw new RuntimeException('Could not write the complete ORDENOWA asset file.');
            }
            chmod($temporary, $mode);
            if (!rename($temporary, $path)) {
                throw new RuntimeException('Could not install the ORDENOWA asset file.');
            }
        } finally {
            if (is_file($temporary)) {
                unlink($temporary);
            }
        }
    }

    if (!$testMode) {
        setOwner($path);
        chmod($path, $mode);
    }
}

function ensureDirectory(string $path, int $mode): void
{
    if (!is_dir($path) && !mkdir($path, $mode, true) && !is_dir($path)) {
        throw new RuntimeException('Could not create an ORDENOWA asset directory.');
    }
    if (is_link($path) || !is_writable($path)) {
        throw new RuntimeException('An ORDENOWA asset directory is unsafe or not writable.');
    }
}

function setPrivatePathOwner(string $privateRoot, string $path): void
{
    $root = rtrim($privateRoot, DIRECTORY_SEPARATOR);
    $current = is_dir($path) ? $path : dirname($path);
    while ($current === $root || str_starts_with($current, $root . DIRECTORY_SEPARATOR)) {
        setOwner($current);
        if ($current === $root) {
            return;
        }
        $current = dirname($current);
    }
    throw new RuntimeException('The private ORDENOWA asset path escaped its configured directory.');
}

function setOwner(string $path): void
{
    if (!chown($path, 'www-data') || !chgrp($path, 'www-data')) {
        throw new RuntimeException('Could not assign ORDENOWA assets to the PrestaShop web process.');
    }
}
