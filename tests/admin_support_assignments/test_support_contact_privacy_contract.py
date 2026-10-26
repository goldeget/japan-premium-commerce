"""Module boundary and isolated browser wiring for account-owned contact privacy."""
import json
from pathlib import Path

from tests.e2e.test_ci_customer_support_browser_contract import load_script
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SupportContactPrivacyContractTests(unittest.TestCase):
    def test_owned_module_hook_guards_native_contact_before_render_and_submission(self):
        module = (ROOT / 'modules/kuraneabackoffice/kuraneabackoffice.php').read_text()
        self.assertTrue('hookActionFrontControllerInitAfter' in module, 'contact privacy requires a module-owned initialization guard')
        self.assertTrue('SupportContactAccessGuard::allows' in module)
        self.assertTrue("$controller->php_self" in module)
        self.assertTrue("'contact'" in module)
        self.assertTrue('http_response_code(403)' in module)
        upgrade = ROOT / 'modules/kuraneabackoffice/upgrade/upgrade-1.0.4.php'
        self.assertTrue(upgrade.is_file(), 'installed modules must register the privacy hook through an upgrade')
        self.assertTrue('installSupportContactPrivacy' in upgrade.read_text())

    def test_project_bootstrap_repairs_privacy_hook_for_preinstalled_modules(self):
        module_bootstrap = (ROOT / 'docker/kuran-install-modules.php').read_text()
        self.assertIn("$backofficeModule->installSupportContactPrivacy()", module_bootstrap)
        self.assertLess(
            module_bootstrap.index("foreach (['kuraneapostcode'"),
            module_bootstrap.index("$backofficeModule->installSupportContactPrivacy()"),
        )

    def test_isolated_browser_covers_valid_links_and_orderless_post_with_admin_readback(self):
        source = (ROOT / 'tests/e2e/verify_ci_customer_support_browser.py').read_text()
        for boundary in ('foreign_valid_thread_denied', 'foreign_orderless_post_denied',
                         'orderless_thread_unchanged', 'order_linked=False',
                         'native_customer_thread_url(\n            ctx.contact_url',
                         'foreign, valid_customer_thread_url, diagnostic_result=result',
                         'assert_foreign_orderless_post_denied(foreign, ctx, attack_marker, diagnostic_result=result)',
                         'orderless_marker not in orderless_body or attack_marker in orderless_body'):
            with self.subTest(boundary=boundary):
                self.assertTrue(boundary in source, 'missing customer-isolation acceptance boundary: ' + boundary)

    def test_denial_probe_rejects_success_login_redirect_and_transport_failure(self):
        support = load_script()
        support.assert_support_denied_response({
            'status': 403, 'formCount': 0, 'redirected': False, 'sameOrigin': True,
        })
        for response in (
            None, {}, {'status': 0, 'formCount': 0, 'redirected': False, 'sameOrigin': True},
            {'status': 200, 'formCount': 0, 'redirected': False, 'sameOrigin': True},
            {'status': 403, 'formCount': 1, 'redirected': False, 'sameOrigin': True},
            {'status': 403, 'formCount': 0, 'redirected': True, 'sameOrigin': True},
            {'status': 403, 'formCount': 0, 'redirected': False, 'sameOrigin': False},
        ):
            with self.subTest(response=response), self.assertRaises(AssertionError):
                support.assert_support_denied_response(response)

    def test_denial_probe_records_only_bounded_response_facts(self):
        support = load_script()

        class Driver:
            script = ""
            response = {'status': 403, 'formCount': 0, 'redirected': False, 'sameOrigin': True}

            def execute_async_script(self, script: str, _href: str) -> dict[str, object]:
                self.script = script
                return self.response

        result = {
            'browser_substage': 'not_applicable', 'support_denial_status': None,
            'support_denial_form_count': 0, 'support_denial_redirected': True,
            'support_denial_same_origin': False,
        }
        driver = Driver()
        support.assert_foreign_thread_denied(
            driver, 'http://localhost:18080/contact?private-token=never-log',
            diagnostic_result=result, probe_substage='foreign_invalid_token_probe',
        )
        self.assertEqual('foreign_invalid_token_probe', result['browser_substage'])
        self.assertEqual(403, result['support_denial_status'])
        self.assertEqual(0, result['support_denial_form_count'])
        self.assertFalse(result['support_denial_redirected'])
        self.assertTrue(result['support_denial_same_origin'])
        self.assertNotIn('private-token', json.dumps(result))
        self.assertNotIn('url: response.url', driver.script)
        self.assertNotIn('"response.url"', driver.script)
        self.assertIn("document.querySelectorAll('.contact-form').length", driver.script)

        driver.response = {'status': 200, 'formCount': 1, 'redirected': True, 'sameOrigin': True}
        with self.assertRaises(AssertionError):
            support.assert_foreign_thread_denied(
                driver, 'http://localhost:18080/contact?id_customer_thread=47',
                diagnostic_result=result, probe_substage='foreign_owned_thread_probe',
            )
        self.assertEqual('foreign_owned_thread_probe', result['browser_substage'])
        self.assertEqual(200, result['support_denial_status'])
        self.assertEqual(1, result['support_denial_form_count'])
        self.assertTrue(result['support_denial_redirected'])

    def test_behavior_fixture_is_in_existing_assignment_php_entrypoint(self):
        fixture = ROOT / 'tests/admin_support_assignments/contact_privacy_guard.php'
        self.assertTrue(fixture.is_file(), 'the guard needs isolated native-object behavior cases')
        source = (ROOT / 'tests/admin_support_assignments/assignment_repository.php').read_text()
        self.assertTrue("require_once __DIR__ . '/contact_privacy_guard.php'" in source)


if __name__ == '__main__':
    unittest.main()
