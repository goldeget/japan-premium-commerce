<?php

declare(strict_types=1);

require_once __DIR__ . '/run.php';

function syntheticBrandPng(int $width, int $height): string
{
    $image = imagecreatetruecolor($width, $height);
    imagealphablending($image, false);
    imagesavealpha($image, true);
    $transparent = imagecolorallocatealpha($image, 0, 0, 0, 127);
    imagefill($image, 0, 0, $transparent);
    $navy = imagecolorallocatealpha($image, 14, 34, 58, 0);
    $gold = imagecolorallocatealpha($image, 211, 174, 99, 0);
    imagefilledrectangle($image, (int) ($width * 0.2), (int) ($height * 0.2), (int) ($width * 0.8), (int) ($height * 0.8), $navy);
    imagefilledellipse($image, (int) ($width * 0.5), (int) ($height * 0.5), (int) ($width * 0.4), (int) ($height * 0.4), $gold);
    ob_start();
    imagepng($image);
    $bytes = ob_get_clean();

    return (string) $bytes;
}

function removeBrandTestDirectory(string $directory): void
{
    if (!is_dir($directory)) {
        return;
    }
    foreach (new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($directory, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST
    ) as $item) {
        $item->isDir() ? rmdir($item->getPathname()) : unlink($item->getPathname());
    }
    rmdir($directory);
}

$temporaryRoot = sys_get_temp_dir() . '/ordenowa-brand-assets-' . bin2hex(random_bytes(5));
$publicRoot = $temporaryRoot . '/public';
$privateRoot = $temporaryRoot . '/private';
mkdir($temporaryRoot, 0700, true);
$original = syntheticBrandPng(160, 96);

assertBusinessProfileThrows(
    static fn () => \Kuranea\BusinessProfile\Infrastructure\BrandAssetProcessor::process('primary_logo', 'not an image', $publicRoot, $privateRoot),
    'Invalid image bytes must be rejected.'
);
assertBusinessProfileThrows(
    static fn () => \Kuranea\BusinessProfile\Infrastructure\BrandAssetProcessor::process('primary_logo', syntheticBrandPng(16, 16), $publicRoot, $privateRoot),
    'Images below the minimum source dimensions must be rejected.'
);
assertBusinessProfileThrows(
    static fn () => \Kuranea\BusinessProfile\Infrastructure\BrandAssetProcessor::process('unknown_slot', $original, $publicRoot, $privateRoot),
    'Unknown source roles must be rejected.'
);
assertBusinessProfileThrows(
    static fn () => \Kuranea\BusinessProfile\Infrastructure\BrandAssetProcessor::process('primary_logo', str_repeat('x', 10 * 1024 * 1024 + 1), $publicRoot, $privateRoot),
    'Oversized source files must be rejected before image decoding.'
);

try {
    $logo = \Kuranea\BusinessProfile\Infrastructure\BrandAssetProcessor::process('primary_logo', $original, $publicRoot, $privateRoot);
    $symbol = \Kuranea\BusinessProfile\Infrastructure\BrandAssetProcessor::process('favicon_symbol', $original, $publicRoot, $privateRoot);
    $appIcon = \Kuranea\BusinessProfile\Infrastructure\BrandAssetProcessor::process('pwa_icon', $original, $publicRoot, $privateRoot);

    foreach ([
        [$logo, ['header_desktop', 'header_mobile', 'admin_login', 'email_logo', 'og_image']],
        [$symbol, ['favicon', 'favicon_16', 'favicon_32']],
        [$appIcon, ['apple_touch', 'pwa_192', 'pwa_512', 'pwa_maskable_512']],
    ] as [$result, $keys]) {
        foreach ($keys as $key) {
            assertBusinessProfileTrue(isset($result['assets'][$key]), 'The ' . $key . ' derivative must be generated from its source role.');
            assertBusinessProfileTrue(is_file($publicRoot . '/' . $result['assets'][$key]), 'The derivative path must resolve under the public image root.');
        }
    }

    assertBusinessProfileSame(hash('sha256', $original), $logo['source']['sha256'], 'The source hash must identify the exact original file.');
    assertBusinessProfileSame($original, file_get_contents($privateRoot . '/' . $logo['source']['path']), 'The original logo bytes must be preserved exactly.');
    assertBusinessProfileSame([640, 200], array_slice(getimagesize($publicRoot . '/' . $logo['assets']['header_desktop']), 0, 2), 'Desktop logo output must use a fixed non-distorting canvas.');
    assertBusinessProfileSame([360, 120], array_slice(getimagesize($publicRoot . '/' . $logo['assets']['header_mobile']), 0, 2), 'Mobile logo output must use a fixed non-distorting canvas.');
    assertBusinessProfileSame([180, 180], array_slice(getimagesize($publicRoot . '/' . $appIcon['assets']['apple_touch']), 0, 2), 'Apple Touch icon must have its required dimensions.');
    assertBusinessProfileSame([512, 512], array_slice(getimagesize($publicRoot . '/' . $appIcon['assets']['pwa_maskable_512']), 0, 2), 'Maskable PWA output must have its required dimensions.');
    assertBusinessProfileSame(hex2bin('00000100'), file_get_contents($publicRoot . '/' . $symbol['assets']['favicon'], false, null, 0, 4), 'The favicon derivative must be a valid ICO container.');
    assertBusinessProfileTrue(str_contains((string) file_get_contents($privateRoot . '/.htaccess'), 'Require all denied'), 'Original source uploads must not be served publicly.');
} finally {
    removeBrandTestDirectory($temporaryRoot);
}

echo "PASS: ORDENOWA source images are preserved, validated, and transformed into immutable role-specific derivatives\n";
