"""Keep import browser QA confined to its disposable synthetic CI project."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTICS_PATH = ROOT / 'tests/e2e/catalog_import_diagnostics.py'
DIAGNOSTICS_SPEC = importlib.util.spec_from_file_location('catalog_import_diagnostics', DIAGNOSTICS_PATH)
DIAGNOSTICS = importlib.util.module_from_spec(DIAGNOSTICS_SPEC)
DIAGNOSTICS_SPEC.loader.exec_module(DIAGNOSTICS)


def png_fixture(width, height):
    def chunk(kind, payload):
        return (struct.pack('!I', len(payload)) + kind + payload
                + struct.pack('!I', zlib.crc32(kind + payload) & 0xffffffff))

    rows = b''.join(b'\x00' + b'\x20\x60\xa0' * width for _ in range(height))
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows))
            + chunk(b'IEND', b''))


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
                       'catalog-import-e2e.log', 'catalog-import-batch.png', 'catalog-import-blocked-submit.png',
                       'catalog-import-unsupported-url.png',
                       'catalog-import-rejected.png',
                       'catalog-import-blocked-options.png', 'catalog-import-review-options.png',
                       'catalog-import-draft.png', 'catalog-import-manager-edited.png',
                       'catalog-import-reimport.png', 'catalog-import-readback.json'):
            self.assertTrue(marker in source, f"Missing integration marker: {marker}")
        for step, variable in (('catalog_import_fixture', 'CATALOG_IMPORT_FIXTURE_OUTCOME'),
                               ('catalog_import_admin_access_readback', 'CATALOG_IMPORT_ADMIN_ACCESS_READBACK_OUTCOME'),
                               ('catalog_import_browser_qa', 'CATALOG_IMPORT_BROWSER_QA_OUTCOME'),
                               ('catalog_import_restore', 'CATALOG_IMPORT_RESTORE_OUTCOME')):
            self.assertIn(variable + ': ${{ steps.' + step + '.outcome }}', source)
            self.assertIn('=$' + variable + '"', source)
        self.assertIn('CATALOG_IMPORT_ADMIN_ACCESS_READY: ${{ steps.catalog_import_admin_access_readback.outputs.authorization_ready }}', source)
        self.assertIn('"catalog_import_admin_access_ready=$CATALOG_IMPORT_ADMIN_ACCESS_READY"', source)
        restore = source.split('id: catalog_import_restore', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('if: always()', restore)
        self.assertIn('up -d --no-deps --force-recreate --wait', restore)
        self.assertNotIn('-f tests/fixtures/', restore)
        fixture = source.split('id: catalog_import_fixture', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('kuranea-ci-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}', fixture)
        self.assertIn('catalog_import_fixture_fetcher.php', fixture)
        self.assertIn('amazon-jp-product.synthetic.html', fixture)
        self.assertIn('amazon-jp-review-single-option.synthetic.html', fixture)
        self.assertIn('rakuten-product.synthetic.html', fixture)

    def test_native_persistence_checks_real_flags_and_duplicate_identity(self):
        source = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        browser = source.split('id: catalog_import_browser_qa', 1)[1].split('\n      - name:', 1)[0]
        for marker in ('product_shop', 'available_for_order', '$row["active"] !== 0',
                       '$row["visibility"] !== "none"', '$sameReference !== 1',
                       '$combinationQuantities !== [5, 5]', '$baseQuantity !== 0',
                       '"combination_quantities" => $combinationQuantities',
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
                       'reject_unsupported_product_url', 'https://example.invalid/not-a-supported-product',
                       'catalog-import-unsupported-url.png',
                       'translation_reviewed_en', 'translation_reviewed_ko', 'confirm_options_supported',
                       'synthetic_ci_fixture', 'import_product_images[]', 'combination_quantities[',
                       'remove_image_ids[]', 'catalog-import-readback.json', 'linked_product_id',
                       'unique_product_ids', 'data-catalog-review-status', 'stage=', 'driver.quit()'):
            self.assertTrue(marker in source, f"Missing integration marker: {marker}")
        self.assertNotIn('page_source', source)
        self.assertNotIn('print(error)', source)
        self.assertNotIn('requests.', source)

    def test_unsupported_url_browser_rejection_precedes_any_valid_import_batch(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        flow = browser.split('def reject_unsupported_product_url(', 1)[1].split('def _safe_rect(', 1)[0]
        for marker in (
            'INVALID_URL_NOTICE',
            "'.alert.alert-danger'",
            "assert 'example.invalid' not in notice",
            "By.ID, 'catalog-import-progress'",
            "catalog-import-unsupported-url.png",
        ):
            self.assertIn(marker, flow)
        self.assertIn("page_class = 'invalid_url_rejected'", browser)
        self.assertIn('invalid_url_notice_visible', browser)
        self.assertIn('INVALID_URL_NOTICE,', browser)
        self.assertLess(browser.index('reject_unsupported_product_url(driver, review_url, state)'),
                        browser.index('submit_batch(driver, review_url, [AMAZON, RAKUTEN, BLOCKED], state)'))

    def test_approved_browser_fixture_has_one_supported_option_group(self):
        fixture_path = ROOT / 'tests/catalog/fixtures/amazon-jp-review-single-option.synthetic.html'
        self.assertTrue(fixture_path.is_file(), 'The browser approval fixture must remain local and synthetic.')
        fixture = fixture_path.read_text(encoding='utf-8')
        match = re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', fixture, re.DOTALL)
        self.assertIsNotNone(match, 'The browser fixture must expose structured product data to the parser.')
        payload = json.loads(match.group(1))
        products = payload.get('@graph', [])
        self.assertEqual(len(products), 1)
        properties = products[0].get('additionalProperty', [])
        self.assertEqual(
            [(item['name'], item['value']) for item in properties],
            [('サイズ', 'M'), ('サイズ', 'L')],
            'The approval flow needs one real option group with two distinct synthetic values.',
        )

        fetcher = self.read_required('tests/catalog/catalog_import_fixture_fetcher.php')
        self.assertIn('/tmp/ordenowa-ci-catalog-import-amazon-review.single-option.synthetic.html', fetcher)
        workflow = self.read_required('.github/workflows/fresh-install.yml')
        fixture_step = workflow.split('id: catalog_import_fixture', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('ordenowa-ci-catalog-import-amazon-review.single-option.synthetic.html', fixture_step)
        self.assertIn('tests/catalog/fixtures/amazon-jp-review-single-option.synthetic.html', fixture_step)

        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        self.assertIn("options_field.get_attribute('value') == 'サイズ:M|L'", browser)
        self.assertIn('assert options_confirmation.is_displayed() and options_confirmation.is_enabled()', browser)
        self.assertIn('assert options_confirmation.is_selected()', browser)

    def test_browser_proves_supported_and_blocked_option_review_forms(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        rejection = browser.split("state['stage'] = 'reject_rakuten'", 1)[1].split(
            "state['stage'] = 'approve_amazon'", 1
        )[0]
        for marker in (
            "rejected_options.get_attribute('value') == '色:生成り\\n容量:12L'",
            '옵션 연결을 지원하지 않아 초안 등록이 차단됩니다.',
            "rejected_form.find_elements(By.NAME, 'confirm_options_supported')",
            'assert not options_confirmations',
            "submitKuraneaCatalogImportedDraft",
            "assert guard_state['review_form_visible']",
            "[data-catalog-review-status=\"approved\"]",
            "a[href*=\"id_product=\"]",
        ):
            self.assertIn(marker, rejection + browser)

        save = browser.split('def save_safe_failure_screenshot(', 1)[1].split(
            'def safe_exception_class(', 1
        )[0]
        approval_capture = save.index("if stage in {'approve_amazon', 'reject_rakuten'}")
        form_capture = save.index('capture_safe_approval_context_crop')
        generic_batch_capture = save.index("driver.find_element(By.ID, 'catalog-import-progress')")
        self.assertLess(approval_capture, form_capture)
        self.assertLess(form_capture, generic_batch_capture)

        context_crop = browser.split('def capture_safe_approval_context_crop(', 1)[1].split(
            'def _safe_document_rect(', 1
        )[0]
        for marker in (
            "form.find_elements(By.NAME, 'options')",
            "form.find_elements(By.CSS_SELECTOR, '.alert-warning')",
            "form.find_elements(By.NAME, 'confirm_options_supported')",
            'window.scrollX',
            'window.scrollY',
            'value.left + window.scrollX',
            'value.top + window.scrollY',
            'document.documentElement.scrollHeight',
            'not _safe_document_rect(option_rect, document_width, document_height)',
            "'x': left,",
            "'y': top,",
            "'captureBeyondViewport': True",
            'catalog-import-review-options.png',
            'catalog-import-blocked-options.png',
        ):
            self.assertIn(marker, context_crop + save + browser)

    def test_native_readback_failure_is_classified_and_captures_the_manager_alert(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        for marker in (
            "state['native_product_id'] = product_id",
            "'상품 관리 화면을 불러오지 못했습니다. 쇼핑몰 설정과 권한을 확인해 주세요.'",
            'manager_load_error',
            'manager_inactive_notice_visible',
            'postback_id_matches',
            'route_id_matches',
            "'manager_product_id_parameter_matches'",
            "'manager_editor_visible'",
            "'manager_load_failure_notice_visible'",
            "phase_substages = {",
            "'reimport_navigation', 'reimport_editor_form_check', 'reimport_editor_id_presence', 'reimport_editor_readback'",
            "'manager_edit_fresh_navigation'",
            'def capture_safe_manager_readback_crop(',
            'def validated_product_id_from_manager_link(',
            "query.get('controller') == ['AdminOrdenowaProductManager']",
            'safe_manager_link_diagnostics',
            'manager_link_path_class',
            'manager_link_controller_matches',
            "state['manager_link_diagnostics'] = safe_manager_link_diagnostics(product_link)",
            'state.get(\'native_product_id\')',
            "'catalog-import-failure.png'",
        ):
            self.assertIn(marker, browser)

        validator = self.read_required('tests/e2e/catalog_import_diagnostics.py')
        self.assertIn("data['stage'] == 'native_readback'", validator)
        self.assertIn("data['manager_route_matches']", validator)
        self.assertIn("data['manager_product_id_parameter_matches']", validator)
        self.assertIn("'native_readback_check': native_readback_check", browser)
        self.assertIn("'native_readback_check_match': native_readback_check_match", browser)
        self.assertIn("'native_readback_check', 'native_readback_check_match'", validator)
        self.assertIn('READBACK_CHECKS', validator)
        self.assertIn("'current_substage': {", validator)
        self.assertNotIn('native_product_id', DIAGNOSTICS.DIAGNOSTIC_FIELDS)

        manager_capture = browser.split('def capture_safe_manager_readback_crop(', 1)[1].split(
            'def save_safe_failure_screenshot(', 1
        )[0]
        self.assertIn('notice.screenshot(str(path))', manager_capture)
        self.assertIn("notice.style.width = '640px'", manager_capture)
        self.assertIn("notice.style.minHeight = '180px'", manager_capture)
        self.assertNotIn('Page.captureScreenshot', manager_capture)

    def test_native_readback_checks_hidden_product_id_presence_without_visibility_wait(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        read_native = browser.split('def read_native(', 1)[1].split('\ndef run(', 1)[0]
        self.assertIn("manager_form.find_elements(By.NAME, 'id_product')", read_native)
        self.assertIn("finish_native_readback_check(state, 'product_id', len(id_fields) == 1)", read_native)
        self.assertIn('manager_form.is_displayed()', read_native)
        self.assertIn('manager_product_id_field_matches', read_native)
        self.assertIn("begin_native_readback_check(state, 'manager_form')", read_native)
        self.assertNotIn("visible(driver, '[name=\"id_product\"]')", read_native)
        self.assertNotIn('EC.presence_of_element_located', read_native)

    def test_native_readback_failure_records_only_an_allowlisted_check_and_boolean(self):
        state = {}
        DIAGNOSTICS.begin_native_readback_check(state, 'price_jpy')
        with self.assertRaises(AssertionError):
            DIAGNOSTICS.finish_native_readback_check(state, 'price_jpy', False)
        self.assertEqual(state, {
            'native_readback_check': 'price_jpy',
            'native_readback_check_match': False,
        })
        self.assertNotIn('6780', json.dumps(state))
        with self.assertRaises(ValueError):
            DIAGNOSTICS.begin_native_readback_check(state, 'price_jpy=6780')

    def test_manager_list_diagnostic_separates_query_state_counts_order_and_membership(self):
        summarize = DIAGNOSTICS.summarize_manager_product_ids
        matched = summarize(
            list_state='loaded',
            link_count=3,
            valid_route_count=3,
            rendered_ids=[19, 12, 7],
            expected_ids=[7, 12, 19],
            expected_product_id=19,
        )
        self.assertEqual(matched, {
            'list_state': 'loaded',
            'link_count': 3,
            'valid_id_count': 3,
            'valid_route_count': 3,
            'unique_id_count': 3,
            'expected_unique_id_count': 3,
            'expected_member_count': 3,
            'expected_product_link_count': 1,
            'expected_product_position': 1,
            'ids_unique': True,
            'all_links_safe_routes': True,
            'expected_count_matches': True,
            'expected_members_present': True,
            'expected_product_present': True,
            'expected_id_set_matches': True,
            'rendered_order_is_unique_descending': True,
        })
        missing_member = summarize(
            list_state='empty',
            link_count=0,
            valid_route_count=0,
            rendered_ids=[],
            expected_ids=[7, 12, 19],
            expected_product_id=19,
        )
        self.assertEqual(missing_member['link_count'], 0)
        self.assertEqual(missing_member['unique_id_count'], 0)
        self.assertEqual(missing_member['expected_member_count'], 0)
        self.assertFalse(missing_member['expected_count_matches'])
        self.assertFalse(missing_member['expected_product_present'])
        self.assertFalse(missing_member['expected_id_set_matches'])
        self.assertNotIn('19', json.dumps(missing_member))

        duplicate_member = summarize(
            list_state='loaded',
            link_count=3,
            valid_route_count=3,
            rendered_ids=[19, 12, 12],
            expected_ids=[7, 12, 19],
            expected_product_id=19,
        )
        self.assertEqual(duplicate_member['link_count'], 3)
        self.assertEqual(duplicate_member['valid_id_count'], 3)
        self.assertEqual(duplicate_member['unique_id_count'], 2)
        self.assertFalse(duplicate_member['ids_unique'])
        self.assertFalse(duplicate_member['expected_count_matches'])
        self.assertTrue(duplicate_member['expected_product_present'])
        self.assertFalse(duplicate_member['expected_id_set_matches'])

    def test_manager_list_loader_state_is_exposed_without_swallowing_error_as_empty(self):
        controller = self.read_required(
            'modules/kuraneacatalog/controllers/admin/AdminOrdenowaProductManagerController.php'
        )
        for marker in (
            '$managerProductsLoadState',
            "'load_error'",
            "'empty'",
            "'loaded'",
            'data-ordenowa-managed-products-state=',
            'catch (Throwable)',
        ):
            self.assertIn(marker, controller)
        self.assertIn("$managerProductsLoadState === 'load_error'", controller)
        self.assertNotRegex(
            controller,
            r"catch \(Throwable\) \{\s*\$products = \[\];\s*\}",
            'a failed manager query must not be indistinguishable from an empty result',
        )

    def test_native_manager_readback_emits_allowlisted_link_set_summary(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        read_native = browser.split('def read_native(', 1)[1].split('\ndef manager_save_confirmation(', 1)[0]
        for marker in (
            'expected_manager_ids=None',
            'manager_list_diagnostics',
            'summarize_manager_product_ids(',
            "state.get('manager_products_load_state'",
            'expected_manager_ids=sorted(before_ids + [product_id])',
        ):
            self.assertIn(marker, browser)
        self.assertIn("state['manager_list_diagnostics'] = summarize_manager_product_ids(", read_native)

    def test_catalog_manager_baseline_is_captured_before_unsupported_url_navigation(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        run = browser.split('\ndef run():', 1)[1].split('\nif __name__ ==', 1)[0]
        manager_navigation = run.index('driver.get(manager_url)')
        baseline_capture = run.index('before_ids = manager_ids(driver)')
        unsupported_navigation = run.index('reject_unsupported_product_url(driver, review_url, state)')

        self.assertLess(manager_navigation, baseline_capture)
        self.assertLess(
            baseline_capture,
            unsupported_navigation,
            'the expected manager ID set must be sampled while the native product manager is open',
        )

    def test_native_manager_readback_guards_product_identity_and_edit_preservation(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        read_native = browser.split('def read_native(', 1)[1].split('\ndef manager_save_confirmation(', 1)[0]
        edit_flow = browser.split('def edit_imported_draft(', 1)[1].split('\ndef run(', 1)[0]
        self.assertLess(
            read_native.index("begin_native_readback_check(state, 'unique_product_ids')"),
            read_native.index('link_count, rendered_ids, valid_route_count = manager_product_link_snapshot(driver)'),
        )
        for marker in (
            "begin_native_readback_check(state, 'option_value')",
            "begin_native_readback_check(state, 'category_ids')",
            "begin_native_readback_check(state, 'image_count')",
            "begin_native_readback_check(state, 'quantity')",
            "begin_native_readback_check(state, 'tax_rules_group_id')",
            "begin_native_readback_check(state, 'combination_count')",
            "begin_native_readback_check(state, 'combination_quantities')",
            "begin_native_readback_check(state, 'image_identity')",
            "begin_native_readback_check(state, 'combination_field_names')",
            "begin_native_readback_check(state, 'unique_product_ids')",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, edit_flow)

    def test_rejected_option_guard_readback_retries_stale_dom_without_relaxing_guard(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        rejection = browser.split("state['stage'] = 'reject_rakuten'", 1)[1].split(
            "state['stage'] = 'approve_amazon'", 1
        )[0]
        for marker in (
            "state['current_substage'] = 'reject_guard_readback'",
            "state['current_substage'] = 'reject_status_readback'",
            'rejected_option_guard_state',
            "document.querySelectorAll('#content .alert-danger')",
            "form.catalog-review-reject",
            "section[data-catalog-review-status=\"rejected\"]",
            'REJECTED_RAKUTEN_SNAPSHOT_NAME',
            'except StaleElementReferenceException',
            'option_guard_notice_visible',
            'assert guard_state[\'review_form_visible\']',
            'assert not guard_state[\'approved_status_visible\']',
            'assert not guard_state[\'product_manager_link_visible\']',
        ):
            self.assertIn(marker, rejection + browser)

        diagnostics = self.read_required('tests/e2e/catalog_import_diagnostics.py')
        self.assertIn("'option_guard_notice_visible'", diagnostics)
        self.assertIn("'reject_guard_readback'", diagnostics)
        self.assertIn("'reject_status_readback'", diagnostics)
        self.assertIn("'unsupported_options_guard'", diagnostics)
        controller = self.read_required(
            'modules/kuraneacatalog/controllers/admin/AdminKuraneaCatalogReviewController.php'
        )
        self.assertIn('$this->content .= $this->renderFeedback();', controller)
        self.assertIn("class=\"catalog-review-reject\"", controller)
        self.assertIn("$html .= $this->renderReviewedStatus();", controller)
        self.assertIn("data-catalog-review-status=\"' . $this->escape($entry->status) . '\"", controller)
        self.assertIn('def capture_safe_option_guard_notice(', browser)
        self.assertIn("'catalog-import-blocked-submit.png'", browser)
        self.assertIn('catalog-import-blocked-submit.png', self.read_required('.github/workflows/fresh-install.yml'))
        self.assertIn(
            '"name": "[TEST FIXTURE] 合成収納ケース B"',
            self.read_required('tests/catalog/fixtures/rakuten-product.synthetic.html'),
        )
        guard_capture = browser.split('def capture_safe_option_guard_notice(', 1)[1].split(
            'def capture_safe_approval_context_crop(', 1
        )[0]
        for marker in (
            "state.get('review_source') != RAKUTEN",
            "query.get('controller') != ['AdminKuraneaCatalogReview']",
            'notice.text.strip() == REJECTED_OPTION_GUARD_MESSAGE',
            "notice.style.width = '640px'",
            "notice.style.minHeight = '180px'",
            'notice.screenshot(str(path))',
            "notice.style.overflowWrap = 'anywhere'",
            'setAttribute(\'style\', arguments[1])',
        ):
            self.assertIn(marker, guard_capture)
        save = browser.split('def save_safe_failure_screenshot(', 1)[1].split(
            'def safe_exception_class(', 1
        )[0]
        self.assertIn("click.get('target') == 'native_draft_submit'", save)
        self.assertIn('click.get(\'returned\') is True', save)
        self.assertIn('pre-submit screenshot would not be', save)

    def test_approved_product_link_accepts_only_native_admin_entrypoint_routes(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        tree = ast.parse(browser)
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                'manager_admin_path_class', 'safe_manager_link_diagnostics',
                'validated_product_id_from_manager_link',
            }
        ]
        namespace = {
            'urlparse': urlparse,
            'parse_qs': parse_qs,
            'ADMIN_LOGIN': 'https://shop.example.test/admin',
            'ADMIN_PATH': '/admin',
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<route-helper-test>', 'exec'), namespace)
        validated = namespace['validated_product_id_from_manager_link']
        path_class = namespace['manager_admin_path_class']
        diagnostics = namespace['safe_manager_link_diagnostics']
        self.assertEqual(path_class('/admin'), 'admin_directory')
        self.assertEqual(path_class('/admin/'), 'admin_directory_slash')
        self.assertEqual(path_class('/admin/index.php'), 'admin_index_php')
        self.assertEqual(path_class('/admin/index.php/other'), 'other')
        for path in ('/admin', '/admin/', '/admin/index.php'):
            with self.subTest(path=path):
                href = (
                    f'https://shop.example.test{path}?controller=AdminOrdenowaProductManager'
                    '&id_product=42&token=synthetic-session-token'
                )
                self.assertEqual(
                    validated(href),
                    42,
                )
                self.assertTrue(diagnostics(href)['manager_link_path_matches'])
        for invalid in (
            'https://outside.example/admin/index.php?controller=AdminOrdenowaProductManager&id_product=42',
            'https://shop.example.test/admin/index.php?controller=AdminKuraneaCatalogReview&id_product=42',
            'https://shop.example.test/admin/other?controller=AdminOrdenowaProductManager&id_product=42',
            'https://shop.example.test/admin/index.php/other?controller=AdminOrdenowaProductManager&id_product=42',
            'https://shop.example.test/admin/index.php;other?controller=AdminOrdenowaProductManager&id_product=42',
            'https://shop.example.test/admin2/index.php?controller=AdminOrdenowaProductManager&id_product=42',
            'https://shop.example.test/admin/index.php?controller=AdminOrdenowaProductManager&id_product=42&id_product=43',
            'https://shop.example.test/admin/index.php?controller=AdminOrdenowaProductManager&id_product=0',
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(AssertionError):
                    validated(invalid)
        invalid_path_diagnostics = diagnostics(
            'https://shop.example.test/admin/index.php/other?'
            'controller=AdminOrdenowaProductManager&id_product=42'
        )
        self.assertEqual(invalid_path_diagnostics['manager_link_path_class'], 'other')
        self.assertFalse(invalid_path_diagnostics['manager_link_path_matches'])
        self.assertEqual(
            diagnostics(
                'https://shop.example.test/admin/index.php;other?'
                'controller=AdminOrdenowaProductManager&id_product=42'
            )['manager_link_path_class'],
            'other',
        )

    def test_browser_requires_one_loaded_native_product_image(self):
        source = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        self.assertIn('len(image_results) == 1', source)
        self.assertIn('naturalWidth', source)

    def test_browser_selects_and_reads_back_the_imported_category(self):
        source = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        self.assertIn('expected_category_ids', source)
        self.assertIn("form.find_elements(By.CSS_SELECTOR, 'input[name=\"category_ids[]\"]')", source)
        self.assertIn("driver.find_elements(By.CSS_SELECTOR, 'input[name=\"category_ids[]\"]')", source)
        self.assertIn("finish_native_readback_check(state, 'category_ids', category_ids == expected_category_ids)", source)
        self.assertIn('read_native(\n            driver, product_id, expected_category_ids, state,', source)
        self.assertIn('expected_manager_ids=sorted(before_ids + [product_id])', source)

    def test_browser_saves_same_imported_draft_then_proves_edit_survives_reimport(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        self.assertIn('def edit_imported_draft(', browser)
        edit = browser.split('def edit_imported_draft(', 1)[1].split('\ndef run(', 1)[0]
        for marker in (
            "'name_ko': 'ORDENOWA 합성 주방 도구 수정'",
            "'description_ko': '관리자에서 저장한 합성 설명입니다.'",
            "'price_jpy': '6780'",
            "expected_combination_quantities = ['5', '5']",
            "[name=\"submitKuraneaProductSave\"]",
            'manager_save_confirmation(browser, expected_notice)',
            'validated_product_id_from_manager_link',
            'driver.get(manager_link)',
            "'manager_edit_save_confirmation'",
            "'manager_edit_fresh_readback'",
            "'catalog-import-manager-edited.png'",
            "'M|L' in initial_readback['option_values']",
            "remove_image_ids[]",
        ):
            self.assertIn(marker, edit)
        self.assertEqual(edit.count(".click()"), 1, 'The manager form must use a real Selenium save click.')
        self.assertNotIn('execute_script', edit)

        run = browser.split('def run():', 1)[1]
        initial_read = run.index('readback = read_native(')
        manager_edit = run.index('readback = edit_imported_draft(')
        reimport = run.index("submit_batch(driver, review_url, [AMAZON], state, prefix='reimport')")
        final_read = run.index('after = read_native(')
        self.assertLess(initial_read, manager_edit)
        self.assertLess(manager_edit, reimport)
        self.assertLess(reimport, final_read)
        self.assertIn("readback['reimport_preserved_manager_edits'] = True", run)
        self.assertIn("'inactive_notice_visible': readback['manager_page']['inactive_notice_visible']", run)
        self.assertIn("$row[\"active\"] !== 0", self.read_required('.github/workflows/fresh-install.yml'))
        self.assertIn("$row[\"available_for_order\"] !== 0", self.read_required('.github/workflows/fresh-install.yml'))

        diagnostics = self.read_required('tests/e2e/catalog_import_diagnostics.py')
        for substage in ('manager_edit_fields', 'manager_edit_save_click',
                         'manager_edit_save_confirmation', 'manager_edit_fresh_navigation',
                         'manager_edit_fresh_readback'):
            self.assertIn(substage, diagnostics)

    def test_imported_product_publication_uses_native_ui_and_same_id_storefront_readback(self):
        browser = self.read_required("tests/e2e/verify_catalog_import_browser.py")
        publication = browser.split("def verify_imported_product_publication(", 1)[1].split(
            "\ndef manager_save_confirmation", 1
        )[0]
        native_editor = browser.split("def native_product_editor_url(", 1)[1].split(
            "\ndef manager_save_confirmation", 1
        )[0]
        for marker in (
            "NATIVE_PRODUCT_DRAFT_FLAGS",
            "NATIVE_PRODUCT_PUBLISHED_FLAGS",
            "read_native_product_publication_flags",
            "controller",
            "id_product",
            "h1.product__name",
            ".product__price",
            'button[data-button-action="add-to-cart"]',
            "fresh_buttons[0].click()",
            "storefront_cart_readback",
            "same_id_cart_readback",
            "finally:",
            "native_unpublish_cleanup",
            "NATIVE_PRODUCT_DRAFT_FLAGS",
        ):
            self.assertIn(marker, publication)
        for marker in (
            "sell/catalog/products/{product_id}/edit",
            "form.product-form[data-product-id]",
            "data-shop-id",
            "Select(field).select_by_value(value)",
            "button.product-form-save-button",
        ):
            self.assertIn(marker, native_editor)
        self.assertNotIn("execute_script", publication)
        self.assertNotIn("send_keys", publication)
        self.assertIn("readback['publication'] = verify_imported_product_publication(driver, product_id, state)", browser)
        run_body = browser.split("def run():", 1)[1]
        approval = run_body.index("""approved = visible(driver, '[data-catalog-review-status="approved"]')""")
        same_id_readback = run_body.index("after = read_native(")
        publication_call = run_body.index(
            "readback['publication'] = verify_imported_product_publication(driver, product_id, state)"
        )
        self.assertLess(approval, same_id_readback)
        self.assertLess(same_id_readback, publication_call)
        self.assertIn("native_publication", browser)
        self.assertIn("sell/catalog/products/{product_id}/edit", browser)
        for marker in (
            'select[name$="[header][active]"]',
            'select[name$="[options][visibility][visibility]"]',
            'select[name$="[options][visibility][available_for_order]"]',
            'select[name$="[options][visibility][show_price]"]',
        ):
            self.assertIn(marker, browser)

        diagnostics = self.read_required("tests/e2e/catalog_import_diagnostics.py")
        self.assertIn("'native_publication'", diagnostics)
        self.assertIn("'native_publish_fresh_field_readback'", diagnostics)
        self.assertIn("'native_publish_fresh_readback'", diagnostics)
        self.assertIn("'storefront_cart_readback'", diagnostics)
        self.assertIn("'native_unpublish_cleanup'", diagnostics)

        workflow = self.read_required(".github/workflows/fresh-install.yml")
        self.assertIn("catalog-import-published-product.png", workflow)
        self.assertIn("catalog-import-published-cart.png", workflow)
        self.assertIn("catalog-import-persistence.json", workflow)

    def test_manager_save_confirmation_reads_visible_success_alert_from_one_dom_snapshot(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        helper_start = browser.find('def manager_save_confirmation(')
        self.assertGreaterEqual(helper_start, 0, 'save confirmation must use the atomic DOM snapshot helper')
        confirmation = browser[helper_start:].split('\ndef edit_imported_draft(', 1)[0]
        self.assertIn('browser.execute_script(', confirmation)
        self.assertIn("document.querySelectorAll('#content .alert-success')", confirmation)
        self.assertIn('const expectedNotice = arguments[0]', confirmation)
        self.assertIn("(element.innerText || element.textContent || '').trim()", confirmation)
        self.assertIn('notice === expectedNotice', confirmation)
        self.assertIn('return isVisible(element) && notice === expectedNotice', confirmation)
        self.assertNotIn('find_elements(', confirmation)
        self.assertNotIn('.is_displayed()', confirmation)
        self.assertIn('manager_save_confirmation(browser, expected_notice)', browser)

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
            'begin_native_readback_check',
            'finish_native_readback_check',
            'native_readback_check_match',
            'category_ids',
            'combination_quantities',
            'image_load',
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
            'invalid_url_notice_visible',
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

        diagnostic_validator = self.read_required('tests/e2e/catalog_import_diagnostics.py')
        self.assertIn("data['stage'] in {'approve_amazon', 'reject_rakuten'}", diagnostic_validator)
        self.assertIn('320 <= screenshot_width <= 640', diagnostic_validator)
        self.assertIn('180 <= screenshot_height <= 480', diagnostic_validator)

        workflow = self.read_required('.github/workflows/fresh-install.yml')
        access_step = workflow.split('id: catalog_import_admin_access_readback', 1)[1].split('\n      - name:', 1)[0]
        self.assertIn('if [[ -z "$access_line" ]]; then', access_step)
        self.assertIn('if [[ "$access_line" != *\'"authorization_ready":true\'* ]]', access_step)
        self.assertIn('raw_log="$RUNNER_TEMP/ordenowa-catalog-admin-access-', access_step)
        self.assertIn('sanitized_log="$QA_ARTIFACT_DIR/catalog-import-admin-access.log"', access_step)
        self.assertIn("GITHUB_OUTPUT", access_step)
        self.assertNotIn('cat "$raw_log"', access_step)
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
        self.assertIn('\"authorization_ready\":false,\"failure_stage\":\"probe_execution\",\"exception_class\":\"ProcessFailure\"', readback_step)
        self.assertIn('\"failure_stage\":\"result_encoding\",\"exception_class\":\"ResultMissing\"', readback_step)

        self.assertIn("ancestor::form", browser)
        self.assertIn("a, table, img, select, iframe, canvas, svg", browser)
        self.assertIn("field.value = ''", browser)
        self.assertIn("field.removeAttribute('value')", browser)
        self.assertIn("progress_panel.screenshot(str(path))", browser)
        self.assertIn('form.screenshot(str(path))', browser)
        self.assertLess(browser.index('progress_panel.screenshot(str(path))'), browser.index('alert.screenshot(str(path))'))
        self.assertLess(browser.index('alert.screenshot(str(path))'), browser.index('form.screenshot(str(path))'))
        self.assertIn("state.get('stage', 'unknown')", browser)

    def test_batch_completion_wait_requires_visible_progress_and_container_together(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        submit = browser.split('def submit_batch(', 1)[1].split('\ndef reject_unsupported_product_url(', 1)[0]
        self.assertIn('def visible_completed_progress(current_driver):', submit)
        self.assertIn("current_driver.find_elements(By.CSS_SELECTOR, '#catalog-import-progress')", submit)
        self.assertIn('if not container.is_displayed():', submit)
        self.assertIn("f'progress[value=\"{len(urls)}\"]'", submit)
        self.assertIn('if any(progress.is_displayed() for progress in progress_bars):', submit)
        self.assertIn('container.text', submit)
        self.assertIn('driver, 60, ignored_exceptions=(StaleElementReferenceException,)', submit)
        self.assertIn('.until(visible_completed_progress)', submit)
        self.assertNotIn("WebDriverWait(driver, 60).until(lambda d: d.find_elements(", submit)

    def test_approval_clicks_capture_allowlisted_native_target_and_safe_obstruction_crop(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        click_helper = browser.split('def click_with_safe_diagnostics(', 1)[1].split(
            'def capture_safe_click_crop(', 1
        )[0]
        self.assertEqual(click_helper.count('element.click()'), 1)
        self.assertNotIn('arguments[0].click()', click_helper)
        self.assertNotIn('form.submit()', click_helper)
        approval = browser.split("state['stage'] = 'approve_amazon'", 1)[1].split(
            "state['last_completed_stage'] = state['stage']", 1
        )[0]
        for marker in (
            'click_with_safe_diagnostics',
            'approve_category_checkbox',
            'approve_translation_review_en',
            'approve_translation_review_ko',
            'approve_options_confirmation',
            'approve_image_rights_confirmation',
            'approve_submit',
        ):
            self.assertIn(marker, approval)
        self.assertNotIn('.click()', approval, 'approval interactions must go through the native-click evidence wrapper')
        self.assertIn('elementFromPoint', browser)
        self.assertIn('center_hit_relation', browser)
        self.assertIn('target_rect', browser)
        self.assertIn('occluder_category', browser)
        self.assertIn('target_fields = {', browser)
        self.assertIn('forms[0].find_elements(By.NAME, target_field_name)', browser)
        self.assertIn('last_completed_substage', browser)
        self.assertIn('capture_safe_click_crop', browser)
        self.assertIn('Page.captureScreenshot', browser)
        self.assertIn('상품 수집 항목을 반려했습니다. 사유와 담당자 기록을 보존했습니다.', browser)
        self.assertIn('기존 TEST/DEMO 등록 경로는 별도 서버 게이트로 비활성화되어 있습니다.', browser)

    def test_approval_actions_follow_the_review_form_document_order(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        approval = browser.split("state['stage'] = 'approve_amazon'", 1)[1].split(
            "state['last_completed_stage'] = state['stage']", 1
        )[0]
        translation_confirmation = approval.index("'translation_reviewed_en':")
        tax_selection = approval.index("Select(form.find_element(By.NAME, 'tax_rules_group_id'))")
        quantity_input = approval.index('own_quantity')
        category_confirmation = approval.index('approve_category_checkbox')
        self.assertLess(
            translation_confirmation,
            tax_selection,
            'The EN/KO translation confirmations are above tax controls and must be clicked before those controls scroll the form down.',
        )
        self.assertLess(
            quantity_input,
            category_confirmation,
            'The category is below the own-quantity field and should be reached in document order.',
        )

    def test_obstruction_crop_translates_viewport_rectangles_to_document_coordinates(self):
        browser = self.read_required('tests/e2e/verify_catalog_import_browser.py')
        crop = browser.split('def capture_safe_click_crop(', 1)[1].split(
            'def safe_catalog_import_browser_state(', 1
        )[0]
        for marker in (
            'window.scrollX',
            'window.scrollY',
            "'x': left + scroll_x",
            "'y': top + scroll_y",
            "'captureBeyondViewport': True",
            "struct.unpack('!II', image[16:24])",
            'image_width < 320 or image_height < 180',
        ):
            self.assertIn(marker, crop)

    def test_click_diagnostic_schema_rejects_unbounded_or_sensitive_target_data(self):
        valid_click = {
            'substage': 'approve_submit', 'target': 'native_draft_submit', 'action': 'native_click',
            'attempted': True, 'returned': False, 'visible': True, 'enabled': True,
            'target_rect': [420, 670, 140, 36], 'occluder_rect': None,
            'center_in_viewport': True, 'center_hit_relation': 'alert', 'occluder_category': 'alert',
        }
        valid = {
            'stage': 'approve_amazon', 'last_completed_stage': 'reject_rakuten',
            'last_completed_substage': 'reject_status_readback', 'click_diagnostics': valid_click,
            'current_substage': 'not_started',
            'native_readback_check': 'not_started', 'native_readback_check_match': None,
            'same_admin_origin': True, 'admin_path_matches': True,
            'controller_parameter_present': True, 'controller_allowed': True,
            'admin_controller': 'AdminKuraneaCatalogReview', 'page_class': 'catalog_import_form',
            'document_ready_state': 'complete', 'login_form_visible': False,
            'product_url_field_visible': True, 'submit_control_visible': True,
            'submit_attempted': True, 'submit_returned': True, 'submitted_url_count': 3,
            'batch_progress_container_visible': False, 'progress_visible': False,
            'progress_value': None, 'progress_max': None, 'row_count': 0,
            'token_rejected_notice_visible': False, 'mutation_access_denied_notice_visible': False,
            'invalid_url_notice_visible': False,
            'empty_url_notice_visible': False, 'batch_save_failure_notice_visible': False,
            'batch_created_notice_visible': False, 'option_guard_notice_visible': False,
            'unclassified_alert_visible': False,
            'visible_alert_count': 3, 'document_response_status': 200,
            'read_only_notice_visible': False, 'access_denied_notice_visible': False,
            'queue_unavailable_notice_visible': False, 'exception_class': 'ElementClickInterceptedException',
            'manager_route_matches': False, 'manager_product_id_parameter_present': False,
            'manager_product_id_parameter_matches': False, 'manager_id_field_present': False,
            'manager_link_same_origin': False, 'manager_link_path_class': 'unknown',
            'manager_link_path_matches': False, 'manager_link_controller_parameter_present': False,
            'manager_link_controller_matches': False, 'manager_link_product_id_parameter_present': False,
            'manager_link_product_id_valid': False,
            'manager_id_field_hidden': False, 'manager_product_id_field_matches': False,
            'manager_editor_visible': False, 'manager_load_failure_notice_visible': False,
            'manager_permission_denied_notice_visible': False, 'manager_inactive_notice_visible': False,
            'manager_save_success_notice_visible': False,
            'manager_products_load_state': 'unknown',
            'manager_list_diagnostics': None,
            'option_guard_notice_visible': False,
            'failure_screenshot_captured': True,
        }
        DIAGNOSTICS.validate(valid)
        invalid_url_rejected = {
            **valid,
            'page_class': 'invalid_url_rejected',
            'invalid_url_notice_visible': True,
            'unclassified_alert_visible': False,
        }
        DIAGNOSTICS.validate(invalid_url_rejected)
        for substage in (
            'manager_edit_fields', 'manager_edit_save_click', 'manager_edit_save_confirmation',
            'manager_edit_fresh_navigation', 'manager_edit_fresh_readback',
        ):
            DIAGNOSTICS.validate({
                **valid,
                'stage': 'native_readback',
                'last_completed_stage': 'native_readback',
                'last_completed_substage': 'manager_edit_save_confirmation',
                'current_substage': substage,
                'click_diagnostics': None,
            })
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'current_substage': 'https://private.invalid/?token=secret'})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'click_diagnostics': {**valid_click, 'target': 'private-css-selector'}})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'click_diagnostics': {**valid_click, 'target_rect': [0, 0, 1, 'secret']}})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'click_diagnostics': {**valid_click, 'occluder_category': 'secret-class'}})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'click_diagnostics': {**valid_click, 'html': '<button>secret</button>'}})

        with tempfile.TemporaryDirectory() as temporary_directory:
            diagnostic_path = Path(temporary_directory) / 'diagnostic.json'
            screenshot_path = Path(temporary_directory) / 'failure.png'
            screenshot_path.write_bytes(png_fixture(1151, 54))
            diagnostic_path.write_text(json.dumps(valid), encoding='utf-8')
            undersized_crop = subprocess.run(
                [sys.executable, str(DIAGNOSTICS_PATH), '--validate',
                 str(diagnostic_path), str(screenshot_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(undersized_crop.returncode, 2)
            self.assertIn('safe bounds', undersized_crop.stdout)

            screenshot_path.write_bytes(png_fixture(640, 320)[:24])
            truncated_png = subprocess.run(
                [sys.executable, str(DIAGNOSTICS_PATH), '--validate',
                 str(diagnostic_path), str(screenshot_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(truncated_png.returncode, 2)
            self.assertTrue(
                'malformed PNG chunk' in truncated_png.stdout or 'incomplete' in truncated_png.stdout,
                truncated_png.stdout,
            )

            screenshot_path.write_bytes(png_fixture(640, 320))
            for broken_click in (None, {**valid_click, 'returned': True}):
                with self.subTest(broken_click=broken_click):
                    diagnostic_path.write_text(json.dumps({
                        **valid,
                        'click_diagnostics': broken_click,
                        'failure_screenshot_captured': False,
                    }), encoding='utf-8')
                    completed = subprocess.run(
                        [sys.executable, str(DIAGNOSTICS_PATH), '--validate',
                         str(diagnostic_path), str(screenshot_path)],
                        check=False, capture_output=True, text=True,
                    )
                    self.assertEqual(completed.returncode, 2)

            diagnostic_path.write_text(json.dumps(valid), encoding='utf-8')
            completed = subprocess.run(
                [sys.executable, str(DIAGNOSTICS_PATH), '--validate',
                 str(diagnostic_path), str(screenshot_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

            manager_readback = {
                **valid,
                'stage': 'native_readback',
                'last_completed_stage': 'approve_amazon',
                'current_substage': 'native_editor_id_presence',
                'click_diagnostics': None,
                'same_admin_origin': True,
                'admin_path_matches': True,
                'controller_parameter_present': True,
                'controller_allowed': True,
                'admin_controller': 'AdminOrdenowaProductManager',
                'page_class': 'manager_load_error',
                'product_url_field_visible': False,
                'submit_control_visible': False,
                'manager_route_matches': True,
                'manager_product_id_parameter_present': True,
                'manager_product_id_parameter_matches': True,
                'manager_id_field_present': False,
                'manager_link_same_origin': False,
                'manager_link_path_class': 'unknown',
                'manager_link_path_matches': False,
                'manager_link_controller_parameter_present': False,
                'manager_link_controller_matches': False,
                'manager_link_product_id_parameter_present': False,
                'manager_link_product_id_valid': False,
                'manager_id_field_hidden': False,
                'manager_product_id_field_matches': False,
                'manager_editor_visible': False,
                'manager_load_failure_notice_visible': True,
                'manager_permission_denied_notice_visible': False,
                'manager_inactive_notice_visible': False,
                'manager_save_success_notice_visible': False,
                'option_guard_notice_visible': False,
                'exception_class': 'TimeoutException',
                'failure_screenshot_captured': True,
            }
            screenshot_path.write_bytes(png_fixture(640, 320))
            diagnostic_path.write_text(json.dumps(manager_readback), encoding='utf-8')
            manager_valid = subprocess.run(
                [sys.executable, str(DIAGNOSTICS_PATH), '--validate',
                 str(diagnostic_path), str(screenshot_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(manager_valid.returncode, 0, manager_valid.stdout + manager_valid.stderr)

            manager_postback = {
                **manager_readback,
                'manager_product_id_parameter_present': False,
                'manager_product_id_parameter_matches': False,
                'manager_id_field_present': True,
                'manager_id_field_hidden': True,
                'manager_product_id_field_matches': True,
                'manager_editor_visible': True,
                'manager_load_failure_notice_visible': False,
                'manager_permission_denied_notice_visible': False,
                'failure_screenshot_captured': True,
            }
            diagnostic_path.write_text(json.dumps(manager_postback), encoding='utf-8')
            postback_valid = subprocess.run(
                [sys.executable, str(DIAGNOSTICS_PATH), '--validate',
                 str(diagnostic_path), str(screenshot_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(postback_valid.returncode, 0, postback_valid.stdout + postback_valid.stderr)

            mismatched_manager_query = {
                **manager_postback,
                'manager_product_id_parameter_present': True,
                'manager_product_id_parameter_matches': False,
            }
            diagnostic_path.write_text(json.dumps(mismatched_manager_query), encoding='utf-8')
            mismatched_manager_query_result = subprocess.run(
                [sys.executable, str(DIAGNOSTICS_PATH), '--validate',
                 str(diagnostic_path), str(screenshot_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(mismatched_manager_query_result.returncode, 2)

    def test_failure_diagnostic_validator_rejects_unlisted_or_malformed_data_before_emission(self):
        valid = {
            'stage': 'batch_completion_wait', 'last_completed_stage': 'batch_submit_click',
            'last_completed_substage': 'not_started', 'click_diagnostics': None,
            'current_substage': 'not_started',
            'native_readback_check': 'not_started', 'native_readback_check_match': None,
            'same_admin_origin': True, 'admin_path_matches': True,
            'controller_parameter_present': True, 'controller_allowed': True,
            'admin_controller': 'AdminKuraneaCatalogReview', 'page_class': 'unclassified_alert',
            'document_ready_state': 'complete', 'login_form_visible': False,
            'product_url_field_visible': True, 'submit_control_visible': True,
            'submit_attempted': True, 'submit_returned': True, 'submitted_url_count': 3,
            'batch_progress_container_visible': False, 'progress_visible': False,
            'progress_value': None, 'progress_max': None, 'row_count': 0,
            'token_rejected_notice_visible': False, 'mutation_access_denied_notice_visible': False,
            'invalid_url_notice_visible': False,
            'empty_url_notice_visible': False, 'batch_save_failure_notice_visible': False,
            'batch_created_notice_visible': False, 'option_guard_notice_visible': False,
            'unclassified_alert_visible': True,
            'visible_alert_count': 1, 'document_response_status': 200,
            'read_only_notice_visible': False, 'access_denied_notice_visible': False,
            'queue_unavailable_notice_visible': False, 'exception_class': 'TimeoutException',
            'manager_route_matches': False, 'manager_product_id_parameter_present': False,
            'manager_product_id_parameter_matches': False, 'manager_id_field_present': False,
            'manager_link_same_origin': False, 'manager_link_path_class': 'unknown',
            'manager_link_path_matches': False, 'manager_link_controller_parameter_present': False,
            'manager_link_controller_matches': False, 'manager_link_product_id_parameter_present': False,
            'manager_link_product_id_valid': False,
            'manager_id_field_hidden': False, 'manager_product_id_field_matches': False,
            'manager_editor_visible': False, 'manager_load_failure_notice_visible': False,
            'manager_permission_denied_notice_visible': False, 'manager_inactive_notice_visible': False,
            'manager_save_success_notice_visible': False,
            'manager_products_load_state': 'unknown',
            'manager_list_diagnostics': None,
            'option_guard_notice_visible': False,
            'failure_screenshot_captured': False,
        }
        DIAGNOSTICS.validate(valid)
        DIAGNOSTICS.validate({
            **valid,
            'native_readback_check': 'price_jpy',
            'native_readback_check_match': False,
        })
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'native_readback_check': 'price_jpy=6780'})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'native_readback_check_match': '6780'})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'unexpected': 'could contain a secret'})
        with self.assertRaises(ValueError):
            DIAGNOSTICS.validate({**valid, 'native_product_id': 42})
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
