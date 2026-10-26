"""Contracts for disposable synthetic Web Push QA; no provider credentials."""
from pathlib import Path
import inspect
import unittest

from tests.e2e import verify_pwa_browser as browser

ROOT = Path(__file__).resolve().parents[2]


class PushWorkflowContractTests(unittest.TestCase):
    def test_module_is_bundled_synced_and_installed(self):
        self.assertIn('COPY modules/kuraneapush/', (ROOT / 'docker/Dockerfile').read_text())
        self.assertIn('sync_module kuraneapush', (ROOT / 'docker/kuranea-entrypoint.sh').read_text())
        bootstrap = (ROOT / 'docker/kuran-install-modules.php').read_text()
        module = (ROOT / 'modules/kuraneapush/kuraneapush.php').read_text()
        self.assertIn("'kuraneapush'", bootstrap)
        self.assertIn("$pushModule->ensureOrderHistoryPushHook()", bootstrap)
        self.assertIn('public function ensureOrderHistoryPushHook(): bool', module)

    def test_ci_copies_all_php_suite_entrypoints(self):
        workflow = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        step = workflow.split('id: pwa_push_qa', 1)[1].split('      - name:', 1)[0]
        for filename in ('run.php', 'repository.php'):
            self.assertIn('cat > /tmp/ordenowa-push-contracts/tests/pwa/php/' + filename, step)
            self.assertIn('< tests/pwa/php/' + filename, step)
        for filename in ('delivery_outbox.php', 'outbox_repository.php', 'order_history_producer.php'):
            self.assertIn('cat > /tmp/ordenowa-push-contracts/tests/pwa/php/' + filename, step)
            self.assertIn('< tests/pwa/php/' + filename, step)
        self.assertIn("require __DIR__ . '/delivery_outbox.php';", (ROOT / 'tests/pwa/php/run.php').read_text())
        self.assertIn("require __DIR__ . '/order_history_producer.php';", (ROOT / 'tests/pwa/php/run.php').read_text())

    def test_ci_executes_isolated_mariadb_outbox_fixture(self):
        workflow = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        step = workflow.split('id: pwa_push_qa', 1)[1].split('      - name:', 1)[0]
        self.assertIn('cat > /tmp/ordenowa-push-contracts/tests/pwa/php/outbox_database.php', step)
        self.assertIn('< tests/pwa/php/outbox_database.php', step)
        self.assertIn('php /tmp/ordenowa-push-contracts/tests/pwa/php/outbox_database.php', step)
        fixture = (ROOT / 'tests/pwa/php/outbox_database.php').read_text()
        self.assertIn('if(PHP_SAPI!==\'cli\'||!Readiness::isolated())', fixture)
        self.assertIn('finally {', fixture)

    def test_local_compose_has_no_storage_key_and_disables_test_mode(self):
        compose = (ROOT / 'compose.yaml').read_text()
        self.assertIn('ORDENOWA_PUSH_TEST_MODE: "0"', compose)
        self.assertNotIn('ORDENOWA_PUSH_STORAGE_KEY', compose)
        self.assertIn('KURANEA_ISOLATED_CI: "0"', compose)

    def test_ci_outcome_is_required_by_actual_aggregate(self):
        workflow = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        for path in ('modules/kuraneapush/**', 'tests/pwa/**', 'tests/smoke/test_kuraneapush_workflow_contract.py'):
            self.assertEqual(2, workflow.count("- '" + path + "'"))
        self.assertIn('tests.smoke.test_kuraneapush_workflow_contract', workflow)
        self.assertIn('id: pwa_push_qa', workflow)
        aggregate = workflow.split('- name: Aggregate browser QA and postal verification failures', 1)[1]
        self.assertIn('PWA_PUSH_QA_OUTCOME: ${{ steps.pwa_push_qa.outcome }}', aggregate)
        self.assertIn('"pwa_push_qa=$PWA_PUSH_QA_OUTCOME"', aggregate)

    def test_synthetic_push_persistence_is_not_skipped_by_browser_pwa_failure(self):
        workflow = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        step = workflow.split('id: pwa_push_qa', 1)[1].split('      - name:', 1)[0]
        self.assertIn("steps.compose_up.outcome == 'success'", step)
        self.assertNotIn("steps.pwa_browser_qa.outcome == 'success'", step)

    def test_browser_never_subscribes_to_provider_and_checks_two_owners(self):
        source = inspect.getsource(browser)
        self.assertNotIn('.pushManager.subscribe(', source)
        self.assertIn('def verify_push_account_control(', source)
        self.assertIn('def verify_synthetic_push_persistence(', source)
        self.assertIn('notice_version: root.dataset.pushNoticeVersion', source)
        self.assertIn('cross_customer', source)
        self.assertIn('requestPermission', source)

    def test_synthetic_compose_and_seed_require_exact_isolation(self):
        path = ROOT / 'tests/pwa/fixtures/ci-push.compose.yaml'
        self.assertTrue(path.is_file(), 'missing isolated push override')
        override = path.read_text()
        for name in ('ORDENOWA_PUSH_STORAGE_KEY', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'CI_COMPOSE_PROJECT_NAME'):
            self.assertIn('${' + name + ':?', override)
        self.assertIn('ORDENOWA_PUSH_TEST_MODE: "1"', override)
        self.assertIn('KURANEA_ISOLATED_CI: "1"', override)
        self.assertIn('never places an order', override)
        fixture = (ROOT / 'tests/pwa/fixtures/push_consent.php').read_text()
        self.assertIn("getenv('ORDENOWA_PUSH_TEST_MODE') !== '1'", fixture)
        self.assertIn('kuranea-ci-', fixture)
        self.assertNotIn('curl_', fixture)
        self.assertNotIn('file_get_contents(', fixture)
        workflow = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        push_step = workflow.split('- name: Verify isolated synthetic push persistence without a provider', 1)[1].split('      - name:', 1)[0]
        self.assertIn('trap restore_push_defaults EXIT', push_step)
        self.assertIn('--force-recreate --wait --wait-timeout 300 prestashop', push_step)


class PushApiEvidenceTests(unittest.TestCase):
    @staticmethod
    def driver(result):
        class Driver:
            def execute_async_script(self, *args):
                return result
        return Driver()

    def test_api_evidence_rejects_nonprivate_or_secret_responses(self):
        for result in ({'failed': True}, {'private': False}, {'private': True, 'secret_leak': True}):
            with self.subTest(result=result), self.assertRaises(AssertionError):
                browser.push_api(self.driver(result), 'subscribe')

    def test_status_evidence_requires_exact_boolean_shape(self):
        valid = {'private': True, 'secret_leak': False, 'safe_shape': True, 'status_shape': True,
                 'active': False, 'can_subscribe': False, 'status': 200}
        self.assertEqual(valid, browser.push_api(self.driver(valid), 'status'))
        for change in ({'active': 0}, {'can_subscribe': 'false'}, {'status_shape': False}):
            with self.subTest(change=change), self.assertRaises(AssertionError):
                browser.push_api(self.driver({**valid, **change}), 'status')

    def test_synthetic_phase_rejects_test_mode_absent_before_browser(self):
        from unittest.mock import patch
        isolated = {'CI': 'true', 'GITHUB_ACTIONS': 'true', 'KURANEA_ISOLATED_CI': '1',
                    'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2',
                    'CI_COMPOSE_PROJECT_NAME': 'kuranea-ci-123-2'}
        with patch.dict('os.environ', isolated, clear=True), self.assertRaises(ValueError):
            browser.verify_synthetic_push_persistence('http://localhost:18080', Path('/tmp'))

    def test_mutation_evidence_rejects_unknown_response_fields(self):
        result = {'private': True, 'secret_leak': False, 'safe_shape': False, 'status': 200}
        with self.assertRaises(AssertionError):
            browser.push_api(self.driver(result), 'subscribe')


class WorkflowFailureExtractionTests(unittest.TestCase):
    def test_failure_extraction_preserves_browser_exit_without_ripgrep(self):
        import os
        import shutil
        import subprocess
        import tempfile
        import textwrap
        workflow = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        cases = (
            ('Verify Korean admin shipping links resolve in Chromium',
             'ORDENOWA_SHIPPING_ADMIN_STAGE=carrier_route\nORDENOWA_SHIPPING_ADMIN_DETAIL=TimeoutException\n',
             'ORDENOWA_SHIPPING_ADMIN_STAGE=carrier_route'),
            ('Verify the published ORDENOWA password-reset email logo in Chromium',
             'FAIL: synthetic reset-email logo assertion\n', 'FAIL: synthetic reset-email logo assertion'),
            ('Configure the free Japan carrier through Chromium AdminCarriers',
             'FAIL: free shipping browser QA at carrier_save (TimeoutException)\n', 'carrier_save'),
        )
        for name, log, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                commands = directory / 'bin'
                commands.mkdir()
                for command in ('grep', 'tail', 'python3'):
                    (commands / command).symlink_to(shutil.which(command))
                self.assertIsNone(shutil.which('rg', path=str(commands)))
                step = workflow.split('- name: ' + name + '\n', 1)[1].split('      - name:', 1)[0]
                script = textwrap.dedent(step.split('        run: |\n', 1)[1])
                marker = 'if [ "$browser_status" -ne 0 ]; then'
                self.assertIn(marker, script, 'missing failure extraction path')
                failure_script = marker + script.split(marker, 1)[1]
                log_path = directory / 'browser.log'
                log_path.write_text(log)
                summary = directory / 'summary.md'
                result = subprocess.run([shutil.which('bash'), '-c',
                    'set -euo pipefail\nbrowser_status=7\n' + failure_script],
                    env={**os.environ, 'PATH': str(commands), 'log_file': str(log_path),
                         'GITHUB_STEP_SUMMARY': str(summary)}, capture_output=True, text=True)
                self.assertEqual(7, result.returncode, result.stderr)
                self.assertIn(expected, summary.read_text())
                self.assertNotIn('command not found', result.stderr)
                if name.startswith('Configure the free'):
                    self.assertIn('::error title=ORDENOWA carrier configure browser QA::', result.stdout)

    def test_preflight_runs_diagnostic_contracts(self):
        workflow = (ROOT / '.github/workflows/fresh-install.yml').read_text()
        preflight = workflow.split('- name: Verify fresh-install workflow contracts', 1)[1].split('      - name:', 1)[0]
        self.assertIn('tests.smoke.test_ci_diagnostics_script', preflight)
        self.assertIn('tests.smoke.test_kuraneapush_workflow_contract', preflight)
