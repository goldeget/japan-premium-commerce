"""Keep import browser QA confined to its disposable synthetic CI project."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CatalogImportBrowserWorkflowContract(unittest.TestCase):
    maxDiff = 1000

    def read_required(self, path):
        target = ROOT / path
        self.assertTrue(target.is_file(), f"Missing required integration file: {path}")
        return target.read_text()

    def test_fixture_override_requires_run_identity_and_isolates_queue_storage(self):
        source = self.read_required('tests/fixtures/ci-catalog-import.compose.yaml')
        for marker in ('CI: "true"', 'GITHUB_ACTIONS: "true"', 'KURANEA_ISOLATED_CI: "1"',
                       'KURANEA_CATALOG_IMPORT_FIXTURE_MODE: "1"', '${GITHUB_RUN_ID:?',
                       '${GITHUB_RUN_ATTEMPT:?', '${CI_COMPOSE_PROJECT_NAME:?',
                       'KURANEA_CI_RUN_ID: ${GITHUB_RUN_ID:?',
                       'KURANEA_CI_RUN_ATTEMPT: ${GITHUB_RUN_ATTEMPT:?'):
            self.assertTrue(marker in source, f"Missing integration marker: {marker}")
        self.assertNotIn('volumes:', source)
        self.assertIn('KURANEA_CATALOG_QUEUE_DIR: /var/lib/kuranea/catalog-import-qa', source)

    def test_workflow_restores_base_and_aggregates_original_outcomes(self):
        source = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        for marker in ('id: catalog_import_fixture', 'id: catalog_import_browser_qa',
                       'id: catalog_import_restore', 'tests/e2e/verify_catalog_import_browser.py',
                       'tests.smoke.test_catalog_import_browser_workflow_contract',
                       'tests.smoke.test_catalog_import_admin_contract',
                       "'tests/smoke/test_catalog_import_admin_contract.py'",
                       'catalog-import-e2e.log', 'catalog-import-batch.png', 'catalog-import-rejected.png',
                       'catalog-import-draft.png', 'catalog-import-reimport.png', 'catalog-import-readback.json'):
            self.assertTrue(marker in source, f"Missing integration marker: {marker}")
        for step, variable in (('catalog_import_fixture', 'CATALOG_IMPORT_FIXTURE_OUTCOME'),
                               ('catalog_import_browser_qa', 'CATALOG_IMPORT_BROWSER_QA_OUTCOME'),
                               ('catalog_import_restore', 'CATALOG_IMPORT_RESTORE_OUTCOME')):
            self.assertIn(variable + ': ${{ steps.' + step + '.outcome }}', source)
            self.assertIn('=$' + variable + '"', source)
        restore = source.split('id: catalog_import_restore', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('if: always()', restore)
        self.assertIn('up -d --no-deps --force-recreate --wait', restore)
        self.assertNotIn('-f tests/fixtures/', restore)
        fixture = source.split('id: catalog_import_fixture', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('kuranea-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}', fixture)
        self.assertIn('catalog_import_fixture_fetcher.php', fixture)
        self.assertIn('amazon-jp-product.synthetic.html', fixture)
        self.assertIn('rakuten-product.synthetic.html', fixture)

    def test_native_persistence_checks_real_flags_and_duplicate_identity(self):
        source = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        browser = source.split('id: catalog_import_browser_qa', 1)[1].split('\n      - name:', 1)[0]
        for marker in ('product_shop', 'available_for_order', '$row["active"] !== 0',
                       '$row["visibility"] !== "none"', '$sameReference !== 1',
                       '$images !== 1', '$combinations !== 2', 'catalog-import-persistence.json'):
            self.assertIn(marker, browser)
        self.assertNotIn('DELETE ', browser)
        self.assertNotIn('UPDATE ', browser)
        integration = (ROOT / 'tests/catalog/verify_native_product_admin.php').read_text()
        self.assertIn('$productCountBeforeImportedRetry', integration)
        self.assertIn('$productCountAfterImportedRetry !== $productCountBeforeImportedRetry', integration)

    def test_browser_uses_exact_fixture_urls_and_observes_native_readback(self):
        source = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        ast.parse(source)
        for marker in ('https://www.amazon.co.jp/dp/B0KURANEA1',
                       'https://item.rakuten.co.jp/fixture-shop/synthetic-case-b/',
                       'https://www.amazon.co.jp/dp/B0KURANEA2', 'validate_isolated_ci_compose_project',
                       'validate_loopback_admin_targets', 'submitKuraneaCatalogReject',
                       'translation_reviewed_en', 'translation_reviewed_ko', 'confirm_options_supported',
                       'synthetic_ci_fixture', 'import_product_images[]', 'combination_quantities[',
                       'remove_image_ids[]', 'catalog-import-readback.json', 'linked_product_id',
                       'unique_product_ids', 'data-catalog-review-status', 'stage=', 'driver.quit()'):
            self.assertTrue(marker in source, f"Missing integration marker: {marker}")
        self.assertNotIn('page_source', source)
        self.assertNotIn('print(error)', source)
        self.assertNotIn('requests.', source)

    def test_browser_requires_one_loaded_native_product_image(self):
        source = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        self.assertIn('len(image_results) == 1', source)
        self.assertIn('naturalWidth', source)

    def test_browser_selects_and_reads_back_the_imported_category(self):
        source = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        self.assertIn('expected_category_ids', source)
        self.assertIn("form.find_elements(By.CSS_SELECTOR, 'input[name=\"category_ids[]\"]')", source)
        self.assertIn("driver.find_elements(By.CSS_SELECTOR, 'input[name=\"category_ids[]\"]')", source)
        self.assertIn('assert category_ids == expected_category_ids', source)
        self.assertIn('read_native(driver, product_id, expected_category_ids)', source)

    def test_retry_controls_stop_after_the_fixed_attempt_limit(self):
        controller = (ROOT / 'modules/kuraneacatalog/controllers/admin/AdminKuraneaCatalogReviewController.php').read_text()
        render = controller.split('private function renderBatch(', 1)[1].split(
            '/** @param list<ProductReviewQueueEntry> $pending */', 1
        )[0]
        submit = controller.split("if (Tools::isSubmit('submitKuraneaCatalogImportRetry'))", 1)[1].split(
            "if (Tools::isSubmit('submitKuraneaCatalogReject'))", 1
        )[0]
        for section in (render, submit):
            self.assertIn('CatalogImportBatchItem::MAX_ATTEMPTS', section)
            self.assertIn('CatalogImportBatchItem::STATUS_FAILED', section)
        self.assertIn('$hasRetryableItems && $this->canApprove()', render)
        self.assertIn('if (!$hasRetryableItems)', submit)
        self.assertIn('재시도 가능한 실패 항목이 없습니다.', submit)


if __name__ == '__main__':
    unittest.main()
