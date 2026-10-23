<?php

declare(strict_types=1);

require_once __DIR__ . '/run.php';

$repository = new InMemoryBusinessProfileRepository();
$service = new \Kuranea\BusinessProfile\Domain\ProfileVersionService($repository, $validator, $brandPublishTestRoot);
$publishedId = $service->saveDraft(1, $initial, 41);
assertBusinessProfileSame(true, $service->publish(1, $publishedId, 41)['published'], 'A complete real derivative set must publish while seller approval is pending.');
$draft = $initial;
$draft['brand']['name']['ko-KR'] = '게시 실패 검증';
$draftId = $service->saveDraft(1, $draft, 42);
foreach ($initial['brand']['assets'] as $asset => $relativePath) {
    $assetPath = $brandPublishTestRoot . '/' . $relativePath;
    $bytes = file_get_contents($assetPath);
    unlink($assetPath);
    $result = $service->publish(1, $draftId, 42);
    assertBusinessProfileSame(false, $result['published'], 'A missing ' . $asset . ' derivative must block publication even before seller approval.');
    assertBusinessProfileTrue($result['errors'] !== [], 'A missing derivative must produce a Korean validation error.');
    assertBusinessProfileSame($publishedId, $repository->loadPublished(1)?->id, 'A failed publication must preserve the prior published pointer.');
    assertBusinessProfileSame(2, count($service->history(1)), 'A failed publication must preserve both immutable versions.');
    file_put_contents($assetPath, $bytes);
}

$assetPath = $brandPublishTestRoot . '/' . $initial['brand']['assets']['header_desktop'];
$bytes = file_get_contents($assetPath);
file_put_contents($assetPath, 'not-an-image');
$malformedResult = $service->publish(1, $draftId, 42);
assertBusinessProfileSame(false, $malformedResult['published'], 'A nonempty malformed PNG derivative must block publication.');
assertBusinessProfileSame($publishedId, $repository->loadPublished(1)?->id, 'A malformed derivative must preserve the prior published pointer.');
file_put_contents($assetPath, $bytes);

$wrongSmallPng = file_get_contents(__DIR__ . '/../../assets/brand/ordenowa/web_assets/favicon-16x16.png');
$wrongLargePng = file_get_contents(__DIR__ . '/../../assets/brand/ordenowa/web_assets/favicon-32x32.png');
foreach (array_keys($initial['brand']['assets']) as $asset) {
    if ($asset === 'favicon') {
        continue;
    }

    $assetPath = $brandPublishTestRoot . '/' . $initial['brand']['assets'][$asset];
    $bytes = file_get_contents($assetPath);
    $wrongDimensions = $asset === 'favicon_16' ? $wrongLargePng : $wrongSmallPng;
    file_put_contents($assetPath, $wrongDimensions);
    assertBusinessProfileSame(false, $service->publish(1, $draftId, 42)['published'], 'A decodable PNG with the wrong dimensions must block ' . $asset . ' publication.');
    assertBusinessProfileSame($publishedId, $repository->loadPublished(1)?->id, 'A wrong-size ' . $asset . ' derivative must preserve the prior published pointer.');
    file_put_contents($assetPath, $bytes);
}

$assetPath = $brandPublishTestRoot . '/' . $initial['brand']['assets']['favicon'];
$icoBytes = file_get_contents($assetPath);
$brokenIco = 'not-an-ico';
file_put_contents($assetPath, $brokenIco);
assertBusinessProfileSame(false, $service->publish(1, $draftId, 42)['published'], 'A nonempty malformed ICO must block publication.');
assertBusinessProfileSame($publishedId, $repository->loadPublished(1)?->id, 'A malformed ICO must preserve the prior published pointer.');
$missing32Icon = substr_replace($icoBytes, pack('v', 1), 4, 2);
file_put_contents($assetPath, $missing32Icon);
assertBusinessProfileSame(false, $service->publish(1, $draftId, 42)['published'], 'An ICO without a 32x32 embedded PNG must block publication.');
$corrupt32Icon = $icoBytes;
$iconHeader = unpack('vcount', substr($icoBytes, 4, 2));
for ($index = 0; $index < $iconHeader['count']; $index++) {
    $entry = unpack('Cwidth/Cheight/Ccolors/Creserved/vplanes/vbitCount/Vbytes/Voffset', substr($icoBytes, 6 + ($index * 16), 16));
    $width = $entry['width'] === 0 ? 256 : $entry['width'];
    $height = $entry['height'] === 0 ? 256 : $entry['height'];
    if ($width === 32 && $height === 32) {
        $corrupt32Icon = substr_replace($corrupt32Icon, "\0", $entry['offset'], 1);
        break;
    }
}
file_put_contents($assetPath, $corrupt32Icon);
assertBusinessProfileSame(false, $service->publish(1, $draftId, 42)['published'], 'A corrupt embedded 32x32 PNG must block ICO publication.');
assertBusinessProfileSame($publishedId, $repository->loadPublished(1)?->id, 'A malformed ICO must preserve the prior published pointer.');
file_put_contents($assetPath, $icoBytes);

$assetPath = $brandPublishTestRoot . '/' . $initial['brand']['assets']['header_desktop'];
$bytes = file_get_contents($assetPath);
file_put_contents($assetPath, '');
assertBusinessProfileSame(false, $service->publish(1, $draftId, 42)['published'], 'An empty derivative must block publication.');
unlink($assetPath);
$outsidePath = $brandPublishTestRoot . '/outside.png';
file_put_contents($outsidePath, $bytes);
symlink($outsidePath, $assetPath);
assertBusinessProfileSame(false, $service->publish(1, $draftId, 42)['published'], 'A symlinked derivative must block publication.');
assertBusinessProfileSame($bytes, file_get_contents($outsidePath), 'Publication validation must preserve a symlink target.');
unlink($assetPath);
unlink($outsidePath);
file_put_contents($assetPath, $bytes);

foreach (['../outside.png', '/outside.png', '', null] as $unsafePath) {
    $unsafeDraft = $draft;
    $unsafeDraft['brand']['assets']['header_desktop'] = $unsafePath;
    $unsafeId = $service->saveDraft(1, $unsafeDraft, 42);
    assertBusinessProfileSame(false, $service->publish(1, $unsafeId, 42)['published'], 'Unsafe or missing derivative references must block publication.');
    assertBusinessProfileSame($publishedId, $repository->loadPublished(1)?->id, 'An unsafe derivative reference must preserve the published pointer.');
}
assertBusinessProfileSame(true, $service->publish(1, $draftId, 42)['published'], 'Restoring the exact derivative must allow the saved draft to publish.');

$generatedProfile = $initial;
foreach ([
    'primary_logo' => 'ORDENOWA-logo.png',
    'favicon_symbol' => 'ORDENOWA-favicon-source.png',
    'pwa_icon' => 'ORDENOWA-pwa-icon-source.png',
] as $slot => $sourceFilename) {
    $processed = \Kuranea\BusinessProfile\Infrastructure\BrandAssetProcessor::process(
        $slot,
        file_get_contents(__DIR__ . '/../../assets/brand/ordenowa/official_originals/' . $sourceFilename),
        $brandPublishTestRoot,
        $brandPublishTestRoot . '/private'
    );
    $generatedProfile['brand']['sources'][$slot] = $processed['source'];
    $generatedProfile['brand']['assets'] = array_replace($generatedProfile['brand']['assets'], $processed['assets']);
}
$generatedRepository = new InMemoryBusinessProfileRepository();
$generatedService = new \Kuranea\BusinessProfile\Domain\ProfileVersionService($generatedRepository, $validator, $brandPublishTestRoot);
$generatedId = $generatedService->saveDraft(1, $generatedProfile, 43);
assertBusinessProfileSame(true, $generatedService->publish(1, $generatedId, 43)['published'], 'Every generated role-specific PNG and the generated 32x32 ICO must publish.');

echo "PASS: missing, malformed, wrong-size, and symlinked brand derivatives block publication while preserving the published pointer\n";
