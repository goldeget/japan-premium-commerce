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
$manifestController = fileText('modules/kuraneabusinessprofile/controllers/front/manifest.php');
$provider = fileText('modules/kuraneabusinessprofile/src/Customer/PublishedProfileProvider.php');
$assetProcessor = fileText('modules/kuraneabusinessprofile/src/Infrastructure/BrandAssetProcessor.php');
$profileForm = fileText('modules/kuraneabusinessprofile/src/Admin/AdminProfileForm.php');
$adminController = fileText('modules/kuraneabusinessprofile/controllers/admin/AdminBusinessProfileController.php');
$bankController = fileText('modules/kuraneabusinessprofile/controllers/admin/AdminBusinessProfileBanksController.php');
$dockerfile = fileText('docker/Dockerfile');
$entrypoint = fileText('docker/kuranea-entrypoint.sh');
$installer = fileText('docker/kuran-install-modules.php');

assertBusinessProfileBundle(str_contains($module, "\$this->name = 'kuraneabusinessprofile'"), 'PrestaShop must load the dedicated business profile module.');
assertBusinessProfileBundle(str_contains($module, 'AdminBusinessProfile') && str_contains($module, 'AdminBusinessProfileBanks'), 'The module must register the Korean profile and bank admin tabs.');
assertBusinessProfileBundle(str_contains($module, "'displayHeader'") && str_contains($module, "'displayFooter'"), 'The module must connect approved profile data to customer pages.');
assertBusinessProfileBundle(str_contains($module, "'actionGetExtraMailTemplateVars'") && str_contains($module, 'hookActionGetExtraMailTemplateVars'), 'The module must provide published brand and operation variables to email templates.');
assertBusinessProfileBundle(str_contains($module, 'hookActionFrontControllerInitBefore') && str_contains($module, "['order', 'order-opc']"), 'Customer checkout must remain blocked until the seller profile is approved.');
assertBusinessProfileBundle(str_contains($module, 'ORDENOWA_SELLER_AUTHORIZATION_CONFIRMED') && str_contains($module, 'externalAuthorizationConfirmed'), 'Admin-entered seller status alone must never activate production checkout.');
assertBusinessProfileBundle(str_contains($provider, 'loadPublished') && !str_contains($provider, 'loadDraft'), 'Anonymous customer output may read only published profile versions.');
assertBusinessProfileBundle(str_contains($manifestController, 'PwaManifestBuilder::build'), 'The public manifest must be generated from the published profile.');
assertBusinessProfileBundle(str_contains($assetProcessor, 'MAX_BYTES') && str_contains($assetProcessor, 'imagecreatefromstring'), 'Brand uploads must validate image bytes and create controlled derivatives.');
assertBusinessProfileBundle(str_contains($assetProcessor, 'Require all denied') && str_contains($assetProcessor, 'writeImmutable'), 'Original image backups must be private and immutable.');
assertBusinessProfileBundle(str_contains($profileForm, 'multipart/form-data') && str_contains($profileForm, 'brand_uploads['), 'Brand image uploads must be available in the Korean admin form.');
assertBusinessProfileBundle(str_contains($adminController, 'BrandAssetProcessor::process'), 'Admin uploads must pass through the image validation and derivative processor.');
$previewStart = strpos($adminController, "if (Tools::isSubmit('submitOrdenowaPreview'))");
$previewEnd = strpos($adminController, "if (Tools::isSubmit('submitOrdenowaRestore'))", $previewStart ?: 0);
$previewAction = $previewStart !== false && $previewEnd !== false ? substr($adminController, $previewStart, $previewEnd - $previewStart) : '';
$editGuardPosition = strpos($previewAction, 'AdminAccessPolicy::canEdit');
$uploadPosition = strpos($previewAction, 'applyUploadedBrandAssets');
assertBusinessProfileBundle($editGuardPosition !== false && $uploadPosition !== false && $editGuardPosition < $uploadPosition, 'Unsaved preview uploads must require edit permission before writing files.');
$footerBuilder = fileText('modules/kuraneabusinessprofile/src/Customer/PublicFooterBuilder.php');
assertBusinessProfileBundle(str_contains($module, 'PublicFooterBuilder::build') && str_contains($footerBuilder, 'responsible_person'), 'Approved public disclosures must render structured seller responsibility fields.');
assertBusinessProfileBundle(str_contains($bankController, 'submitOrdenowaRestoreBanks') && str_contains($bankController, 'restoreBankAccountsAsDraft'), 'Authorized bank administrators must be able to restore only prior account settings.');
assertBusinessProfileBundle(str_contains($dockerfile, 'COPY modules/kuraneabusinessprofile/'), 'The custom PrestaShop image must include the module source.');
assertBusinessProfileBundle(str_contains($entrypoint, 'sync_module kuraneabusinessprofile'), 'The entrypoint must synchronize module files into the PrestaShop volume.');
assertBusinessProfileBundle(str_contains($installer, "'kuraneabusinessprofile'"), 'The official install bootstrap must install the module after PrestaShop setup.');

echo "PASS: business profile module is bundled, synchronized, and installed by the PrestaShop runtime\n";
