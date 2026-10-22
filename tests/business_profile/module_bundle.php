<?php

declare(strict_types=1);

function assertBusinessProfileBundle(bool $condition, string $message): void
{
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

function fileText(string $path): string
{
    $text = file_get_contents(__DIR__ . '/../../' . $path);
    assertBusinessProfileBundle($text !== false, 'Required module bundle file is missing: ' . $path);

    return (string) $text;
}

$module = fileText('modules/kuraneabusinessprofile/kuraneabusinessprofile.php');
$dockerfile = fileText('docker/Dockerfile');
$entrypoint = fileText('docker/kuranea-entrypoint.sh');
$installer = fileText('docker/kuran-install-modules.php');

assertBusinessProfileBundle(str_contains($module, "\$this->name = 'kuraneabusinessprofile'"), 'PrestaShop must load the dedicated business profile module.');
assertBusinessProfileBundle(str_contains($module, 'AdminBusinessProfile') && str_contains($module, 'AdminBusinessProfileBanks'), 'The module must register the Korean profile and bank admin tabs.');
assertBusinessProfileBundle(str_contains($dockerfile, 'COPY modules/kuraneabusinessprofile/'), 'The custom PrestaShop image must include the module source.');
assertBusinessProfileBundle(str_contains($entrypoint, 'sync_module kuraneabusinessprofile'), 'The entrypoint must synchronize module files into the PrestaShop volume.');
assertBusinessProfileBundle(str_contains($installer, "'kuraneabusinessprofile'"), 'The official install bootstrap must install the module after PrestaShop setup.');

echo "PASS: business profile module is bundled, synchronized, and installed by the PrestaShop runtime\n";
