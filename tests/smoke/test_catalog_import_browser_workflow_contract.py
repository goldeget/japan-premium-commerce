"""Keep import browser QA confined to its disposable synthetic CI project."""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTICS_PATH = ROOT / 'tests/e2e/catalog_import_diagnostics.py'
DIAGNOSTICS_SPEC = importlib.util.spec_from_file_location('catalog_import_diagnostics', DIAGNOSTICS_PATH)
DIAGNOSTICS = importlib.util.module_from_spec(DIAGNOSTICS_SPEC)
DIAGNOSTICS_SPEC.loader.exec_module(DIAGNOSTICS)


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
                       'id: catalog_import_admin_access_readback', 'id: catalog_import_restore',
                       'read_catalog_import_admin_access.php', 'catalog-import-admin-access.log',
                       'tests/e2e/verify_catalog_import_browser.py',
                       'tests.smoke.test_catalog_import_browser_workflow_contract',
                       'tests.smoke.test_catalog_import_admin_contract',
                       "'tests/smoke/test_catalog_import_admin_contract.py'",
                       'catalog-import-e2e.log', 'catalog-import-batch.png', 'catalog-import-rejected.png',
                       'catalog-import-draft.png', 'catalog-import-reimport.png', 'catalog-import-readback.json'):
            self.assertTrue(marker in source, f"Missing integration marker: {marker}")
        for step, variable in (('catalog_import_fixture', 'CATALOG_IMPORT_FIXTURE_OUTCOME'),
                               ('catalog_import_admin_access_readback', 'CATALOG_IMPORT_ADMIN_ACCESS_READBACK_OUTCOME'),
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
        self.assertIn('$productCountAfterImportedRetry === $productCountBeforeImportedRetry', integration)
        self.assertIn("'product_count_unchanged' =>", integration)

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

    def test_browser_batch_waits_and_failure_summary_expose_safe_substage_evidence(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        for marker in (
            'def safe_catalog_import_browser_state',
            'batch_review_navigation',
            'batch_url_field',
            'batch_submit_control',
            'batch_submit_click',
            'batch_completion_wait',
            'batch_progress_readback',
            'same_admin_origin',
            'admin_path_matches',
            'controller_parameter_present',
            'controller_allowed',
            'login_form_visible',
            'product_url_field_visible',
            'submit_control_visible',
            'submit_returned',
            'progress_visible',
            'batch_progress_container_visible',
            'progress_value',
            'progress_max',
            'row_count',
            'token_rejected_notice_visible',
            'mutation_access_denied_notice_visible',
            'empty_url_notice_visible',
            'batch_save_failure_notice_visible',
            'batch_created_notice_visible',
            'unclassified_alert_visible',
            'visible_alert_count',
            'document_response_status',
            'read_only_notice_visible',
            'access_denied_notice_visible',
            'failure_screenshot_captured',
            'save_safe_failure_screenshot',
            'safe_messages',
            'safe_exception_class(error)',
            'catalog-import-failure-diagnostics.json',
        ):
            self.assertIn(marker, browser)
        self.assertNotIn('print(driver.current_url', browser)
        self.assertNotIn('page_source', browser)

        workflow = self.read_required('.github/workflows/fresh-install.yml')
        access_step = workflow.split('id: catalog_import_admin_access_readback', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('if [[ -z "$access_line" && "$readback_status" -eq 0 ]]', access_step)
        self.assertIn('if [[ "$access_line" != *\'"authorization_ready":true\'* ]]', access_step)
        self.assertNotIn('cat "$QA_ARTIFACT_DIR/catalog-import-admin-access.log"', access_step)
        browser_step = workflow.split('id: catalog_import_browser_qa', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('pipeline_status=("${PIPESTATUS[@]}")', browser_step)
        self.assertIn('browser_status="${pipeline_status[0]:-1}"', browser_step)
        self.assertIn('GITHUB_STEP_SUMMARY', browser_step)
        self.assertIn('::error title=ORDENOWA catalog import browser QA::', browser_step)
        self.assertIn('diagnostic_file="$QA_ARTIFACT_DIR/catalog-import-failure-diagnostics.json"', browser_step)
        self.assertIn('tests/e2e/catalog_import_diagnostics.py --json "$diagnostic_file"', browser_step)
        self.assertNotIn("rg '^ORDENOWA_CATALOG_IMPORT_SAFE_DIAGNOSTICS='", browser_step)
        self.assertNotIn('rg ', browser_step)
        self.assertNotIn('cat "$log_file"', browser_step)
        self.assertIn('catalog-import-e2e.log', browser_step)
        self.assertIn('catalog-import-failure-diagnostics.json', workflow)
        self.assertIn('tests/e2e/catalog_import_diagnostics.py --validate', workflow)

        readback_step = workflow.split('id: catalog_import_admin_access_readback', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('access_line=$(python3 -', readback_step)
        self.assertNotIn('rg ', readback_step)
        self.assertIn('\"authorization_ready\":false,\"failure_stage\":\"unknown\",\"exception_class\":\"Exception\"', readback_step)

        self.assertIn("ancestor::form", browser)
        self.assertIn("a, table, img, select, iframe, canvas, svg", browser)
        self.assertIn("field.value = ''", browser)
        self.assertIn("field.removeAttribute('value')", browser)
        self.assertIn("progress_panel.screenshot(str(path))", browser)
        self.assertIn('form.screenshot(str(path))', browser)
        self.assertLess(browser.index('progress_panel.screenshot(str(path))'), browser.index('alert.screenshot(str(path))'))
        self.assertLess(browser.index('alert.screenshot(str(path))'), browser.index('form.screenshot(str(path))'))
        self.assertIn("state.get('stage', 'unknown')", browser)

    def test_failure_diagnostic_validator_rejects_unlisted_or_malformed_data_before_emission(self):
        valid = {
            'stage': 'batch_completion_wait', 'last_completed_stage': 'batch_submit_click',
            'same_admin_origin': True, 'admin_path_matches': True,
            'controller_parameter_present': True, 'controller_allowed': True,
            'admin_controller': 'AdminKuraneaCatalogReview', 'page_class': 'unclassified_alert',
            'document_ready_state': 'complete', 'login_form_visible': False,
            'product_url_field_visible': True, 'submit_control_visible': True,
            'submit_attempted': True, 'submit_returned': True, 'submitted_url_count': 3,
            'batch_progress_container_visible': False, 'progress_visible': False,
            'progress_value': None, 'progress_max': None, 'row_count': 0,
            'token_rejected_notice_visible': False, 'mutation_access_denied_notice_visible': False,
            'empty_url_notice_visible': False, 'batch_save_failure_notice_visible': False,
            'batch_created_notice_visible': False, 'unclassified_alert_visible': True,
            'visible_alert_count': 1, 'document_response_status': 200,
            'read_only_notice_visible': False, 'access_denied_notice_visible': False,
            'queue_unavailable_notice_visible': False, 'exception_class': 'TimeoutException',
            'failure_screenshot_captured': False,
        }
        DIAGNOSTICS.validate(valid)
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'unexpected': 'could contain a secret'})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'stage': 'https://private.invalid/?token=secret'})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'visible_alert_count': True})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'stage': ['not', 'a', 'stage']})

        with tempfile.TemporaryDirectory() as temporary:
            diagnostic = Path(temporary) / 'unsafe.json'
            diagnostic.write_text(json.dumps({**valid, 'unexpected': 'private-value'}), encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(DIAGNOSTICS_PATH), '--json', str(diagnostic)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('private-value', result.stdout + result.stderr)

            diagnostic.write_text(json.dumps({**valid, 'stage': 'batch_completion_wait'}), encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(DIAGNOSTICS_PATH), '--validate', str(diagnostic)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('screenshot was not captured', result.stdout)

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
