<?php

declare(strict_types=1);

function catalogContractSource(string $path): string
{
    $source = file_get_contents(dirname(__DIR__, 2) . '/' . $path);
    if ($source === false) {
        throw new RuntimeException('Could not read catalog integration contract source: ' . $path);
    }

    return $source;
}

$moduleEntry = catalogContractSource('modules/kuraneacatalog/kuraneacatalog.php');
$controller = catalogContractSource('modules/kuraneacatalog/controllers/admin/AdminKuraneaCatalogReviewController.php');
$storage = catalogContractSource('modules/kuraneacatalog/src/Infrastructure/Persistence/CatalogQueueRepositoryFactory.php');
$compose = catalogContractSource('compose.yaml');
$dockerfile = catalogContractSource('docker/Dockerfile');
$entrypoint = catalogContractSource('docker/kuranea-entrypoint.sh');
$installer = catalogContractSource('docker/kuran-install-modules.php');
$workflow = catalogContractSource('.github/workflows/fresh-install.yml');

assertCatalogTrue(str_contains($moduleEntry, "'AdminKuraneaCatalogReview'") && str_contains($moduleEntry, "'상품 검수 대기열'"), 'The catalog module should install a Korean Back Office review tab.');
assertCatalogTrue(str_contains($moduleEntry, 'removeTab') && str_contains($moduleEntry, 'preserved on uninstall'), 'Catalog tab lifecycle should preserve the review queue when the module is uninstalled.');
assertCatalogTrue(str_contains($controller, 'ProductApprovalService') && str_contains($controller, '->pending()'), 'The admin controller should use the persistent queue and approval service.');
assertCatalogTrue(
    str_contains($controller, 'return $this->viewAccess();')
        && str_contains($controller, 'return $this->canView() && $this->access(\'edit\') && $this->access(\'add\');')
        && str_contains($controller, 'context->employee->id'),
    'Viewing and approval should use PrestaShop Back Office access APIs and an authenticated employee identity.'
);
assertCatalogTrue(str_contains($controller, "'amazon_jp' => '아마존 일본'") && str_contains($controller, "'rakuten_ichiba' => '라쿠텐 이치바'"), 'Marketplace identifiers should display as Korean labels in the admin screen.');
assertCatalogTrue(str_contains($controller, 'KURANEA_CATALOG_TEST_DEMO_APPROVAL') && str_contains($controller, 'confirm_test_demo'), 'Native registration should require a TEST/DEMO deployment gate and explicit confirmation.');
assertCatalogTrue(
    str_contains($controller, 'isValidImportMutationToken()')
        && str_contains($controller, '\\PrestaShop\\PrestaShop\\Adapter\\SymfonyContainer::getInstance()')
        && str_contains($controller, 'UserTokenManager::class')
        && str_contains($controller, '->isTokenValid()')
        && !str_contains($controller, 'hash_equals($expectedToken, $submittedToken)'),
    'Import mutations should use PrestaShop CSRF validation rather than compare masked token strings.'
);
assertCatalogTrue(str_contains($storage, '$shopRoot') && str_contains($storage, 'KURANEA_CATALOG_QUEUE_DIR'), 'Queue storage should use an injected path outside the public shop root.');
assertCatalogTrue(str_contains($compose, 'catalog_review_data:') && str_contains($compose, '/var/lib/kuranea/catalog-review') && str_contains($compose, 'KURANEA_CATALOG_QUEUE_DIR'), 'Compose should mount a named queue volume outside the PrestaShop webroot.');
assertCatalogTrue(str_contains($dockerfile, 'modules/kuraneacatalog/'), 'The catalog module should be copied into the PrestaShop image.');
assertCatalogTrue(str_contains($entrypoint, 'sync_module kuraneacatalog') && str_contains($entrypoint, '/var/lib/kuranea/catalog-review'), 'Container startup should sync the module and prepare the private queue directory.');
assertCatalogTrue(str_contains($installer, "'kuraneacatalog'"), 'The first-run installer should install the catalog module.');
assertCatalogTrue(str_contains($workflow, 'modules/kuraneacatalog/**') && str_contains($workflow, 'verify_catalog_installation.php'), 'Fresh-install CI should run the catalog module integration check.');

echo "PASS: Korean catalog admin review integration contracts\n";
